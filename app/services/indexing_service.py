from __future__ import annotations

import math
import re
from collections import Counter, defaultdict

from app.schemas.models import ChunkRecord


TOKEN_RE = re.compile(r"[A-Za-z0-9_./:-]+")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text or "") if len(token) > 1]


class BM25Index:
    """Small dependency-free BM25 index for local/offline benchmark runs."""

    def __init__(self, k1: float = 1.5, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.chunks: list[ChunkRecord] = []
        self.doc_freq: dict[str, int] = defaultdict(int)
        self.term_freqs: list[Counter[str]] = []
        self.doc_lengths: list[int] = []
        self.avgdl: float = 0.0

    def fit(self, chunks: list[ChunkRecord]) -> "BM25Index":
        self.chunks = chunks
        self.term_freqs = []
        self.doc_freq = defaultdict(int)
        self.doc_lengths = []
        for chunk in chunks:
            tokens = tokenize(chunk.text)
            tf = Counter(tokens)
            self.term_freqs.append(tf)
            self.doc_lengths.append(len(tokens))
            for term in tf.keys():
                self.doc_freq[term] += 1
        self.avgdl = sum(self.doc_lengths) / max(1, len(self.doc_lengths))
        return self

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        q_tokens = tokenize(query)
        scores: list[tuple[int, float]] = []
        n_docs = len(self.chunks)
        for idx, tf in enumerate(self.term_freqs):
            score = 0.0
            dl = self.doc_lengths[idx] or 1
            for term in q_tokens:
                if term not in tf:
                    continue
                df = self.doc_freq.get(term, 0)
                idf = math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
                freq = tf[term]
                denom = freq + self.k1 * (1 - self.b + self.b * dl / max(self.avgdl, 1e-9))
                score += idf * (freq * (self.k1 + 1)) / max(denom, 1e-9)
            if score > 0:
                scores.append((idx, score))
        scores.sort(key=lambda pair: pair[1], reverse=True)
        results = []
        for rank, (idx, score) in enumerate(scores[:top_k], start=1):
            chunk = self.chunks[idx]
            results.append(
                {
                    "rank": rank,
                    "score": round(score, 6),
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "document_type": chunk.document_type,
                    "title": chunk.title,
                    "heading": chunk.heading,
                    "text_preview": chunk.text[:500],
                }
            )
        return results
