from __future__ import annotations

import json
import re
import shutil
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from app.config import settings
from app.services.cpiview_evidence_service import CPIViewEvidenceService
from app.services.sap_cpi_client import SAPCPIClient


@dataclass(frozen=True)
class NativeCPIEvidenceStatus:
    enabled: bool
    configured: bool
    tenant_id: str
    input_dir: str
    output_dir: str
    available: bool
    counts: dict[str, int]
    notes: list[str]


class NativeCPIEvidenceService:
    """Download and analyze SAP Cloud Integration evidence in Python.

    This service intentionally writes CPIView-compatible JSON folders so the
    existing v2.0.1 Scenario Lab and Monitoring integration can consume the
    same evidence model without Java/CPIView.
    """

    ODATA_DIR_NAME = "odata"
    ANALYSIS_DIR_NAME = "analysis"

    def __init__(
        self,
        client: SAPCPIClient | None = None,
        input_dir: Path | None = None,
        output_dir: Path | None = None,
        tenant_id: str | None = None,
    ) -> None:
        self.client = client or SAPCPIClient()
        self.tenant_id = (
            tenant_id
            or settings.cpi_native_tenant_id
            or settings.cpiview_tenant_id
            or self._tenant_from_url(settings.sap_cpi_base_url)
        )
        self.input_dir = input_dir or settings.cpi_native_input_dir_path
        self.output_dir = output_dir or settings.cpi_native_output_dir_path
        self.odata_dir = self.input_dir / self.ODATA_DIR_NAME
        self.analysis_dir = self.input_dir / self.ANALYSIS_DIR_NAME
        self.bpmn_dir = self.analysis_dir / "iflows-bpmn"
        self.zip_dir = self.input_dir / "zips"

    def status(self) -> NativeCPIEvidenceStatus:
        counts = self._counts()
        notes: list[str] = []
        if not settings.cpi_native_enabled:
            notes.append(
                "CPI_NATIVE_ENABLED=false; native Python CPI evidence download is disabled."
            )
        if not settings.cpi_is_configured:
            notes.append("SAP_CPI_* OAuth connection is not fully configured.")
        if self.odata_dir.exists():
            notes.append(
                "Native CPI evidence folder exists and can be imported into Scenario Lab resources."
            )
        return NativeCPIEvidenceStatus(
            enabled=settings.cpi_native_enabled,
            configured=settings.cpi_is_configured,
            tenant_id=self.tenant_id,
            input_dir=str(self.input_dir),
            output_dir=str(self.output_dir),
            available=self.odata_dir.exists(),
            counts=counts,
            notes=notes,
        )

    def download_and_analyze(
        self, *, download_content: bool | None = None, max_iflows: int | None = None
    ) -> dict[str, Any]:
        """Run the native download pipeline and import the generated evidence.

        The method is best-effort by component. It records component errors in
        the manifest instead of failing the whole pipeline when optional entity
        sets such as security descriptors are not exposed by a tenant.
        """
        if not settings.cpi_native_enabled:
            return {"status": "skipped", "reason": "CPI_NATIVE_ENABLED=false"}
        if not settings.cpi_is_configured:
            return {"status": "skipped", "reason": "SAP_CPI_* connection is not fully configured"}

        self.odata_dir.mkdir(parents=True, exist_ok=True)
        self.analysis_dir.mkdir(parents=True, exist_ok=True)
        self.bpmn_dir.mkdir(parents=True, exist_ok=True)
        self.zip_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        download_content_flag = (
            settings.cpi_native_download_content
            if download_content is None
            else bool(download_content)
        )
        component_errors: dict[str, str] = {}
        files: list[str] = []

        packages = self._safe_call(
            "IntegrationPackages", component_errors, lambda: self.client.get_integration_packages()
        )
        files.append(
            self._write_json(self.odata_dir / "packages.json", self._odata_payload(packages))
        )

        iflows = self._safe_call(
            "IntegrationDesigntimeArtifacts",
            component_errors,
            lambda: self.client.get_iflows(packages),
        )
        if max_iflows and max_iflows > 0:
            iflows = iflows[:max_iflows]
        files.append(self._write_json(self.odata_dir / "iflows.json", self._odata_payload(iflows)))

        runtimes = self._safe_call(
            "IntegrationRuntimeArtifacts", component_errors, self._download_runtimes
        )
        files.append(
            self._write_json(self.odata_dir / "runtimes.json", self._odata_payload(runtimes))
        )
        self._write_progress_manifest(files, component_errors, stage="core_odata_downloaded")

        downloaded_zips: list[Path] = []
        if download_content_flag:
            downloaded_zips = self._download_iflow_zips(iflows, component_errors)
            self._write_progress_manifest(
                files,
                component_errors,
                stage="artifact_content_downloaded",
                extra={"downloaded_zips": len(downloaded_zips)},
            )

        analysis = self._analyze_downloaded_iflows(downloaded_zips)
        for filename, rows in analysis.items():
            files.append(self._write_json(self.analysis_dir / filename, rows))
        self._write_progress_manifest(
            files,
            component_errors,
            stage="bpmn_analysis_written",
            extra={"bpmn_files": len(list(self.bpmn_dir.glob("*.iflw")))},
        )

        configurations: list[dict[str, Any]] = []
        resources: list[dict[str, Any]] = []
        message_mappings: list[dict[str, Any]] = []
        script_collections: list[dict[str, Any]] = []
        if bool(getattr(settings, "cpi_native_download_children", True)):
            configurations, resources, message_mappings, script_collections = (
                self._download_artifact_children(iflows, component_errors)
            )
        else:
            component_errors.setdefault(
                "ArtifactChildren", "Skipped because CPI_NATIVE_DOWNLOAD_CHILDREN=false"
            )

        for name, payload in [
            ("configurations.json", self._odata_payload(configurations)),
            ("resources.json", self._odata_payload(resources)),
            ("message-mappings.json", self._odata_payload(message_mappings)),
            ("script-collections.json", self._odata_payload(script_collections)),
        ]:
            files.append(self._write_json(self.odata_dir / name, payload))

        security = self._download_security_descriptors(component_errors)
        for name, security_rows in security.items():
            files.append(
                self._write_json(self.odata_dir / name, self._odata_payload(security_rows))
            )
        self._write_progress_manifest(
            files, component_errors, stage="child_odata_and_security_written"
        )

        rich = CPIViewEvidenceService(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            tenant_id=self.tenant_id,
            enabled_override=True,
        ).build_rich_inventory(write=False)
        rich_path = self.analysis_dir / "iflow_rich_inventory.json"
        files.append(self._write_json(rich_path, rich))

        if bool(getattr(settings, "cpi_native_generate_excel", True)):
            excel_files = self._generate_excel_views(
                packages, iflows, runtimes, configurations, resources, analysis
            )
            files.extend(excel_files)

        manifest = {
            "source_system": "sap_ci",
            "source_type": "native_python_cpi_download",
            "tenant_id": self.tenant_id,
            "generated_at": self._timestamp(),
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "download_content_enabled": download_content_flag,
            "counts": rich.get("counts", {}),
            "component_errors": component_errors,
            "files": files,
            "secret_handling": "OAuth credentials are read from .env only; security descriptor values are redacted where keys indicate secrets.",
        }
        files.append(self._write_json(self.odata_dir / "native_evidence_manifest.json", manifest))

        # Copy into the canonical resources/cpi/input locations used by the existing UI.
        imported = CPIViewEvidenceService(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            tenant_id=self.tenant_id,
            enabled_override=True,
        ).import_to_resources()
        status = "ok" if not component_errors else "partial_ok"
        return {
            "status": status,
            "manifest": str(self.odata_dir / "native_evidence_manifest.json"),
            "rich_inventory": str(rich_path),
            "counts": rich.get("counts", {}),
            "component_errors": component_errors,
            "files": files,
            "imported_to_resources": imported,
        }

    def _generate_excel_views(
        self,
        packages: list[dict[str, Any]],
        iflows: list[dict[str, Any]],
        runtimes: list[dict[str, Any]],
        configurations: list[dict[str, Any]],
        resources: list[dict[str, Any]],
        analysis: dict[str, list[dict[str, Any]]],
    ) -> list[str]:
        """Generate CPIView-compatible Excel views.

        v2.0.2 wrote a single optional workbook only to the native output
        folder. v2.0.3 writes both a compact workbook and CPIView-style files
        into resources/cpi/output so downstream generation code can discover
        concrete iFlow/channel rows without extra configuration.
        """
        try:
            import importlib

            openpyxl = importlib.import_module("openpyxl")
            Workbook = openpyxl.Workbook
        except Exception:
            return []

        written: list[str] = []
        tenant = self.tenant_id or "tenant"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        canonical_output = settings.resources_dir / "cpi" / "output"
        canonical_output.mkdir(parents=True, exist_ok=True)

        # Compact native workbook for troubleshooting.
        compact = self.output_dir / f"{tenant}_native_cpi_evidence.xlsx"
        wb = Workbook()
        default = wb.active
        if default is None:
            default = wb.create_sheet()
        default.title = "packages"
        self._append_sheet(default, packages)
        for title, rows in [
            ("iflows", iflows),
            ("runtimes", runtimes),
            ("configurations", configurations),
            ("resources", resources),
            ("channels", analysis.get("bpmn-channels.json", [])),
            ("channel_properties", analysis.get("bpmn-channels-properties.json", [])),
            ("activities", analysis.get("bpmn-activities.json", [])),
            ("content_modifiers", analysis.get("bpmn-content-modifiers.json", [])),
            ("groovy_scripts", analysis.get("bpmn-groovy-scripts.json", [])),
            ("message_mappings", analysis.get("bpmn-message-mappings.json", [])),
            ("xslt_mappings", analysis.get("bpmn-xslt-mappings.json", [])),
            ("timers", analysis.get("bpmn-timers.json", [])),
        ]:
            ws = wb.create_sheet(title[:31])
            self._append_sheet(ws, rows)
        wb.save(compact)
        written.append(self._rel_path(compact))

        # CPIView-compatible one-sheet workbooks consumed by GenerationService.
        self._write_one_sheet_xlsx(
            canonical_output / f"{tenant}_iflow.xlsx",
            self._iflow_excel_rows(iflows, packages, runtimes),
        )
        self._write_one_sheet_xlsx(
            canonical_output / f"{tenant}_artifact_runtime.xlsx",
            self._prefixed_rows(runtimes, "rt_"),
        )
        self._write_one_sheet_xlsx(
            canonical_output / f"{tenant}_iflow_configuration.xlsx",
            self._prefixed_rows(configurations, "cfg_"),
        )
        self._write_one_sheet_xlsx(
            canonical_output / f"{tenant}_iflow_resource.xlsx",
            self._prefixed_rows(resources, "res_"),
        )
        self._write_one_sheet_xlsx(
            canonical_output / f"{tenant}_iflow_channel.xlsx",
            self._channel_excel_rows(analysis.get("bpmn-channels.json", [])),
        )
        self._write_one_sheet_xlsx(
            canonical_output / f"{tenant}_iflow_channel_property.xlsx",
            self._channel_property_excel_rows(analysis.get("bpmn-channels-properties.json", [])),
        )
        self._write_one_sheet_xlsx(
            canonical_output / f"{tenant}_iflow_step.xlsx",
            self._activity_excel_rows(analysis.get("bpmn-activities.json", [])),
        )
        self._write_one_sheet_xlsx(
            canonical_output / f"{tenant}_iflow_step_for_content_modifier.xlsx",
            self._prefixed_rows(analysis.get("bpmn-content-modifiers.json", []), "cm_"),
        )
        self._write_one_sheet_xlsx(
            canonical_output / f"{tenant}_iflow_step_for_groovy_script.xlsx",
            self._prefixed_rows(analysis.get("bpmn-groovy-scripts.json", []), "gs_"),
        )
        self._write_one_sheet_xlsx(
            canonical_output / f"{tenant}_iflow_step_for_message_mapping.xlsx",
            self._prefixed_rows(analysis.get("bpmn-message-mappings.json", []), "mm_"),
        )
        self._write_one_sheet_xlsx(
            canonical_output / f"{tenant}_iflow_step_for_xslt_mapping.xlsx",
            self._prefixed_rows(analysis.get("bpmn-xslt-mappings.json", []), "xslt_"),
        )
        self._write_one_sheet_xlsx(
            canonical_output / f"{tenant}_iflow_timer.xlsx",
            self._prefixed_rows(analysis.get("bpmn-timers.json", []), "tm_"),
        )
        for path in sorted(canonical_output.glob(f"{tenant}_*.xlsx")):
            written.append(self._rel_path(path))

        # Keep a mirror in the configured native output folder for operators who
        # inspect resources/native/output directly.
        for path in sorted(canonical_output.glob(f"{tenant}_*.xlsx")):
            if path == compact:
                continue
            mirror = self.output_dir / path.name
            if mirror.resolve() != path.resolve():
                shutil.copy2(path, mirror)
        return sorted(set(written))

    def _write_one_sheet_xlsx(self, path: Path, rows: list[dict[str, Any]]) -> None:
        import importlib

        try:
            openpyxl = importlib.import_module("openpyxl")
            Workbook = openpyxl.Workbook
        except Exception:
            return

        path.parent.mkdir(parents=True, exist_ok=True)
        wb = Workbook()
        ws = wb.active
        if ws is None:
            ws = wb.create_sheet()
        ws.title = "data"
        self._append_sheet(ws, rows)
        wb.save(path)

    @staticmethod
    def _append_sheet(ws: Any, rows: list[dict[str, Any]]) -> None:
        if not rows:
            ws.append(["no_records"])
            return
        keys = sorted({str(k) for row in rows for k in row.keys()})[:120]
        ws.append(keys)
        for row in rows[:20000]:
            ws.append(
                [
                    json.dumps(row.get(k), ensure_ascii=False, default=str)
                    if isinstance(row.get(k), (dict, list))
                    else row.get(k)
                    for k in keys
                ]
            )

    def _iflow_excel_rows(
        self,
        iflows: list[dict[str, Any]],
        packages: list[dict[str, Any]],
        runtimes: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        package_by_id = {
            str(p.get("Id") or p.get("PackageId") or p.get("TechnicalName") or ""): p
            for p in packages
        }
        runtime_by_id = {str(r.get("Id") or ""): r for r in runtimes}
        runtime_by_name = {str(r.get("Name") or ""): r for r in runtimes}
        rows: list[dict[str, Any]] = []
        for item in iflows:
            iflow_id = str(item.get("Id") or item.get("ID") or item.get("Name") or "")
            if not iflow_id:
                continue
            name = str(item.get("Name") or iflow_id)
            package_id = str(item.get("PackageId") or item.get("PackageID") or "")
            package = package_by_id.get(package_id, {})
            runtime = runtime_by_id.get(iflow_id) or runtime_by_name.get(name) or {}
            rows.append(
                {
                    "ifw_package_id": package_id,
                    "ifw_package_name": package.get("Name")
                    or package.get("DisplayName")
                    or package_id,
                    "ifw_id": iflow_id,
                    "ifw_name": name,
                    "ifw_description": item.get("Description") or item.get("ShortText") or "",
                    "ifw_version": item.get("Version") or item.get("ArtifactVersion") or "",
                    "ifw_created_at": item.get("CreatedAt") or item.get("CreatedOn") or "",
                    "ifw_modified_at": item.get("ModifiedAt") or item.get("ModifiedOn") or "",
                    "ifw_runtime_status": runtime.get("Status") or "",
                    "ifw_deployed_by": runtime.get("DeployedBy") or "",
                    "ifw_deployed_on": runtime.get("DeployedOn") or "",
                }
            )
        return rows

    def _channel_excel_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for row in rows:
            out.append(
                {
                    "chn_package_id": row.get("packageId") or row.get("PackageId") or "",
                    "chn_iflow_id": row.get("iflowId") or row.get("IflowId") or "",
                    "chn_iflow_name": row.get("iflowId") or row.get("IflowId") or "",
                    "chn_id": row.get("id") or "",
                    "chn_name": row.get("name") or "",
                    "chn_type": row.get("type") or "",
                    "chn_participant_name": row.get("participantName") or "",
                    "chn_component_type": row.get("componentType") or "",
                    "chn_message_protocol": row.get("messageProtocol") or "",
                    "chn_transport_protocol": row.get("transportProtocol") or "",
                    "chn_system": row.get("system") or "",
                    "chn_address": row.get("address") or "",
                    "chn_authentication_method": row.get("authenticationMethod") or "",
                    "chn_credential_name": row.get("credentialName") or "",
                    "chn_key_alias": row.get("keyAlias") or "",
                }
            )
        return out

    def _channel_property_excel_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "chp_package_id": row.get("packageId") or row.get("PackageId") or "",
                "chp_iflow_id": row.get("iflowId") or row.get("IflowId") or "",
                "chp_channel_id": row.get("channelId") or row.get("id") or "",
                "chp_channel_name": row.get("channelName") or row.get("name") or "",
                "chp_key": row.get("key") or "",
                "chp_raw_value": row.get("rawValue") or "",
                "chp_resolved_value": row.get("resolvedValue") or "",
            }
            for row in rows
        ]

    def _activity_excel_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "stp_package_id": row.get("packageId") or row.get("PackageId") or "",
                "stp_iflow_id": row.get("iflowId") or row.get("IflowId") or "",
                "stp_iflow_name": row.get("iflowId") or row.get("IflowId") or "",
                "stp_id": row.get("id") or "",
                "stp_name": row.get("name") or "",
                "stp_activity_type": row.get("activityType") or "",
                "stp_component_version": row.get("componentVersion") or "",
                "stp_cmd_variant_uri": row.get("cmdVariantUri") or "",
            }
            for row in rows
        ]

    @staticmethod
    def _prefixed_rows(rows: list[dict[str, Any]], prefix: str) -> list[dict[str, Any]]:
        return [{f"{prefix}{str(k)}": v for k, v in row.items()} for row in rows]

    def _download_runtimes(self) -> list[dict[str, Any]]:
        return self.client.get_integration_runtime_artifacts()

    def _download_artifact_children(
        self, iflows: list[dict[str, Any]], component_errors: dict[str, str]
    ) -> tuple[
        list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]
    ]:
        configurations: list[dict[str, Any]] = []
        resources: list[dict[str, Any]] = []
        message_mappings: list[dict[str, Any]] = []
        script_collections: list[dict[str, Any]] = []

        mapping = {
            "Configurations": (configurations, self.client.get_artifact_configurations),
            "Resources": (resources, self.client.get_artifact_resources),
            "MessageMappings": (message_mappings, self.client.get_artifact_message_mappings),
            "ScriptCollections": (script_collections, self.client.get_artifact_script_collections),
        }

        tasks: list[tuple[dict[str, Any], str, Any]] = []
        for artifact in iflows:
            aid = self._first(artifact, "Id", "ID", "Name")
            if not aid:
                continue
            for label, (_, getter) in mapping.items():
                tasks.append((artifact, label, getter))

        workers = max(1, min(int(getattr(settings, "cpi_native_parallel_workers", 8) or 1), 16))
        if workers == 1:
            for artifact, label, getter in tasks:
                self._download_one_child(
                    artifact, label, getter, mapping[label][0], component_errors
                )
        else:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {
                    pool.submit(self._download_child_rows, artifact, label, getter): label
                    for artifact, label, getter in tasks
                }
                for future in as_completed(futures):
                    label = futures[future]
                    try:
                        rows = future.result()
                        mapping[label][0].extend(rows)
                    except Exception as exc:
                        component_errors.setdefault(label, str(exc))
        return configurations, resources, message_mappings, script_collections

    def _download_one_child(
        self,
        artifact: dict[str, Any],
        label: str,
        getter: Any,
        target: list[dict[str, Any]],
        component_errors: dict[str, str],
    ) -> None:
        try:
            target.extend(self._download_child_rows(artifact, label, getter))
        except Exception as exc:
            component_errors.setdefault(label, str(exc))

    def _download_child_rows(
        self, artifact: dict[str, Any], label: str, getter: Any
    ) -> list[dict[str, Any]]:
        aid = self._first(artifact, "Id", "ID", "Name")
        version = self._first(artifact, "Version", "ArtifactVersion") or "active"
        package_id = self._first(artifact, "PackageId", "PackageID")
        rows = getter(str(aid), str(version), package_id=str(package_id) if package_id else None)
        for row in rows:
            row.setdefault("IflowId", aid)
            row.setdefault("PackageId", package_id)
        return rows

    def _download_security_descriptors(
        self, component_errors: dict[str, str]
    ) -> dict[str, list[dict[str, Any]]]:
        descriptors = {
            "security-keystore-entries.json": ["KeystoreEntries", "KeystoreEntries()"],
            "security-oauth2-client-credentials.json": [
                "OAuth2ClientCredentials",
                "OAuth2ClientCredentials()",
            ],
            "security-user-credentials.json": ["UserCredentials", "UserCredentials()"],
            "security-secure-parameters.json": ["SecureParameters", "SecureParameters()"],
        }
        result: dict[str, list[dict[str, Any]]] = {}
        for filename, entity_candidates in descriptors.items():
            rows: list[dict[str, Any]] = []
            last_error = ""
            for entity in entity_candidates:
                try:
                    rows = self.client.get_entity_collection(
                        entity, max_records=settings.cpi_native_max_records
                    )
                    break
                except Exception as exc:
                    last_error = str(exc)
            result[filename] = [self._redact_security_row(row) for row in rows]
            if not rows and last_error:
                component_errors.setdefault(filename, last_error)
        return result

    def _download_iflow_zips(
        self, iflows: list[dict[str, Any]], component_errors: dict[str, str]
    ) -> list[Path]:
        artifacts = [artifact for artifact in iflows if self._first(artifact, "Id", "ID", "Name")]
        workers = max(1, min(int(getattr(settings, "cpi_native_parallel_workers", 8) or 1), 16))
        written: list[Path] = []
        if workers == 1:
            for artifact in artifacts:
                path = self._download_one_iflow_zip(artifact, component_errors)
                if path is not None:
                    written.append(path)
            return written
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(self._download_one_iflow_zip, artifact, component_errors): artifact
                for artifact in artifacts
            }
            for future in as_completed(futures):
                try:
                    path = future.result()
                    if path is not None:
                        written.append(path)
                except Exception as exc:
                    artifact = futures[future]
                    aid = self._first(artifact, "Id", "ID", "Name")
                    component_errors.setdefault(f"ArtifactContent:{aid}", str(exc))
        return written

    def _download_one_iflow_zip(
        self, artifact: dict[str, Any], component_errors: dict[str, str]
    ) -> Path | None:
        aid = self._first(artifact, "Id", "ID", "Name")
        version = self._first(artifact, "Version", "ArtifactVersion") or "active"
        package_id = self._first(artifact, "PackageId", "PackageID")
        if not aid:
            return None
        safe = self._safe_filename(f"{package_id or 'package'} --- {aid}.zip")
        target = self.zip_dir / safe
        try:
            blob = self.client.download_artifact_content(
                str(aid), str(version), package_id=str(package_id) if package_id else None
            )
            if blob:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(blob)
                self._extract_iflw_from_zip(target, package_id=str(package_id), iflow_id=str(aid))
                return target
        except Exception as exc:
            component_errors.setdefault(f"ArtifactContent:{aid}:{version}", str(exc))
        return None

    def _extract_iflw_from_zip(self, zip_path: Path, *, package_id: str, iflow_id: str) -> None:
        try:
            with zipfile.ZipFile(zip_path) as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".iflw"):
                        target = self.bpmn_dir / self._safe_filename(
                            f"{package_id} --- {iflow_id}.iflw"
                        )
                        target.write_bytes(zf.read(name))
                        return
        except zipfile.BadZipFile:
            return

    def _analyze_downloaded_iflows(self, zip_paths: list[Path]) -> dict[str, list[dict[str, Any]]]:
        rows: dict[str, list[dict[str, Any]]] = {
            "bpmn-participants.json": [],
            "bpmn-channels.json": [],
            "bpmn-channels-properties.json": [],
            "bpmn-activities.json": [],
            "bpmn-activities-properties.json": [],
            "bpmn-content-modifiers.json": [],
            "bpmn-groovy-scripts.json": [],
            "bpmn-message-mappings.json": [],
            "bpmn-xslt-mappings.json": [],
            "bpmn-timers.json": [],
        }
        for iflw in self.bpmn_dir.glob("*.iflw"):
            pkg, iflow_id = self._pkg_iflow_from_iflw(iflw)
            self._analyze_iflw_file(iflw, pkg, iflow_id, rows)
        return rows

    def _analyze_iflw_file(
        self, path: Path, package_id: str, iflow_id: str, rows: dict[str, list[dict[str, Any]]]
    ) -> None:
        try:
            root = ET.fromstring(path.read_bytes())
        except Exception:
            return
        participants: dict[str, str] = {}
        activities: dict[str, dict[str, Any]] = {}
        for elem in root.iter():
            lname = self._local(elem.tag)
            attrs = self._attrs(elem)
            eid = attrs.get("id", "")
            name = attrs.get("name", "")
            if lname == "participant" and eid:
                participants[eid] = name or eid
                rows["bpmn-participants.json"].append(
                    {"id": eid, "name": name or eid, "iflowId": iflow_id, "packageId": package_id}
                )
            if lname in {
                "callActivity",
                "serviceTask",
                "scriptTask",
                "sendTask",
                "receiveTask",
                "startEvent",
                "endEvent",
                "subProcess",
                "exclusiveGateway",
                "parallelGateway",
                "eventBasedGateway",
                "intermediateCatchEvent",
                "intermediateThrowEvent",
            }:
                props = self._element_properties(elem)
                activity_type = (
                    props.get("activityType")
                    or props.get("componentType")
                    or props.get("cmdVariantUri")
                    or lname
                )
                rec = {
                    "id": eid,
                    "name": name or eid,
                    "iflowId": iflow_id,
                    "packageId": package_id,
                    "activityType": activity_type,
                    "componentVersion": props.get("componentVersion")
                    or props.get("componentVersionNumber")
                    or "",
                    "cmdVariantUri": props.get("cmdVariantUri") or attrs.get("cmdVariantUri", ""),
                }
                activities[eid] = rec
                rows["bpmn-activities.json"].append(rec)
                for k, v in props.items():
                    rows["bpmn-activities-properties.json"].append(
                        {
                            "packageId": package_id,
                            "iflowId": iflow_id,
                            "activityId": eid,
                            "activityName": name or eid,
                            "key": k,
                            "rawValue": v,
                            "resolvedValue": v,
                        }
                    )
                blob = json.dumps(
                    {"attrs": attrs, "props": props, "name": name}, ensure_ascii=False
                ).lower()
                if "content modifier" in blob or "enricher" in blob:
                    for k, v in props.items():
                        rows["bpmn-content-modifiers.json"].append(
                            {
                                "id": eid,
                                "name": name or eid,
                                "iflowId": iflow_id,
                                "packageId": package_id,
                                "rowName": k,
                                "rowValue": v,
                                "rowValueResolved": v,
                                "activityType": activity_type,
                            }
                        )
                if "groovy" in blob or ".groovy" in blob:
                    rows["bpmn-groovy-scripts.json"].append(
                        {
                            "id": eid,
                            "name": name or eid,
                            "iflowId": iflow_id,
                            "packageId": package_id,
                            "script": props.get("script") or props.get("resource") or name,
                        }
                    )
                if "message mapping" in blob or "mapping" in blob:
                    rows["bpmn-message-mappings.json"].append(
                        {
                            "id": eid,
                            "name": name or eid,
                            "iflowId": iflow_id,
                            "packageId": package_id,
                            "mapping": props.get("mapping") or props.get("resource") or name,
                        }
                    )
                if "xslt" in blob or ".xsl" in blob:
                    rows["bpmn-xslt-mappings.json"].append(
                        {
                            "id": eid,
                            "name": name or eid,
                            "iflowId": iflow_id,
                            "packageId": package_id,
                            "mapping": props.get("xslt") or props.get("resource") or name,
                        }
                    )
                if "timer" in blob or lname in {"startEvent", "intermediateCatchEvent"}:
                    timer_props = {
                        k: v
                        for k, v in props.items()
                        if "timer" in k.lower() or "schedule" in k.lower() or "cron" in k.lower()
                    }
                    if timer_props:
                        rows["bpmn-timers.json"].append(
                            {
                                "id": eid,
                                "name": name or eid,
                                "iflowId": iflow_id,
                                "packageId": package_id,
                                **timer_props,
                            }
                        )
            if lname == "messageFlow" and eid:
                props = self._element_properties(elem)
                source = attrs.get("sourceRef", "")
                target = attrs.get("targetRef", "")
                psource = participants.get(source, source)
                ptarget = participants.get(target, target)
                component = (
                    props.get("componentType")
                    or props.get("adapterType")
                    or props.get("transportProtocol")
                    or name
                    or "UNKNOWN"
                )
                rec = {
                    "id": eid,
                    "name": name or component,
                    "type": "EndpointSender" if source in participants else "EndpointReceiver",
                    "participantId": source if source in participants else target,
                    "participantName": psource if source in participants else ptarget,
                    "iflowId": iflow_id,
                    "packageId": package_id,
                    "componentType": component,
                    "messageProtocol": props.get("messageProtocol") or "",
                    "transportProtocol": props.get("transportProtocol") or "",
                    "system": psource if source in participants else ptarget,
                    "address": props.get("address")
                    or props.get("url")
                    or props.get("host")
                    or props.get("path")
                    or "",
                    "authenticationMethod": props.get("authentication")
                    or props.get("authenticationMethod")
                    or "",
                    "credentialName": props.get("credential_name")
                    or props.get("credentialName")
                    or props.get("credential")
                    or "",
                    "keyAlias": props.get("keyAlias") or props.get("key_alias") or "",
                }
                rows["bpmn-channels.json"].append(rec)
                for k, v in props.items():
                    rows["bpmn-channels-properties.json"].append(
                        {
                            "packageId": package_id,
                            "iflowId": iflow_id,
                            "channelId": eid,
                            "channelName": name or component,
                            "key": k,
                            "rawValue": v,
                            "resolvedValue": v,
                        }
                    )

    def _element_properties(self, elem: ET.Element) -> dict[str, str]:
        props: dict[str, str] = {}
        for k, v in elem.attrib.items():
            lk = self._local(k)
            if v not in (None, ""):
                props[lk] = str(v)
        for child in elem.iter():
            if child is elem:
                continue
            lname = self._local(child.tag)
            attrs = self._attrs(child)
            key = attrs.get("key") or attrs.get("name") or attrs.get("id") or lname
            value = (
                attrs.get("value")
                or attrs.get("defaultValue")
                or attrs.get("rawValue")
                or (child.text or "").strip()
            )
            if key and value and len(str(value)) < 2000:
                props[str(key)] = str(value)
        return props

    def _pkg_iflow_from_iflw(self, path: Path) -> tuple[str, str]:
        stem = path.stem
        if " --- " in stem:
            pkg, iflow = stem.split(" --- ", 1)
            return pkg, iflow
        return "", stem

    def _counts(self) -> dict[str, int]:
        return {
            "packages": len(CPIViewEvidenceService._read_records(self.odata_dir / "packages.json")),
            "iflows": len(CPIViewEvidenceService._read_records(self.odata_dir / "iflows.json")),
            "runtime_artifacts": len(
                CPIViewEvidenceService._read_records(self.odata_dir / "runtimes.json")
            ),
            "deployed_iflows": CPIViewEvidenceService.count_deployed_iflows(
                CPIViewEvidenceService._read_records(self.odata_dir / "runtimes.json")
            ),
            "bpmn_files": len(list(self.bpmn_dir.glob("*.iflw"))) if self.bpmn_dir.exists() else 0,
        }

    @staticmethod
    def _safe_call(label: str, component_errors: dict[str, str], fn: Any) -> list[dict[str, Any]]:
        try:
            return fn()
        except Exception as exc:
            component_errors[label] = str(exc)
            return []

    @staticmethod
    def _odata_payload(records: list[dict[str, Any]]) -> dict[str, Any]:
        return {"d": {"results": records}}

    @staticmethod
    def _redact_security_row(row: dict[str, Any]) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key, value in row.items():
            low = key.lower()
            if any(word in low for word in ("password", "secret", "token", "value")):
                out[key] = "***redacted***" if value not in (None, "") else value
            else:
                out[key] = value
        return out

    @staticmethod
    def _attrs(elem: ET.Element) -> dict[str, str]:
        return {NativeCPIEvidenceService._local(k): str(v) for k, v in elem.attrib.items()}

    @staticmethod
    def _local(tag: str) -> str:
        return tag.split("}", 1)[-1].split(":", 1)[-1]

    @staticmethod
    def _first(item: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return value
        return ""

    @staticmethod
    def _safe_filename(value: str) -> str:
        return re.sub(r"[<>:\\|?*\x00-\x1f]+", "_", value).strip(" .") or "artifact"

    @staticmethod
    def _tenant_from_url(url: str) -> str:
        if not url:
            return "tenant"
        host = re.sub(r"^https?://", "", url).split("/", 1)[0]
        return host.split(".", 1)[0] or "tenant"

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    def _write_progress_manifest(
        self,
        files: list[str],
        component_errors: dict[str, str],
        *,
        stage: str,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "source_system": "sap_ci",
            "source_type": "native_python_cpi_download_progress",
            "tenant_id": self.tenant_id,
            "stage": stage,
            "updated_at": self._timestamp(),
            "input_dir": str(self.input_dir),
            "output_dir": str(self.output_dir),
            "files_written_so_far": list(files),
            "component_errors_so_far": dict(list(component_errors.items())[:100]),
        }
        if extra:
            payload.update(extra)
        self._write_json(self.odata_dir / "native_download_progress.json", payload)

    @staticmethod
    def _rel_path(path: Path) -> str:
        try:
            return str(path.relative_to(settings.project_root)).replace("\\", "/")
        except Exception:
            return str(path)

    @staticmethod
    def _write_json(path: Path, payload: Any) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )
        try:
            return str(path.relative_to(settings.project_root)).replace("\\", "/")
        except Exception:
            return str(path)
