from __future__ import annotations

import json
import tempfile
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.contracts import CONTRACT_VERSION, ContractPackageValidator
from app.contracts.customer_context_validator import CustomerContextValidator
from app.contracts.interface_inventory_validator import InterfaceInventoryValidator


@dataclass(frozen=True)
class PackageQualityGateResult:
    status: str
    promotion_decision: str
    report_path: str
    issues_count: int
    high_or_critical_issues_count: int

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class PackageQualityGate:
    """Runs all deterministic promotion checks and stamps package metadata."""

    APPROVED_DECISION = "approved_for_ai4biz_ingestion"
    BLOCKED_DECISION = "blocked"

    def __init__(self) -> None:
        self.contract_validator = ContractPackageValidator()
        self.customer_validator = CustomerContextValidator()
        self.interface_validator = InterfaceInventoryValidator()

    def evaluate_to_file(
        self, package_root: str | Path, output_json: str | Path | None = None
    ) -> PackageQualityGateResult:
        source = Path(package_root)
        output = Path(output_json) if output_json else self._default_output(source)

        with self._prepared_package_root(source) as root:
            report = self.evaluate(root, package_display_path=source)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )

            # Only mutate manifest/metadata when the original package is an extracted folder.
            # For ZIP input we keep the archive immutable and write the report externally.
            if source.is_dir():
                self._stamp_manifest_and_metadata(
                    source, report, self._safe_relative(output, source)
                )

        report_path = self._safe_relative(output, source if source.is_dir() else output.parent)
        return PackageQualityGateResult(
            status=report["status"],
            promotion_decision=report["promotion_decision"],
            report_path=report_path,
            issues_count=report["summary"]["issues_count"],
            high_or_critical_issues_count=report["summary"]["high_or_critical_issues_count"],
        )

    def evaluate(
        self, package_root: str | Path, package_display_path: str | Path | None = None
    ) -> dict[str, Any]:
        root = Path(package_root)
        display_path = Path(package_display_path) if package_display_path is not None else root
        manifest = self._load_json(root / "manifest.json")
        contract_report = self.contract_validator.validate(root).to_dict()
        customer_report = self.customer_validator.validate(root, manifest).to_dict()
        interface_report = self.interface_validator.validate(root, manifest).to_dict()
        issues = self._flatten_issues(contract_report, customer_report, interface_report)
        high_or_critical = [
            issue for issue in issues if issue.get("severity") in {"critical", "high"}
        ]
        approved = not high_or_critical and contract_report.get("status") == "approved"
        return {
            "report_type": "package_quality_gate_report",
            "contract_version": CONTRACT_VERSION,
            "generated_at": self._now(),
            "package_path": str(display_path),
            "status": "approved" if approved else "blocked",
            "promotion_decision": self.APPROVED_DECISION if approved else self.BLOCKED_DECISION,
            "quality_gates": {
                "contract_validation": contract_report,
                "customer_context_validation": customer_report,
                "interface_inventory_validation": interface_report,
            },
            "summary": {
                "artifact_count": contract_report.get("artifact_count", 0),
                "issues_count": len(issues),
                "high_or_critical_issues_count": len(high_or_critical),
                "required_customers": customer_report.get("required_customers", []),
                "required_interface_ids": interface_report.get("required_interface_ids", []),
            },
        }

    def _flatten_issues(self, *reports: dict[str, Any]) -> list[dict[str, Any]]:
        issues: list[dict[str, Any]] = []
        for report in reports:
            for issue in report.get("issues", []):
                if isinstance(issue, dict):
                    issues.append(issue)
        return issues

    def _default_output(self, source: Path) -> Path:
        if source.is_dir():
            return source / "quality" / "package_quality_gate_report.json"
        return (
            source.parent
            / f"{source.stem}_operator_outputs"
            / "quality"
            / "package_quality_gate_report.json"
        )

    @contextmanager
    def _prepared_package_root(self, source: Path):
        if source.is_dir():
            yield source
            return
        if source.is_file() and source.suffix.lower() == ".zip":
            with tempfile.TemporaryDirectory(prefix="qdkep_quality_gate_") as tmp:
                temp_root = Path(tmp)
                self._extract_zip_safe(source, temp_root)
                yield self._detect_root(temp_root)
            return
        yield source

    def _extract_zip_safe(self, archive: Path, target: Path) -> None:
        target_resolved = target.resolve()
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                member_path = target / member.filename
                resolved = member_path.resolve()
                if target_resolved not in resolved.parents and resolved != target_resolved:
                    raise ValueError(f"Unsafe path in ZIP archive: {member.filename}")
            zf.extractall(target)

    def _detect_root(self, folder: Path) -> Path:
        if (folder / "manifest.json").exists() or (folder / "knowledge").exists():
            return folder
        children = [child for child in folder.iterdir() if child.is_dir()]
        if len(children) == 1:
            return children[0]
        return folder

    def _safe_relative(self, path: Path, root: Path) -> str:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()

    def _stamp_manifest_and_metadata(
        self, root: Path, report: dict[str, Any], report_rel: str
    ) -> None:
        for name in ("manifest.json", "package_metadata.json"):
            path = root / name
            if not path.exists():
                continue
            data = self._load_json(path)
            data["promotion_decision"] = report["promotion_decision"]
            data["quality_gate_status"] = report["status"]
            data["quality_gate_report"] = report_rel
            data["quality_gate_evaluated_at"] = report["generated_at"]
            if name == "package_metadata.json":
                data["quality_report"] = report_rel
                data["promotion_policy"] = {
                    "required_status": "approved",
                    "decision": self.APPROVED_DECISION,
                    "blocking_issue_severities": ["critical", "high"],
                }
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
