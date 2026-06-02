from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.contracts import CONTRACT_VERSION, FilenameValidator, MetadataNormalizer
from app.services.artifact_router import RoutedArtifact


class ManifestService:
    """Creates and persists manifest.json for contract-compliant packages."""

    def __init__(self) -> None:
        self.metadata_normalizer = MetadataNormalizer()
        self.filename_validator = FilenameValidator()

    def build_manifest(
        self,
        artifacts: list[RoutedArtifact],
        package_id: str,
        package_version: str,
        package_name: str,
    ) -> dict[str, Any]:
        return {
            "manifest_version": "1.0",
            "contract_version": CONTRACT_VERSION,
            "package_id": package_id,
            "package_name": package_name,
            "package_version": package_version,
            "generated_at": self._now(),
            "layout": {
                "root_files": ["manifest.json", "package_metadata.json"],
                "knowledge_roots": ["knowledge/RB", "knowledge/KB", "knowledge/DOC"],
                "quality_root": "quality",
            },
            "artifacts": [self._artifact_entry(artifact) for artifact in artifacts],
        }

    def write_manifest(self, manifest: dict[str, Any], package_root: Path) -> Path:
        path = package_root / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def _artifact_entry(self, artifact: RoutedArtifact) -> dict[str, Any]:
        source_text = artifact.source_path.read_text(encoding="utf-8", errors="replace")
        metadata = self.metadata_normalizer.normalize_markdown(source_text).metadata
        filename_result = self.filename_validator.validate(
            Path(artifact.package_relative_path).name
        )
        entry: dict[str, Any] = {
            "filename": artifact.package_relative_path,
            "artifact_type": artifact.artifact_kind,
            "artifact_type_prefix": artifact.artifact_type_prefix,
            "sha256": self._sha256(artifact.source_path),
            "bytes": artifact.source_path.stat().st_size,
            "metadata": dict(metadata),
            "source_path": str(artifact.source_path),
        }
        if filename_result.valid:
            entry["filename_contract"] = filename_result.to_dict()
        if artifact.issues:
            entry["routing_issues"] = list(artifact.issues)
        return entry

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
