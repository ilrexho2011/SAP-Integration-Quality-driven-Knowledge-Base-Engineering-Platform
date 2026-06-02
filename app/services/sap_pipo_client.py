from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

from app.config import settings
from app.services.sap_cpi_client import SAPCPIClient


class SAPPIPOClientError(RuntimeError):
    """Raised when the SAP PI/PO adapter cannot complete a live request."""


class SAPPIPOClient:
    """SAP PI/PO monitor client with JSON and SOAP-aware execution.

    SAP PI/PO 7.50 AdapterMessageMonitoring is SOAP-first. The important
    detail for the live MPL call is the operation namespace. Several SAP PO
    systems expose getMessageList under the namespace ``urn:AdapterMessageMonitoringVi``;
    using ``http://sap.com/xi/XI/Message/30`` leads to the classic SOAP fault
    "No operation found using soap keys". This client therefore discovers the
    WSDL when possible and falls back to SAP PO default namespace candidates.
    """

    DEFAULT_OPERATION_NAME = "getMessageList"
    DEFAULT_NAMESPACE_CANDIDATES = [
        "urn:AdapterMessageMonitoringVi",
        "http://sap.com/xi/XI/Message/30",
    ]
    DEFAULT_FILTER_NAMESPACE = "urn:com.sap.aii.mdt.server.adapterframework.ws"
    DEFAULT_SOAP_ACTION_CANDIDATES = [
        "",
        "getMessageList",
        "urn:getMessageList",
    ]

    def __init__(self) -> None:
        self.base_url = (
            settings.sap_pipo_base_url.rstrip("/") + "/" if settings.sap_pipo_base_url else ""
        )
        self.timeout = settings.sap_pipo_timeout_seconds
        self.verify_ssl = settings.sap_pipo_verify_ssl
        self.auth = (settings.sap_pipo_username, settings.sap_pipo_password)
        self.logs_dir = settings.project_root / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self._wsdl_metadata: dict[str, Any] | None = None

    @property
    def configured(self) -> bool:
        return settings.pipo_is_configured

    @property
    def has_live_endpoints(self) -> bool:
        return settings.pipo_has_live_endpoints

    def _require_configured(self) -> None:
        if not self.configured:
            raise SAPPIPOClientError(
                "SAP PI/PO live connection is not fully configured. Required: "
                "SAP_PIPO_BASE_URL, SAP_PIPO_USERNAME, SAP_PIPO_PASSWORD."
            )

    def _setting(self, name: str, default: Any = None) -> Any:
        """Read a setting defensively so optional PIPO_MPL_* fields cannot crash the backend."""
        return getattr(settings, name, default)

    def _bool_setting(self, name: str, default: bool = False) -> bool:
        value = getattr(settings, name, default)
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    def _str_setting(self, name: str, default: str = "") -> str:
        value = getattr(settings, name, default)
        if value is None:
            return default
        return str(value).strip()

    def _endpoint_url(self, endpoint: str) -> str:
        clean = (endpoint or "").strip()
        if not clean:
            raise SAPPIPOClientError("SAP PI/PO endpoint is empty.")
        if clean.startswith("http://") or clean.startswith("https://"):
            return clean
        return urljoin(self.base_url, clean.lstrip("/"))

    def get_json(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | list[Any]:
        self._require_configured()
        try:
            response = requests.get(
                self._endpoint_url(endpoint),
                params=params or {},
                auth=self.auth,
                headers={"Accept": "application/json"},
                timeout=self.timeout,
                verify=self.verify_ssl,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise SAPPIPOClientError(
                f"SAP PI/PO JSON GET failed for endpoint {endpoint}: {exc}"
            ) from exc
        except ValueError as exc:
            raise SAPPIPOClientError(f"SAP PI/PO endpoint did not return JSON: {endpoint}") from exc

    def post_soap(
        self,
        endpoint: str,
        body: str,
        soap_action: str = "",
        extra_actions: list[str] | None = None,
    ) -> str:
        """POST a SOAP envelope with SOAPAction retries and diagnostics."""
        self._require_configured()
        url = self._endpoint_url(endpoint)
        actions = self._unique_actions(
            [soap_action, *(extra_actions or []), *self.DEFAULT_SOAP_ACTION_CANDIDATES]
        )
        errors: list[str] = []
        self._dump_debug("pipo_soap_last_request.xml", body)

        for action in actions:
            headers = {
                "Content-Type": "text/xml; charset=utf-8",
                "Accept": "text/xml, application/soap+xml, */*",
            }
            # SAP Java SOAP services usually accept an empty SOAPAction, but some
            # landscapes require the header to be present. Try both.
            if action:
                headers["SOAPAction"] = action
            try:
                response = requests.post(
                    url,
                    data=body.encode("utf-8"),
                    auth=self.auth,
                    headers=headers,
                    timeout=self.timeout,
                    verify=self.verify_ssl,
                )
                if response.text:
                    self._dump_debug("pipo_soap_last_response.xml", response.text)
                response.raise_for_status()
                return response.text
            except requests.RequestException as exc:
                action_label = action or "<empty SOAPAction>"
                exc_response = getattr(exc, "response", None)
                fault = self._extract_fault_string(
                    exc_response.text if exc_response is not None else ""
                )
                if fault:
                    errors.append(f"SOAPAction={action_label}: {exc} | Fault={fault}")
                else:
                    errors.append(f"SOAPAction={action_label}: {exc}")
                if exc_response is not None:
                    self._dump_debug("pipo_soap_last_error_response.xml", exc_response.text or "")

        error_text = " | ".join(errors[-4:]) if errors else "unknown SOAP error"
        self._dump_debug("pipo_soap_last_error.txt", error_text)
        raise SAPPIPOClientError(
            f"SAP PI/PO SOAP POST failed for endpoint {endpoint}: {error_text}"
        )

    @staticmethod
    def extract_results(payload: Any) -> list[dict[str, Any]]:
        return SAPCPIClient.extract_results(payload)

    def get_packages(self) -> list[dict[str, Any]]:
        if not settings.sap_pipo_packages_endpoint:
            return []
        if settings.sap_pipo_inventory_mode.lower() == "json":
            payload = self.get_json(
                settings.sap_pipo_packages_endpoint, {"$top": str(settings.sap_pipo_mpl_top)}
            )
            return self.extract_results(payload)
        return []

    def get_iflows(self) -> list[dict[str, Any]]:
        if not settings.sap_pipo_iflows_endpoint:
            return []
        if settings.sap_pipo_inventory_mode.lower() == "json":
            payload = self.get_json(
                settings.sap_pipo_iflows_endpoint, {"$top": str(settings.sap_pipo_mpl_top)}
            )
            return self.extract_results(payload)
        return []

    def get_message_processing_logs(
        self, start_time: datetime | None = None, end_time: datetime | None = None
    ) -> list[dict[str, Any]]:
        if not settings.sap_pipo_mpl_endpoint:
            return []

        mode = settings.sap_pipo_mpl_mode.lower()
        if mode == "json":
            payload = self.get_json(
                settings.sap_pipo_mpl_endpoint, {"$top": str(settings.sap_pipo_mpl_top)}
            )
            return self.extract_results(payload)

        bodies = self._build_mpl_request_candidates(start_time=start_time, end_time=end_time)
        errors: list[str] = []
        for label, body, actions in bodies:
            try:
                xml_text = self.post_soap(
                    settings.sap_pipo_mpl_endpoint,
                    body,
                    soap_action=settings.pipo_mpl_list_soap_action,
                    extra_actions=actions,
                )
                records = self._extract_records_from_xml(xml_text)
                if records:
                    self._dump_debug("pipo_soap_last_success_variant.txt", label)
                    return records
                errors.append(f"{label}: SOAP call succeeded but no message records were parsed")
            except SAPPIPOClientError as exc:
                errors.append(f"{label}: {exc}")

        raise SAPPIPOClientError(
            "; ".join(errors[-5:]) if errors else "No PI/PO MPL request variant returned records"
        )

    def _build_mpl_request_candidates(
        self, start_time: datetime | None = None, end_time: datetime | None = None
    ) -> list[tuple[str, str, list[str]]]:
        candidates: list[tuple[str, str, list[str]]] = []
        operation_name = (
            self._str_setting("pipo_mpl_operation_name", self.DEFAULT_OPERATION_NAME)
            or self.DEFAULT_OPERATION_NAME
        )
        namespaces = self._operation_namespaces()

        template = self._load_text_template(settings.pipo_mpl_list_template)
        if template:
            candidates.append(
                (
                    "legacy PIPO_MPL_LIST_TEMPLATE original",
                    self._render_mpl_template(template, start_time=start_time, end_time=end_time),
                    self._soap_actions_for(operation_name, namespaces[0] if namespaces else ""),
                )
            )
            for namespace in namespaces:
                if (
                    "http://sap.com/xi/XI/Message/30" in template
                    or "urn:AdapterMessageMonitoringVi" in template
                ):
                    rewritten = template.replace("http://sap.com/xi/XI/Message/30", namespace)
                    rewritten = rewritten.replace("urn:AdapterMessageMonitoringVi", namespace)
                    candidates.append(
                        (
                            f"legacy PIPO_MPL_LIST_TEMPLATE rewritten namespace={namespace}",
                            self._render_mpl_template(
                                rewritten, start_time=start_time, end_time=end_time
                            ),
                            self._soap_actions_for(operation_name, namespace),
                        )
                    )

        for namespace in namespaces:
            candidates.append(
                (
                    f"AdapterMessageMonitoringVi wrapped filter namespace={namespace}",
                    self._build_wrapped_filter_envelope(
                        namespace, operation_name, start_time=start_time, end_time=end_time
                    ),
                    self._soap_actions_for(operation_name, namespace),
                )
            )
            candidates.append(
                (
                    f"AdapterMessageMonitoringVi flat date range namespace={namespace}",
                    self._build_flat_date_envelope(
                        namespace, operation_name, start_time=start_time, end_time=end_time
                    ),
                    self._soap_actions_for(operation_name, namespace),
                )
            )
        return candidates

    def _operation_namespaces(self) -> list[str]:
        """Return namespaces that are valid for the SOAP operation wrapper.

        SAP PO WSDL files often expose a root targetNamespace such as
        ``urn:AdapterMessageMonitoringWsd`` while the actual request wrapper for
        ``getMessageList`` is ``urn:AdapterMessageMonitoringVi``. Using the WSDL
        root namespace as operation namespace causes the SAP runtime fault
        "No operation found using soap keys". Therefore configured namespace
        candidates are preferred and WSDL namespaces are used only when they
        look like operation wrapper namespaces.
        """
        namespaces: list[str] = []
        configured_namespace = self._str_setting("pipo_mpl_operation_namespace", "")
        if configured_namespace:
            namespaces.append(configured_namespace)

        raw_candidates = (
            self._str_setting(
                "pipo_mpl_namespace_candidates",
                ",".join(self.DEFAULT_NAMESPACE_CANDIDATES),
            )
            or ""
        )
        for item in raw_candidates.split(","):
            value = item.strip()
            if value:
                namespaces.append(value)
        namespaces.extend(self.DEFAULT_NAMESPACE_CANDIDATES)

        metadata = (
            self._discover_wsdl_metadata()
            if self._bool_setting("pipo_mpl_use_wsdl_discovery", True)
            else {}
        )
        for ns in metadata.get("target_namespaces", []) if isinstance(metadata, dict) else []:
            ns = str(ns).strip()
            if not ns:
                continue
            if ns.endswith("/AdapterMessageMonitoringVi") or ns.endswith(
                "AdapterMessageMonitoringVi"
            ):
                namespaces.append(ns)
            elif ns == "urn:AdapterMessageMonitoringWsd":
                # Common SAP PO WSDL root namespace; map to the request wrapper namespace.
                namespaces.append("urn:AdapterMessageMonitoringVi")
        return self._unique_actions(namespaces)

    def _soap_actions_for(self, operation_name: str, namespace: str) -> list[str]:
        actions: list[str] = []
        metadata = (
            self._discover_wsdl_metadata()
            if self._bool_setting("pipo_mpl_use_wsdl_discovery", True)
            else {}
        )
        if isinstance(metadata, dict):
            actions.extend(metadata.get("soap_actions", {}).get(operation_name, []))
        actions.extend(
            [
                "",
                operation_name,
                f"urn:{operation_name}",
                f"{namespace}/{operation_name}" if namespace else "",
                f"{namespace}#{operation_name}" if namespace else "",
            ]
        )
        return self._unique_actions(actions)

    def _discover_wsdl_metadata(self) -> dict[str, Any]:
        if self._wsdl_metadata is not None:
            return self._wsdl_metadata
        metadata: dict[str, Any] = {"target_namespaces": [], "operations": [], "soap_actions": {}}
        if not self._bool_setting("pipo_mpl_use_wsdl_discovery", True):
            self._wsdl_metadata = metadata
            return metadata
        wsdl_url = self._str_setting("pipo_mpl_wsdl_url", "")
        if not wsdl_url and settings.sap_pipo_mpl_endpoint:
            endpoint = self._endpoint_url(settings.sap_pipo_mpl_endpoint)
            wsdl_url = re.sub(r"\?.*$", "", endpoint) + "?wsdl&style=document"
        if not wsdl_url:
            self._wsdl_metadata = metadata
            return metadata
        try:
            response = requests.get(
                wsdl_url, auth=self.auth, timeout=self.timeout, verify=self.verify_ssl
            )
            response.raise_for_status()
            wsdl_text = response.text
            root = ET.fromstring(wsdl_text.encode("utf-8"))
            target_ns = root.attrib.get("targetNamespace")
            if target_ns:
                metadata["target_namespaces"].append(target_ns)
            ns = {
                "wsdl": "http://schemas.xmlsoap.org/wsdl/",
                "soap": "http://schemas.xmlsoap.org/wsdl/soap/",
            }
            for op in root.findall(".//wsdl:operation", ns):
                name = op.attrib.get("name")
                if not name:
                    continue
                metadata["operations"].append(name)
                for soap_operation in op.findall("soap:operation", ns):
                    action = soap_operation.attrib.get("soapAction")
                    if action:
                        metadata.setdefault("soap_actions", {}).setdefault(name, []).append(action)
            metadata["target_namespaces"] = self._unique_actions(metadata["target_namespaces"])
            metadata["operations"] = self._unique_actions(metadata["operations"])
            self._dump_debug("pipo_wsdl_discovery.json", json.dumps(metadata, indent=2))
        except Exception as exc:
            metadata["error"] = str(exc)
            self._dump_debug("pipo_wsdl_discovery_error.txt", str(exc))
        self._wsdl_metadata = metadata
        return metadata

    def _load_text_template(self, raw_path: str) -> str | None:
        if not raw_path:
            return None
        try:
            path = Path(raw_path)
            if path.exists() and path.is_file():
                return path.read_text(encoding="utf-8")
        except Exception:
            return None
        return None

    def _render_mpl_template(
        self, template: str, start_time: datetime | None = None, end_time: datetime | None = None
    ) -> str:
        date_from, date_to = self._resolve_date_range(start_time=start_time, end_time=end_time)
        replacements = {
            "STATUS": settings.pipo_mpl_status,
            "DATE_FROM": date_from,
            "DATE_TO": date_to,
            "MAX_MESSAGES": str(settings.sap_pipo_mpl_top),
        }
        rendered = template
        for key, value in replacements.items():
            rendered = rendered.replace("{{" + key + "}}", value)
        return rendered

    def _resolve_date_range(
        self, start_time: datetime | None = None, end_time: datetime | None = None
    ) -> tuple[str, str]:
        if start_time or end_time:
            now = datetime.now()
            date_to_dt = end_time or now
            date_from_dt = start_time or (
                date_to_dt - timedelta(hours=settings.sap_pipo_monitor_lookback_hours)
            )
            return date_from_dt.strftime("%Y-%m-%dT%H:%M:%S"), date_to_dt.strftime(
                "%Y-%m-%dT%H:%M:%S"
            )
        date_to = settings.pipo_mpl_date_to.strip()
        date_from = settings.pipo_mpl_date_from.strip()
        if date_to and date_from:
            return date_from, date_to
        now = datetime.now()
        if not date_to:
            date_to = now.strftime("%Y-%m-%dT%H:%M:%S")
        if not date_from:
            date_from = (now - timedelta(hours=settings.sap_pipo_monitor_lookback_hours)).strftime(
                "%Y-%m-%dT%H:%M:%S"
            )
        return date_from, date_to

    def _build_wrapped_filter_envelope(
        self,
        namespace: str,
        operation_name: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> str:
        """Build a SAP PO AdapterMessageMonitoringVi request with full AdapterFilter.

        The SAP PO service accepts the operation wrapper in
        ``urn:AdapterMessageMonitoringVi``, but the nested AdapterFilter fields
        are defined in ``urn:com.sap.aii.mdt.server.adapterframework.ws``. The
        filter fields are intentionally verbose because many SAP PO 7.5 systems
        reject a minimal filter and require fields such as archive, dateType,
        nodeId, onlyFaultyMessages, retries, retryInterval, timesFailed and
        wasEdited even when their default values are used.
        """
        date_from, date_to = self._resolve_date_range(start_time=start_time, end_time=end_time)
        filter_ns = (
            self._str_setting("pipo_mpl_filter_namespace", self.DEFAULT_FILTER_NAMESPACE)
            or self.DEFAULT_FILTER_NAMESPACE
        )
        archive = self._bool_xml(self._bool_setting("pipo_mpl_filter_archive", False))
        only_faulty = self._bool_xml(
            self._bool_setting("pipo_mpl_filter_only_faulty_messages", False)
        )
        was_edited = self._bool_xml(self._bool_setting("pipo_mpl_filter_was_edited", False))
        date_type = self._str_setting("pipo_mpl_filter_date_type", "0") or "0"
        node_id = self._str_setting("pipo_mpl_filter_node_id", "0") or "0"
        retries = self._str_setting("pipo_mpl_filter_retries", "0") or "0"
        retry_interval = self._str_setting("pipo_mpl_filter_retry_interval", "0") or "0"
        times_failed = self._str_setting("pipo_mpl_filter_times_failed", "0") or "0"
        status_xml = (
            f"<af:status>{self._xml_escape(settings.pipo_mpl_status)}</af:status>"
            if settings.pipo_mpl_status
            else ""
        )
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:amm="{namespace}"
                  xmlns:af="{filter_ns}">
  <soapenv:Header/>
  <soapenv:Body>
    <amm:{operation_name}>
      <amm:filter>
        <af:archive>{archive}</af:archive>
        <af:dateType>{date_type}</af:dateType>
        <af:fromTime>{date_from}</af:fromTime>
        <af:nodeId>{node_id}</af:nodeId>
        <af:onlyFaultyMessages>{only_faulty}</af:onlyFaultyMessages>
        <af:retries>{retries}</af:retries>
        <af:retryInterval>{retry_interval}</af:retryInterval>
        {status_xml}
        <af:timesFailed>{times_failed}</af:timesFailed>
        <af:toTime>{date_to}</af:toTime>
        <af:wasEdited>{was_edited}</af:wasEdited>
      </amm:filter>
      <amm:maxMessages>{settings.sap_pipo_mpl_top}</amm:maxMessages>
    </amm:{operation_name}>
  </soapenv:Body>
</soapenv:Envelope>'''

    @staticmethod
    def _bool_xml(value: bool) -> str:
        return "true" if bool(value) else "false"

    @staticmethod
    def _xml_escape(value: Any) -> str:
        text = str(value or "")
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;")
        )

    def _build_flat_date_envelope(
        self,
        namespace: str,
        operation_name: str,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> str:
        date_from, date_to = self._resolve_date_range(start_time=start_time, end_time=end_time)
        status_xml = (
            f"<urn:Status>{settings.pipo_mpl_status}</urn:Status>"
            if settings.pipo_mpl_status
            else ""
        )
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:urn="{namespace}">
  <soapenv:Header/>
  <soapenv:Body>
    <urn:{operation_name}>
      {status_xml}
      <urn:DateFrom>{date_from}</urn:DateFrom>
      <urn:DateTo>{date_to}</urn:DateTo>
      <urn:MaxMessages>{settings.sap_pipo_mpl_top}</urn:MaxMessages>
    </urn:{operation_name}>
  </soapenv:Body>
</soapenv:Envelope>'''

    @staticmethod
    def _local_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1] if "}" in tag else tag

    @staticmethod
    def _unique_actions(actions: list[str]) -> list[str]:
        unique: list[str] = []
        seen: set[str] = set()
        for action in actions:
            value = (action or "").strip()
            if value not in seen:
                seen.add(value)
                unique.append(value)
        return unique

    def _dump_debug(self, filename: str, content: str) -> None:
        if not self._bool_setting("pipo_mpl_debug_dump", True):
            return
        try:
            (self.logs_dir / filename).write_text(content or "", encoding="utf-8")
        except Exception:
            pass

    def _extract_fault_string(self, xml_text: str) -> str:
        if not xml_text:
            return ""
        try:
            root = ET.fromstring(xml_text.encode("utf-8"))
            for element in root.iter():
                if self._local_name(element.tag).lower() == "faultstring":
                    return (element.text or "").strip()
        except ET.ParseError:
            return ""
        return ""

    def _extract_records_from_xml(self, xml_text: str) -> list[dict[str, Any]]:
        try:
            root = ET.fromstring(xml_text.encode("utf-8"))
        except ET.ParseError:
            return []

        # Short-circuit SOAP faults as no records. The caller will already have
        # raised for HTTP errors; this handles HTTP 200 SOAP faults defensively.
        if self._extract_fault_string(xml_text):
            return []

        candidates: list[dict[str, Any]] = []
        for element in root.iter():
            children = list(element)
            if not children:
                continue
            record: dict[str, Any] = {}
            for child in children:
                name = self._local_name(child.tag)
                text = (child.text or "").strip()
                if text:
                    record[name] = text
            if self._looks_like_message_record(record):
                candidates.append(self._normalize_xml_record(record))

        deduped: list[dict[str, Any]] = []
        seen: set[str] = set()
        for record in candidates:
            key = str(
                record.get("MessageGuid")
                or record.get("MessageKey")
                or record.get("MessageId")
                or record.get("messageID")
                or json.dumps(record, sort_keys=True)
            )
            if key not in seen:
                seen.add(key)
                deduped.append(record)
        return deduped

    def _looks_like_message_record(self, record: dict[str, Any]) -> bool:
        if not record:
            return False
        normalized_keys = {k.lower() for k in record}
        interesting = {
            "status",
            "messagestatus",
            "messagestate",
            "messageid",
            "messageguid",
            "messagekey",
            "errortext",
            "errormessage",
            "sender",
            "receiver",
            "messagedirection",
            "component",
            "interface",
        }
        return bool(normalized_keys.intersection(interesting))

    def _normalize_xml_record(self, record: dict[str, Any]) -> dict[str, Any]:
        normalized = dict(record)
        for key in list(record):
            lower = key.lower()
            value = record[key]
            if lower in {"status", "messagestatus", "messagestate"}:
                normalized.setdefault("Status", value)
            elif lower in {"messageid", "messageguid", "messagekey"}:
                normalized.setdefault("MessageGuid", value)
            elif lower in {"errortext", "errormessage", "error"}:
                normalized.setdefault("ErrorMessage", value)
        if "Status" not in normalized and any(k.lower().startswith("error") for k in normalized):
            normalized["Status"] = "FAILED"
        if "Status" in normalized:
            normalized["Status"] = re.sub(r"\s+", "_", str(normalized["Status"]).strip()).upper()
        return normalized
