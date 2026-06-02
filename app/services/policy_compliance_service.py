from __future__ import annotations

import re
from statistics import mean

from app.schemas.models import DocumentRecord


REQUIRED_METADATA = [
    "customer_id",
    "system_id",
    "sap_sid",
    "artifact_type",
    "object_name",
    "priority",
    "version",
]

ALLOWED_HEADINGS = {
    "summary",
    "symptoms",
    "root cause",
    "diagnosis",
    "resolution",
    "resolution steps",
    "fix",
    "validation",
    "rollback",
    "evidence",
    "metadata",
    "impact",
    "monitoring",
    "references",
    "operational procedure",
    "known error",
    "trigger",
    "scope",
}

EVIDENCE_RE = re.compile(
    r"(MessageGuid|MPL|HTTP\s*[0-9]{3}|CorrelationId|Adapter|Sender|Receiver|iFlow|integration_flow_id|Exception)",
    re.IGNORECASE,
)


class PolicyComplianceService:
    def evaluate_documents(self, documents: list[DocumentRecord]) -> dict:
        per_document = [self.evaluate_document(document) for document in documents]
        if not per_document:
            return {"score": 0.0, "documents": [], "summary": {"document_count": 0}}
        return {
            "score": round(mean(item["score"] for item in per_document), 2),
            "documents": per_document,
            "summary": {
                "document_count": len(per_document),
                "needs_remediation": sum(1 for item in per_document if item["score"] < 80),
                "disqualified": sum(1 for item in per_document if item["score"] < 60),
            },
        }

    def evaluate_document(self, document: DocumentRecord) -> dict:
        checks = {
            "title_searchability": self._title_searchability(document),
            "metadata_completeness": self._metadata_completeness(document),
            "stable_headings": self._stable_headings(document),
            "evidence_presence": self._evidence_presence(document),
            "diagnosis_fix_separation": self._diagnosis_fix_separation(document),
            "bm25_keyword_readiness": self._bm25_keyword_readiness(document),
            "canonical_term_consistency": self._canonical_term_consistency(document),
        }
        score = round(mean(checks.values()), 2)
        status = (
            "Enterprise Ready"
            if score >= 90
            else "Ready with minor improvements"
            if score >= 80
            else "Conditional readiness"
            if score >= 70
            else "Needs remediation"
            if score >= 60
            else "Not ready for RAG ingestion"
        )
        return {
            "document_id": document.document_id,
            "document_type": document.document_type,
            "title": document.title,
            "score": score,
            "status": status,
            "checks": checks,
        }

    def _title_searchability(self, document: DocumentRecord) -> float:
        title = document.title.lower()
        candidates = [
            document.metadata.get("object_name", ""),
            document.metadata.get("error_pattern", ""),
            document.metadata.get("integration_flow_id", ""),
        ]
        candidate_terms = [
            term.lower()
            for val in candidates
            for term in re.split(r"[\s_|:./-]+", val)
            if len(term) >= 4
        ]
        matches = sum(1 for term in set(candidate_terms) if term and term in title)
        if len(title) >= 20 and matches >= 2:
            return 100.0
        if len(title) >= 15 and matches >= 1:
            return 85.0
        if len(title) >= 15:
            return 70.0
        return 45.0

    def _metadata_completeness(self, document: DocumentRecord) -> float:
        present = sum(1 for key in REQUIRED_METADATA if document.metadata.get(key))
        return round(100 * present / len(REQUIRED_METADATA), 2)

    def _stable_headings(self, document: DocumentRecord) -> float:
        if not document.headings:
            return 40.0
        normalized = [h.strip().lower() for h in document.headings]
        good = sum(
            1
            for h in normalized
            if h in ALLOWED_HEADINGS or any(h.startswith(a) for a in ALLOWED_HEADINGS)
        )
        return round(100 * good / len(normalized), 2)

    def _evidence_presence(self, document: DocumentRecord) -> float:
        matches = EVIDENCE_RE.findall(document.raw_text)
        if len(matches) >= 4:
            return 100.0
        if len(matches) >= 2:
            return 80.0
        if len(matches) >= 1:
            return 60.0
        return 30.0

    def _diagnosis_fix_separation(self, document: DocumentRecord) -> float:
        headings = {h.lower() for h in document.headings}
        has_diag = any(h in headings for h in ["diagnosis", "root cause", "known error"])
        has_fix = any(
            h in headings
            for h in ["resolution", "resolution steps", "fix", "operational procedure"]
        )
        has_validation = any(h in headings for h in ["validation", "rollback"])
        if has_diag and has_fix and has_validation:
            return 100.0
        if has_diag and has_fix:
            return 80.0
        if has_diag or has_fix:
            return 55.0
        return 25.0

    def _bm25_keyword_readiness(self, document: DocumentRecord) -> float:
        text = document.raw_text.lower()
        technical_terms = re.findall(
            r"\b(http|sftp|odata|adapter|mapping|exception|timeout|certificate|json|xml|idoc|mpl|retry|receiver|sender|api|auth|authorization|connection|payload)\b",
            text,
        )
        unique_terms = len(set(technical_terms))
        density = len(technical_terms) / max(1, len(text.split())) * 100
        if unique_terms >= 8 and density >= 1.5:
            return 100.0
        if unique_terms >= 5:
            return 80.0
        if unique_terms >= 3:
            return 60.0
        return 35.0

    def _canonical_term_consistency(self, document: DocumentRecord) -> float:
        pattern = document.metadata.get("error_pattern", "")
        if pattern and " | " in pattern:
            return 100.0
        if pattern:
            return 75.0
        if document.metadata.get("object_name"):
            return 70.0
        return 45.0
