from __future__ import annotations

import json
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class DashboardArtifact:
    key: str
    label: str
    relative_path: str
    exists: bool
    size_bytes: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "relative_path": self.relative_path,
            "exists": self.exists,
            "size_bytes": self.size_bytes,
        }


class DashboardSummaryService:
    """Read-only Enterprise QA summary for QDKEP dashboard.

    This service does not reimplement validation, package building, quality gate,
    AI4BIZ export, traceability, or benchmark logic. It only reads the artifacts
    produced by the existing services and converts them into a UI/API-friendly
    review model.
    """

    WORKFLOW_FILES: dict[str, str] = {
        "contract_validation": "quality/contract_validation_report.json",
        "package_quality_gate": "quality/package_quality_gate_report.json",
        "ai4biz_export_readiness": "quality/ai4biz_ingestion_readiness_report.json",
        "traceability": "quality/traceability_report.json",
        "benchmark_readiness": "quality/benchmark_readiness_report.json",
        "golden_questions_generation": "quality/golden_questions_generation_report.json",
    }

    DOWNLOAD_FILES: dict[str, tuple[str, str]] = {
        "zip": ("Package ZIP", ""),
        "manifest": ("manifest.json", "manifest.json"),
        "package_metadata": ("package_metadata.json", "package_metadata.json"),
        "contract_validation_report": (
            "contract_validation_report.json",
            "quality/contract_validation_report.json",
        ),
        "package_quality_gate_report": (
            "package_quality_gate_report.json",
            "quality/package_quality_gate_report.json",
        ),
        "ai4biz_ingestion_readiness_report": (
            "ai4biz_ingestion_readiness_report.json",
            "quality/ai4biz_ingestion_readiness_report.json",
        ),
        "traceability_report": ("traceability_report.json", "quality/traceability_report.json"),
        "benchmark_readiness_report": (
            "benchmark_readiness_report.json",
            "quality/benchmark_readiness_report.json",
        ),
        "golden_questions": (
            "golden_questions.jsonl",
            "resources/golden_datasets/golden_questions.jsonl",
        ),
    }

    def summarize(self, package_path: str | Path) -> dict[str, Any]:
        source = Path(package_path)
        if not source.exists():
            return {
                "status": "error",
                "package_path": str(source),
                "issues": [{"severity": "error", "message": f"Path not found: {source}"}],
                "warnings": [],
                "metrics": {},
                "promotion_decision": "unknown",
                "workflow": {},
                "downloads": [],
            }

        if source.is_file() and source.suffix.lower() == ".zip":
            with tempfile.TemporaryDirectory(prefix="qdkep_dashboard_") as tmp:
                root = self._extract_zip(source, Path(tmp))
                summary = self._summarize_root(root, source)
                summary["package_path"] = str(source)
                return summary
        return self._summarize_root(source, source)

    def _extract_zip(self, source: Path, tmp_dir: Path) -> Path:
        r"""Extract a QDKEP ZIP and normalize Windows-style member paths.

        Some historical packages were built on Windows and contain backslashes in
        ZIP member names. Python's ZipFile treats those as literal filename
        characters on Linux, so reports such as quality\traceability_report.json
        would be invisible to the dashboard. Normalizing here keeps old packages
        reviewable without changing the package contents.
        """
        with zipfile.ZipFile(source) as zf:
            for member in zf.infolist():
                normalized_name = member.filename.replace("\\", "/").lstrip("/")
                if not normalized_name or ".." in Path(normalized_name).parts:
                    continue
                target = tmp_dir / normalized_name
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, target.open("wb") as dst:
                    dst.write(src.read())
        root_markers = ["manifest.json", "package_metadata.json", "upload_manifest.json", "quality"]
        if any((tmp_dir / marker).exists() for marker in root_markers):
            return tmp_dir
        children = [p for p in tmp_dir.iterdir() if p.is_dir()]
        if len(children) == 1 and any((children[0] / marker).exists() for marker in root_markers):
            return children[0]
        return tmp_dir

    def _summarize_root(self, root: Path, original_source: Path) -> dict[str, Any]:
        reports = {name: self._read_json(root / rel) for name, rel in self.WORKFLOW_FILES.items()}
        manifest = self._read_json(root / "manifest.json")
        package_metadata = self._read_json(root / "package_metadata.json")
        upload_manifest = self._read_json(root / "upload_manifest.json") or self._read_json(
            root / "exports/ai4biz_rag_console_payload_v1.4/upload_manifest.json"
        )

        issues: list[dict[str, Any]] = []
        warnings: list[str] = []
        workflow: dict[str, Any] = {}
        for name, rel in self.WORKFLOW_FILES.items():
            report = reports.get(name) or {}
            report_path = root / rel
            state = self._workflow_state(name, report, report_path.exists())
            workflow[name] = state
            issues.extend(self._collect_issues(name, report))
            warnings.extend(self._collect_warnings(name, report, report_path.exists()))

        promotion_decision = self._promotion_decision(manifest, package_metadata, reports)
        blockers = [
            issue for issue in issues if issue.get("severity") in {"critical", "error", "blocking"}
        ]
        status = "blocked" if blockers else "review_ready"

        metrics = self._metrics(root, reports, manifest, package_metadata, upload_manifest)
        downloads = self._downloads(root, original_source)

        return {
            "status": status,
            "package_path": str(original_source),
            "package_root": str(root),
            "promotion_decision": promotion_decision,
            "metrics": metrics,
            "workflow": workflow,
            "issues": blockers,
            "warnings": warnings,
            "downloads": [item.to_dict() for item in downloads],
        }

    def _workflow_state(self, name: str, report: dict[str, Any], exists: bool) -> dict[str, Any]:
        if not exists:
            return {
                "status": "missing",
                "summary": "Report not found",
                "source": self.WORKFLOW_FILES[name],
            }
        status = str(
            report.get("status")
            or report.get("validation_status")
            or report.get("readiness_status")
            or "available"
        )
        return {
            "status": status,
            "summary": self._short_summary(report),
            "source": self.WORKFLOW_FILES[name],
        }

    def _short_summary(self, report: dict[str, Any]) -> str:
        if not report:
            return "No report data available"
        for key in ["promotion_decision", "status", "validation_status", "readiness_status"]:
            if report.get(key):
                return f"{key}={report[key]}"
        return "Report available"

    def _metrics(
        self,
        root: Path,
        reports: dict[str, dict[str, Any]],
        manifest: dict[str, Any],
        package_metadata: dict[str, Any],
        upload_manifest: dict[str, Any],
    ) -> dict[str, Any]:
        golden_questions = root / "resources/golden_datasets/golden_questions.jsonl"
        metadata_files = (
            list((root / "metadata").glob("*.metadata.json"))
            if (root / "metadata").exists()
            else []
        )
        documents = list((root / "documents").glob("**/*")) if (root / "documents").exists() else []
        documents = [p for p in documents if p.is_file()]
        trace = reports.get("traceability", {})
        bench = reports.get("benchmark_readiness", {})
        # All *_count metrics are coerced to int (never None). The dashboard
        # renders these in a single Arrow-backed table column; a mix of int and
        # None/"N/A" makes PyArrow infer int64 and then fail on the string
        # sentinel ("Could not convert 'N/A' with type str"). Returning 0 for a
        # missing count keeps the column homogeneously integer and Arrow-safe.
        artifact_count = self._first_number(
            [manifest, package_metadata, reports.get("contract_validation", {})],
            ["artifact_count", "total_artifacts"],
        )
        document_count = self._first_number(
            [upload_manifest, reports.get("ai4biz_export_readiness", {})],
            ["document_count", "documents"],
        )
        metadata_file_count = self._first_number(
            [reports.get("ai4biz_export_readiness", {})], ["metadata_file_count"]
        )
        return {
            "artifact_count": artifact_count if artifact_count is not None else 0,
            "document_count": document_count if document_count is not None else len(documents),
            "metadata_file_count": metadata_file_count
            if metadata_file_count is not None
            else len(metadata_files),
            "golden_question_count": self._count_lines(golden_questions),
            "traceability_status": trace.get("status", "unknown"),
            "traceability_counts": trace.get("evidence_status_counts")
            or trace.get("traceability_counts")
            or {},
            "static_package_readiness": self._nested_status(bench, "static_package_readiness"),
            "retrieval_readiness": self._nested_status(bench, "retrieval_readiness"),
            "answer_readiness": self._nested_status(bench, "answer_readiness"),
        }

    def _first_number(self, containers: list[dict[str, Any]], keys: list[str]) -> int | None:
        for container in containers:
            for key in keys:
                value = container.get(key) if isinstance(container, dict) else None
                if isinstance(value, int):
                    return value
                if isinstance(value, str) and value.isdigit():
                    return int(value)
        return None

    def _nested_status(self, report: dict[str, Any], key: str) -> str:
        value = report.get(key) if isinstance(report, dict) else None
        if isinstance(value, dict):
            return str(value.get("status", "unknown"))
        return "unknown"

    def _promotion_decision(
        self,
        manifest: dict[str, Any],
        package_metadata: dict[str, Any],
        reports: dict[str, dict[str, Any]],
    ) -> str:
        for container in [
            manifest,
            package_metadata,
            reports.get("package_quality_gate", {}),
            reports.get("contract_validation", {}),
        ]:
            value = container.get("promotion_decision") if isinstance(container, dict) else None
            if value:
                return str(value)
        return "unknown"

    def _downloads(self, root: Path, original_source: Path) -> list[DashboardArtifact]:
        items: list[DashboardArtifact] = []
        for key, (label, rel) in self.DOWNLOAD_FILES.items():
            if (
                key == "zip"
                and original_source.is_file()
                and original_source.suffix.lower() == ".zip"
            ):
                items.append(
                    DashboardArtifact(
                        key, label, str(original_source), True, original_source.stat().st_size
                    )
                )
                continue
            if key == "zip":
                items.append(DashboardArtifact(key, label, str(original_source), False, None))
                continue
            candidate = root / rel
            items.append(
                DashboardArtifact(
                    key,
                    label,
                    rel,
                    candidate.exists(),
                    candidate.stat().st_size if candidate.exists() else None,
                )
            )
        return items

    def _collect_issues(self, workflow_name: str, report: dict[str, Any]) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        if not isinstance(report, dict):
            return issues
        for key in ["issues", "blocking_issues", "blocking_reasons"]:
            raw = report.get(key)
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict):
                        issues.append({"workflow": workflow_name, **item})
                    else:
                        issues.append(
                            {
                                "workflow": workflow_name,
                                "severity": "blocking",
                                "message": str(item),
                            }
                        )
        return issues

    def _collect_warnings(
        self, workflow_name: str, report: dict[str, Any], exists: bool
    ) -> list[str]:
        warnings: list[str] = []
        if not exists:
            warnings.append(f"{workflow_name}: report is missing")
            return warnings
        raw = report.get("warnings") if isinstance(report, dict) else None
        if isinstance(raw, list):
            warnings.extend(str(item) for item in raw)
        # v2.0.5 policy: retrieval_readiness and answer_readiness require
        # target AI4BIZ/RAG index and answer traces. Missing traces in this
        # source platform are expected, so they must not pollute the dashboard
        # warning panel. The benchmark report still keeps the raw evidence.
        return warnings

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}
        return {}

    def _count_lines(self, path: Path) -> int:
        try:
            if path.exists():
                return sum(
                    1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
                )
        except Exception:
            return 0
        return 0
