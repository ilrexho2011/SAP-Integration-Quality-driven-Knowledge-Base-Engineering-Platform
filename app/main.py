from __future__ import annotations

import shutil
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from app.config import settings
from app.contracts import CONTRACT_VERSION
from app.services.ai_assistance_service import AIAssistanceService
from app.services.feedback_service import FeedbackService
from app.services.generation_service import GenerationService
from app.services.iflow_scenario_service import IflowScenarioService
from app.services.cpiview_evidence_service import CPIViewEvidenceService
from app.services.cpi_native_evidence_service import NativeCPIEvidenceService
from app.services.monitor_service import MonitorService
from app.services.operator_workflow import OperatorWorkflowService
from app.services.scenario_lab_config import (
    normalize_archived_mpl_source,
    normalize_generation_mode,
    normalize_source_system,
)

app = FastAPI(title=settings.app_name, version=settings.app_version)
workflow = OperatorWorkflowService()


class WorkflowResponseModel(BaseModel):
    status: str
    output_path: str | None = None
    issues: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    command: str | None = None
    data: dict = Field(default_factory=dict)


class ContractValidationRequest(BaseModel):
    package_path: str = Field(
        ..., description="Path to a QDKEP ZIP package or extracted package folder"
    )
    output_json: str | None = Field(
        None, description="Optional path for contract_validation_report.json"
    )


class BuildPackageRequest(BaseModel):
    source_root: str = Field(
        ..., description="Folder or Markdown file containing source knowledge artifacts"
    )
    output_zip: str = Field(..., description="Target ZIP path")
    package_id: str = "quality-driven-knowledge-engineering-platform"
    package_version: str = "1.9"
    package_name: str = "Quality-Driven Knowledge Engineering Platform"


class PackageQualityGateRequest(BaseModel):
    package_path: str = Field(..., description="Path to an extracted QDKEP package folder")
    output_json: str | None = Field(
        None, description="Optional path for package_quality_gate_report.json"
    )


class AI4BIZExportRequest(BaseModel):
    package_path: str = Field(
        ..., description="Path to an approved extracted QDKEP package folder or ZIP package"
    )
    output_root: str | None = Field(
        None, description="Optional output folder for AI4BIZ RAG Console payloads"
    )


class FunctionalKnowledgeGenerationRequest(BaseModel):
    source_package: str = Field(..., description="Path to a v1.5+ QDKEP ZIP/package folder")
    output_root: str = Field(
        ..., description="Folder where generated RB/KB/DOC artifacts will be written"
    )


class BenchmarkRunRequest(BaseModel):
    package_path: str
    benchmark_profile: str = "default"
    ai4biz_retrieval_trace: str | None = None
    answer_trace: str | None = None
    golden_questions_jsonl: str | None = None


class DashboardReviewRequest(BaseModel):
    package_path: str = Field(
        ..., description="Path to a QDKEP ZIP package or extracted package folder"
    )


class NativeCPIDownloadRequest(BaseModel):
    download_content: bool | None = Field(
        None, description="Download CPI iFlow $value ZIP content and parse .iflw files"
    )
    max_iflows: int | None = Field(None, description="Optional limit for DEV/testing")


class ScenarioLabRunRequest(BaseModel):
    zip_dir: str | None = Field(None, description="Folder containing SAP CPI iFlow ZIP exports")
    bpmn_dir: str | None = Field(None, description="Folder containing analyzed .iflw BPMN files")
    source_system: Literal["sap_ci", "sap_pipo"] = "sap_ci"
    scenario_lab_run_id: str | None = Field(
        None, description="Optional stable run id; defaults to timestamp"
    )
    collect_mpl_evidence: bool = True
    max_iflows: int | None = Field(None, description="Optional limit for preview/testing")


