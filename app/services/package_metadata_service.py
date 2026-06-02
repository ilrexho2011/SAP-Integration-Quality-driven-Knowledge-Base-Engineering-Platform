from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.contracts import CONTRACT_VERSION
from app.services.artifact_router import RoutedArtifact


class PackageMetadataService:
    """Creates package_metadata.json for traceability and lifecycle control."""

    def build_metadata(
        self,
        artifacts: list[RoutedArtifact],
        package_id: str,
        package_version: str,
        package_name: str,
        source_root: Path,
    ) -> dict[str, Any]:
        counts = {"RB": 0, "KB": 0, "DOC": 0}
        for artifact in artifacts:
            counts[artifact.artifact_type_prefix] = counts.get(artifact.artifact_type_prefix, 0) + 1
        return {
            "package_id": package_id,
            "package_name": package_name,
            "package_version": package_version,
            "contract_version": CONTRACT_VERSION,
            "created_at": self._now(),
            "source_root": str(source_root),
            "artifact_count": len(artifacts),
            "artifact_counts_by_type": counts,
            "quality_report": "quality/contract_validation_report.json",
            "promotion_policy": {
                "required_status": "approved",
                "decision": "approved_for_ai4biz_ingestion",
            },
        }

    def write_metadata(self, metadata: dict[str, Any], package_root: Path) -> Path:
        path = package_root / "package_metadata.json"
        path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def _now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
