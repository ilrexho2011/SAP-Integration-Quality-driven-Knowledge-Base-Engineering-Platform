"""External monitoring evidence core (v2.0.10).

Canonical contract that every external monitoring connector emits. QDKEP already
consumes MPL evidence from SAP CPI and SAP PI/PO through the native evidence
services; this module makes evidence intake source-agnostic so that APIM, AEM,
B2B/EDI, S/4HANA (IDoc, SM58/qRFC), HANA Cloud, on-premise MSSQL and on-premise
SFTP can feed the same Scenario Lab & Generation flow.

Design rules (aligned with the platform):
- Typed dataclasses, explicit error handling, deterministic IDs.
- ``evidence_id`` is derived from identity + signature (no timestamps) so the
  same observed error is idempotent under Duplicate Governance.
- No secrets in evidence: on-prem backends use Cloud Connector aliases, never
  host:port plus credentials.
- Missing values are marked ``missing`` in ``field_status``; never invented.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class Technology(str, Enum):
    """External-monitoring technology vocabulary (extends interface inventory)."""

    APIM = "APIM"
    AEM = "AEM"
    B2B_EDI = "B2B_EDI"
    IDOC = "IDoc"
    RFC = "RFC"
    HANA_DB = "HANA_DB"
    MSSQL = "MSSQL"
    SFTP = "SFTP"


class MonitoringSource(str, Enum):
    """One value per concrete external monitoring origin."""

    APIM_ANALYTICS = "APIM_ANALYTICS"
    AEM_BROKER = "AEM_BROKER"
    B2B_MONITORING = "B2B_MONITORING"
    S4_IDOC_MONITORING = "S4_IDOC_MONITORING"
    S4_SM58 = "S4_SM58"
    S4_QRFC = "S4_QRFC"
    HANA_CLOUD_ALERTS = "HANA_CLOUD_ALERTS"
    MSSQL_ERROR_LOG = "MSSQL_ERROR_LOG"
    SFTP_SERVER_LOG = "SFTP_SERVER_LOG"


class Severity(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class ArtifactHint(str, Enum):
    """Which QDKEP artifact this evidence most naturally seeds."""

    KEDB = "kedb"
    RUNBOOK = "runbook"
    CATALOG = "catalog"


_TOKEN_RE = re.compile(r"[^A-Z0-9]+")


def normalize_token(value: str) -> str:
    """Uppercase, underscore-joined, no spaces (ERROR_CODE-style)."""
    return _TOKEN_RE.sub("_", (value or "").strip().upper()).strip("_")


def build_taxonomy(domain: str, category: str, subcategory: str, code: str) -> str:
    """BM25 normalized taxonomy: ``DOMAIN | CATEGORY | SUBCATEGORY | CODE``."""
    parts = [normalize_token(p) for p in (domain, category, subcategory, code)]
    return " | ".join(p for p in parts if p)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class EvidenceRecord:
    """Single contract QDKEP Scenario Lab & Generation consumes for external sources."""

    # identity / routing
    customer_id: str
    system_id: str
    technology: Technology
    monitoring_source: MonitoringSource
    monitoring_object: str
    monitoring_event_type: str
    priority: Severity
    artifact_hint: ArtifactHint

    # signature (BM25 / retrieval critical)
    canonical_error_phrase: str
    taxonomy: str
    exact_error_text: str | None = None

    # correlation
    sap_sid: str | None = None
    http_status: str | None = None
    message_guid: str | None = None
    correlation_id: str | None = None
    integration_flow_name: str | None = None
    interface_id: str | None = None
    sender: str | None = None
    receiver: str | None = None
    endpoint_alias: str | None = None  # alias only, never host:port+creds

    # provenance
    mode: str = "local"  # 'live' | 'local'
    observed_at: str | None = None
    ingested_at: str = field(default_factory=utc_now_iso)
    raw_ref: str | None = None
    field_status: dict[str, str] = field(default_factory=dict)
    extra: dict[str, Any] = field(default_factory=dict)

    evidence_id: str = field(default="", init=False)

    def __post_init__(self) -> None:
        if not self.customer_id:
            raise ValueError("customer_id is required")
        if not self.system_id:
            raise ValueError("system_id is required")
        if not self.canonical_error_phrase:
            raise ValueError("canonical_error_phrase is required")
        self.technology = Technology(self.technology)
        self.monitoring_source = MonitoringSource(self.monitoring_source)
        self.priority = Severity(self.priority)
        self.artifact_hint = ArtifactHint(self.artifact_hint)
        self.evidence_id = self._compute_evidence_id()

    def _compute_evidence_id(self) -> str:
        """Deterministic ID from stable identity + signature (no timestamps).

        Supports QDKEP 'prevent dublicate ID' governance: the same observed error
        maps to the same evidence_id regardless of when it was ingested.
        """
        basis = "|".join(
            [
                self.customer_id,
                self.system_id,
                self.technology.value,
                self.monitoring_source.value,
                normalize_token(self.monitoring_object),
                self.taxonomy,
                (self.http_status or ""),
            ]
        )
        digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:12].upper()
        return f"EV-{self.technology.value}-{digest}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["technology"] = self.technology.value
        data["monitoring_source"] = self.monitoring_source.value
        data["priority"] = self.priority.value
        data["artifact_hint"] = self.artifact_hint.value
        data["evidence_id"] = self.evidence_id
        return data

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2, **kwargs)

    def suggested_filename(self) -> str:
        """Maps to the ingestion-guide naming convention.

        ``<TYPE>_<CUSTOMER>_<SYSTEM>_<ERROR_CODE>_<PRIORITY>_<VERSION>.md``
        """
        type_prefix = {"runbook": "RB", "kedb": "KB", "catalog": "DOC"}[self.artifact_hint.value]
        segs = [s.strip() for s in self.taxonomy.split("|") if s.strip()]
        if len(segs) >= 2:
            error_code = normalize_token("_".join(segs[-2:]))
        elif segs:
            error_code = normalize_token(segs[-1])
        else:
            error_code = "UNKNOWN"
        sys_token = normalize_token(self.system_id)
        cust_token = normalize_token(self.customer_id)
        return f"{type_prefix}_{cust_token}_{sys_token}_{error_code}_{self.priority.value}_v1.md"