class GenerateDocumentsRequest(BaseModel):
    version: str = Field(..., description="Generation version, for example v1")
    source_system: Literal["sap_ci", "sap_pipo"] = "sap_ci"
    source_mode: Literal["live_mpl", "archived_mpl"] = "archived_mpl"
    generation_mode: Literal["generate", "update_existing_docs"] = "generate"
    existing_documents_path: str | None = Field(
        None, description="Required when generation_mode=update_existing_docs"
    )
    feedback_source: Literal["none", "latest", "selected"] = "none"
    feedback_path: str | None = Field(
        None, description="Optional feedback JSON file used when feedback_source=selected"
    )
    apply_remediation_hints: bool = False
    scenario_lab_run_id: str | None = Field(
        None, description="Optional Scenario Lab run id used for scenario-backed generation"
    )
    scenario_manifest_path: str | None = Field(
        None, description="Optional path to scenario_manifest.json"
    )
    iflow_analysis_report_path: str | None = Field(
        None, description="Optional path to iflow_analysis_report.json"
    )
    archived_mpl_source: str | None = Field(
        "all_sources", description="Archived MPL source key selected from Scenario Lab defaults"
    )
    prevent_duplicate_doc_id: bool = Field(
        False, description="Backward-compatible alias for prevent_duplicate_id"
    )
    prevent_duplicate_id: bool = Field(
        False,
        description="When true, matching DOC/KEDB/RUNBOOK signatures skip existing duplicates instead of creating duplicates",
    )
    restart_kedb_id_counting: bool = Field(
        False, description="When true, KEDB IDs restart from KEDB-Px-0001"
    )
    restart_runbook_id_counting: bool = Field(
        False, description="When true, Runbook IDs restart from RB-Px-0001"
    )
    customer_id: str = Field(
        "RCMO", description="Customer ID used in generated metadata and filenames (multi-customer)"
    )
    environment: str = Field(
        "demo", description="Environment label: demo | development | quality | production | sandbox"
    )


class CreateFeedbackRequest(BaseModel):
    package_id: str = "quality-driven-knowledge-engineering-platform"
    benchmark_report_path: str | None = None
    output_filename: str | None = None


def _ensure_exists(path: str | Path) -> Path:
    candidate = Path(path)
    if not candidate.exists():
        raise HTTPException(status_code=404, detail=f"Path not found: {candidate}")
    return candidate


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "version": settings.app_version,
        "default_language": settings.default_language,
        "cpi_configured": settings.cpi_is_configured,
        "pipo_configured": settings.pipo_is_configured,
        "ai_assistance": AIAssistanceService().describe(),
        "contract_version": CONTRACT_VERSION,
        "operator_response_model": [
            "status",
            "output_path",
            "issues",
            "warnings",
            "command",
            "data",
        ],
    }


@app.get("/api/monitor/summary")
def monitor_summary(
    system: str = Query("sap_ci", description="sap_ci or sap_pipo"),
    time_range: str = Query(
        "past_24_hours", description="past_hour, past_24_hours, past_week, past_month, custom"
    ),
    date_from: str | None = Query(None, description="Custom range start timestamp"),
    date_to: str | None = Query(None, description="Custom range end timestamp"),
    display_field: str = Query("last_updated", description="last_updated or log_start"),
) -> dict:
    return MonitorService().get_summary(
        system=system,
        time_range=time_range,
        date_from=date_from,
        date_to=date_to,
        display_field=display_field,
    )


@app.get("/api/monitor/inventory")
def monitor_inventory(
    system: str = Query("sap_ci", description="sap_ci or sap_pipo"),
    inventory_type: str = Query("all", description="all, objects, interfaces"),
) -> dict:
    data = MonitorService().get_inventory(system=system, inventory_type=inventory_type)
    return {
        "status": "success",
        "output_path": None,
        "issues": [],
        "warnings": [],
        "command": "monitor-inventory",
        "data": data,
    }


@app.get("/api/monitor/messages")
def monitor_messages(
    system: str = Query("sap_ci", description="sap_ci or sap_pipo"),
    status: str = Query("COMPLETED", description="COMPLETED or FAILED"),
    time_range: str = Query(
        "past_24_hours", description="past_hour, past_24_hours, past_week, past_month, custom"
    ),
    date_from: str | None = Query(None, description="Custom range start timestamp"),
    date_to: str | None = Query(None, description="Custom range end timestamp"),
    display_field: str = Query("last_updated", description="last_updated or log_start"),
) -> dict:
    data = MonitorService().get_messages(
        system=system,
        status=status,
        time_range=time_range,
        date_from=date_from,
        date_to=date_to,
        display_field=display_field,
    )
    return {
        "status": "success",
        "output_path": None,
        "issues": [],
        "warnings": [],
        "command": "monitor-messages",
        "data": data,
    }


