from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

from app.schemas.models import BenchmarkQuery, ChunkRecord, DocumentRecord
from app.services.indexing_service import BM25Index


class RetrievalBenchmarkService:
    def load_or_generate_queries(self, documents: list[DocumentRecord], query_file: Path | None = None) -> list[BenchmarkQuery]:
        if query_file and query_file.exists():
            queries: list[BenchmarkQuery] = []
            for line in query_file.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                item = json.loads(line)
                queries.append(BenchmarkQuery(**item))
            return queries

        generated: list[BenchmarkQuery] = []
        for document in documents:
            title = document.title or document.document_id
            base = {
                "expected_doc_id": document.document_id,
                "priority": document.metadata.get("priority"),
            }
            generated.append(BenchmarkQuery(test_id=f"{document.document_id}-Q01", query=title, **base))
            if document.metadata.get("object_name"):
                generated.append(BenchmarkQuery(test_id=f"{document.document_id}-Q02", query=f"How to resolve {document.metadata['object_name']}?", **base))
            if document.metadata.get("error_pattern"):
                generated.append(BenchmarkQuery(test_id=f"{document.document_id}-Q03", query=f"Find runbook for {document.metadata['error_pattern']}", **base))
        return generated

    def evaluate(self, chunks: list[ChunkRecord], queries: list[BenchmarkQuery], top_k: int = 5) -> dict:
        if not chunks or not queries:
            return {"score": 0.0, "queries": [], "summary": {"query_count": 0}}

        index = BM25Index().fit(chunks)
        per_query = []
        for query in queries:
            results = index.search(query.query, top_k=top_k)
            result_doc_ids = [r["document_id"] for r in results]
            hit_rank = None
            for idx, doc_id in enumerate(result_doc_ids, start=1):
                if doc_id == query.expected_doc_id:
                    hit_rank = idx
                    break
            hit_at_1 = 1.0 if hit_rank == 1 else 0.0
            hit_at_3 = 1.0 if hit_rank and hit_rank <= 3 else 0.0
            hit_at_5 = 1.0 if hit_rank and hit_rank <= 5 else 0.0
            mrr = 1.0 / hit_rank if hit_rank else 0.0
            precision_at_k = sum(1 for doc_id in result_doc_ids if doc_id == query.expected_doc_id) / max(1, len(result_doc_ids))
            recall_proxy = 1.0 if hit_rank else 0.0
            per_query.append(
                {
                    "test_id": query.test_id,
                    "query": query.query,
                    "expected_doc_id": query.expected_doc_id,
                    "hit_rank": hit_rank,
                    "hit_at_1": hit_at_1,
                    "hit_at_3": hit_at_3,
                    "hit_at_5": hit_at_5,
                    "mrr": round(mrr, 4),
                    "precision_at_k": round(precision_at_k, 4),
                    "recall_proxy": round(recall_proxy, 4),
                    "results": results,
                }
            )

        summary = {
            "query_count": len(per_query),
            "hit_at_1": round(mean(q["hit_at_1"] for q in per_query) * 100, 2),
            "hit_at_3": round(mean(q["hit_at_3"] for q in per_query) * 100, 2),
            "hit_at_5": round(mean(q["hit_at_5"] for q in per_query) * 100, 2),
            "mrr": round(mean(q["mrr"] for q in per_query) * 100, 2),
            "retrieval_precision": round(mean(q["precision_at_k"] for q in per_query) * 100, 2),
            "retrieval_recall": round(mean(q["recall_proxy"] for q in per_query) * 100, 2),
        }
        score = round((summary["hit_at_3"] * 0.35 + summary["mrr"] * 0.35 + summary["retrieval_precision"] * 0.15 + summary["retrieval_recall"] * 0.15), 2)
        return {"score": score, "queries": per_query, "summary": summary}
