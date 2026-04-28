from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class DocumentRecord:
    document_id: str
    path: str
    document_type: str
    title: str
    raw_text: str
    metadata: dict[str, str] = field(default_factory=dict)
    headings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ChunkRecord:
    chunk_id: str
    document_id: str
    document_type: str
    title: str
    text: str
    metadata: dict[str, str] = field(default_factory=dict)
    heading: str | None = None
    index: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class BenchmarkQuery:
    test_id: str
    query: str
    expected_doc_id: str
    expected_keywords: list[str] = field(default_factory=list)
    expected_answer_type: str | None = None
    priority: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MetricBundle:
    policy_compliance: float = 0.0
    bm25_readiness: float = 0.0
    chunking_quality: float = 0.0
    retrieval_precision: float = 0.0
    retrieval_recall: float = 0.0
    faithfulness: float = 0.0
    citation_evidence_accuracy: float = 0.0
    final_score: float = 0.0
    status: str = "Not evaluated"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