@app.get("/api/feedback/list")
def list_feedback() -> dict:
    data = FeedbackService().list_feedback()
    return {
        "status": "success",
        "output_path": None,
        "issues": [],
        "warnings": [],
        "command": "feedback-list",
        "data": data,
    }


@app.get("/api/feedback/read")
def read_feedback(filename: str | None = Query(None), path: str | None = Query(None)) -> dict:
    try:
        data = FeedbackService().read_feedback(filename=filename, path=path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "status": "success",
        "output_path": data.get("path"),
        "issues": [],
        "warnings": [],
        "command": "feedback-read",
        "data": data,
    }


@app.post("/api/feedback/create")
def create_feedback(request: CreateFeedbackRequest) -> dict:
    data = FeedbackService().create_feedback(
        package_id=request.package_id,
        benchmark_report_path=request.benchmark_report_path,
        output_filename=request.output_filename,
    )
    return {
        "status": "generated",
        "output_path": data.get("output_path"),
        "issues": [],
        "warnings": [],
        "command": "feedback-create",
        "data": data,
    }


@app.post("/api/monitor/export-local-mpl")
def export_local_mpl() -> dict:
    output_zip = MonitorService().export_latest_local_mpl_zip()
    return {
        "status": "exported",
        "output_path": str(output_zip),
        "issues": [],
        "warnings": [],
        "command": "export-local-mpl",
        "data": {"output_zip": str(output_zip)},
    }


