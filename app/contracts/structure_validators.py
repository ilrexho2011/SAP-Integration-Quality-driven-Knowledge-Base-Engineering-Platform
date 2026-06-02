from __future__ import annotations

import re
from dataclasses import dataclass
from collections.abc import Iterable

from app.contracts.constants import (
    DOC_REQUIRED_BLOCKS,
    DOC_REQUIRED_HEADINGS,
    KEDB_REQUIRED_BLOCKS,
    KEDB_REQUIRED_HEADINGS,
    RUNBOOK_REQUIRED_HEADINGS,
    RUNBOOK_SACRED_HEADINGS,
)

NUMBERED_HEADING_RE = re.compile(
    r"^(?P<num>\d+)\.\s+(?P<title>[A-Z][A-Z0-9 /&-]+)\s*$", re.MULTILINE
)


@dataclass(frozen=True)
class StructureValidationResult:
    valid: bool
    artifact_kind: str
    missing_headings: tuple[str, ...] = ()
    renamed_or_extra_heading_hints: tuple[str, ...] = ()
    missing_blocks: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "artifact_kind": self.artifact_kind,
            "missing_headings": list(self.missing_headings),
            "renamed_or_extra_heading_hints": list(self.renamed_or_extra_heading_hints),
            "missing_blocks": list(self.missing_blocks),
        }


def _normalize_heading(line: str) -> str:
    line = line.strip().lstrip("#").strip()
    line = re.sub(r"\s+", " ", line)
    return line.upper()


def _extract_numbered_headings(text: str) -> list[str]:
    return [
        _normalize_heading(f"{m.group('num')}. {m.group('title')}")
        for m in NUMBERED_HEADING_RE.finditer(text)
    ]


def _missing_required_blocks(text: str, required_blocks: Iterable[str]) -> tuple[str, ...]:
    upper = text.upper()
    return tuple(
        block
        for block in required_blocks
        if not re.search(rf"(^|\n)\s*{re.escape(block)}\s*($|\n)", upper)
    )


class RunbookSacredHeadingsValidator:
    def validate(self, markdown_text: str) -> StructureValidationResult:
        headings = _extract_numbered_headings(markdown_text)
        required = [_normalize_heading(h) for h in RUNBOOK_REQUIRED_HEADINGS]
        missing = tuple(h for h in required if h not in headings)
        sacred_missing = [h for h in RUNBOOK_SACRED_HEADINGS if _normalize_heading(h) in missing]
        hints: list[str] = []
        if sacred_missing:
            hints.append(
                "Sacred headings must never be renamed: ERROR SIGNATURE, DIAGNOSIS STEPS, RECOVERY STEPS, ESCALATION CRITERIA"
            )
        if headings and headings != required:
            hints.append(
                "Runbook headings must appear exactly as the 11-section ingestion-guide sequence"
            )
        return StructureValidationResult(
            valid=not missing and not hints,
            artifact_kind="runbook",
            missing_headings=missing,
            renamed_or_extra_heading_hints=tuple(hints),
        )


class KedbBasicStructureValidator:
    def validate(self, markdown_text: str) -> StructureValidationResult:
        headings = _extract_numbered_headings(markdown_text)
        required = [_normalize_heading(h) for h in KEDB_REQUIRED_HEADINGS]
        missing = tuple(h for h in required if h not in headings)
        blocks = _missing_required_blocks(markdown_text, KEDB_REQUIRED_BLOCKS)
        return StructureValidationResult(
            valid=not missing and not blocks,
            artifact_kind="kedb",
            missing_headings=missing,
            missing_blocks=blocks,
        )


class DocBasicStructureValidator:
    def validate(self, markdown_text: str) -> StructureValidationResult:
        headings = _extract_numbered_headings(markdown_text)
        required = [_normalize_heading(h) for h in DOC_REQUIRED_HEADINGS]
        missing = tuple(h for h in required if h not in headings)
        blocks = _missing_required_blocks(markdown_text, DOC_REQUIRED_BLOCKS)
        return StructureValidationResult(
            valid=not missing and not blocks,
            artifact_kind="documentation",
            missing_headings=missing,
            missing_blocks=blocks,
        )
