from __future__ import annotations

import re
from statistics import mean


WORD_RE = re.compile(r"[A-Za-z0-9_./:-]+")


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in WORD_RE.findall(text or "") if len(token) > 2}


class RagEvaluationService:
    """Heuristic evaluation hooks for v0.1.

    This service is intentionally lightweight and offline-capable. In v0.2 it can be
    extended with RAGAS, DeepEval, Phoenix or another enterprise evaluation service.
    """

    def evaluate_retrieved_context(self, retrieval_result: dict) -> dict:
        query_scores = []
        for item in retrieval_result.get("queries", []):
            query_tokens = _tokens(item.get("query", ""))
            previews = " ".join(result.get("text_preview", "") for result in item.get("results", []))
            context_tokens = _tokens(previews)
            overlap = len(query_tokens & context_tokens) / max(1, len(query_tokens))
            query_scores.append(overlap * 100)
        context_quality = round(mean(query_scores), 2) if query_scores else 0.0
        faithfulness_proxy = min(100.0, round(context_quality * 0.85 + retrieval_result.get("summary", {}).get("hit_at_3", 0) * 0.15, 2))
        return {
            "context_quality": context_quality,
            "faithfulness": faithfulness_proxy,
            "answer_relevancy_proxy": context_quality,
            "groundedness_proxy": faithfulness_proxy,
            "note": "Heuristic offline score. Replace or augment with RAGAS/DeepEval for LLM-as-judge evaluation.",
        }