@app.post("/api/packages/upload")
async def upload_package(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    if not file.filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Only .zip knowledge packages are supported")
    target = settings.uploaded_knowledge_dir / file.filename
    with target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    return {
        "status": "uploaded",
        "output_path": str(target),
        "issues": [],
        "warnings": [],
        "command": "upload-package",
        "data": {"filename": file.filename},
    }


@app.post("/api/contracts/validate-package", response_model=WorkflowResponseModel)
def validate_contract_package(request: ContractValidationRequest) -> dict:
    _ensure_exists(request.package_path)
    return workflow.validate_contract(request.package_path, request.output_json).to_dict()


@app.post("/api/packages/build-package", response_model=WorkflowResponseModel)
def build_contract_package(request: BuildPackageRequest) -> dict:
    _ensure_exists(request.source_root)
    try:
        return workflow.build_package(
            request.source_root,
            request.output_zip,
            request.package_id,
            request.package_version,
            request.package_name,
        ).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/packages/package-quality-gate", response_model=WorkflowResponseModel)
def package_quality_gate(request: PackageQualityGateRequest) -> dict:
    _ensure_exists(request.package_path)
    return workflow.quality_gate(request.package_path, request.output_json).to_dict()


@app.post("/api/packages/export-ai4biz-ingestion", response_model=WorkflowResponseModel)
def export_ai4biz_ingestion(request: AI4BIZExportRequest) -> dict:
    _ensure_exists(request.package_path)
    return workflow.export_ai4biz(request.package_path, request.output_root).to_dict()


@app.post("/api/packages/generate-runbooks", response_model=WorkflowResponseModel)
def generate_runbooks(request: FunctionalKnowledgeGenerationRequest) -> dict:
    _ensure_exists(request.source_package)
    return workflow.generate_runbooks(request.source_package, request.output_root).to_dict()


@app.post("/api/packages/generate-kedb", response_model=WorkflowResponseModel)
def generate_kedb(request: FunctionalKnowledgeGenerationRequest) -> dict:
    _ensure_exists(request.source_package)
    return workflow.generate_kedb(request.source_package, request.output_root).to_dict()


@app.post("/api/packages/generate-docs", response_model=WorkflowResponseModel)
def generate_docs(request: FunctionalKnowledgeGenerationRequest) -> dict:
    _ensure_exists(request.source_package)
    return workflow.generate_docs(request.source_package, request.output_root).to_dict()


@app.post("/api/packages/generate-functional-knowledge", response_model=WorkflowResponseModel)
def generate_functional_knowledge(request: FunctionalKnowledgeGenerationRequest) -> dict:
    _ensure_exists(request.source_package)
    # Backward-compatible endpoint: docs command returns the unified response while the service still writes full RB/KB/DOC set.
    return workflow.generate_docs(request.source_package, request.output_root).to_dict()


@app.post("/api/dashboard/enterprise-review", response_model=WorkflowResponseModel)
def dashboard_enterprise_review(request: DashboardReviewRequest) -> dict:
    _ensure_exists(request.package_path)
    return workflow.dashboard_summary(request.package_path).to_dict()


@app.post("/api/dashboard/enterprise-quality-console", response_model=WorkflowResponseModel)
def dashboard_enterprise_quality_console(request: DashboardReviewRequest) -> dict:
    _ensure_exists(request.package_path)
    return workflow.dashboard_summary(request.package_path).to_dict()


@app.post("/api/benchmark/run", response_model=WorkflowResponseModel)
def run_benchmark(request: BenchmarkRunRequest) -> dict:
    _ensure_exists(request.package_path)
    return workflow.benchmark_package(
        request.package_path,
        benchmark_profile=request.benchmark_profile,
        ai4biz_retrieval_trace=request.ai4biz_retrieval_trace,
        answer_trace=request.answer_trace,
        golden_questions_jsonl=request.golden_questions_jsonl,
    ).to_dict()


@app.post("/api/benchmark/generate-golden-questions", response_model=WorkflowResponseModel)
def generate_golden_questions(request: BenchmarkRunRequest) -> dict:
    _ensure_exists(request.package_path)
    return workflow.benchmark_package(
        request.package_path,
        benchmark_profile=request.benchmark_profile,
        golden_questions_jsonl=request.golden_questions_jsonl,
    ).to_dict()


@app.get("/api/scenario-lab/defaults")
def scenario_lab_defaults(source_system: Literal["sap_ci", "sap_pipo"] = Query("sap_ci")) -> dict:
    data = IflowScenarioService().describe_defaults(normalize_source_system(source_system))
    return {
        "status": "success",
        "output_path": None,
        "issues": [],
        "warnings": [],
        "command": "scenario-lab-defaults",
        "data": data,
    }


@app.post("/api/scenario-lab/upload-iflow-zip")
async def upload_iflow_zip(file: UploadFile = File(...)) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")
    try:
        data = IflowScenarioService().save_uploaded_zip(file.filename, await file.read())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": "uploaded",
        "output_path": data.get("path"),
        "issues": [],
        "warnings": [],
        "command": "scenario-lab-upload-iflow-zip",
        "data": data,
    }


@app.post("/api/scenario-lab/import-cpiview")
def import_cpiview_evidence() -> dict:
    data = CPIViewEvidenceService().import_to_resources()
    status = "success" if data.get("status") == "ok" else "skipped"
    warnings = (
        []
        if data.get("status") == "ok"
        else [str(data.get("reason", "CPIView evidence is not available."))]
    )
    return {
        "status": status,
        "output_path": data.get("rich_inventory"),
        "issues": [],
        "warnings": warnings,
        "command": "scenario-lab-import-cpiview",
        "data": data,
    }


@app.post("/api/scenario-lab/download-native-cpi")
def download_native_cpi_evidence(request: NativeCPIDownloadRequest) -> dict:
    data = NativeCPIEvidenceService().download_and_analyze(
        download_content=request.download_content,
        max_iflows=request.max_iflows,
    )
    status = "success" if data.get("status") in {"ok", "partial_ok"} else "skipped"
    warnings = (
        []
        if data.get("status") == "ok"
        else [
            str(
                data.get("reason")
                or data.get("component_errors")
                or "Native CPI download completed with warnings."
            )
        ]
    )
    return {
        "status": status,
        "output_path": data.get("rich_inventory"),
        "issues": [],
        "warnings": warnings,
        "command": "scenario-lab-download-native-cpi",
        "data": data,
    }


