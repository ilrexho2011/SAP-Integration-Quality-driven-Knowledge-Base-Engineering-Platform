from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.feedback_generator import FeedbackGenerator


class FeedbackService:
    """Create and expose corrective feedback artifacts for controlled regeneration."""

    def list_feedback(self) -> dict[str, Any]:
        settings.feedback_dir.mkdir(parents=True, exist_ok=True)
        items: list[dict[str, Any]] = []
        for path in sorted(
            settings.feedback_dir.glob("*_feedback.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            payload = self._read_json(path)
            items.append(
                {
                    "filename": path.name,
                    "path": str(path),
                    "created_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(
                        timespec="seconds"
                    ),
                    "package_id": payload.get("package_id", "unknown")
                    if isinstance(payload, dict)
                    else "unknown",
                    "overall_score": payload.get("overall_score")
                    if isinstance(payload, dict)
                    else None,
                    "status": payload.get("status", "unknown")
                    if isinstance(payload, dict)
                    else "unknown",
                    "documents_needing_remediation": payload.get("documents_needing_remediation", 0)
                    if isinstance(payload, dict)
                    else 0,
                    "disqualified_documents": payload.get("disqualified_documents", 0)
                    if isinstance(payload, dict)
                    else 0,
                }
            )
        return {"feedback": items, "count": len(items), "latest": items[0] if items else None}

    def read_feedback(self, filename: str | None = None, path: str | None = None) -> dict[str, Any]:
        target = self._resolve_feedback_path(filename=filename, path=path)
        payload = self._read_json(target)
        return {"filename": target.name, "path": str(target), "payload": payload}

    def create_feedback(
        self,
        package_id: str,
        benchmark_report_path: str | None = None,
        output_filename: str | None = None,
    ) -> dict[str, Any]:
        settings.feedback_dir.mkdir(parents=True, exist_ok=True)
        benchmark_path = Path(
            benchmark_report_path
            or settings.project_root / "quality" / "benchmark_readiness_report.json"
        )
        benchmark_payload = self._read_json(benchmark_path) if benchmark_path.exists() else {}

        # Support both the legacy FeedbackGenerator inputs and the newer static benchmark report shape.
        policy_result = self._policy_result_from_benchmark(benchmark_payload)
        retrieval_result = benchmark_payload.get("retrieval_result") or {
            "summary": benchmark_payload.get("retrieval_summary", {})
        }
        final_score = benchmark_payload.get("final_score")
        if final_score is None:
            final_score = benchmark_payload.get("overall_score") or 0.0
        status = str(
            benchmark_payload.get("status")
            or benchmark_payload.get("static_package_readiness", {}).get("status")
            or "feedback_generated_from_available_benchmark_evidence"
        )
        feedback = FeedbackGenerator().generate(
            package_id, policy_result, retrieval_result, float(final_score or 0.0), status
        )
        feedback["created_at"] = datetime.now().isoformat(timespec="seconds")
        feedback["source_benchmark_report"] = str(benchmark_path)
        feedback["generation_notes"] = [
            "Corrective feedback is advisory and must be applied only through controlled regeneration after user approval.",
            "If the source benchmark has no per-document checks, this artifact preserves package-level readiness context.",
        ]

        filename = (
            output_filename or f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_feedback.json"
        )
        if not filename.endswith("_feedback.json"):
            filename = filename.replace(".json", "") + "_feedback.json"
        output_path = settings.feedback_dir / Path(filename).name
        output_path.write_text(json.dumps(feedback, indent=2, ensure_ascii=False), encoding="utf-8")
        return {"output_path": str(output_path), "feedback": feedback}

    def latest_feedback_path(self) -> str | None:
        listing = self.list_feedback().get("feedback", [])
        return str(listing[0]["path"]) if listing else None

    def _resolve_feedback_path(self, filename: str | None = None, path: str | None = None) -> Path:
        if path:
            target = Path(path)
        elif filename:
            target = settings.feedback_dir / Path(filename).name
        else:
            latest = self.latest_feedback_path()
            if not latest:
                raise FileNotFoundError("No feedback artifacts found.")
            target = Path(latest)
        if not target.exists() or not target.is_file():
            raise FileNotFoundError(f"Feedback file not found: {target}")
        return target

    def _read_json(self, path: Path) -> dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return payload if isinstance(payload, dict) else {}
        except Exception:
            return {}

    def _policy_result_from_benchmark(self, benchmark_payload: dict[str, Any]) -> dict[str, Any]:
        if isinstance(benchmark_payload.get("policy_result"), dict):
            return benchmark_payload["policy_result"]
        if isinstance(benchmark_payload.get("documents"), list):
            return {"documents": benchmark_payload["documents"]}
        # Static package readiness reports may not contain document-level checks.
        return {"documents": []}
