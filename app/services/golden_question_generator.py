from __future__ import annotations
import json
import re
import zipfile
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from app.contracts.metadata_normalizer import MetadataNormalizer


@dataclass(frozen=True)
class GoldenQuestionGenerationResult:
    status: str
    output_jsonl: str
    report_path: str
    rb_count: int
    kb_count: int
    question_count: int
    question_type_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class GoldenQuestionGenerator:
    def __init__(self) -> None:
        self.norm = MetadataNormalizer()

    def generate(
        self, package_path: str | Path, output_jsonl: str | Path | None = None
    ) -> GoldenQuestionGenerationResult:
        src = Path(package_path).resolve()
        root = src
        if src.is_file() and src.suffix.lower() == ".zip":
            tmp = Path(tempfile.mkdtemp(prefix="qdkep_gq_"))
            with zipfile.ZipFile(src) as zf:
                zf.extractall(tmp)
            dirs = [p for p in tmp.iterdir() if p.is_dir()]
            root = dirs[0] if len(dirs) == 1 else tmp
        out = (
            Path(output_jsonl).resolve()
            if output_jsonl
            else root / "resources/golden_datasets/golden_questions.jsonl"
        )
        out.parent.mkdir(parents=True, exist_ok=True)
        recs: list[dict[str, Any]] = []
        for folder, atype in [
            (root / "knowledge/RB", "RB"),
            (root / "knowledge/KB", "KB"),
            (root / "generated_functional_knowledge/runbooks", "RB"),
            (root / "generated_functional_knowledge/kedb", "KB"),
        ]:
            if not folder.exists():
                continue
            for path in sorted(folder.glob("*.md")):
                text = path.read_text(encoding="utf-8", errors="replace")
                md = self.norm.parse_markdown_metadata(text)
                doc = path.stem
                obj = md.get("object_name") or re.sub(r"^(RB|KB)_|_v\d+$", "", doc)
                iface = md.get("interface_id", "")
                pr = md.get("priority", "")
                title = next(
                    (line[2:].strip() for line in text.splitlines() if line.startswith("# ")),
                    obj.replace("_", " "),
                )
                terms = [x for x in re.split(r"[_\W]+", obj) if len(x) > 2]
                common = {
                    "artifact_id": doc,
                    "artifact_type": atype,
                    "expected_doc_id": doc,
                    "priority": pr,
                    "interface_id": iface,
                    "object_name": obj,
                    "expected_keywords": [x for x in [obj, iface, pr] + terms[:4] if x],
                }
                qs = [
                    (
                        "diagnosis",
                        f"How do I diagnose {obj} on interface {iface or 'the affected interface'}?",
                        "diagnosis",
                    ),
                    (
                        "recovery",
                        f"What recovery steps should I follow for {title}?",
                        "recovery",
                    ),
                    (
                        "root_cause",
                        f"What are the likely root causes for {obj}?",
                        "root_cause",
                    ),
                    (
                        "dirty_mpl_log",
                        f"mpl failed log {iface} error {' '.join(terms[:3]) or obj} retry not working status FAILED how fix",
                        "diagnosis",
                    ),
                    (
                        "synonym_heavy",
                        f"incident playbook troubleshooting remediation RCA workaround for {' '.join(terms[:4]) or obj} {iface}",
                        "diagnosis",
                    ),
                ]
                for qt, q, ea in qs:
                    recs.append(
                        {
                            **common,
                            "test_id": f"{doc}::{qt}",
                            "query": re.sub(r"\s+", " ", q).strip(),
                            "query_type": qt,
                            "expected_answer_type": ea,
                            "expected_behavior": "match_expected_document",
                            "negative": False,
                        }
                    )
                recs.append(
                    {
                        **common,
                        "test_id": f"{doc}::negative_distractor",
                        "query": f"Find unrelated payroll tax printing issue not connected to {obj} or {iface}",
                        "query_type": "negative_distractor",
                        "expected_answer_type": "no_answer",
                        "expected_doc_id": "__NO_MATCH__",
                        "expected_keywords": [],
                        "expected_behavior": "no_match",
                        "negative": True,
                    }
                )
        seen: dict[tuple[Any, Any], dict[str, Any]] = {}
        for r in recs:
            seen.setdefault((r["artifact_id"], r["query_type"]), r)
        recs = list(seen.values())
        with out.open("w", encoding="utf-8") as h:
            for r in recs:
                h.write(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n")
        counts: dict[str, int] = {}
        rb = kb = 0
        for r in recs:
            query_type = str(r["query_type"])
            counts[query_type] = counts.get(query_type, 0) + 1
            if r["query_type"] == "diagnosis" and r["artifact_type"] == "RB":
                rb += 1
            if r["query_type"] == "diagnosis" and r["artifact_type"] == "KB":
                kb += 1
        report = {
            "schema_version": "1.0",
            "status": "generated",
            "output_jsonl": self._rel(root, out),
            "rb_count": rb,
            "kb_count": kb,
            "question_count": len(recs),
            "question_type_counts": counts,
            "runtime_values_policy": "No MessageGuid, MPL id, endpoint URL, credential, or payload value is fabricated.",
        }
        rp = root / "quality/golden_questions_generation_report.json"
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return GoldenQuestionGenerationResult(
            "generated",
            self._rel(root, out),
            self._rel(root, rp),
            rb,
            kb,
            len(recs),
            counts,
        )

    def _rel(self, root: Path, path: Path) -> str:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return str(path)
