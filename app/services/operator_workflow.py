from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.contracts import ContractPackageValidator
from app.services.ai4biz_export_adapter import AI4BIZExportAdapter
from app.services.benchmark_orchestrator import BenchmarkOrchestrator
from app.services.functional_knowledge_generation import FunctionalKnowledgeGenerationService
from app.services.dashboard_summary import DashboardSummaryService
from app.services.golden_question_generator import GoldenQuestionGenerator
from app.services.package_builder import PackageBuilder
from app.services.package_quality_gate import PackageQualityGate
from app.services.workflow_response import WorkflowResponse, issue_count_from_result


class OperatorWorkflowService:
    """Developer/AMS operational facade shared by CLI and API.

    Every method returns the same response contract: status, output_path,
    issues, warnings, command and data. This keeps CLI and API behavior aligned.
    """

    def validate_contract(
        self, package_path: str | Path, output_json: str | Path | None = None
    ) -> WorkflowResponse:
        package = Path(package_path)
        output = (
            Path(output_json)
            if output_json
            else self._default_output(package, "quality/contract_validation_report.json")
        )
        report = ContractPackageValidator().validate_to_file(package, output)
        data = report.to_dict()
        return WorkflowResponse(
            command="validate-contract",
            status=data.get("status", "unknown"),
            output_path=str(output),
            issues=issue_count_from_result(data),
            warnings=self._warnings_from_status(data.get("status")),
            data=data,
        )

    def build_package(
        self,
        source_root: str | Path,
        output_zip: str | Path,
        package_id: str = "quality-driven-knowledge-engineering-platform",
        package_version: str = "1.9",
        package_name: str = "Quality-Driven Knowledge Engineering Platform",
    ) -> WorkflowResponse:
        result = PackageBuilder().build(
            source_root=Path(source_root),
            output_zip=Path(output_zip),
            package_id=package_id,
            package_version=package_version,
            package_name=package_name,
        )
        data = result.to_dict()
        status = "success" if data.get("status") == "built" else data.get("status", "unknown")
        warnings = (
            []
            if data.get("promotion_decision") == "approved_for_ai4biz_ingestion"
            else ["Package is built but not approved for AI4BIZ ingestion."]
        )
        return WorkflowResponse(
            command="build-package",
            status=status,
            output_path=data.get("output_zip"),
            warnings=warnings,
            data=data,
        )

    def quality_gate(
        self, package_path: str | Path, output_json: str | Path | None = None
    ) -> WorkflowResponse:
        package = Path(package_path)
        output = (
            Path(output_json)
            if output_json
            else self._default_output(package, "quality/package_quality_gate_report.json")
        )
        result = PackageQualityGate().evaluate_to_file(package, output)
        data = result.to_dict()
        status = data.get("status", "unknown")
        issues = self._load_report_issues(output)
        return WorkflowResponse(
            command="quality-gate",
            status=status,
            output_path=str(output),
            issues=issues,
            warnings=self._warnings_from_status(status),
            data=data,
        )

    def export_ai4biz(
        self, package_path: str | Path, output_root: str | Path | None = None
    ) -> WorkflowResponse:
        package = Path(package_path)
        output = (
            Path(output_root)
            if output_root
            else self._default_output(package, "exports/ai4biz_rag_console_payload")
        )
        result = AI4BIZExportAdapter().export(package, output)
        data = result.to_dict()
        warnings = (
            []
            if data.get("status") == "ready"
            else [
                "AI4BIZ export is blocked; inspect readiness report for missing critical metadata."
            ]
        )
        report_path = output / data.get(
            "readiness_report", "quality/ai4biz_ingestion_readiness_report.json"
        )
        return WorkflowResponse(
            command="export-ai4biz",
            status=data.get("status", "unknown"),
            output_path=str(report_path),
            warnings=warnings,
            data=data,
        )

    def generate_runbooks(
        self, source_package: str | Path, output_root: str | Path
    ) -> WorkflowResponse:
        return self._generate_subset("generate-runbooks", source_package, output_root, "runbooks")

    def generate_kedb(
        self, source_package: str | Path, output_root: str | Path
    ) -> WorkflowResponse:
        return self._generate_subset("generate-kedb", source_package, output_root, "kedb")

    def generate_docs(
        self, source_package: str | Path, output_root: str | Path
    ) -> WorkflowResponse:
        return self._generate_subset("generate-docs", source_package, output_root, "documentation")

    def benchmark_package(
        self,
        package_path: str | Path,
        benchmark_profile: str = "default",
        ai4biz_retrieval_trace: str | Path | None = None,
        answer_trace: str | Path | None = None,
        golden_questions_jsonl: str | Path | None = None,
    ) -> WorkflowResponse:
        package = Path(package_path)
        gq_result = (
            GoldenQuestionGenerator()
            .generate(package, Path(golden_questions_jsonl) if golden_questions_jsonl else None)
            .to_dict()
        )
        bench = BenchmarkOrchestrator().run(
            package,
            benchmark_profile=benchmark_profile,
            ai4biz_retrieval_trace=Path(ai4biz_retrieval_trace) if ai4biz_retrieval_trace else None,
            answer_trace=Path(answer_trace) if answer_trace else None,
        )
        warnings = []
        if bench.get("retrieval_readiness", {}).get("status") == "not_evaluated":
            warnings.append(
                "retrieval_readiness is not scored because AI4BIZ retrieval traces are missing."
            )
        if bench.get("answer_readiness", {}).get("status") == "not_evaluated":
            warnings.append("answer_readiness is not scored because answer traces are missing.")
        data = {"golden_questions": gq_result, "benchmark": bench}
        return WorkflowResponse(
            command="benchmark-package",
            status="completed",
            output_path=str(bench.get("report_path") or "quality/benchmark_readiness_report.json"),
            warnings=warnings,
            data=data,
        )

    def dashboard_summary(self, package_path: str | Path) -> WorkflowResponse:
        data = DashboardSummaryService().summarize(package_path)
        return WorkflowResponse(
            command="dashboard-summary",
            status=data.get("status", "unknown"),
            output_path=str(package_path),
            issues=list(data.get("issues", [])),
            warnings=list(data.get("warnings", [])),
            data=data,
        )

    def _generate_subset(
        self, command: str, source_package: str | Path, output_root: str | Path, subset: str
    ) -> WorkflowResponse:
        output = Path(output_root)
        result = FunctionalKnowledgeGenerationService().generate(Path(source_package), output)
        data = result.to_dict()
        subset_path = output / subset
        count_key = {
            "runbooks": "runbook_count",
            "kedb": "kedb_count",
            "documentation": "documentation_count",
        }[subset]
        return WorkflowResponse(
            command=command,
            status=data.get("status", "unknown"),
            output_path=str(subset_path),
            warnings=[
                "Functional generator writes the complete RB/KB/DOC evidence set so validators and traceability remain consistent."
            ],
            data={**data, "selected_output": subset, "selected_count": data.get(count_key, 0)},
        )

    def _default_output(self, package: Path, relative: str) -> Path:
        if package.is_dir():
            return package / relative
        base = package.parent / f"{package.stem}_operator_outputs"
        return base / relative

    def _warnings_from_status(self, status: Any) -> list[str]:
        return (
            []
            if status in {"approved", "success", "ready", "generated"}
            else ["Workflow completed with non-approved status; inspect issues for remediation."]
        )

    def _load_report_issues(self, output: Path) -> list[dict[str, Any]]:
        try:
            data = json.loads(output.read_text(encoding="utf-8"))
        except Exception:
            return []
        if isinstance(data.get("issues"), list):
            return [issue for issue in data["issues"] if isinstance(issue, dict)]
        issues: list[dict[str, Any]] = []
        for gate in (
            data.get("quality_gates", {}).values()
            if isinstance(data.get("quality_gates"), dict)
            else []
        ):
            for issue in gate.get("issues", []) if isinstance(gate, dict) else []:
                if isinstance(issue, dict):
                    issues.append(issue)
        return issues
