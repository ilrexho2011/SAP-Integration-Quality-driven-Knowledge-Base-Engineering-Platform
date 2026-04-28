from __future__ import annotations

import re
from pathlib import Path

from app.schemas.models import DocumentRecord


HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
SETEXT_RE = re.compile(r"^\s*(=+|-+)\s*$")
META_RE = re.compile(r"^\s*([A-Za-z0-9_\- ]{2,60})\s*:\s*[\"']?(.*?)[\"']?\s*$")


def _clean_id(value: str) -> str:
    value = value.strip()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"[^A-Za-z0-9_\-.]+", "", value)
    return value[:120] or "UNKNOWN_DOC"


def detect_document_type(path: Path, metadata: dict[str, str]) -> str:
    lower = str(path).lower()
    artifact_type = metadata.get("artifact_type", "").lower()
    if "runbook" in lower or artifact_type == "runbook":
        return "runbook"
    if "kedb" in lower or artifact_type == "kedb":
        return "kedb"
    if "catalog" in lower or artifact_type in {"catalog", "integration_catalog"}:
        return "catalog_doc"
    return "knowledge_doc"


def parse_markdown_file(path: Path) -> DocumentRecord:
    raw_text = path.read_text(encoding="utf-8", errors="replace")
    lines = raw_text.splitlines()
    title = ""
    metadata: dict[str, str] = {}
    headings: list[str] = []

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if line.startswith("#"):
            title = re.sub(r"^#+\s*", "", stripped).strip()
            break
        if idx + 1 < len(lines) and SETEXT_RE.match(lines[idx + 1]):
            title = stripped
            break
        title = stripped
        break

    metadata_window = lines[:80]
    for line in metadata_window:
        match = META_RE.match(line)
        if match:
            key = match.group(1).strip().lower().replace(" ", "_")
            val = match.group(2).strip()
            metadata[key] = val

    for line in lines:
        match = HEADING_RE.match(line)
        if match:
            headings.append(match.group(2).strip())

    document_id = (
        metadata.get("runbook_id")
        or metadata.get("kedb_id")
        or metadata.get("known_error_id")
        or path.stem
        or metadata.get("object_name")
    )
    document_type = detect_document_type(path, metadata)

    return DocumentRecord(
        document_id=_clean_id(document_id),
        path=str(path),
        document_type=document_type,
        title=title or path.stem,
        raw_text=raw_text,
        metadata=metadata,
        headings=headings,
    )
