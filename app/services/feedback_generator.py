from __future__ import annotations

from statistics import mean


class FeedbackGenerator:
    def generate(self, package_id: str, policy_result: dict, retrieval_result: dict, final_score: float, status: str) -> dict:
        document_feedback = []
        for item in policy_result.get("documents", []):
            issues = []
            checks = item.get("checks", {})
            for category, score in checks.items():
                if score < 80:
                    issues.append(
                        {
                            "category": category,
                            "severity": "high" if score < 60 else "medium",
                            "score": score,
                            "message": self._message_for(category),
                            "recommendation": self._recommendation_for(category),
                        }
                    )
            if issues:
                document_feedback.append(
                    {
                        "document_id": item["document_id"],
                        "document_type": item["document_type"],
                        "title": item["title"],
                        "overall_score": item["score"],
                        "status": item["status"],
                        "issues": issues,
                        "regeneration_hints": {
                            "fields_to_enrich": self._fields_to_enrich(issues),
                            "preserve_document_id": True,
                            "preserve_metadata_order": True,
                            "apply_only_after_user_approval": True,
                        },
                    }
                )

        return {
            "package_id": package_id,
            "overall_score": final_score,
            "status": status,
            "documents_needing_remediation": len(document_feedback),
            "disqualified_documents": sum(1 for item in document_feedback if item["overall_score"] < 60),
            "retrieval_summary": retrieval_result.get("summary", {}),
            "document_feedback": document_feedback,
            "governance": {
                "direct_document_modification_allowed": False,
                "requires_user_approval_for_regeneration": True,
                "reason": "The evaluator produces corrective feedback only. The generator applies remediation under controlled workflow.",
            },
        }

    def _message_for(self, category: str) -> str:
        messages = {
            "title_searchability": "The title may not contain the dominant searchable error phrase.",
            "metadata_completeness": "Mandatory metadata fields are missing or empty.",
            "stable_headings": "The document uses headings that are not part of the approved stable structure.",
            "evidence_presence": "Runtime evidence such as MessageGuid, HTTP code, adapter or iFlow context is weak or missing.",
            "diagnosis_fix_separation": "Diagnosis, fix, validation and rollback are not clearly separated.",
            "bm25_keyword_readiness": "Important retrieval keywords are not repeated in a controlled and searchable way.",
            "canonical_term_consistency": "Canonical terms or error pattern formatting are inconsistent.",
        }
        return messages.get(category, "The document needs remediation.")

    def _recommendation_for(self, category: str) -> str:
        recommendations = {
            "title_searchability": "Add the main error phrase and key technical terms to the title or subtitle.",
            "metadata_completeness": "Fill all mandatory metadata fields without changing the document ID.",
            "stable_headings": "Normalize headings to the approved KEDB/Runbook structure.",
            "evidence_presence": "Add runtime evidence: MessageGuid, HTTP status, adapter, sender/receiver and integration flow.",
            "diagnosis_fix_separation": "Separate diagnosis, resolution steps, validation and rollback sections.",
            "bm25_keyword_readiness": "Repeat canonical searchable terms in title, diagnosis, resolution and evidence sections.",
            "canonical_term_consistency": "Normalize error_pattern using spaced pipe separators, for example: HTTP | API | RATE_LIMIT.",
        }
        return recommendations.get(category, "Review and remediate according to the ingestion policy.")

    def _fields_to_enrich(self, issues: list[dict]) -> list[str]:
        mapping = {
            "title_searchability": "title",
            "metadata_completeness": "metadata",
            "stable_headings": "headings",
            "evidence_presence": "evidence",
            "diagnosis_fix_separation": "diagnosis_resolution_validation",
            "bm25_keyword_readiness": "keywords",
            "canonical_term_consistency": "error_pattern",
        }
        return sorted({mapping.get(issue["category"], "content") for issue in issues})
