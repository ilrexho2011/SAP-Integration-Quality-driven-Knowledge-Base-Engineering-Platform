"""External monitoring connectors (v2.0.10).

Normalizes monitoring events from APIM, AEM, B2B/EDI, S/4HANA (IDoc, SM58, qRFC),
HANA Cloud, on-premise MSSQL and on-premise SFTP into a single canonical
``EvidenceRecord`` that QDKEP Scenario Lab & Generation consumes — the same role
SAP CPI MPL plays in the native evidence services.

The connectors parse already-fetched raw records (live API page rows or local
export lines) into evidence. Credentialed, read-only-first fetching is a separate
concern, gated behind ``settings.external_monitoring_enabled``.
"""

from .connectors import (
    CONNECTOR_REGISTRY,
    AemConnector,
    ApimConnector,
    B2BConnector,
    BaseConnector,
    HanaCloudConnector,
    MssqlConnector,
    S4IDocConnector,
    S4QrfcConnector,
    S4Sm58Connector,
    SftpConnector,
    get_connector,
)
from .core import (
    ArtifactHint,
    EvidenceRecord,
    MonitoringSource,
    Severity,
    Technology,
    build_taxonomy,
    normalize_token,
)

__all__ = [
    "ArtifactHint",
    "EvidenceRecord",
    "MonitoringSource",
    "Severity",
    "Technology",
    "build_taxonomy",
    "normalize_token",
    "CONNECTOR_REGISTRY",
    "BaseConnector",
    "ApimConnector",
    "AemConnector",
    "B2BConnector",
    "S4IDocConnector",
    "S4Sm58Connector",
    "S4QrfcConnector",
    "HanaCloudConnector",
    "MssqlConnector",
    "SftpConnector",
    "get_connector",
]
