from __future__ import annotations
import datetime as dt
import json
from pathlib import Path
from app.config import settings
from app.services.chunking_service import ChunkingService
from app.services.document_loader import (
    copy_or_extract_package,
    load_markdown_documents,
)
from app.services.golden_question_generator import GoldenQuestionGenerator
from app.services.policy_compliance_service import PolicyComplianceService
from app.services.report_generator import ReportGenerator


class BenchmarkOrchestrator:
    def __init__(self):
        self.chunking = ChunkingService(settings.chunk_max_chars, settings.chunk_overlap_chars)
        self.policy = PolicyComplianceService()
        self.reports = ReportGenerator()
        self.golden = GoldenQuestionGenerator()

    def run(
        self,
        package_path: Path,
        benchmark_profile: str = "default",
        ai4biz_retrieval_trace: Path | None = None,
        answer_trace: Path | None = None,
    ) -> dict:
        run_id = f"run_{dt.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        root = copy_or_extract_package(package_path, settings.benchmark_runs_dir / run_id / "input")
        docs = load_markdown_documents(root)
        chunks = self.chunking.chunk_documents(docs)
        gq = root / "resources/golden_datasets/golden_questions.jsonl"
        if not gq.exists():
            self.golden.generate(root, gq)
        qcount = sum(1 for line in gq.read_text(encoding="utf-8").splitlines() if line.strip())
        neg = sum(
            1
            for line in gq.read_text(encoding="utf-8").splitlines()
            if '"expected_behavior": "no_match"' in line
        )
        pol = self.policy.evaluate_documents(docs)
        bm = self._bm25(pol)
        cq = 90.0 if chunks else 0.0
        ss = round(0.4 * pol.get("score", 0) + 0.3 * bm + 0.3 * cq, 2)
        ret = (
            {
                "status": "not_evaluated",
                "score": None,
                "blocking_reason": "AI4BIZ index retrieval trace is missing; retrieval readiness is not scored.",
                "required_input": "AI4BIZ RAG Console retrieval results for golden_questions.jsonl.",
            }
            if not ai4biz_retrieval_trace
            else {
                "status": "trace_provided",
                "score": None,
                "trace_path": str(ai4biz_retrieval_trace),
            }
        )
        ans = (
            {
                "status": "not_evaluated",
                "score": None,
                "blocking_reason": "Answer traces are missing; answer readiness and faithfulness are not scored.",
                "required_input": "Answer traces with answer, citations, contexts, and faithfulness evidence.",
            }
            if not answer_trace
            else {
                "status": "trace_provided",
                "score": None,
                "trace_path": str(answer_trace),
            }
        )
        res = {
            "run_id": run_id,
            "benchmark_profile": benchmark_profile,
            "final_score": None,
            "final_score_policy": "No combined final score without static_package_readiness, retrieval_readiness and answer_readiness evidence.",
            "document_count": len(docs),
            "chunk_count": len(chunks),
            "query_count": qcount,
            "positive_query_count": qcount - neg,
            "negative_query_count": neg,
            "static_package_readiness": {
                "status": self._status(ss),
                "score": ss,
                "metrics": {
                    "policy_compliance": pol.get("score", 0),
                    "bm25_readiness": bm,
                    "chunking_quality": cq,
                },
            },
            "retrieval_readiness": ret,
            "answer_readiness": ans,
            "local_bm25_smoke_test": {
                "status": "diagnostic_only",
                "score": None,
                "note": "Not an AI4BIZ index readiness score.",
            },
        }
        (root / "quality").mkdir(exist_ok=True)
        report_path = root / "quality/benchmark_readiness_report.json"
        res["report_path"] = str(report_path)
        report_path.write_text(
            json.dumps(res, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return res

    def _bm25(self, pol):
        vals = [
            d.get("checks", {}).get("bm25_keyword_readiness", 0) for d in pol.get("documents", [])
        ]
        return round(sum(vals) / max(1, len(vals)), 2)

    def _status(self, score):
        return (
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
