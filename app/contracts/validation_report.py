from __future__ import annotations

import json
import tempfile
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.contracts.constants import CONTRACT_SOURCE_EN, CONTRACT_SOURCE_SQ, CONTRACT_VERSION
from app.contracts.filename_validator import FilenameValidator
from app.contracts.metadata_normalizer import MetadataNormalizer
from app.contracts.structure_validators import (
    DocBasicStructureValidator,
    KedbBasicStructureValidator,
    RunbookSacredHeadingsValidator,
)


@dataclass(frozen=True)
class ContractIssue:
    artifact: str
    category: str
    severity: str
    message: str
    recommendation: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class ContractValidationReport:
    package_path: str
    contract_version: str = CONTRACT_VERSION
    generated_at: str = field(
        default_factory=lambda: (
            datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
    )
    status: str = "approved"
    promotion_decision: str = "approved_for_ai4biz_ingestion"
    artifact_count: int = 0
    checked_files: list[str] = field(default_factory=list)
    issues: list[ContractIssue] = field(default_factory=list)
    contract_sources: dict[str, str] = field(
        default_factory=lambda: {"en": CONTRACT_SOURCE_EN, "sq": CONTRACT_SOURCE_SQ}
    )

    def add_issue(
        self, artifact: str, category: str, severity: str, message: str, recommendation: str
    ) -> None:
        self.issues.append(ContractIssue(artifact, category, severity, message, recommendation))
        if severity in {"critical", "high"}:
            self.status = "needs_remediation"
            self.promotion_decision = "blocked"

    def to_dict(self) -> dict:
        return {
            "package_path": self.package_path,
            "contract_version": self.contract_version,
            "generated_at": self.generated_at,
            "status": self.status,
            "promotion_decision": self.promotion_decision,
            "artifact_count": self.artifact_count,
            "checked_files": self.checked_files,
            "issues": [issue.to_dict() for issue in self.issues],
            "contract_sources": self.contract_sources,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


class ContractPackageValidator:
    def __init__(self) -> None:
        self.filename_validator = FilenameValidator()
        self.metadata_normalizer = MetadataNormalizer()
        self.runbook_validator = RunbookSacredHeadingsValidator()
        self.kedb_validator = KedbBasicStructureValidator()
        self.doc_validator = DocBasicStructureValidator()

    def validate(self, package_path: str | Path) -> ContractValidationReport:
        source = Path(package_path)
        report = ContractValidationReport(package_path=str(source))
        if not source.exists():
            report.add_issue(
                str(source),
                "package",
                "critical",
                "Package path does not exist",
                "Provide an existing ZIP or folder",
            )
            return report
        if source.is_file() and source.suffix.lower() == ".zip":
            with tempfile.TemporaryDirectory() as tmp:
                with zipfile.ZipFile(source) as zf:
                    zf.extractall(tmp)
                root = self._detect_root(Path(tmp))
                self._validate_folder(root, report)
        elif source.is_dir():
            self._validate_folder(source, report)
        else:
            report.add_issue(
                str(source),
                "package",
                "critical",
                "Package must be a ZIP or folder",
                "Provide a .zip package or extracted package folder",
            )
        return report

    def validate_to_file(
        self, package_path: str | Path, output_json: str | Path
    ) -> ContractValidationReport:
        report = self.validate(package_path)
        out = Path(output_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report.to_json() + "\n", encoding="utf-8")
        return report

    def _detect_root(self, folder: Path) -> Path:
        children = [child for child in folder.iterdir() if child.is_dir()]
        if len(children) == 1 and not (folder / "manifest.json").exists():
            return children[0]
        return folder

    def _validate_folder(self, root: Path, report: ContractValidationReport) -> None:
        required_root_files = ["manifest.json", "package_metadata.json"]
        for name in required_root_files:
            if not (root / name).exists():
                report.add_issue(
                    name,
                    "structural_contract",
                    "high",
                    f"{name} is mandatory",
                    f"Generate {name} in the ZIP root",
                )
        markdown_files = (
            sorted((root / "knowledge").glob("*/*.md")) if (root / "knowledge").exists() else []
        )
        report.artifact_count = len(markdown_files)
        if not markdown_files:
            report.add_issue(
                "knowledge/",
                "structural_contract",
                "high",
                "No Markdown artifacts found under knowledge/RB, knowledge/KB or knowledge/DOC",
                "Generate one atomic Markdown file per knowledge artifact",
            )
        for md in markdown_files:
            rel = md.relative_to(root).as_posix()
            report.checked_files.append(rel)
            self._validate_markdown_artifact(root, md, rel, report)
        self._validate_manifest_consistency(root, report)

    def _validate_markdown_artifact(
        self, root: Path, path: Path, rel: str, report: ContractValidationReport
    ) -> None:
        text = path.read_text(encoding="utf-8", errors="replace")
        folder_issues = self.filename_validator.validate_path_folder_alignment(rel)
        if folder_issues:
            for issue in folder_issues:
                report.add_issue(
                    rel,
                    "filename_contract",
                    "high",
                    issue,
                    "Rename/move the artifact according to knowledge/<TYPE>/<TYPE>_<CUSTOMER>_<SYSTEM>_<OBJECT>_<PRIORITY>_<VERSION>.md",
                )
        filename_result = self.filename_validator.validate(path.name)
        if not filename_result.valid:
            return
        metadata_result = self.metadata_normalizer.normalize_markdown(text)
        for key in metadata_result.missing_required:
            report.add_issue(
                rel,
                "metadata_contract",
                "high",
                f"Mandatory metadata field is missing: {key}",
                f"Add {key} in the stable metadata block",
            )
        for issue in metadata_result.order_issues:
            report.add_issue(
                rel,
                "metadata_contract",
                "medium",
                issue,
                "Render metadata using MetadataNormalizer.render_block",
            )
        if filename_result.object_code and metadata_result.metadata.get("object_name"):
            object_name = metadata_result.metadata.get("object_name", "")
            allowed_object_names = {filename_result.object_code}
            if filename_result.system:
                allowed_object_names.add(f"{filename_result.system}_{filename_result.object_code}")
            if object_name not in allowed_object_names:
                report.add_issue(
                    rel,
                    "metadata_manifest_consistency",
                    "high",
                    "object_name metadata does not match filename object code",
                    "Align object_name with the filename ERROR_CODE_OR_OBJECT_CODE, optionally prefixed by SYSTEM_",
                )
        if (
            filename_result.priority
            and metadata_result.metadata.get("priority")
            and metadata_result.metadata.get("priority") != filename_result.priority
        ):
            report.add_issue(
                rel,
                "metadata_manifest_consistency",
                "high",
                "priority metadata does not match filename priority",
                "Align priority with the filename priority",
            )
        if (
            filename_result.version
            and metadata_result.metadata.get("version")
            and metadata_result.metadata.get("version") != filename_result.version
        ):
            report.add_issue(
                rel,
                "metadata_manifest_consistency",
                "high",
                "version metadata does not match filename version",
                "Align version with the filename version",
            )
        if filename_result.artifact_type_prefix == "RB":
            self._apply_structure_result(rel, self.runbook_validator.validate(text), report)
        elif filename_result.artifact_type_prefix == "KB":
            self._apply_structure_result(rel, self.kedb_validator.validate(text), report)
        elif filename_result.artifact_type_prefix == "DOC":
            self._apply_structure_result(rel, self.doc_validator.validate(text), report)

    def _apply_structure_result(
        self, rel: str, result: Any, report: ContractValidationReport
    ) -> None:
        for heading in result.missing_headings:
            report.add_issue(
                rel,
                f"{result.artifact_kind}_structure_contract",
                "high",
                f"Required heading is missing or renamed: {heading}",
                f"Regenerate the artifact with exact heading {heading}",
            )
        for block in result.missing_blocks:
            report.add_issue(
                rel,
                f"{result.artifact_kind}_structure_contract",
                "medium",
                f"Required block is missing: {block}",
                f"Add stable block {block}",
            )
        for hint in result.renamed_or_extra_heading_hints:
            report.add_issue(
                rel,
                f"{result.artifact_kind}_heading_contract",
                "high",
                hint,
                "Use the exact contract heading sequence",
            )

    def _validate_manifest_consistency(self, root: Path, report: ContractValidationReport) -> None:
        manifest_path = root / "manifest.json"
        if not manifest_path.exists():
            return
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            report.add_issue(
                "manifest.json",
                "manifest_contract",
                "critical",
                f"Invalid JSON: {exc}",
                "Regenerate manifest.json as valid JSON",
            )
            return
        artifacts = manifest.get("artifacts", [])
        if not isinstance(artifacts, list):
            report.add_issue(
                "manifest.json",
                "manifest_contract",
                "high",
                "manifest.artifacts must be a list",
                "Regenerate manifest artifacts array",
            )
            return
        manifest_files: set[str] = {
            item["filename"]
            for item in artifacts
            if isinstance(item, dict) and isinstance(item.get("filename"), str)
        }
        checked = set(report.checked_files)
        missing_in_manifest = checked - manifest_files
        stale_in_manifest = manifest_files - checked
        for rel in sorted(missing_in_manifest):
            report.add_issue(
                rel,
                "manifest_contract",
                "high",
                "Artifact is missing from manifest.json",
                "Add artifact entry with relative filename and metadata",
            )
        for rel in sorted(stale_in_manifest):
            report.add_issue(
                "manifest.json",
                "manifest_contract",
                "medium",
                f"Manifest references missing artifact: {rel}",
                "Remove stale manifest entry or generate the referenced artifact",
            )
