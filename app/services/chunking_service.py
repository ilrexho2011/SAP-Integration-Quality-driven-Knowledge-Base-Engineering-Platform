from __future__ import annotations

import re

from app.schemas.models import ChunkRecord, DocumentRecord


HEADING_SPLIT_RE = re.compile(r"(?m)^(#{1,6}\s+.+)$")


class ChunkingService:
    def __init__(self, max_chars: int = 1800, overlap_chars: int = 220) -> None:
        self.max_chars = max_chars
        self.overlap_chars = overlap_chars

    def chunk_documents(self, documents: list[DocumentRecord]) -> list[ChunkRecord]:
        chunks: list[ChunkRecord] = []
        for document in documents:
            chunks.extend(self.chunk_document(document))
        return chunks

    def chunk_document(self, document: DocumentRecord) -> list[ChunkRecord]:
        sections = self._split_by_heading(document.raw_text)
        chunks: list[ChunkRecord] = []
        index = 0
        for heading, text in sections:
            for segment in self._split_long_text(text):
                chunk_id = f"{document.document_id}::chunk-{index:04d}"
                chunks.append(
                    ChunkRecord(
                        chunk_id=chunk_id,
                        document_id=document.document_id,
                        document_type=document.document_type,
                        title=document.title,
                        text=self._attach_context(document, heading, segment),
                        metadata=document.metadata,
                        heading=heading,
                        index=index,
                    )
                )
                index += 1
        return chunks

    def _attach_context(self, document: DocumentRecord, heading: str | None, text: str) -> str:
        metadata_lines = [
            f"document_id: {document.document_id}",
            f"document_type: {document.document_type}",
            f"title: {document.title}",
        ]
        for key in [
            "priority",
            "error_pattern",
            "object_name",
            "integration_flow_id",
            "integration_flow_name",
            "package_name",
        ]:
            if key in document.metadata:
                metadata_lines.append(f"{key}: {document.metadata[key]}")
        if heading:
            metadata_lines.append(f"section_heading: {heading}")
        return "\n".join(metadata_lines) + "\n\n" + text.strip()

    def _split_by_heading(self, text: str) -> list[tuple[str | None, str]]:
        parts = HEADING_SPLIT_RE.split(text)
        if len(parts) == 1:
            return [(None, text)]
        sections: list[tuple[str | None, str]] = []
        preface = parts[0].strip()
        if preface:
            sections.append(("Preface", preface))
        idx = 1
        while idx < len(parts):
            heading = re.sub(r"^#{1,6}\s+", "", parts[idx]).strip()
            body = parts[idx + 1] if idx + 1 < len(parts) else ""
            sections.append((heading, body))
            idx += 2
        return sections

    def _split_long_text(self, text: str) -> list[str]:
        text = text.strip()
        if not text:
            return [""]
        if len(text) <= self.max_chars:
            return [text]

        segments: list[str] = []
        start = 0
        while start < len(text):
            end = min(start + self.max_chars, len(text))
            boundary = max(text.rfind("\n\n", start, end), text.rfind(". ", start, end))
            if boundary > start + int(self.max_chars * 0.55):
                end = boundary + 1
            segments.append(text[start:end].strip())
            if end >= len(text):
                break
            start = max(0, end - self.overlap_chars)
        return [segment for segment in segments if segment]
