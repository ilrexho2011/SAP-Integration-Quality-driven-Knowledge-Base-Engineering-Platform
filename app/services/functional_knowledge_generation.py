from __future__ import annotations

import json
import re
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.contracts import MetadataNormalizer


@dataclass(frozen=True)
class FunctionalKnowledgeGenerationResult:
    status: str
    output_root: str
    artifact_count: int
    runbook_count: int
    kedb_count: int
    documentation_count: int
    source_package: str
    report_path: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class FunctionalKnowledgeGenerationService:
    """Generate evidence-grounded RB/KB/DOC artifacts.

    Runtime values are never fabricated. MPL identifiers, MessageGuid values,
    endpoint URLs and payload samples remain missing unless present in real
    evidence files copied into the generated source root.
    """

    def __init__(self) -> None:
        self.normalizer = MetadataNormalizer()

    def generate(
        self, source_package: str | Path, output_root: str | Path
    ) -> FunctionalKnowledgeGenerationResult:
        source = Path(source_package).resolve()
        output = Path(output_root).resolve()
        if output.exists():
            shutil.rmtree(output)
        output.mkdir(parents=True, exist_ok=True)

        with self._open_root(source) as root:
            records = self._load_records(root)
            if not records:
                raise ValueError(f"No package artifact metadata found in {source}")
            source_map = self._source_map(root)
            normalized = [self._normalize_record(record, source_map) for record in records]
            rb = [record for record in normalized if record["prefix"] == "RB"]
            kb = [record for record in normalized if record["prefix"] == "KB"]

            docs: dict[str, dict[str, Any]] = {}
            for record in normalized:
                key = (
                    record["metadata"].get("interface_id")
                    or record["metadata"].get("object_name")
                    or record["filename"]
                )
                docs.setdefault(str(key), record)

            written: list[Path] = []
            for record in rb:
                path = output / "runbooks" / record["filename"]
                self._write(path, self._render_runbook(record))
                written.append(path)
            for record in kb:
                path = output / "kedb" / record["filename"]
                self._write(path, self._render_kedb(record))
                written.append(path)
            for record in docs.values():
                metadata = self._doc_metadata(record)
                path = output / "documentation" / self._filename("DOC", metadata)
                self._write(path, self._render_doc(record, metadata))
                written.append(path)

            for src_rel, dst_rel in [
                ("logs/mpl", "logs/mpl"),
                ("resources/mpl", "resources/mpl"),
                ("sap_ci", "sap_ci"),
                ("sap_pipo", "sap_pipo"),
                ("sap_ci_cpi", "sap_ci_cpi"),
                ("sap_pi_po", "sap_pi_po"),
                ("inventory", "inventory"),
            ]:
                self._copy_tree(root / src_rel, output / dst_rel)

            report = {
                "status": "generated",
                "generated_at": self._now(),
                "source_package": str(source),
                "artifact_count": len(written),
                "runbook_count": len(rb),
                "kedb_count": len(kb),
                "documentation_count": len(docs),
                "source_map": source_map,
                "rules": [
                    "RB/KB/DOC files are generated from package metadata and evidence maps.",
                    "Runtime/MPL values are not fabricated; they remain missing unless present in real log files.",
                    "Catalog DOC entries are generated per unique interface_id/object_name.",
                ],
            }
            self._write_json(
                output / "quality" / "functional_knowledge_generation_report.json", report
            )
            return FunctionalKnowledgeGenerationResult(
                "generated",
                str(output),
                len(written),
                len(rb),
                len(kb),
                len(docs),
                str(source),
                "quality/functional_knowledge_generation_report.json",
            )

    def _open_root(self, source: Path):
        class Context:
            def __init__(self, path: Path) -> None:
                self.path = path
                self.tmp: tempfile.TemporaryDirectory[str] | None = None

            def __enter__(self) -> Path:
                if self.path.is_dir():
                    return self.path
                self.tmp = tempfile.TemporaryDirectory(prefix="qdkep_func_gen_")
                with zipfile.ZipFile(self.path) as zf:
                    zf.extractall(self.tmp.name)
                base = Path(self.tmp.name)
                children = [path for path in base.iterdir() if path.is_dir()]
                return (
                    children[0]
                    if len(children) == 1 and not (base / "manifest.json").exists()
                    else base
                )

            def __exit__(self, *_: Any) -> None:
                if self.tmp:
                    self.tmp.cleanup()

        return Context(source)

    def _load_records(self, root: Path) -> list[dict[str, Any]]:
        ingestion_zips = (
            sorted((root / "exports").glob("*ingestion-package.zip"))
            if (root / "exports").exists()
            else []
        )
        for zip_path in reversed(ingestion_zips):
            with tempfile.TemporaryDirectory(prefix="qdkep_func_meta_") as tmp:
                with zipfile.ZipFile(zip_path) as zf:
                    zf.extractall(tmp)
                records = self._records_from_metadata_dir(Path(tmp) / "metadata")
                if records:
                    return records
        records = self._records_from_metadata_dir(root / "metadata")
        if records:
            return records
        manifest = self._load_json(root / "manifest.json")
        output: list[dict[str, Any]] = []
        for artifact in manifest.get("artifacts", []) if isinstance(manifest, dict) else []:
            if not isinstance(artifact, dict):
                continue
            filename = Path(str(artifact.get("filename", "artifact.md"))).name
            prefix = str(artifact.get("artifact_type_prefix") or filename.split("_", 1)[0]).upper()
            output.append(
                {
                    "prefix": prefix,
                    "filename": filename,
                    "metadata": dict(artifact.get("metadata", {})),
                }
            )
        return output

    def _records_from_metadata_dir(self, folder: Path) -> list[dict[str, Any]]:
        if not folder.exists():
            return []
        records: list[dict[str, Any]] = []
        for path in sorted(folder.glob("*.metadata.json")):
            data = self._load_json(path)
            filename = Path(
                str(
                    data.get("source_package_path")
                    or data.get("document_path")
                    or path.name.replace(".metadata.json", ".md")
                )
            ).name
            prefix = str(data.get("artifact_type") or filename.split("_", 1)[0]).upper()
            metadata = {
                key: str(data.get(key, ""))
                for key in [
                    "environment",
                    "customer_id",
                    "system_id",
                    "sap_sid",
                    "object_name",
                    "priority",
                    "version",
                    "interface_id",
                    "interface_name",
                    "integration_flow_id",
                    "integration_flow_name",
                    "package_name",
                    "review_cycle",
                    "review_status",
                ]
            }
            metadata["artifact_type"] = {"RB": "runbook", "KB": "kedb", "DOC": "documentation"}.get(
                prefix, "documentation"
            )
            metadata["source_file"] = str(data.get("source_package_path", ""))
            records.append({"prefix": prefix, "filename": filename, "metadata": metadata})
        return records

    def _source_map(self, root: Path) -> dict[str, Any]:
        mpl_files: list[str] = []
        for base in [root / "logs" / "mpl", root / "resources" / "mpl"]:
            if base.exists():
                mpl_files.extend(
                    path.relative_to(root).as_posix() for path in sorted(base.glob("*.json"))
                )
        return {
            "manifest": (root / "manifest.json").exists(),
            "package_metadata": (root / "package_metadata.json").exists(),
            "customer_context_files": [
                path.relative_to(root).as_posix()
                for path in sorted((root / "customer").glob("*.yaml"))
            ]
            if (root / "customer").exists()
            else [],
            "interface_inventory": (
                root / "interface_inventory" / "interface_inventory.json"
            ).exists(),
            "traceability_report": (root / "quality" / "traceability_report.json").exists(),
            "mpl_log_files": mpl_files,
        }

    def _normalize_record(
        self, record: dict[str, Any], source_map: dict[str, Any]
    ) -> dict[str, Any]:
        prefix = str(record.get("prefix", "DOC")).upper()
        metadata = dict(record.get("metadata", {}))
        metadata["customer_id"] = self._token(metadata.get("customer_id"), "RCMO")
        metadata["system_id"] = self._token(
            metadata.get("system_id") or metadata.get("sap_sid"), "CPI"
        )
        metadata["sap_sid"] = self._token(
            metadata.get("sap_sid") or metadata.get("system_id"), "CPI"
        )
        metadata["object_name"] = self._object_code(
            metadata.get("object_name") or record.get("filename")
        )
        metadata["priority"] = (
            metadata.get("priority")
            if metadata.get("priority") in {"P1", "P2", "P3", "P4"}
            else "P3"
        )
        metadata["version"] = (
            metadata.get("version")
            if re.match(r"^v[1-9][0-9]*$", str(metadata.get("version")))
            else "v1"
        )
        metadata["artifact_type"] = {"RB": "runbook", "KB": "kedb", "DOC": "documentation"}.get(
            prefix, "documentation"
        )
        metadata["generated_at"] = self._now()
        metadata["generator_version"] = "functional_knowledge_generation_v1.7"
        return {
            "prefix": prefix,
            "metadata": metadata,
            "filename": self._filename(prefix, metadata),
            "note": self._runtime_note(source_map),
        }

    def _doc_metadata(self, record: dict[str, Any]) -> dict[str, Any]:
        metadata = dict(record["metadata"])
        metadata["artifact_type"] = "documentation"
        metadata["object_name"] = self._object_code(
            metadata.get("interface_id")
            or metadata.get("integration_flow_id")
            or metadata.get("object_name")
        )
        metadata["priority"] = "P3"
        metadata["doc_subtype"] = "interface_catalog_document"
        return metadata

    def _render_runbook(self, record: dict[str, Any]) -> str:
        metadata = record["metadata"]
        title = self._title(metadata)
        interface_id = metadata.get("interface_id") or "missing"
        flow_id = metadata.get("integration_flow_id") or interface_id
        return f"""# Runbook - {title}

{self.normalizer.render_block(metadata)}

1. PURPOSE
Provide deterministic operator guidance for {title} on interface `{interface_id}`.

2. BUSINESS CONTEXT
Customer `{metadata.get("customer_id")}` uses system `{metadata.get("system_id")}` in environment `{metadata.get("environment")}`.

3. TECHNICAL LANDSCAPE
- SAP SID: `{metadata.get("sap_sid")}`
- Integration flow id: `{flow_id}`
- Package name: `{metadata.get("package_name") or "missing"}`

4. MONITORING AND MPL EVIDENCE
{record["note"]}
- Do not create MessageGuid, MPL id, endpoint URL or receiver payload values unless present in real logs.

5. ERROR SIGNATURE
- Object/error code: `{metadata.get("object_name")}`
- Priority: `{metadata.get("priority")}`
- Interface id: `{interface_id}`

6. KNOWN ROOT CAUSES
- Check SAP CI/CPI or PI/PO inventory for adapter, receiver and mapping configuration.
- Treat runtime-specific cause as missing until confirmed by MPL/log evidence.

7. PREREQUISITES FOR INVESTIGATION
- Access to SAP monitor and read-only MPL/log files.
- Access to customer context and interface inventory records.

8. DIAGNOSIS STEPS
1. Confirm `interface_id={interface_id}` in interface inventory.
2. Search real MPL/log evidence for `{metadata.get("object_name")}` and `{flow_id}`.
3. Record missing evidence as `missing`; do not infer runtime values.

9. RECOVERY STEPS
1. Resolve only the configuration or data issue confirmed by evidence.
2. Replay messages only according to customer-approved operations policy.
3. Capture post-fix evidence before closing the incident.

10. ESCALATION CRITERIA
- Escalate if runtime evidence is missing for a production-impacting P1/P2 incident.
- Escalate if interface inventory conflicts with SAP inventory.

11. POST-FIX VALIDATION
- Confirm no new failed MPL entries for `{interface_id}`.
- Attach evidence references to the incident record.
"""

    def _render_kedb(self, record: dict[str, Any]) -> str:
        metadata = record["metadata"]
        title = self._title(metadata)
        return f"""# KEDB - {title}

{self.normalizer.render_block(metadata)}

KEDB ID
KEDB-{metadata.get("priority")}-{self._stable_number(metadata)}

KEDB TITLE
{title}

CUSTOMER
{metadata.get("customer_id")}

SYSTEM
{metadata.get("sap_sid")}

PRIORITY
{metadata.get("priority")}

VERSION
{metadata.get("version")}

1. SYMPTOM
- Failure pattern associated with `{metadata.get("object_name")}` for interface `{metadata.get("interface_id") or "missing"}`.

2. ERROR PATTERN
- `{metadata.get("object_name")}`

3. ROOT CAUSE
- Root cause must be confirmed from SAP inventory, customer context or real MPL/log evidence.

4. DIAGNOSIS SIGNALS
- Interface inventory id: `{metadata.get("interface_id") or "missing"}`
- Integration flow id: `{metadata.get("integration_flow_id") or "missing"}`
- Evidence status: {record["note"]}

5. RESOLUTION
- Apply the matching runbook and capture new MPL/log evidence after remediation.

6. VALIDATION
- No repeated failures for the same interface and object code in the validation window.

7. WORKAROUND
- Use customer-approved replay or temporary routing only when documented by operations policy.

8. RELATED ARTIFACTS
- Interface inventory: `{metadata.get("interface_id") or "missing"}`
- Customer context: `{metadata.get("customer_id")}`
"""

    def _render_doc(self, record: dict[str, Any], metadata: dict[str, Any]) -> str:
        title = f"Interface Catalog - {metadata.get('interface_id') or metadata.get('object_name')}"
        return f"""# {title}

{self.normalizer.render_block(metadata)}

DOC ID
DOC-{self._stable_number(metadata)}

DOC TITLE
{title}

1. PURPOSE
Document the interface `{metadata.get("interface_id") or "missing"}` using QDKEP evidence.

2. SCOPE
- Customer: `{metadata.get("customer_id")}`
- System: `{metadata.get("system_id")}`
- SAP SID: `{metadata.get("sap_sid")}`

3. KEY TERMS
- `source-backed`: value is present in package evidence.
- `derived`: value is deterministically derived.
- `missing`: expected evidence is absent.

4. CORE EXPLANATION
This catalog document links the interface to generated RB/KB artifacts and package evidence. Runtime identifiers are not generated unless present in logs.

5. OPERATIONAL RELEVANCE
{record["note"]}
- Use traceability report to determine which fields are source-backed.

6. RELATED ARTIFACTS
- Source artifact: `{record["filename"]}`
- Customer context: `{metadata.get("customer_id")}`
"""

    def _filename(self, prefix: str, metadata: dict[str, Any]) -> str:
        customer = self._token(metadata.get("customer_id"), "RCMO")
        system = self._token(metadata.get("system_id"), "CPI")
        priority = metadata.get("priority", "P3")
        version = metadata.get("version", "v1")
        base = f"{prefix}_{customer}_{system}_"
        suffix = f"_{priority}_{version}.md"
        room = max(8, 80 - len(base) - len(suffix))
        object_code = self._short_token(self._object_code(metadata.get("object_name")), room)
        return f"{base}{object_code}{suffix}"

    def _object_code(self, value: Any) -> str:
        text = Path(str(value or "")).stem.upper()
        text = re.sub(r"^(RB|KB|DOC)_", "", text)
        parts = text.split("_")
        if len(parts) > 5 and parts[0] == "RCMO":
            text = "_".join(parts[2:-2])
        text = re.sub(r"[^A-Z0-9]+", "_", text).strip("_")
        text = re.sub(r"_+", "_", text)
        if (
            not text
            or len(text.split("_")) < 2
            or text in {"ERROR", "OBJECT", "DOC", "RUNBOOK", "KEDB", "UNKNOWN", "GENERAL", "MISC"}
        ):
            text = "INTERFACE_CATALOG"
        return self._short_token(text, 80)

    def _token(self, value: Any, default: str) -> str:
        token = re.sub(r"[^A-Za-z0-9]+", "", str(value or default)).upper()
        return token or default

    def _title(self, metadata: dict[str, Any]) -> str:
        text = str(metadata.get("object_name", "Interface incident"))
        if "API_THROTTLING_RATE_LIMIT_EXCEEDED" in text:
            return "Receiver throttled requests due to API rate limit"
        return text.replace("_", " ").title()

    def _short_token(self, token: str, limit: int) -> str:
        token = re.sub(r"_+", "_", str(token or "").strip("_")) or "INTERFACE_CATALOG"
        if len(token) <= limit:
            return token
        parts = token.split("_")
        kept: list[str] = []
        for part in parts:
            candidate = "_".join([*kept, part]) if kept else part
            if len(candidate) > limit:
                break
            kept.append(part)
        return "_".join(kept) if kept else token[:limit].rstrip("_")

    def _runtime_note(self, source_map: dict[str, Any]) -> str:
        files = source_map.get("mpl_log_files") or []
        if files:
            shown = ", ".join(files[:3])
            suffix = "" if len(files) <= 3 else f" and {len(files) - 3} more"
            return f"- Real MPL/log files are available for matching: {shown}{suffix}. Values must still be copied only from matched log records."
        return "- MPL/log evidence is missing in the package; runtime fields are intentionally marked `missing`."

    def _stable_number(self, metadata: dict[str, Any]) -> str:
        raw = "|".join(
            str(metadata.get(key, ""))
            for key in ["customer_id", "system_id", "interface_id", "object_name", "version"]
        )
        return str(abs(hash(raw)) % 100000).zfill(5)

    def _load_json(self, path: Path) -> dict[str, Any]:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _write(self, path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.rstrip() + "\n", encoding="utf-8")

    def _write_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _copy_tree(self, source: Path, target: Path) -> None:
        if source.exists():
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)

    def _now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
