from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.contracts.filename_validator import FilenameValidator


@dataclass(frozen=True)
class RoutedArtifact:
    source_path: Path
    package_relative_path: str
    artifact_type_prefix: str
    artifact_kind: str
    valid_filename: bool
    issues: tuple[str, ...]

    def to_manifest_seed(self) -> dict:
        return {
            "source_path": str(self.source_path),
            "filename": self.package_relative_path,
            "artifact_type_prefix": self.artifact_type_prefix,
            "artifact_kind": self.artifact_kind,
            "valid_filename": self.valid_filename,
            "issues": list(self.issues),
        }


class ArtifactRouter:
    """Routes Markdown knowledge artifacts into the contract ZIP layout.

    The router is intentionally deterministic: one Markdown file becomes one
    knowledge artifact under knowledge/RB, knowledge/KB or knowledge/DOC.
    """

    PREFIX_TO_KIND = {"RB": "runbook", "KB": "kedb", "DOC": "documentation"}

    def __init__(self, filename_validator: FilenameValidator | None = None) -> None:
        self.filename_validator = filename_validator or FilenameValidator()

    def route_file(self, path: Path) -> RoutedArtifact:
        result = self.filename_validator.validate(path.name)
        prefix = result.artifact_type_prefix or self._infer_prefix(path)
        kind = self.PREFIX_TO_KIND.get(prefix, "documentation")
        return RoutedArtifact(
            source_path=path,
            package_relative_path=f"knowledge/{prefix}/{path.name}",
            artifact_type_prefix=prefix,
            artifact_kind=kind,
            valid_filename=result.valid,
            issues=tuple(result.issues),
        )

    def route_many(self, source_root: Path) -> list[RoutedArtifact]:
        if not source_root.exists():
            raise FileNotFoundError(f"Source root not found: {source_root}")
        if source_root.is_file():
            candidates = [source_root] if source_root.suffix.lower() == ".md" else []
        else:
            candidates = sorted(
                path
                for path in source_root.rglob("*.md")
                if not self._is_package_control_file(path)
                and not path.name.lower().endswith("_template.md")
            )
        return [self.route_file(path) for path in candidates]

    def _infer_prefix(self, path: Path) -> str:
        upper_parts = {part.upper() for part in path.parts}
        stem = path.stem.upper()
        if "RB" in upper_parts or "RUNBOOK" in stem:
            return "RB"
        if "KB" in upper_parts or "KEDB" in stem:
            return "KB"
        return "DOC"

    def _is_package_control_file(self, path: Path) -> bool:
        control_names = {"README.md", "PROJECT_STRUCTURE.md"}
        if path.name in control_names:
            return True
        normalized = path.as_posix()
        return any(part in normalized for part in ["/.venv/", "/.git/", "/docs/contracts/"])
