from __future__ import annotations

import json
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.evidence_mapper import EvidenceMapper


@dataclass(frozen=True)
class TraceabilityResult:
    status: str
    report_path: str
    artifact_count: int
    missing_count: int
    assumption_count: int
    source_backed_count: int
    derived_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "report_path": self.report_path,
            "artifact_count": self.artifact_count,
            "missing_count": self.missing_count,
            "assumption_count": self.assumption_count,
            "source_backed_count": self.source_backed_count,
            "derived_count": self.derived_count,
        }


class TraceabilityService:
    """Produces quality/traceability_report.json for a QDKEP package."""

    def __init__(self, evidence_mapper: EvidenceMapper | None = None) -> None:
        self.evidence_mapper = evidence_mapper or EvidenceMapper()

    def evaluate_to_file(
        self, package_path: str | Path, output_json: str | Path | None = None
    ) -> TraceabilityResult:
        source = Path(package_path)
        if source.is_file() and source.suffix.lower() == ".zip":
            with tempfile.TemporaryDirectory(prefix="qdkep_traceability_eval_") as tmp:
                with zipfile.ZipFile(source) as zf:
                    zf.extractall(tmp)
                root = self._detect_root(Path(tmp))
                report = self._build_report(root)
                target = (
                    Path(output_json)
                    if output_json
                    else source.with_suffix("") / "quality" / "traceability_report.json"
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(
                    json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
                )
                counts = report["evidence_status_counts"]
                return TraceabilityResult(
                    report["status"],
                    str(target),
                    report["artifact_count"],
                    counts["missing"],
                    counts["assumption"],
                    counts["source-backed"],
                    counts["derived"],
                )
        root = source
        report = self._build_report(root)
        target = Path(output_json) if output_json else root / "quality" / "traceability_report.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._stamp_manifest_and_metadata(root, report)
        counts = report["evidence_status_counts"]
        return TraceabilityResult(
            report["status"],
            self._relative(target, root),
            report["artifact_count"],
            counts["missing"],
            counts["assumption"],
            counts["source-backed"],
            counts["derived"],
        )

    def _build_report(self, package_root: Path) -> dict[str, Any]:
        mapping = self.evidence_mapper.map_package(package_root)
        return {
            "report_schema_version": "qdkep_traceability_report_v1",
            "generated_at": self._now(),
            "status": mapping.status,
            "policy": {
                "runtime_value_policy": "Do not fabricate MessageGuid, endpoint, adapter, MPL status, timestamps, or runtime payload values. Mark absent runtime evidence as missing.",
                "allowed_evidence_statuses": ["source-backed", "derived", "missing", "assumption"],
            },
            "artifact_count": mapping.artifact_count,
            "evidence_status_counts": mapping.to_dict()["evidence_status_counts"],
            "source_map": mapping.source_map,
            "traceability_matrix": mapping.mappings,
        }

    def _stamp_manifest_and_metadata(self, package_root: Path, report: dict[str, Any]) -> None:
        for name in ["manifest.json", "package_metadata.json"]:
            path = package_root / name
            if not path.exists():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            data["traceability_report"] = "quality/traceability_report.json"
            data["traceability_status"] = report.get("status")
            data["traceability_counts"] = report.get("evidence_status_counts", {})
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _detect_root(self, extracted: Path) -> Path:
        if (extracted / "manifest.json").exists():
            return extracted
        candidates = [
            path
            for path in extracted.iterdir()
            if path.is_dir() and (path / "manifest.json").exists()
        ]
        return candidates[0] if candidates else extracted

    def _relative(self, path: Path, root: Path) -> str:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return str(path)

    def _now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
