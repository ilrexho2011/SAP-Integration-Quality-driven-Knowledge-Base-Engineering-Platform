from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AI4BIZExportResult:
    status: str
    promotion_decision: str
    export_root: str
    upload_manifest: str
    readiness_report: str
    document_count: int
    blocked_reason_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "promotion_decision": self.promotion_decision,
            "export_root": self.export_root,
            "upload_manifest": self.upload_manifest,
            "readiness_report": self.readiness_report,
            "document_count": self.document_count,
            "blocked_reason_count": self.blocked_reason_count,
        }


class AI4BIZExportAdapter:
    """Create deterministic AI4BIZ RAG Console upload payloads from an approved QDKEP package.

    Output layout:
    - upload_manifest.json
    - documents/<artifact_filename>.md
    - metadata/<artifact_stem>.metadata.json
    - quality/ai4biz_ingestion_readiness_report.json
    """

    APPROVED_DECISION = "approved_for_ai4biz_ingestion"
    READY_DECISION = "ready_for_ai4biz_rag_console_upload"
    BLOCKED_DECISION = "blocked"

    PREFIX_MAPPING: dict[str, dict[str, str]] = {
        "RB": {
            "document_type": "runbook",
            "artifact_type": "RB",
            "chunk_mode": "heading_aware_runbook",
        },
        "KB": {
            "document_type": "knowledge_base_entry",
            "artifact_type": "KB",
            "chunk_mode": "heading_aware_kedb",
        },
        "DOC": {
            "document_type": "documentation",
            "artifact_type": "DOC",
            "chunk_mode": "heading_aware_documentation",
        },
    }

    CRITICAL_METADATA_FIELDS = [
        "environment",
        "customer_id",
        "system_id",
        "sap_sid",
        "artifact_type",
        "object_name",
        "priority",
        "version",
        "interface_id",
    ]

    def export(
        self,
        package_path: str | Path,
        output_root: str | Path | None = None,
    ) -> AI4BIZExportResult:
        source = Path(package_path)
        if source.is_file() and source.suffix.lower() == ".zip":
            with tempfile.TemporaryDirectory(prefix="qdkep_ai4biz_export_") as tmp:
                with zipfile.ZipFile(source) as zf:
                    zf.extractall(tmp)
                root = self._detect_root(Path(tmp))
                target = (
                    Path(output_root) if output_root else source.with_suffix("") / "ai4biz_export"
                )
                return self._export_folder(root, target)
        return self._export_folder(
            source, Path(output_root) if output_root else source / "ai4biz_export"
        )

    def _export_folder(self, package_root: Path, output_root: Path) -> AI4BIZExportResult:
        output_root.mkdir(parents=True, exist_ok=True)
        documents_dir = output_root / "documents"
        metadata_dir = output_root / "metadata"
        quality_dir = output_root / "quality"
        for folder in (documents_dir, metadata_dir, quality_dir):
            folder.mkdir(parents=True, exist_ok=True)

        manifest = self._load_json(package_root / "manifest.json")
        package_metadata = self._load_json(package_root / "package_metadata.json")
        quality_gate_report = self._load_json(
            package_root / "quality" / "package_quality_gate_report.json"
        )

        blocking_reasons: list[dict[str, Any]] = []
        package_decision = self._package_decision(manifest, package_metadata, quality_gate_report)
        if package_decision != self.APPROVED_DECISION:
            blocking_reasons.append(
                self._issue(
                    "package",
                    "promotion_decision",
                    "critical",
                    f"Package promotion_decision is {package_decision or 'missing'}, expected {self.APPROVED_DECISION}",
                    "Run PackageQualityGate and export only approved packages.",
                )
            )

        artifact_entries = manifest.get("artifacts", []) if isinstance(manifest, dict) else []
        if not isinstance(artifact_entries, list) or not artifact_entries:
            blocking_reasons.append(
                self._issue(
                    "manifest.json",
                    "upload_manifest_contract",
                    "critical",
                    "manifest.artifacts is missing or empty",
                    "Build a package with one manifest entry per knowledge artifact.",
                )
            )
            artifact_entries = []

        upload_documents: list[dict[str, Any]] = []
        used_document_names: set[str] = set()
        for index, artifact in enumerate(artifact_entries, start=1):
            if not isinstance(artifact, dict):
                blocking_reasons.append(
                    self._issue(
                        "manifest.json",
                        "artifact_entry",
                        "critical",
                        "Artifact entry is not an object",
                        "Regenerate manifest.json.",
                    )
                )
                continue
            rel = str(artifact.get("filename", "")).strip()
            source_file = package_root / rel
            prefix = str(artifact.get("artifact_type_prefix", "")).strip().upper()
            mapping = self.PREFIX_MAPPING.get(prefix)
            if not mapping:
                blocking_reasons.append(
                    self._issue(
                        rel or f"artifact[{index}]",
                        "artifact_type_mapping",
                        "critical",
                        f"Unsupported artifact_type_prefix: {prefix or 'missing'}",
                        "Use RB, KB, or DOC artifact prefixes.",
                    )
                )
                continue
            if not source_file.exists():
                blocking_reasons.append(
                    self._issue(
                        rel,
                        "artifact_file",
                        "critical",
                        "Artifact file referenced by manifest does not exist",
                        "Ensure every manifest artifact filename exists in the package.",
                    )
                )
                continue
            metadata = (
                artifact.get("metadata", {})
                if isinstance(artifact.get("metadata", {}), dict)
                else {}
            )
            missing = [
                field
                for field in self.CRITICAL_METADATA_FIELDS
                if not str(metadata.get(field, "")).strip()
            ]
            if missing:
                blocking_reasons.append(
                    self._issue(
                        rel,
                        "critical_metadata",
                        "critical",
                        f"Missing critical metadata fields: {', '.join(missing)}",
                        "Regenerate the artifact metadata block before AI4BIZ export.",
                    )
                )
                continue
            document_name = self._unique_document_name(source_file.name, used_document_names)
            target_document = documents_dir / document_name
            shutil.copy2(source_file, target_document)
            document_id = self._document_id(metadata, source_file, artifact)
            metadata_name = f"{Path(document_name).stem}.metadata.json"
            metadata_rel = f"metadata/{metadata_name}"
            document_rel = f"documents/{document_name}"
            document_metadata = self._document_metadata(
                document_id=document_id,
                artifact=artifact,
                mapping=mapping,
                source_rel=rel,
                document_rel=document_rel,
                metadata_rel=metadata_rel,
                sha256=self._sha256(target_document),
            )
            (metadata_dir / metadata_name).write_text(
                json.dumps(document_metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            upload_documents.append(
                {
                    "document_id": document_id,
                    "document_path": document_rel,
                    "metadata_path": metadata_rel,
                    "document_type": mapping["document_type"],
                    "artifact_type": mapping["artifact_type"],
                    "chunk_mode": mapping["chunk_mode"],
                    "customer_id": document_metadata["customer_id"],
                    "interface_id": document_metadata["interface_id"],
                    "sha256": document_metadata["sha256"],
                }
            )

        status = "ready" if not blocking_reasons and upload_documents else "blocked"
        decision = self.READY_DECISION if status == "ready" else self.BLOCKED_DECISION
        upload_manifest = self._upload_manifest(
            package_root,
            manifest,
            package_metadata,
            quality_gate_report,
            upload_documents,
            status,
            decision,
        )
        upload_manifest_path = output_root / "upload_manifest.json"
        upload_manifest_path.write_text(
            json.dumps(upload_manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        report = self._readiness_report(
            package_root, status, decision, upload_documents, blocking_reasons, quality_gate_report
        )
        report_path = quality_dir / "ai4biz_ingestion_readiness_report.json"
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        return AI4BIZExportResult(
            status=status,
            promotion_decision=decision,
            export_root=str(output_root),
            upload_manifest="upload_manifest.json",
            readiness_report="quality/ai4biz_ingestion_readiness_report.json",
            document_count=len(upload_documents),
            blocked_reason_count=len(blocking_reasons),
        )

    def _document_metadata(
        self,
        document_id: str,
        artifact: dict[str, Any],
        mapping: dict[str, str],
        source_rel: str,
        document_rel: str,
        metadata_rel: str,
        sha256: str,
    ) -> dict[str, Any]:
        raw_metadata = (
            artifact.get("metadata", {}) if isinstance(artifact.get("metadata", {}), dict) else {}
        )
        return {
            "metadata_schema_version": "ai4biz_rag_console_v1",
            "document_id": document_id,
            "document_path": document_rel,
            "metadata_path": metadata_rel,
            "source_package_path": source_rel,
            "document_type": mapping["document_type"],
            "artifact_type": mapping["artifact_type"],
            "chunk_mode": mapping["chunk_mode"],
            "chunking_contract": {
                "mode": mapping["chunk_mode"],
                "preserve_headings": True,
                "one_file_one_artifact": True,
            },
            "customer_id": str(raw_metadata.get("customer_id", "")).strip(),
            "environment": str(raw_metadata.get("environment", "")).strip(),
            "system_id": str(raw_metadata.get("system_id", "")).strip(),
            "sap_sid": str(raw_metadata.get("sap_sid", "")).strip(),
            "interface_id": str(raw_metadata.get("interface_id", "")).strip(),
            "interface_name": str(raw_metadata.get("interface_name", "")).strip(),
            "integration_flow_id": str(raw_metadata.get("integration_flow_id", "")).strip(),
            "integration_flow_name": str(raw_metadata.get("integration_flow_name", "")).strip(),
            "package_name": str(raw_metadata.get("package_name", "")).strip(),
            "object_name": str(raw_metadata.get("object_name", "")).strip(),
            "priority": str(raw_metadata.get("priority", "")).strip(),
            "version": str(raw_metadata.get("version", "")).strip(),
            "review_cycle": str(raw_metadata.get("review_cycle", "")).strip(),
            "review_status": str(raw_metadata.get("review_status", "")).strip(),
            "sha256": sha256,
            "source_sha256": str(artifact.get("sha256", "")).strip(),
        }

    def _upload_manifest(
        self,
        package_root: Path,
        manifest: dict[str, Any],
        package_metadata: dict[str, Any],
        quality_gate_report: dict[str, Any],
        documents: list[dict[str, Any]],
        status: str,
        decision: str,
    ) -> dict[str, Any]:
        return {
            "upload_manifest_version": "ai4biz_rag_console_upload_v1",
            "generated_at": self._now(),
            "source_package": {
                "package_id": manifest.get("package_id") or package_metadata.get("package_id"),
                "package_name": manifest.get("package_name")
                or package_metadata.get("package_name"),
                "package_version": manifest.get("package_version")
                or package_metadata.get("package_version"),
                "package_path": str(package_root),
                "promotion_decision": self._package_decision(
                    manifest, package_metadata, quality_gate_report
                ),
                "quality_gate_status": quality_gate_report.get("status"),
            },
            "status": status,
            "promotion_decision": decision,
            "target": "AI4BIZ_RAG_Console",
            "documents_root": "documents",
            "metadata_root": "metadata",
            "quality_report": "quality/ai4biz_ingestion_readiness_report.json",
            "document_count": len(documents),
            "documents": documents,
        }

    def _readiness_report(
        self,
        package_root: Path,
        status: str,
        decision: str,
        documents: list[dict[str, Any]],
        blocking_reasons: list[dict[str, Any]],
        quality_gate_report: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "report_type": "ai4biz_ingestion_readiness_report",
            "generated_at": self._now(),
            "package_path": str(package_root),
            "status": status,
            "promotion_decision": decision,
            "quality_gate_status": quality_gate_report.get("status"),
            "source_promotion_decision": quality_gate_report.get("promotion_decision"),
            "summary": {
                "document_count": len(documents),
                "metadata_file_count": len(documents),
                "blocking_reason_count": len(blocking_reasons),
                "document_type_counts": self._type_counts(documents),
            },
            "deterministic_mapping": self.PREFIX_MAPPING,
            "critical_metadata_fields": self.CRITICAL_METADATA_FIELDS,
            "blocking_reasons": blocking_reasons,
            "documents": documents,
        }

    def _type_counts(self, documents: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for doc in documents:
            key = str(doc.get("artifact_type", "unknown"))
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items()))

    def _package_decision(
        self,
        manifest: dict[str, Any],
        package_metadata: dict[str, Any],
        quality_gate_report: dict[str, Any],
    ) -> str:
        for source in (quality_gate_report, manifest, package_metadata):
            value = source.get("promotion_decision") if isinstance(source, dict) else None
            if value:
                return str(value)
        return ""

    def _document_id(
        self, metadata: dict[str, Any], source_file: Path, artifact: dict[str, Any]
    ) -> str:
        seed = "|".join(
            [
                str(metadata.get("customer_id", "")).strip(),
                str(metadata.get("system_id", "")).strip(),
                str(metadata.get("interface_id", "")).strip(),
                source_file.name,
                str(artifact.get("sha256", "")).strip(),
            ]
        )
        digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
        return f"AI4BIZ-{digest}"

    def _unique_document_name(self, filename: str, used: set[str]) -> str:
        if filename not in used:
            used.add(filename)
            return filename
        stem = Path(filename).stem
        suffix = Path(filename).suffix
        index = 2
        while f"{stem}-{index}{suffix}" in used:
            index += 1
        name = f"{stem}-{index}{suffix}"
        used.add(name)
        return name

    def _issue(
        self, artifact: str, category: str, severity: str, message: str, recommendation: str
    ) -> dict[str, Any]:
        return {
            "artifact": artifact,
            "category": category,
            "severity": severity,
            "message": message,
            "recommendation": recommendation,
        }

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    def _detect_root(self, folder: Path) -> Path:
        children = [child for child in folder.iterdir() if child.is_dir()]
        if len(children) == 1 and not (folder / "manifest.json").exists():
            return children[0]
        return folder

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
