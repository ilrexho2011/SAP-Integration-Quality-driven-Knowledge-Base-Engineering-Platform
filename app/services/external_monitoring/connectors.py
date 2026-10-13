"""
QDKEP Source Connectors
=======================

One connector per monitoring source. Each connector takes a *raw* record
(a dict already pulled from the source — live API page or local export line)
and normalizes it into a canonical :class:`EvidenceRecord`.

Connectors do NOT fetch data themselves here; fetching is a separate, credentialed,
read-only-first concern (see fetchers/ in a real deployment). This keeps parsing
deterministic and unit-testable, per the platform code-review checklist.

Anchored to the user's landscape:
- S/4HANA 2023, Client 100, SID = S4H
- Integration Suite APIM proxies: restcountries_by_code, restcountries, IR23_IF01_Explore
- HANA Cloud instance: HANA_DB_LEARN
- On-prem MSSQL: LENOVO\\ILRE_SQL (DBs ILRE_CPI, Northwind) via mssql-virtual-host:1433
- On-prem SFTP: /n software SFTP via my-sftp-virtual-host:2288
- Cloud Connector bridges the on-prem TCP backends
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from .core import (
    ArtifactHint,
    EvidenceRecord,
    MonitoringSource,
    Severity,
    Technology,
    build_taxonomy,
)


class BaseConnector(ABC):
    """Common interface. Subclasses map raw source dicts -> EvidenceRecord."""

    technology: Technology
    monitoring_source: MonitoringSource

    def __init__(self, customer_id: str, *, mode: str = "local") -> None:
        if mode not in ("live", "local"):
            raise ValueError("mode must be 'live' or 'local'")
        self.customer_id = customer_id
        self.mode = mode

    @abstractmethod
    def normalize(self, raw: dict[str, Any]) -> EvidenceRecord:
        """Convert one raw source record into a canonical EvidenceRecord."""

    def normalize_many(self, raws: list[dict[str, Any]]) -> list[EvidenceRecord]:
        out: list[EvidenceRecord] = []
        for r in raws:
            try:
                out.append(self.normalize(r))
            except (KeyError, ValueError) as exc:
                # Never invent values; surface the bad record instead.
                out.append(self._error_evidence(r, str(exc)))
        return out

    # -- shared helpers --
    @staticmethod
    def _get(raw: dict[str, Any], key: str, default: Any = None) -> Any:
        return raw.get(key, default)

    def _error_evidence(self, raw: dict[str, Any], reason: str) -> EvidenceRecord:
        return EvidenceRecord(
            customer_id=self.customer_id,
            system_id=raw.get("system_id", "UNKNOWN"),
            technology=self.technology,
            monitoring_source=self.monitoring_source,
            monitoring_object=str(raw.get("monitoring_object", "UNKNOWN")),
            monitoring_event_type="normalization_error",
            priority=Severity.P3,
            artifact_hint=ArtifactHint.KEDB,
            canonical_error_phrase=f"Evidence normalization failed: {reason}",
            taxonomy=build_taxonomy("PLATFORM", "INGEST", "NORMALIZE_ERROR", "0"),
            mode=self.mode,
            field_status={"_all": "missing"},
            extra={"raw_keys": sorted(raw.keys())},
        )


# --------------------------------------------------------------------------- #
# 1. APIM (SAP API Management)                                                  #
# --------------------------------------------------------------------------- #
class ApimConnector(BaseConnector):
    """
    Source: APIM API Analytics / API Monitoring.
    Raw expected: {api_proxy, status_code, fault_type?, latency_ms?, timestamp?}
    """

    technology = Technology.APIM
    monitoring_source = MonitoringSource.APIM_ANALYTICS

    _FAULT_MAP = {
        "429": ("QUOTA_EXCEEDED", "Quota/spike arrest limit exceeded", Severity.P2),
        "401": ("UNAUTHORIZED", "API proxy authentication failed", Severity.P2),
        "403": ("FORBIDDEN", "API proxy authorization denied", Severity.P2),
        "503": ("BACKEND_UNAVAILABLE", "API backend target unavailable", Severity.P1),
        "500": ("POLICY_FAULT", "API policy execution fault", Severity.P2),
    }

    def normalize(self, raw: dict[str, Any]) -> EvidenceRecord:
        proxy = raw["api_proxy"]  # required
        status = str(raw["status_code"])  # required
        sub, phrase, sev = self._FAULT_MAP.get(
            status, ("HTTP_ERROR", f"API proxy returned HTTP {status}", Severity.P3)
        )
        return EvidenceRecord(
            customer_id=self.customer_id,
            system_id=raw.get("system_id", "BTP-APIM"),
            technology=self.technology,
            monitoring_source=self.monitoring_source,
            monitoring_object=proxy,
            monitoring_event_type="policy_fault" if status in self._FAULT_MAP else "http_error",
            priority=sev,
            artifact_hint=ArtifactHint.KEDB,
            canonical_error_phrase=f"{phrase} on {proxy}",
            taxonomy=build_taxonomy("API", "POLICY", sub, status),
            exact_error_text=raw.get("fault_string"),
            http_status=status,
            interface_id=proxy,
            endpoint_alias=raw.get("provider"),  # e.g. restcountries_provider
            observed_at=raw.get("timestamp"),
            mode=self.mode,
            raw_ref=raw.get("raw_ref"),
            field_status={
                "monitoring_object": "source-backed",
                "http_status": "source-backed",
                "canonical_error_phrase": "derived",
            },
            extra={"latency_ms": raw.get("latency_ms")},
        )


# --------------------------------------------------------------------------- #
# 2. AEM (Advanced Event Mesh / Event Mesh)                                     #
# --------------------------------------------------------------------------- #
class AemConnector(BaseConnector):
    """
    Source: AEM broker monitoring (queue/DMQ stats).
    Raw expected: {queue_name, event, redelivery_count?, spooled?, timestamp?}
    """

    technology = Technology.AEM
    monitoring_source = MonitoringSource.AEM_BROKER

    def normalize(self, raw: dict[str, Any]) -> EvidenceRecord:
        queue = raw["queue_name"]  # required
        event = raw.get("event", "message_spooled_to_dmq")
        redel = raw.get("redelivery_count")
        if event == "message_spooled_to_dmq":
            sub, phrase, sev = (
                "DEAD_MESSAGE_QUEUE",
                "Message moved to Dead Message Queue",
                Severity.P1,
            )
        elif event == "queue_backlog":
            sub, phrase, sev = (
                "QUEUE_BACKLOG",
                "Queue spooled-message backlog over threshold",
                Severity.P2,
            )
        else:
            sub, phrase, sev = "DELIVERY_ERROR", f"AEM delivery event {event}", Severity.P2
        return EvidenceRecord(
            customer_id=self.customer_id,
            system_id=raw.get("system_id", "BTP-AEM"),
            technology=self.technology,
            monitoring_source=self.monitoring_source,
            monitoring_object=f"{queue}/DMQ" if "dmq" in event else queue,
            monitoring_event_type=event,
            priority=sev,
            artifact_hint=ArtifactHint.RUNBOOK,
            canonical_error_phrase=f"{phrase} on {queue}",
            taxonomy=build_taxonomy("EVENT", "DELIVERY", sub, "MAXREDELIVERY" if redel else "0"),
            exact_error_text=raw.get("error_text"),
            interface_id=queue,
            observed_at=raw.get("timestamp"),
            mode=self.mode,
            raw_ref=raw.get("raw_ref"),
            field_status={
                "monitoring_object": "source-backed" if raw.get("queue_name") else "missing",
                "canonical_error_phrase": "derived",
            },
            extra={"redelivery_count": redel, "spooled": raw.get("spooled")},
        )


# --------------------------------------------------------------------------- #
# 3. B2B / EDI (Trading Partner Management monitoring)                          #
# --------------------------------------------------------------------------- #
class B2BConnector(BaseConnector):
    """
    Source: Integration Suite B2B Monitoring.
    Raw expected: {agreement, document_type, event, partner?, direction?, timestamp?}
    """

    technology = Technology.B2B_EDI
    monitoring_source = MonitoringSource.B2B_MONITORING

    def normalize(self, raw: dict[str, Any]) -> EvidenceRecord:
        agreement = raw["agreement"]  # required
        doc_type = raw.get("document_type", "UNKNOWN")
        event = raw.get("event", "functional_ack_missing")
        if event == "functional_ack_missing":
            sub, code, phrase, sev = (
                "ACK",
                "997",
                "Functional acknowledgment not received",
                Severity.P2,
            )
        elif event == "envelope_validation_failed":
            sub, code, phrase, sev = "ENVELOPE", "0", "EDI envelope validation failed", Severity.P2
        else:
            sub, code, phrase, sev = "PROCESSING", "0", f"B2B event {event}", Severity.P3
        return EvidenceRecord(
            customer_id=self.customer_id,
            system_id=raw.get("system_id", "BTP-B2B"),
            technology=self.technology,
            monitoring_source=self.monitoring_source,
            monitoring_object=f"{agreement}/{doc_type}",
            monitoring_event_type=event,
            priority=sev,
            artifact_hint=ArtifactHint.RUNBOOK,
            canonical_error_phrase=f"{phrase} for {doc_type} ({agreement})",
            taxonomy=build_taxonomy("EDI", sub, doc_type, code),
            exact_error_text=raw.get("error_text"),
            interface_id=agreement,
            sender=raw.get("partner") if raw.get("direction") == "inbound" else None,
            receiver=raw.get("partner") if raw.get("direction") == "outbound" else None,
            observed_at=raw.get("timestamp"),
            mode=self.mode,
            raw_ref=raw.get("raw_ref"),
            field_status={
                "monitoring_object": "source-backed",
                "canonical_error_phrase": "derived",
                "partner": "source-backed" if raw.get("partner") else "missing",
            },
            extra={"direction": raw.get("direction")},
        )


# --------------------------------------------------------------------------- #
# 4. S/4HANA — IDoc, SM58 (tRFC/aRFC), qRFC queues                              #
# --------------------------------------------------------------------------- #
class S4IDocConnector(BaseConnector):
    """
    Source: WE05/WE02 + EDIDC/EDIDS. SID anchored to S4H, client 100.
    Raw expected: {idoc_number?, message_type, direction, status, status_text?, timestamp?}
    """

    technology = Technology.IDOC
    monitoring_source = MonitoringSource.S4_IDOC_MONITORING

    # IDoc status -> (canonical, severity). Subset of common error statuses.
    _STATUS = {
        "51": ("APPLICATION_ERROR", Severity.P2),  # inbound application error
        "56": ("IDOC_WITH_ERRORS", Severity.P2),  # inbound, IDoc with errors
        "29": ("ALE_ERROR", Severity.P2),  # outbound ALE service error
        "02": ("OUTBOUND_TRANSMISSION_ERROR", Severity.P2),
        "30": ("READY_FOR_DISPATCH", Severity.P3),
    }

    def normalize(self, raw: dict[str, Any]) -> EvidenceRecord:
        msg_type = raw["message_type"]  # required, e.g. ORDERS05
        status = str(raw["status"])  # required
        direction = raw.get("direction", "inbound")
        sub, sev = self._STATUS.get(status, ("IDOC_STATUS", Severity.P3))
        return EvidenceRecord(
            customer_id=self.customer_id,
            system_id=raw.get("system_id", "S4H-PROD"),
            sap_sid="S4H",
            technology=self.technology,
            monitoring_source=self.monitoring_source,
            monitoring_object=f"{msg_type}/{direction}",
            monitoring_event_type="idoc_processing_error",
            priority=sev,
            artifact_hint=ArtifactHint.RUNBOOK,
            canonical_error_phrase=f"IDoc {msg_type} {direction} status {status}",
            taxonomy=build_taxonomy("IDOC", direction.upper(), sub, f"STATUS_{status}"),
            exact_error_text=raw.get("status_text"),
            correlation_id=raw.get("idoc_number"),
            observed_at=raw.get("timestamp"),
            mode=self.mode,
            raw_ref=raw.get("raw_ref"),
            field_status={
                "monitoring_object": "source-backed",
                "exact_error_text": "source-backed" if raw.get("status_text") else "missing",
                "sap_sid": "source-backed",
            },
            extra={"client": raw.get("client", "100")},
        )


class S4Sm58Connector(BaseConnector):
    """
    Source: SM58 Asynchronous RFC Error Log (ARFCSSTATE/ARFCSDATA).
    Raw expected: {function_module, target_system?, status_text, timestamp?}
    """

    technology = Technology.RFC
    monitoring_source = MonitoringSource.S4_SM58

    def normalize(self, raw: dict[str, Any]) -> EvidenceRecord:
        fm = raw["function_module"]  # required
        status_text = raw.get("status_text", "")
        return EvidenceRecord(
            customer_id=self.customer_id,
            system_id=raw.get("system_id", "S4H-PROD"),
            sap_sid="S4H",
            technology=self.technology,
            monitoring_source=self.monitoring_source,
            monitoring_object=fm,
            monitoring_event_type="rfc_call_failed",
            priority=Severity.P2,
            artifact_hint=ArtifactHint.KEDB,
            canonical_error_phrase=f"Asynchronous RFC call failed: {fm}",
            taxonomy=build_taxonomy("RFC", "ASYNC", "CALL_FAILED", "SM58"),
            exact_error_text=status_text,
            receiver=raw.get("target_system"),
            observed_at=raw.get("timestamp"),
            mode=self.mode,
            raw_ref=raw.get("raw_ref"),
            field_status={
                "monitoring_object": "source-backed",
                "exact_error_text": "source-backed" if status_text else "missing",
            },
        )


class S4QrfcConnector(BaseConnector):
    """
    Source: SMQ1 (outbound) / SMQ2 (inbound) qRFC monitor (TRFCQOUT/TRFCQIN).
    Raw expected: {queue_name, direction, queue_status, entries?, timestamp?}
    """

    technology = Technology.RFC
    monitoring_source = MonitoringSource.S4_QRFC

    def normalize(self, raw: dict[str, Any]) -> EvidenceRecord:
        queue = raw["queue_name"]  # required
        direction = raw.get("direction", "outbound")
        status = raw.get("queue_status", "SYSFAIL")
        sev = Severity.P1 if status in ("SYSFAIL", "STOP") else Severity.P2
        return EvidenceRecord(
            customer_id=self.customer_id,
            system_id=raw.get("system_id", "S4H-PROD"),
            sap_sid="S4H",
            technology=self.technology,
            monitoring_source=self.monitoring_source,
            monitoring_object=f"{queue}/{direction}",
            monitoring_event_type="queue_stuck",
            priority=sev,
            artifact_hint=ArtifactHint.RUNBOOK,
            canonical_error_phrase=f"qRFC queue {queue} in status {status}",
            taxonomy=build_taxonomy("QRFC", direction.upper(), "QUEUE_STUCK", status),
            exact_error_text=raw.get("status_text"),
            observed_at=raw.get("timestamp"),
            mode=self.mode,
            raw_ref=raw.get("raw_ref"),
            field_status={
                "monitoring_object": "source-backed",
                "canonical_error_phrase": "derived",
            },
            extra={"entries": raw.get("entries")},
        )


# --------------------------------------------------------------------------- #
# 5. HANA Cloud DB (HANA_DB_LEARN)                                              #
# --------------------------------------------------------------------------- #
class HanaCloudConnector(BaseConnector):
    """
    Source: HANA Cloud Central Alerts / M_ALERTS.
    Raw expected: {instance, alert_id?, alert_name, alert_rating?, timestamp?}
    """

    technology = Technology.HANA_DB
    monitoring_source = MonitoringSource.HANA_CLOUD_ALERTS

    def normalize(self, raw: dict[str, Any]) -> EvidenceRecord:
        instance = raw["instance"]  # required, e.g. HANA_DB_LEARN
        alert_name = raw["alert_name"]  # required
        rating = str(raw.get("alert_rating", "3"))  # 1..5; 5 = error
        sev = Severity.P1 if rating in ("4", "5") else Severity.P2
        return EvidenceRecord(
            customer_id=self.customer_id,
            system_id=raw.get("system_id", "HANA-CLOUD"),
            technology=self.technology,
            monitoring_source=self.monitoring_source,
            monitoring_object=instance,
            monitoring_event_type="db_alert",
            priority=sev,
            artifact_hint=ArtifactHint.KEDB,
            canonical_error_phrase=f"HANA Cloud alert: {alert_name} on {instance}",
            taxonomy=build_taxonomy("DB", "HANA", "ALERT_ACTIVE", str(raw.get("alert_id", "0"))),
            exact_error_text=raw.get("alert_details"),
            observed_at=raw.get("timestamp"),
            mode=self.mode,
            raw_ref=raw.get("raw_ref"),
            field_status={
                "monitoring_object": "source-backed",
                "canonical_error_phrase": "derived",
            },
            extra={"alert_rating": rating},
        )


# --------------------------------------------------------------------------- #
# 6. On-Premise MSSQL (LENOVO\\ILRE_SQL)                                        #
# --------------------------------------------------------------------------- #
class MssqlConnector(BaseConnector):
    """
    Source: SQL Server Error Log / sys.dm_exec_requests.
    Reached from CPI/BTP via Cloud Connector alias 'mssql-virtual-host:1433'.
    Raw expected: {database, error_number, message?, timestamp?}
    """

    technology = Technology.MSSQL
    monitoring_source = MonitoringSource.MSSQL_ERROR_LOG

    _ERR = {
        "18456": ("LOGIN_FAILED", "SQL Server login failed", Severity.P2),
        "1205": ("DEADLOCK", "SQL Server deadlock victim", Severity.P2),
        "8645": ("MEMORY_TIMEOUT", "Timeout waiting for memory resource", Severity.P2),
        "-2": ("CONNECTION_TIMEOUT", "SQL connection/query timeout", Severity.P2),
    }

    def normalize(self, raw: dict[str, Any]) -> EvidenceRecord:
        db = raw["database"]  # required, e.g. ILRE_CPI
        err_no = str(raw["error_number"])  # required
        sub, phrase, sev = self._ERR.get(
            err_no, ("DB_ERROR", f"SQL Server error {err_no}", Severity.P3)
        )
        return EvidenceRecord(
            customer_id=self.customer_id,
            system_id=raw.get("system_id", "ONPREM-SQL-LENOVO"),
            technology=self.technology,
            monitoring_source=self.monitoring_source,
            monitoring_object=db,
            monitoring_event_type="connection_failure" if err_no == "18456" else "db_error",
            priority=sev,
            artifact_hint=ArtifactHint.KEDB,
            canonical_error_phrase=f"{phrase} on {db}",
            taxonomy=build_taxonomy("DB", "MSSQL", sub, err_no),
            exact_error_text=raw.get("message"),
            endpoint_alias="mssql-virtual-host:1433",  # Cloud Connector alias, no creds
            observed_at=raw.get("timestamp"),
            mode=self.mode,
            raw_ref=raw.get("raw_ref"),
            field_status={
                "monitoring_object": "source-backed",
                "endpoint_alias": "source-backed",
                "canonical_error_phrase": "derived",
            },
            extra={"via": "cloud_connector"},
        )


# --------------------------------------------------------------------------- #
# 7. On-Premise SFTP (/n software SFTP)                                         #
# --------------------------------------------------------------------------- #
class SftpConnector(BaseConnector):
    """
    Source: SFTP server session log + CPI SFTP adapter MPL.
    Reached via Cloud Connector alias 'my-sftp-virtual-host:2288'.
    Raw expected: {event, path?, message?, timestamp?}
    """

    technology = Technology.SFTP
    monitoring_source = MonitoringSource.SFTP_SERVER_LOG

    _EVENT = {
        "authentication_error": ("AUTH", "KEY_REJECTED", "SFTP authentication failed", Severity.P2),
        "connection_failure": ("CONN", "REFUSED", "SFTP connection refused/timeout", Severity.P1),
        "file_not_found": ("FILE", "NOT_FOUND", "SFTP file not found at path", Severity.P3),
        "poll_error": ("POLL", "ERROR", "SFTP polling error", Severity.P2),
    }

    def normalize(self, raw: dict[str, Any]) -> EvidenceRecord:
        event = raw.get("event", "authentication_error")
        cat, sub, phrase, sev = self._EVENT.get(
            event, ("SFTP", "ERROR", f"SFTP event {event}", Severity.P3)
        )
        obj = raw.get("path") or "my-sftp-virtual-host:2288"
        return EvidenceRecord(
            customer_id=self.customer_id,
            system_id=raw.get("system_id", "ONPREM-SFTP"),
            technology=self.technology,
            monitoring_source=self.monitoring_source,
            monitoring_object=obj,
            monitoring_event_type=event,
            priority=sev,
            artifact_hint=ArtifactHint.RUNBOOK,
            canonical_error_phrase=f"{phrase} ({obj})",
            taxonomy=build_taxonomy("SFTP", cat, sub, "0"),
            exact_error_text=raw.get("message"),
            endpoint_alias="my-sftp-virtual-host:2288",
            observed_at=raw.get("timestamp"),
            mode=self.mode,
            raw_ref=raw.get("raw_ref"),
            field_status={
                "endpoint_alias": "source-backed",
                "canonical_error_phrase": "derived",
            },
            extra={"via": "cloud_connector"},
        )


# --------------------------------------------------------------------------- #
# Registry — pick a connector by source key                                     #
# --------------------------------------------------------------------------- #
CONNECTOR_REGISTRY: dict[str, type[BaseConnector]] = {
    "apim": ApimConnector,
    "aem": AemConnector,
    "b2b": B2BConnector,
    "s4_idoc": S4IDocConnector,
    "s4_sm58": S4Sm58Connector,
    "s4_qrfc": S4QrfcConnector,
    "hana_cloud": HanaCloudConnector,
    "mssql": MssqlConnector,
    "sftp": SftpConnector,
}


def get_connector(source_key: str, customer_id: str, *, mode: str = "local") -> BaseConnector:
    try:
        cls = CONNECTOR_REGISTRY[source_key]
    except KeyError as exc:
        raise ValueError(
            f"Unknown source '{source_key}'. Known: {sorted(CONNECTOR_REGISTRY)}"
        ) from exc
    return cls(customer_id, mode=mode)
