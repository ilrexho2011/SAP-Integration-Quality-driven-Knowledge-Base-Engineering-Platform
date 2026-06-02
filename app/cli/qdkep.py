from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.services.operator_workflow import OperatorWorkflowService


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qdkep",
        description="QDKEP developer/operator CLI for contract validation, package building, AI4BIZ export and benchmarking.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate-contract", help="Validate a QDKEP package contract")
    p.add_argument("package_path")
    p.add_argument("--output-json", default=None)

    p = sub.add_parser("build-package", help="Build a contract-compliant QDKEP package")
    p.add_argument("--source-root", required=True)
    p.add_argument("--output-zip", required=True)
    p.add_argument("--package-id", default="quality-driven-knowledge-engineering-platform")
    p.add_argument("--package-version", default="1.9")
    p.add_argument("--package-name", default="Quality-Driven Knowledge Engineering Platform")

    p = sub.add_parser("quality-gate", help="Run deterministic promotion quality gate")
    p.add_argument("package_path")
    p.add_argument("--output-json", default=None)

    p = sub.add_parser(
        "export-ai4biz", help="Export an approved package to AI4BIZ RAG Console payload layout"
    )
    p.add_argument("package_path")
    p.add_argument("--output-root", default=None)

    for name, help_text in [
        ("generate-runbooks", "Generate evidence-grounded runbooks"),
        ("generate-kedb", "Generate evidence-grounded KEDB entries"),
        ("generate-docs", "Generate evidence-grounded catalog documentation"),
    ]:
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--source-package", required=True)
        p.add_argument("--output-root", required=True)

    p = sub.add_parser(
        "benchmark-package",
        help="Generate golden questions and separated benchmark readiness report",
    )
    p.add_argument("package_path")
    p.add_argument("--benchmark-profile", default="default")
    p.add_argument("--ai4biz-retrieval-trace", default=None)
    p.add_argument("--answer-trace", default=None)
    p.add_argument("--golden-questions-jsonl", default=None)

    p = sub.add_parser(
        "dashboard-summary",
        help="Summarize package status for the Streamlit Enterprise QA dashboard",
    )
    p.add_argument("package_path")

    p = sub.add_parser("serve-dashboard", help="Launch the Streamlit Enterprise QA dashboard")
    p.add_argument("streamlit_args", nargs=argparse.REMAINDER, default=[])

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    service = OperatorWorkflowService()

    if args.command == "validate-contract":
        response = service.validate_contract(args.package_path, args.output_json)
    elif args.command == "build-package":
        response = service.build_package(
            args.source_root,
            args.output_zip,
            package_id=args.package_id,
            package_version=args.package_version,
            package_name=args.package_name,
        )
    elif args.command == "quality-gate":
        response = service.quality_gate(args.package_path, args.output_json)
    elif args.command == "export-ai4biz":
        response = service.export_ai4biz(args.package_path, args.output_root)
    elif args.command == "generate-runbooks":
        response = service.generate_runbooks(args.source_package, args.output_root)
    elif args.command == "generate-kedb":
        response = service.generate_kedb(args.source_package, args.output_root)
    elif args.command == "generate-docs":
        response = service.generate_docs(args.source_package, args.output_root)
    elif args.command == "benchmark-package":
        response = service.benchmark_package(
            args.package_path,
            benchmark_profile=args.benchmark_profile,
            ai4biz_retrieval_trace=args.ai4biz_retrieval_trace,
            answer_trace=args.answer_trace,
            golden_questions_jsonl=args.golden_questions_jsonl,
        )
    elif args.command == "dashboard-summary":
        response = service.dashboard_summary(args.package_path)
    elif args.command == "serve-dashboard":
        import subprocess

        dashboard = (
            Path(__file__).resolve().parents[2]
            / "dashboard"
            / "qdkep_enterprise_quality_console.py"
        )
        return subprocess.call(
            [sys.executable, "-m", "streamlit", "run", str(dashboard), *args.streamlit_args]
        )
    else:
        raise SystemExit(f"Unsupported command: {args.command}")

    payload = response.to_dict()
    print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
    return 0 if payload["status"] not in {"blocked", "needs_remediation", "error"} else 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
