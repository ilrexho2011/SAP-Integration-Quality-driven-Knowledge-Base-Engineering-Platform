from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class WorkflowResponse:
    """Unified response model for QDKEP CLI and API operator workflows."""

    status: str
    output_path: str | None = None
    issues: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    command: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "output_path": self.output_path,
            "issues": self.issues,
            "warnings": self.warnings,
            "command": self.command,
            "data": self.data,
        }


def issue_count_from_result(result: dict[str, Any]) -> list[dict[str, Any]]:
    issues = result.get("issues", [])
    if isinstance(issues, list):
        return [item for item in issues if isinstance(item, dict)]
    return []


def rel_or_abs(path: Path, base: Path | None = None) -> str:
    if base:
        try:
            return path.relative_to(base).as_posix()
        except ValueError:
            pass
    return str(path)