@app.post("/api/scenario-lab/run")
def run_scenario_lab(request: ScenarioLabRunRequest) -> dict:
    try:
        data = IflowScenarioService().run(
            zip_dir=request.zip_dir,
            bpmn_dir=request.bpmn_dir,
            source_system=request.source_system,
            scenario_lab_run_id=request.scenario_lab_run_id,
            collect_mpl_evidence=request.collect_mpl_evidence,
            max_iflows=request.max_iflows,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": data.get("status", "generated"),
        "output_path": data.get("output_dir"),
        "issues": [],
        "warnings": []
        if data.get("status") == "generated"
        else ["No iFlow ZIP/BPMN evidence was found."],
        "command": "scenario-lab-run",
        "data": data,
    }


@app.post("/api/monitoring-generation/generate/{document_type}")
def generate_monitoring_documents(
    document_type: Literal["catalog_docs", "kedb", "runbooks"], request: GenerateDocumentsRequest
) -> dict:
    version = request.version.strip()
    if not version:
        raise HTTPException(
            status_code=400, detail="Generation version is required, for example: v1"
        )
    try:
        data = GenerationService().generate(
            document_type=document_type,
            version=version,
            source_system=request.source_system,
            source_mode=request.source_mode,
            generation_mode=normalize_generation_mode(request.generation_mode),
            existing_documents_path=request.existing_documents_path,
            feedback_source=request.feedback_source,
            feedback_path=request.feedback_path,
            apply_remediation_hints=request.apply_remediation_hints,
            scenario_lab_run_id=request.scenario_lab_run_id,
            scenario_manifest_path=request.scenario_manifest_path,
            iflow_analysis_report_path=request.iflow_analysis_report_path,
            archived_mpl_source=normalize_archived_mpl_source(
                request.source_system, request.archived_mpl_source
            ),
            prevent_duplicate_doc_id=request.prevent_duplicate_doc_id,
            prevent_duplicate_id=request.prevent_duplicate_id,
            restart_kedb_id_counting=request.restart_kedb_id_counting,
            restart_runbook_id_counting=request.restart_runbook_id_counting,
            customer_id=request.customer_id,
            environment=request.environment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": data.get("status", "generated"),
        "output_path": data.get("output_dir"),
        "issues": [],
        "warnings": []
        if data.get("status") == "generated"
        else ["No eligible MPL/inventory evidence was found."],
        "command": f"monitoring-generation-{document_type}",
        "data": data,
    }


@app.post("/api/generate/{document_type}")
def legacy_generate_documents(
    document_type: Literal["catalog_docs", "kedb", "runbooks"], request: GenerateDocumentsRequest
) -> dict:
    version = request.version.strip()
    if not version:
        raise HTTPException(
            status_code=400, detail="Generation version is required, for example: v1"
        )
    try:
        data = GenerationService().generate(
            document_type=document_type,
            version=version,
            source_system=request.source_system,
            source_mode=request.source_mode,
            generation_mode=normalize_generation_mode(request.generation_mode),
            existing_documents_path=request.existing_documents_path,
            feedback_source=request.feedback_source,
            feedback_path=request.feedback_path,
            apply_remediation_hints=request.apply_remediation_hints,
            scenario_lab_run_id=request.scenario_lab_run_id,
            scenario_manifest_path=request.scenario_manifest_path,
            iflow_analysis_report_path=request.iflow_analysis_report_path,
            archived_mpl_source=normalize_archived_mpl_source(
                request.source_system, request.archived_mpl_source
            ),
            prevent_duplicate_doc_id=request.prevent_duplicate_doc_id,
            prevent_duplicate_id=request.prevent_duplicate_id,
            restart_kedb_id_counting=request.restart_kedb_id_counting,
            restart_runbook_id_counting=request.restart_runbook_id_counting,
            customer_id=request.customer_id,
            environment=request.environment,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "status": data.get("status", "generated"),
        "output_path": data.get("output_dir"),
        "issues": [],
        "warnings": [
            "Legacy endpoint; prefer /api/packages/generate-runbooks, generate-kedb or generate-docs."
        ],
        "command": f"legacy-generate-{document_type}",
        "data": data,
    }
