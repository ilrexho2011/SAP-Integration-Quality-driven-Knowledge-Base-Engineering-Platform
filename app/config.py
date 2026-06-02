from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]
# Load local .env automatically when backend, scripts or Streamlit are started
# from the project root. This avoids the common Windows/PowerShell issue where
# values exist in .env but are not present in os.environ.
load_dotenv(PROJECT_ROOT / ".env", override=False)
load_dotenv(PROJECT_ROOT / ".env.local", override=False)


def _bool_env(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_env(*names: str, default: int) -> int:
    for name in names:
        raw = os.getenv(name)
        if raw not in (None, ""):
            try:
                return int(str(raw).strip())
            except ValueError:
                return default
    return default


@dataclass(frozen=True)
class Settings:
    app_name: str = "RCA Quality-Driven Knowledge Engineering Platform"
    app_version: str = "2.0.9.1-architecture-refactor"
    default_language: str = "EN"
    score_threshold: float = 80.0
    top_k: int = 5
    chunk_max_chars: int = 1800
    chunk_overlap_chars: int = 220
    api_base_url: str = "http://localhost:8000"
    api_timeout_seconds: int = 600
    monitor_refresh_ttl_seconds: int = 60
    project_root: Path = PROJECT_ROOT
    upload_dir: Path = PROJECT_ROOT / "upload_packages"
    uploaded_knowledge_dir: Path = PROJECT_ROOT / "uploaded_knowledge_packages"
    benchmark_runs_dir: Path = PROJECT_ROOT / "benchmark_runs"
    reports_dir: Path = PROJECT_ROOT / "reports"
    feedback_dir: Path = PROJECT_ROOT / "feedback"
    exports_dir: Path = PROJECT_ROOT / "exports"
    resources_dir: Path = PROJECT_ROOT / "resources"

    # SAP Cloud Integration connectivity
    sap_cpi_base_url: str = ""
    sap_cpi_api_prefix: str = "/api/v1"
    sap_cpi_token_url: str = ""
    sap_cpi_client_id: str = ""
    sap_cpi_client_secret: str = ""
    sap_cpi_timeout_seconds: int = 30
    sap_cpi_verify_ssl: bool = True
    sap_cpi_mpl_top: int = 100000
    sap_monitor_lookback_hours: int = 24
    sap_cpi_mpl_filter_field: str = "LogStart"
    sap_cpi_design_artifact_types: str = "*"
    sap_cpi_design_download_content: bool = False
    sap_live_snapshot_enabled: bool = True

    # CPIView local evidence integration (read-only local folder import)
    cpiview_enabled: bool = False
    cpiview_root: str = ""
    cpiview_tenant_id: str = ""
    cpiview_input_dir: str = ""
    cpiview_output_dir: str = ""

    # Native Python CPI evidence pipeline (Java/CPIView independent)
    cpi_native_enabled: bool = False
    cpi_native_tenant_id: str = ""
    cpi_native_input_dir: str = ""
    cpi_native_output_dir: str = ""
    cpi_native_download_content: bool = True
    cpi_native_max_records: int = 100000
    cpi_native_generate_excel: bool = True
    cpi_native_parallel_workers: int = 8
    cpi_native_download_children: bool = True

    # SAP PI/PO connectivity. PI/PO is SOAP-first in most 7.50 landscapes.
    sap_pipo_base_url: str = ""
    sap_pipo_username: str = ""
    sap_pipo_password: str = ""
    sap_pipo_timeout_seconds: int = 30
    sap_pipo_verify_ssl: bool = True
    sap_pipo_packages_endpoint: str = ""
    sap_pipo_iflows_endpoint: str = ""
    sap_pipo_mpl_endpoint: str = ""
    sap_pipo_mpl_top: int = 100000
    sap_pipo_monitor_lookback_hours: int = 24
    sap_pipo_inventory_mode: str = "soap"  # soap | json | skip
    sap_pipo_mpl_mode: str = "soap"  # soap | json
    pipo_mpl_wsdl_url: str = ""
    pipo_mpl_list_template: str = ""
    pipo_mpl_details_template: str = ""
    pipo_mpl_list_soap_action: str = ""
    pipo_mpl_details_soap_action: str = ""
    pipo_mpl_status: str = ""
    pipo_mpl_date_from: str = ""
    pipo_mpl_date_to: str = ""
    pipo_mpl_local_root: str = ""
    pipo_dir_services: str = ""
    pipo_demo_esr_tpz: str = ""
    pipo_demo_mpl_input: str = ""
    pipo_demo_knowledge_file: str = ""
    pipo_mpl_source_mode: str = "auto"  # auto | live | local
    pipo_mpl_use_local_on_live_error: bool = True
    pipo_mpl_debug_dump: bool = True
    pipo_mpl_use_wsdl_discovery: bool = True
    pipo_mpl_operation_name: str = "getMessageList"
    pipo_mpl_operation_namespace: str = ""
    pipo_mpl_namespace_candidates: str = (
        "urn:AdapterMessageMonitoringVi,http://sap.com/xi/XI/Message/30"
    )
    pipo_mpl_filter_namespace: str = "urn:com.sap.aii.mdt.server.adapterframework.ws"
    pipo_mpl_filter_date_type: str = "0"
    pipo_mpl_filter_archive: bool = False
    pipo_mpl_filter_node_id: int = 0
    pipo_mpl_filter_only_faulty_messages: bool = False
    pipo_mpl_filter_retries: int = 0
    pipo_mpl_filter_retry_interval: int = 0
    pipo_mpl_filter_times_failed: int = 0
    pipo_mpl_filter_was_edited: bool = False

    # AI assistance configuration. All providers are optional and must be non-blocking.
    ai_provider: str = "none"  # none | openai | anthropic | gemini | perplexity
    ai_model: str = ""  # optional model override; empty = provider default
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    gemini_api_key: str = ""
    perplexity_api_key: str = ""

    @staticmethod
    def from_env() -> Settings:
        return Settings(
            app_name=os.getenv("APP_NAME", "RCA Quality-Driven Knowledge Engineering Platform"),
            # Single source of truth: the application version is fixed in code and
            # is intentionally NOT read from the environment (see .env.example).
            app_version="2.0.9.1-architecture-refactor",
            default_language=os.getenv("DEFAULT_LANGUAGE", "EN"),
            score_threshold=float(os.getenv("SCORE_THRESHOLD", "80")),
            top_k=int(os.getenv("TOP_K", "5")),
            chunk_max_chars=int(os.getenv("CHUNK_MAX_CHARS", "1800")),
            chunk_overlap_chars=int(os.getenv("CHUNK_OVERLAP_CHARS", "220")),
            api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000"),
            api_timeout_seconds=int(os.getenv("API_TIMEOUT_SECONDS", "600")),
            monitor_refresh_ttl_seconds=int(os.getenv("MONITOR_REFRESH_TTL_SECONDS", "60")),
            sap_cpi_base_url=(
                os.getenv("SAP_CPI_BASE_URL", "").strip()
                or os.getenv("CPI_DEMO_BASE_URL", "").strip()
            ),
            sap_cpi_api_prefix=os.getenv("SAP_CPI_API_PREFIX", "/api/v1").strip() or "/api/v1",
            sap_cpi_token_url=(
                os.getenv("SAP_CPI_TOKEN_URL", "").strip()
                or os.getenv("CPI_DEMO_TOKEN_URL", "").strip()
            ),
            sap_cpi_client_id=(
                os.getenv("SAP_CPI_CLIENT_ID", "").strip()
                or os.getenv("CPI_DEMO_CLIENT_ID", "").strip()
            ),
            sap_cpi_client_secret=(
                os.getenv("SAP_CPI_CLIENT_SECRET", "").strip()
                or os.getenv("CPI_DEMO_CLIENT_SECRET", "").strip()
            ),
            sap_cpi_timeout_seconds=_int_env(
                "SAP_CPI_TIMEOUT_SECONDS", "CPI_DEMO_TIMEOUT", default=30
            ),
            sap_cpi_verify_ssl=_bool_env(
                "SAP_CPI_VERIFY_SSL", _bool_env("CPI_DEMO_VERIFY_SSL", True)
            ),
            sap_cpi_mpl_top=_int_env("SAP_CPI_MPL_TOP", "CPI_DEMO_ODATA_TOP", default=100000),
            sap_monitor_lookback_hours=int(os.getenv("SAP_MONITOR_LOOKBACK_HOURS", "24")),
            sap_cpi_mpl_filter_field=os.getenv("SAP_CPI_MPL_FILTER_FIELD", "LogStart").strip()
            or "LogStart",
            sap_cpi_design_artifact_types=os.getenv(
                "SAP_CPI_DESIGN_ARTIFACT_TYPES", os.getenv("CPI_DEMO_DESIGN_ARTIFACT_TYPES", "*")
            ).strip()
            or "*",
            sap_cpi_design_download_content=_bool_env(
                "SAP_CPI_DESIGN_DOWNLOAD_CONTENT",
                _bool_env("CPI_DEMO_DESIGN_DOWNLOAD_CONTENT", False),
            ),
            sap_live_snapshot_enabled=_bool_env("SAP_LIVE_SNAPSHOT_ENABLED", True),
            cpiview_enabled=_bool_env("CPIVIEW_ENABLED", False),
            cpiview_root=os.getenv("CPIVIEW_ROOT", "").strip(),
            cpiview_tenant_id=os.getenv("CPIVIEW_TENANT_ID", "").strip(),
            cpiview_input_dir=os.getenv("CPIVIEW_INPUT_DIR", "").strip(),
            cpiview_output_dir=os.getenv("CPIVIEW_OUTPUT_DIR", "").strip(),
            cpi_native_enabled=_bool_env("CPI_NATIVE_ENABLED", False),
            cpi_native_tenant_id=(
                os.getenv("CPI_NATIVE_TENANT_ID", "").strip()
                or os.getenv("CPIVIEW_TENANT_ID", "").strip()
            ),
            cpi_native_input_dir=os.getenv("CPI_NATIVE_INPUT_DIR", "").strip(),
            cpi_native_output_dir=os.getenv("CPI_NATIVE_OUTPUT_DIR", "").strip(),
            cpi_native_download_content=_bool_env(
                "CPI_NATIVE_DOWNLOAD_CONTENT", _bool_env("SAP_CPI_DESIGN_DOWNLOAD_CONTENT", True)
            ),
            cpi_native_max_records=_int_env(
                "CPI_NATIVE_MAX_RECORDS", "SAP_CPI_MPL_TOP", default=100000
            ),
            cpi_native_generate_excel=_bool_env("CPI_NATIVE_GENERATE_EXCEL", True),
            cpi_native_parallel_workers=_int_env("CPI_NATIVE_PARALLEL_WORKERS", default=8),
            cpi_native_download_children=_bool_env("CPI_NATIVE_DOWNLOAD_CHILDREN", True),
            sap_pipo_base_url=(
                os.getenv("SAP_PIPO_BASE_URL", "").strip()
                or os.getenv("PIPO_DEMO_DIR_BASE_URL", "").strip()
            ),
            sap_pipo_username=(
                os.getenv("SAP_PIPO_USERNAME", "").strip()
                or os.getenv("PIPO_MPL_USERNAME", "").strip()
                or os.getenv("PIPO_DEMO_DIR_USERNAME", "").strip()
            ),
            sap_pipo_password=(
                os.getenv("SAP_PIPO_PASSWORD", "").strip()
                or os.getenv("PIPO_MPL_PASSWORD", "").strip()
                or os.getenv("PIPO_DEMO_DIR_PASSWORD", "").strip()
            ),
            sap_pipo_timeout_seconds=_int_env(
                "SAP_PIPO_TIMEOUT_SECONDS", "PIPO_MPL_TIMEOUT", "PIPO_DEMO_DIR_TIMEOUT", default=30
            ),
            sap_pipo_verify_ssl=_bool_env(
                "SAP_PIPO_VERIFY_SSL", _bool_env("PIPO_MPL_VERIFY_SSL", True)
            ),
            sap_pipo_packages_endpoint=(
                os.getenv("SAP_PIPO_PACKAGES_ENDPOINT", "").strip()
                or os.getenv("PIPO_PACKAGES_ENDPOINT", "").strip()
            ),
            sap_pipo_iflows_endpoint=(
                os.getenv("SAP_PIPO_IFLOWS_ENDPOINT", "").strip()
                or os.getenv("PIPO_IFLOWS_ENDPOINT", "").strip()
            ),
            sap_pipo_mpl_endpoint=(
                os.getenv("SAP_PIPO_MPL_ENDPOINT", "").strip()
                or os.getenv("PIPO_MPL_ENDPOINT", "").strip()
            ),
            sap_pipo_mpl_top=_int_env("SAP_PIPO_MPL_TOP", "PIPO_MPL_MAX_MESSAGES", default=100000),
            sap_pipo_monitor_lookback_hours=int(os.getenv("SAP_PIPO_MONITOR_LOOKBACK_HOURS", "24")),
            sap_pipo_inventory_mode=os.getenv("SAP_PIPO_INVENTORY_MODE", "soap").strip() or "soap",
            sap_pipo_mpl_mode=os.getenv("SAP_PIPO_MPL_MODE", "soap").strip() or "soap",
            pipo_mpl_wsdl_url=(
                os.getenv("PIPO_MPL_WSDL_URL", "").strip()
                or os.getenv("SAP_PIPO_MPL_WSDL_URL", "").strip()
            ),
            pipo_mpl_list_template=os.getenv("PIPO_MPL_LIST_TEMPLATE", "").strip(),
            pipo_mpl_details_template=os.getenv("PIPO_MPL_DETAILS_TEMPLATE", "").strip(),
            pipo_mpl_list_soap_action=os.getenv("PIPO_MPL_LIST_SOAP_ACTION", "").strip(),
            pipo_mpl_details_soap_action=os.getenv("PIPO_MPL_DETAILS_SOAP_ACTION", "").strip(),
            pipo_mpl_status=os.getenv("PIPO_MPL_STATUS", "").strip(),
            pipo_mpl_date_from=os.getenv("PIPO_MPL_DATE_FROM", "").strip(),
            pipo_mpl_date_to=os.getenv("PIPO_MPL_DATE_TO", "").strip(),
            pipo_mpl_local_root=(
                os.getenv("PIPO_MPL_LOCAL_ROOT", "").strip()
                or os.getenv("PIPO_RAG_MPL_INPUT", "").strip()
            ),
            pipo_dir_services=(
                os.getenv("PIPO_DEMO_DIR_SERVICES", "").strip()
                or os.getenv("SAP_PIPO_DIR_SERVICES", "").strip()
            ),
            pipo_demo_esr_tpz=os.getenv("PIPO_DEMO_ESR_TPZ", "").strip(),
            pipo_demo_mpl_input=os.getenv("PIPO_DEMO_MPL_INPUT", "").strip(),
            pipo_demo_knowledge_file=os.getenv("PIPO_DEMO_KNOWLEDGE_FILE", "").strip(),
            pipo_mpl_source_mode=os.getenv("PIPO_MPL_SOURCE_MODE", "auto").strip().lower()
            or "auto",
            pipo_mpl_use_local_on_live_error=_bool_env("PIPO_MPL_USE_LOCAL_ON_LIVE_ERROR", True),
            pipo_mpl_debug_dump=_bool_env("PIPO_MPL_DEBUG_DUMP", True),
            pipo_mpl_use_wsdl_discovery=_bool_env("PIPO_MPL_USE_WSDL_DISCOVERY", True),
            pipo_mpl_operation_name=os.getenv("PIPO_MPL_OPERATION_NAME", "getMessageList").strip()
            or "getMessageList",
            pipo_mpl_operation_namespace=os.getenv("PIPO_MPL_OPERATION_NAMESPACE", "").strip(),
            pipo_mpl_namespace_candidates=os.getenv(
                "PIPO_MPL_NAMESPACE_CANDIDATES",
                "urn:AdapterMessageMonitoringVi,http://sap.com/xi/XI/Message/30",
            ).strip(),
            pipo_mpl_filter_namespace=os.getenv(
                "PIPO_MPL_FILTER_NAMESPACE", "urn:com.sap.aii.mdt.server.adapterframework.ws"
            ).strip()
            or "urn:com.sap.aii.mdt.server.adapterframework.ws",
            pipo_mpl_filter_date_type=os.getenv("PIPO_MPL_FILTER_DATE_TYPE", "0").strip() or "0",
            pipo_mpl_filter_archive=_bool_env("PIPO_MPL_FILTER_ARCHIVE", False),
            pipo_mpl_filter_node_id=_int_env("PIPO_MPL_FILTER_NODE_ID", default=0),
            pipo_mpl_filter_only_faulty_messages=_bool_env(
                "PIPO_MPL_FILTER_ONLY_FAULTY_MESSAGES", False
            ),
            pipo_mpl_filter_retries=_int_env("PIPO_MPL_FILTER_RETRIES", default=0),
            pipo_mpl_filter_retry_interval=_int_env("PIPO_MPL_FILTER_RETRY_INTERVAL", default=0),
            pipo_mpl_filter_times_failed=_int_env("PIPO_MPL_FILTER_TIMES_FAILED", default=0),
            pipo_mpl_filter_was_edited=_bool_env("PIPO_MPL_FILTER_WAS_EDITED", False),
            ai_provider=os.getenv("AI_PROVIDER", "none").strip().lower() or "none",
            ai_model=os.getenv("AI_MODEL", "").strip(),
            openai_api_key=os.getenv("OPENAI_API_KEY", "").strip(),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
            gemini_api_key=os.getenv("GEMINI_API_KEY", "").strip(),
            perplexity_api_key=os.getenv("PERPLEXITY_API_KEY", "").strip(),
        )

    @property
    def cpiview_root_path(self) -> Path:
        raw = self.cpiview_root.strip()
        return Path(raw) if raw else self.project_root / "resources" / "cpiview"

    @property
    def cpiview_input_dir_path(self) -> Path:
        if self.cpiview_input_dir.strip():
            return Path(self.cpiview_input_dir.strip())
        tenant = self.cpiview_tenant_id.strip() or "tenant"
        return self.cpiview_root_path / "input" / tenant

    @property
    def cpiview_output_dir_path(self) -> Path:
        if self.cpiview_output_dir.strip():
            return Path(self.cpiview_output_dir.strip())
        return self.cpiview_root_path / "output"

    @property
    def cpi_native_root_path(self) -> Path:
        raw = os.getenv("CPI_NATIVE_ROOT", "").strip()
        if raw:
            return Path(raw)
        return self.project_root / "resources" / "native"

    @property
    def cpi_native_input_dir_path(self) -> Path:
        tenant = self.cpi_native_tenant_id.strip() or self.cpiview_tenant_id.strip() or "tenant"
        raw = self.cpi_native_input_dir.strip()
        if raw:
            path = Path(raw)
            if not path.is_absolute():
                # Treat values such as "input" as relative to CPI_NATIVE_ROOT,
                # not to the shell working directory. This avoids silent writes
                # to ./input when operators expect resources/native/input/<tenant>.
                path = self.cpi_native_root_path / path
            if path.name.lower() == "input":
                return path / tenant
            return path
        return self.cpi_native_root_path / "input" / tenant

    @property
    def cpi_native_output_dir_path(self) -> Path:
        raw = self.cpi_native_output_dir.strip()
        if raw:
            path = Path(raw)
            if not path.is_absolute():
                path = self.cpi_native_root_path / path
            return path
        return self.cpi_native_root_path / "output"

    def ensure_directories(self) -> None:
        for directory in [
            self.upload_dir,
            self.uploaded_knowledge_dir,
            self.benchmark_runs_dir,
            self.reports_dir,
            self.feedback_dir,
            self.exports_dir,
            self.resources_dir,
            self.resources_dir / "mpl",
            self.resources_dir / "pipo" / "mpl",
            self.resources_dir / "cpi" / "input" / "odata" / "iflows",
            self.resources_dir / "cpi" / "input" / "analysis" / "iflows-bpmn",
            self.resources_dir / "pipo" / "esr_id",
            self.resources_dir / "pipo" / "ico",
            self.cpi_native_input_dir_path / "odata",
            self.cpi_native_input_dir_path / "analysis" / "iflows-bpmn",
            self.cpi_native_output_dir_path,
            self.exports_dir / "generated_documents",
        ]:
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def cpi_is_configured(self) -> bool:
        return all(
            [
                self.sap_cpi_base_url,
                self.sap_cpi_token_url,
                self.sap_cpi_client_id,
                self.sap_cpi_client_secret,
            ]
        )

    @property
    def pipo_is_configured(self) -> bool:
        return all(
            [
                self.sap_pipo_base_url,
                self.sap_pipo_username,
                self.sap_pipo_password,
            ]
        )

    @property
    def pipo_has_live_endpoints(self) -> bool:
        return any(
            [
                self.sap_pipo_packages_endpoint,
                self.sap_pipo_iflows_endpoint,
                self.sap_pipo_mpl_endpoint,
                self.pipo_dir_services,
            ]
        )


settings = Settings.from_env()
settings.ensure_directories()
