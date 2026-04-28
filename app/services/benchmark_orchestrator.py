from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from app.config import settings
from app.services.chunking_service import ChunkingService
from app.services.document_loader import copy_or_extract_package, load_markdown_documents
from app.services.feedback_generator import FeedbackGenerator
from app.services.policy_compliance_service import PolicyComplianceService
from app.services.rag_evaluation_service import RagEvaluationService
from app.services.report_generator import ReportGenerator
from app.services.retrieval_benchmark_service import RetrievalBenchmarkService


class BenchmarkOrchestrator:
    def __init__(self) -> None:
        self.chunking = ChunkingService(settings.chunk_max_chars, settings.chunk_overlap_chars)
        self.policy = PolicyComplianceService()
        self.retrieval = RetrievalBenchmarkService()
        self.rag = RagEvaluationService()
        self.feedback = FeedbackGenerator()
        self.reports = ReportGenerator()

    def run(self, package_path: Path, benchmark_profile: str = "default") -> dict:
        run_id = f"run_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        run_dir = settings.benchmark_runs_dir / run_id
        input_dir = run_dir / "input"
        output_dir = run_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)

        extracted_root = copy_or_extract_package(package_path, input_dir)
        documents = load_markdown_documents(extracted_root)
        chunks = self.chunking.chunk_documents(documents)

        golden_file = settings.resources_dir / "golden_datasets" / "golden_questions.jsonl"
        queries = self.retrieval.load_or_generate_queries(documents, golden_file if golden_file.exists() else None)
        policy_result = self.policy.evaluate_documents(documents)
        retrieval_result = self.retrieval.evaluate(chunks, queries, top_k=settings.top_k)
        rag_result = self.rag.evaluate_retrieved_context(retrieval_result)

        chunking_quality = self._chunking_quality(documents, chunks)
        citation_evidence_accuracy = min(100.0, policy_result.get("score", 0.0) * 0.75 + rag_result.get("groundedness_proxy", 0.0) * 0.25)

        metrics = {
            "policy_compliance": policy_result.get("score", 0.0),
            "bm25_readiness": self._bm25_readiness_from_policy(policy_result),
            "chunking_quality": chunking_quality,
            "retrieval_precision": retrieval_result.get("summary", {}).get("retrieval_precision", 0.0),
            "retrieval_recall": retrieval_result.get("summary", {}).get("retrieval_recall", 0.0),
            "faithfulness": rag_result.get("faithfulness", 0.0),
            "citation_evidence_accuracy": round(citation_evidence_accuracy, 2),
        }
        final_score = self._final_score(metrics)
        status = self._status(final_score)
        package_id = package_path.stem

        feedback = self.feedback.generate(package_id, policy_result, retrieval_result, final_score, status)

        result = {
            "run_id": run_id,
            "package_id": package_id,
            "benchmark_profile": benchmark_profile,
            "status": status,
            "final_score": final_score,
            "document_count": len(documents),
            "chunk_count": len(chunks),
            "query_count": len(queries),
            "metrics": metrics,
            "policy_result": policy_result,
            "retrieval_result": retrieval_result,
            "rag_result": rag_result,
            "feedback": feedback,
            "recommendation": self._recommendation(final_score),
        }

        self.reports.write_json(result, output_dir / "benchmark_result.json")
        self.reports.write_json(feedback, settings.feedback_dir / f"{run_id}_feedback.json")
        self.reports.write_metrics_xlsx(result, settings.reports_dir / f"{run_id}_metrics.xlsx")
        self.reports.write_docx_report(result, settings.reports_dir / f"{run_id}_enterprise_report.docx")

        return result

    def _chunking_quality(self, documents, chunks) -> float:
        if not documents:
            return 0.0
        if not chunks:
            return 0.0
        avg_chunks_per_doc = len(chunks) / max(1, len(documents))
        if avg_chunks_per_doc <= 1.2:
            return 70.0
        if avg_chunks_per_doc <= 8:
            return 90.0
        return 78.0

    def _bm25_readiness_from_policy(self, policy_result: dict) -> float:
        docs = policy_result.get("documents", [])
        values = [doc.get("checks", {}).get("bm25_keyword_readiness", 0.0) for doc in docs]
        return round(sum(values) / max(1, len(values)), 2)

    def _final_score(self, metrics: dict) -> float:
        return round(
            0.20 * metrics["policy_compliance"]
            + 0.15 * metrics["bm25_readiness"]
            + 0.15 * metrics["chunking_quality"]
            + 0.20 * metrics["retrieval_precision"]
            + 0.15 * metrics["retrieval_recall"]
            + 0.10 * metrics["faithfulness"]
            + 0.05 * metrics["citation_evidence_accuracy"],
            2,
        )

    def _status(self, score: float) -> str:
        if score >= 90:
            return "Enterprise Ready"
        if score >= 80:
            return "Ready with minor improvements"
        if score >= 70:
            return "Conditional readiness"
        if score >= 60:
            return "Needs remediation"
        return "Not ready for RAG ingestion"

    def _recommendation(self, score: float) -> str:
        if score >= settings.score_threshold:
            return "Package can be promoted to approved RAG ingestion after governance review."
        return "Package should be remediated using the generated corrective feedback before publication."
