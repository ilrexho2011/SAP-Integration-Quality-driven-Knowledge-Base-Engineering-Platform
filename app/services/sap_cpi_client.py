from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

from app.config import settings


class SAPCPIClientError(RuntimeError):
    """Raised when the SAP CPI client cannot complete a live request."""


class SAPCPIClient:
    """Minimal SAP Cloud Integration OData client for inventory and MPL monitor data.

    The class is intentionally defensive: tenant capabilities differ and trial
    tenants may not expose every entity set. The monitor service can still fall
    back to local MPL files when a live endpoint is unavailable.
    """

    def __init__(self) -> None:
        self.base_url = settings.sap_cpi_base_url.rstrip("/")
        self.api_prefix = "/" + settings.sap_cpi_api_prefix.strip("/")
        self.timeout = settings.sap_cpi_timeout_seconds
        self.verify_ssl = settings.sap_cpi_verify_ssl
        self._token: str | None = None

    @property
    def configured(self) -> bool:
        return settings.cpi_is_configured

    def _require_configured(self) -> None:
        if not self.configured:
            raise SAPCPIClientError(
                "SAP CPI live connection is not fully configured. Required: "
                "SAP_CPI_BASE_URL, SAP_CPI_TOKEN_URL, SAP_CPI_CLIENT_ID, SAP_CPI_CLIENT_SECRET."
            )

    def _entity_url(self, entity_path: str) -> str:
        clean_path = entity_path.lstrip("/")
        if clean_path.startswith("http://") or clean_path.startswith("https://"):
            return clean_path
        return f"{self.base_url}{self.api_prefix}/{clean_path}"

    @staticmethod
    def _append_default_format(url: str) -> str:
        """Append $format=json to relative or absolute OData URLs when missing."""
        parts = urlsplit(url)
        query_pairs = parse_qsl(parts.query, keep_blank_values=True)
        query_keys = {key for key, _ in query_pairs}
        if "$format" not in query_keys:
            query_pairs.append(("$format", "json"))
        return urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(query_pairs), parts.fragment)
        )

    def _get_token(self) -> str:
        self._require_configured()
        if self._token:
            return self._token
        try:
            response = requests.post(
                settings.sap_cpi_token_url,
                data={"grant_type": "client_credentials"},
                auth=(settings.sap_cpi_client_id, settings.sap_cpi_client_secret),
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            response.raise_for_status()
            payload = response.json()
            token = payload.get("access_token")
            if not token:
                raise SAPCPIClientError("OAuth token response does not contain access_token.")
            self._token = token
            return token
        except requests.RequestException as exc:
            raise SAPCPIClientError(f"OAuth token request failed: {exc}") from exc

    def get_json(self, entity_path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        token = self._get_token()
        url = self._entity_url(entity_path)
        final_params: dict[str, Any] | None
        if params is None:
            # Preserve OData nextLink URLs exactly, but still ensure JSON output.
            url = self._append_default_format(url)
            final_params = None
        else:
            final_params = {"$format": "json"}
            final_params.update(params)
        try:
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                params=final_params,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise SAPCPIClientError(f"GET {entity_path} failed: {exc}") from exc

    @staticmethod
    def extract_results(payload: Any) -> list[dict[str, Any]]:
        """Support SAP OData V2 and OData V4 JSON envelopes."""
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        if isinstance(payload.get("value"), list):
            return [item for item in payload["value"] if isinstance(item, dict)]
        d = payload.get("d")
        if isinstance(d, dict) and isinstance(d.get("results"), list):
            return [item for item in d["results"] if isinstance(item, dict)]
        if isinstance(payload.get("results"), list):
            return [item for item in payload["results"] if isinstance(item, dict)]
        return []

    @staticmethod
    def _extract_next_link(payload: Any) -> str | None:
        """Extract OData nextLink from V2 and V4 response payloads."""
        if not isinstance(payload, dict):
            return None

        for key in ("@odata.nextLink", "odata.nextLink"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        d = payload.get("d")
        if isinstance(d, dict):
            value = d.get("__next") or d.get("next")
            if isinstance(value, str) and value.strip():
                return value.strip()

        value = payload.get("__next") or payload.get("next")
        if isinstance(value, str) and value.strip():
            return value.strip()

        return None

    @staticmethod
    def _dedupe_key(item: dict[str, Any]) -> str | None:
        """Return a stable key for common CPI entities, if present."""
        for key in (
            "MessageGuid",
            "MessageGUID",
            "Id",
            "ID",
            "PackageId",
            "TechnicalName",
            "Name",
        ):
            value = item.get(key)
            if value is not None and str(value).strip():
                return f"{key}:{str(value).strip()}"
        return None

    def _get_paged_results(
        self,
        entity_path: str,
        params: dict[str, Any] | None = None,
        *,
        max_records: int,
        page_size: int = 1000,
        deduplicate: bool = True,
    ) -> list[dict[str, Any]]:
        """Read an OData collection using server-side pagination.

        SAP CPI tenants commonly cap a single OData response at 1000 records.
        This method follows OData nextLink when available and falls back to
        $skip pagination when the tenant returns full pages without nextLink.
        """
        if max_records <= 0:
            return []

        collected: list[dict[str, Any]] = []
        seen: set[str] = set()
        base_params = dict(params or {})
        page_size = max(1, min(page_size, max_records))
        skip = 0
        next_path: str | None = entity_path
        next_params: dict[str, Any] | None = dict(base_params)

        while next_path and len(collected) < max_records:
            remaining = max_records - len(collected)
            current_top = min(page_size, remaining)

            if next_params is None:
                request_params = None
            else:
                request_params = dict(next_params)
                request_params["$top"] = str(current_top)
                if skip:
                    request_params["$skip"] = str(skip)

            payload = self.get_json(next_path, request_params)
            page = self.extract_results(payload)
            if not page:
                break

            added = 0
            for item in page:
                key = self._dedupe_key(item) if deduplicate else None
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                collected.append(item)
                added += 1
                if len(collected) >= max_records:
                    break

            if len(collected) >= max_records:
                break

            next_link = self._extract_next_link(payload)
            if next_link:
                next_path = next_link
                next_params = None
                skip = 0
                continue

            if len(page) < current_top:
                break

            # Fallback when the service does not return nextLink. Avoid an
            # infinite loop when all rows are duplicates due to unsupported $skip.
            if added == 0:
                break
            skip += len(page)
            next_path = entity_path
            next_params = dict(base_params)

        return collected[:max_records]

    def get_integration_packages(self) -> list[dict[str, Any]]:
        return self._get_paged_results(
            "IntegrationPackages",
            max_records=1000,
            page_size=1000,
        )

    def get_iflows(self, packages: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
        # Some tenants expose IntegrationDesigntimeArtifacts directly; others expose it below each package.
        try:
            direct_results = self._get_paged_results(
                "IntegrationDesigntimeArtifacts",
                max_records=1000,
                page_size=1000,
            )
            if direct_results:
                return direct_results
        except SAPCPIClientError:
            pass

        collected: list[dict[str, Any]] = []
        seen: set[str] = set()
        for package in packages or []:
            package_id = (
                package.get("Id")
                or package.get("ID")
                or package.get("PackageId")
                or package.get("TechnicalName")
            )
            if not package_id:
                continue
            escaped = str(package_id).replace("'", "''")
            try:
                artifacts = self._get_paged_results(
                    f"IntegrationPackages('{escaped}')/IntegrationDesigntimeArtifacts",
                    max_records=1000,
                    page_size=1000,
                )
                for artifact in artifacts:
                    key = self._dedupe_key(artifact) or str(artifact)
                    if key in seen:
                        continue
                    seen.add(key)
                    collected.append(artifact)
            except SAPCPIClientError:
                continue
        return collected

    def get_bytes(
        self,
        entity_path: str,
        params: dict[str, Any] | None = None,
        accept: str = "application/octet-stream",
    ) -> bytes:
        token = self._get_token()
        url = self._entity_url(entity_path)
        try:
            response = requests.get(
                url,
                headers={"Authorization": f"Bearer {token}", "Accept": accept},
                params=params,
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            response.raise_for_status()
            return response.content
        except requests.RequestException as exc:
            raise SAPCPIClientError(f"GET binary {entity_path} failed: {exc}") from exc

    def get_entity_collection(
        self, entity_path: str, max_records: int = 100000, page_size: int = 1000
    ) -> list[dict[str, Any]]:
        return self._get_paged_results(
            entity_path,
            max_records=max_records,
            page_size=page_size,
        )

    def get_integration_runtime_artifacts(self) -> list[dict[str, Any]]:
        return self._get_paged_results(
            "IntegrationRuntimeArtifacts",
            max_records=getattr(settings, "cpi_native_max_records", 100000),
            page_size=1000,
        )

    @staticmethod
    def _artifact_key(artifact_id: str, version: str | None = None) -> str:
        safe_id = str(artifact_id).replace("'", "''")
        safe_ver = str(version or "active").replace("'", "''")
        return f"IntegrationDesigntimeArtifacts(Id='{safe_id}',Version='{safe_ver}')"

    def _artifact_child_candidates(
        self, artifact_id: str, version: str | None, child: str, package_id: str | None = None
    ) -> list[str]:
        key = self._artifact_key(artifact_id, version)
        candidates = [f"{key}/{child}"]
        if package_id:
            pkg = str(package_id).replace("'", "''")
            aid = str(artifact_id).replace("'", "''")
            ver = str(version or "active").replace("'", "''")
            candidates.append(
                f"IntegrationPackages('{pkg}')/IntegrationDesigntimeArtifacts(Id='{aid}',Version='{ver}')/{child}"
            )
            candidates.append(
                f"IntegrationPackages('{pkg}')/IntegrationDesigntimeArtifacts('{aid}')/{child}"
            )
        return candidates

    def _get_first_success_collection(
        self, candidates: list[str], max_records: int = 100000
    ) -> list[dict[str, Any]]:
        last_error: Exception | None = None
        for path in candidates:
            try:
                return self._get_paged_results(path, max_records=max_records, page_size=1000)
            except SAPCPIClientError as exc:
                last_error = exc
        if last_error:
            raise last_error
        return []

    def get_artifact_configurations(
        self, artifact_id: str, version: str | None = None, package_id: str | None = None
    ) -> list[dict[str, Any]]:
        return self._get_first_success_collection(
            self._artifact_child_candidates(artifact_id, version, "Configurations", package_id)
        )

    def get_artifact_resources(
        self, artifact_id: str, version: str | None = None, package_id: str | None = None
    ) -> list[dict[str, Any]]:
        return self._get_first_success_collection(
            self._artifact_child_candidates(artifact_id, version, "Resources", package_id)
        )

    def get_artifact_message_mappings(
        self, artifact_id: str, version: str | None = None, package_id: str | None = None
    ) -> list[dict[str, Any]]:
        return self._get_first_success_collection(
            self._artifact_child_candidates(artifact_id, version, "MessageMappings", package_id)
        )

    def get_artifact_script_collections(
        self, artifact_id: str, version: str | None = None, package_id: str | None = None
    ) -> list[dict[str, Any]]:
        return self._get_first_success_collection(
            self._artifact_child_candidates(artifact_id, version, "ScriptCollections", package_id)
        )

    def download_artifact_content(
        self, artifact_id: str, version: str | None = None, package_id: str | None = None
    ) -> bytes:
        candidates = self._artifact_child_candidates(artifact_id, version, "$value", package_id)
        last_error: Exception | None = None
        for path in candidates:
            try:
                return self.get_bytes(path, accept="application/zip,application/octet-stream,*/*")
            except SAPCPIClientError as exc:
                last_error = exc
        if last_error:
            raise last_error
        return b""

    def get_message_processing_logs(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        display_field: str | None = None,
    ) -> list[dict[str, Any]]:
        """Read MPL records for the selected monitor time range.

        Backward compatibility is preserved: without explicit values the method
        uses SAP_MONITOR_LOOKBACK_HOURS and the configured CPI timestamp field.
        """
        # Use a technical SAP CPI MPL timestamp for OData filtering. The UI
        # display_field is intentionally not used here because labels such as
        # last_updated may not exist as filterable OData fields on all tenants.
        field = (settings.sap_cpi_mpl_filter_field or "LogStart").strip() or "LogStart"
        now = datetime.now(timezone.utc)
        start = start_time or (now - timedelta(hours=settings.sap_monitor_lookback_hours))
        end = end_time or now
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)

        start_literal = start.strftime("%Y-%m-%dT%H:%M:%S")
        end_literal = end.strftime("%Y-%m-%dT%H:%M:%S")
        filter_expr = f"{field} ge datetime'{start_literal}' and {field} le datetime'{end_literal}'"
        params = {
            "$orderby": f"{field} desc",
            "$filter": filter_expr,
        }
        max_records = int(settings.sap_cpi_mpl_top)
        page_size = int(getattr(settings, "sap_cpi_mpl_page_size", 1000) or 1000)
        page_size = max(1, min(page_size, 1000))

        try:
            return self._get_paged_results(
                "MessageProcessingLogs",
                params,
                max_records=max_records,
                page_size=page_size,
            )
        except SAPCPIClientError:
            # Fallback for tenants that reject date filters. The service layer
            # filters these records locally so custom ranges still work.
            return self._get_paged_results(
                "MessageProcessingLogs",
                {},
                max_records=max_records,
                page_size=page_size,
            )
