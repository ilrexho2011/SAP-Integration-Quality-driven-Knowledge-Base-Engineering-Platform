from __future__ import annotations

import json
import shutil
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.contracts import ContractPackageValidator, MetadataNormalizer
from app.services.artifact_router import ArtifactRouter
from app.services.ai4biz_export_adapter import AI4BIZExportAdapter
from app.services.manifest_service import ManifestService
from app.services.package_metadata_service import PackageMetadataService
from app.services.package_quality_gate import PackageQualityGate
from app.services.traceability_service import TraceabilityService


@dataclass(frozen=True)
class PackageBuildResult:
    status: str
    output_zip: str
    package_root: str
    artifact_count: int
    validation_status: str
    promotion_decision: str
    quality_report: str
    package_quality_gate_report: str
    ai4biz_export_root: str
    ai4biz_ingestion_readiness_report: str
    traceability_report: str

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "output_zip": self.output_zip,
            "package_root": self.package_root,
            "artifact_count": self.artifact_count,
            "validation_status": self.validation_status,
            "promotion_decision": self.promotion_decision,
            "quality_report": self.quality_report,
            "package_quality_gate_report": self.package_quality_gate_report,
            "ai4biz_export_root": self.ai4biz_export_root,
            "ai4biz_ingestion_readiness_report": self.ai4biz_ingestion_readiness_report,
            "traceability_report": self.traceability_report,
        }


class PackageBuilder:
    """Builds a contract-compliant QDKEP ZIP package and runs Sprint 8 developer/operator workflows."""

    def __init__(self) -> None:
        self.router = ArtifactRouter()
        self.manifest_service = ManifestService()
        self.metadata_service = PackageMetadataService()
        self.validator = ContractPackageValidator()
        self.quality_gate = PackageQualityGate()
        self.metadata_normalizer = MetadataNormalizer()
        self.ai4biz_export_adapter = AI4BIZExportAdapter()
        self.traceability_service = TraceabilityService()

    def build(
        self,
        source_root: str | Path,
        output_zip: str | Path,
        package_id: str = "quality-driven-knowledge-engineering-platform",
        package_version: str = "1.9",
        package_name: str = "Quality-Driven Knowledge Engineering Platform",
    ) -> PackageBuildResult:
        source = Path(source_root).resolve()
        output = Path(output_zip).resolve()
        with tempfile.TemporaryDirectory(prefix="qdkep_package_build_") as tmp:
            tmp_root = Path(tmp)
            prepared_source = self._prepare_source_root(source, tmp_root / "source")
            artifacts = self.router.route_many(prepared_source)
            if not artifacts:
                raise ValueError(
                    "No Markdown knowledge artifacts found. "
                    f"Input: {source}. Effective source: {prepared_source}. "
                    "Build Package expects an extracted folder, a Markdown file, or a ZIP that contains .md artifacts. "
                    "If you selected an already-built QDKEP package, ensure it contains knowledge/RB, knowledge/KB, or knowledge/DOC Markdown files."
                )
            package_root = tmp_root / f"{package_id}-v{package_version}"
            self._create_layout(package_root)
            for artifact in artifacts:
                target = package_root / artifact.package_relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                self._copy_normalized_markdown(artifact.source_path, target)
            manifest = self.manifest_service.build_manifest(
                artifacts, package_id, package_version, package_name
            )
            metadata = self.metadata_service.build_metadata(
                artifacts, package_id, package_version, package_name, source
            )
            self.manifest_service.write_manifest(manifest, package_root)
            self.metadata_service.write_metadata(metadata, package_root)
            self._write_customer_contexts(package_root, manifest)
            self._write_interface_inventory(package_root, manifest)
            self._copy_evidence_sources(prepared_source, package_root)
            contract_report_path = package_root / "quality" / "contract_validation_report.json"
            self.validator.validate_to_file(package_root, contract_report_path)
            gate_result = self.quality_gate.evaluate_to_file(
                package_root, package_root / "quality" / "package_quality_gate_report.json"
            )
            ai4biz_result = self.ai4biz_export_adapter.export(package_root, package_root)
            traceability_result = self.traceability_service.evaluate_to_file(
                package_root, package_root / "quality" / "traceability_report.json"
            )
            self._zip_folder(package_root, output)
            return PackageBuildResult(
                status="built",
                output_zip=str(output),
                package_root=str(package_root),
                artifact_count=len(artifacts),
                validation_status=gate_result.status,
                promotion_decision=gate_result.promotion_decision,
                quality_report="quality/contract_validation_report.json",
                package_quality_gate_report="quality/package_quality_gate_report.json",
                ai4biz_export_root=".",
                ai4biz_ingestion_readiness_report=ai4biz_result.readiness_report,
                traceability_report=traceability_result.report_path
                if traceability_result.report_path.startswith("quality/")
                else "quality/traceability_report.json",
            )

    def _prepare_source_root(self, source: Path, extraction_root: Path) -> Path:
        """Return a buildable source path.

        The dashboard can pass either an extracted folder, a single Markdown file,
        or an already-built QDKEP ZIP package. The original implementation only
        scanned folders/files directly, so ZIP inputs produced an empty artifact
        list and the API returned HTTP 400. ZIP inputs are now extracted into the
        build workspace and scanned there.
        """
        if source.is_dir():
            return source
        if source.is_file() and source.suffix.lower() == ".md":
            return source
        if source.is_file() and source.suffix.lower() == ".zip":
            extraction_root.mkdir(parents=True, exist_ok=True)
            self._safe_extract_zip(source, extraction_root)
            return self._select_extracted_source_root(extraction_root)
        raise ValueError(
            f"Unsupported source_root for package build: {source}. "
            "Expected an extracted folder, a .md file, or a .zip package."
        )

    def _safe_extract_zip(self, source_zip: Path, destination: Path) -> None:
        destination_resolved = destination.resolve()
        try:
            with zipfile.ZipFile(source_zip) as zf:
                for member in zf.infolist():
                    member_path = destination / member.filename
                    resolved_member_path = member_path.resolve()
                    if not str(resolved_member_path).startswith(str(destination_resolved)):
                        raise ValueError(f"Unsafe ZIP member path rejected: {member.filename}")
                zf.extractall(destination)
        except zipfile.BadZipFile as exc:
            raise ValueError(f"Invalid ZIP package: {source_zip}") from exc

    def _select_extracted_source_root(self, extraction_root: Path) -> Path:
        children = [path for path in extraction_root.iterdir() if path.name not in {"__MACOSX"}]
        dirs = [path for path in children if path.is_dir()]
        files = [path for path in children if path.is_file()]
        if len(dirs) == 1 and not files:
            return dirs[0]
        return extraction_root

    def _copy_evidence_sources(self, source: Path, package_root: Path) -> None:
        optional_dirs = [
            ("logs/mpl", "logs/mpl"),
            ("resources/mpl", "resources/mpl"),
            ("sap_ci", "sap_ci"),
            ("sap_pipo", "sap_pipo"),
            ("sap_ci_cpi", "sap_ci_cpi"),
            ("sap_pi_po", "sap_pi_po"),
            ("inventory", "inventory"),
        ]
        for src_rel, dst_rel in optional_dirs:
            src = source / src_rel
            if src.exists() and src.is_dir():
                dst = package_root / dst_rel
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)

    def _copy_normalized_markdown(self, source: Path, target: Path) -> None:
        text = source.read_text(encoding="utf-8", errors="replace")
        metadata = self.metadata_normalizer.parse_markdown_metadata(text)
        if not metadata:
            shutil.copy2(source, target)
            return
        lines = text.splitlines()
        start: int | None = None
        end: int | None = None
        metadata_keys = set(metadata)
        for idx, line in enumerate(lines):
            stripped = line.strip()
            is_meta_line = any(stripped.startswith(f"{key}:") for key in metadata_keys)
            if start is None and is_meta_line:
                start = idx
            elif start is not None and stripped and not is_meta_line:
                end = idx
                break
        if start is None:
            shutil.copy2(source, target)
            return
        if end is None:
            end = len(lines)
        normalized_block = self.metadata_normalizer.render_block(metadata).splitlines()
        new_lines = lines[:start] + normalized_block + [""] + lines[end:]
        target.write_text("\n".join(new_lines).rstrip() + "\n", encoding="utf-8")

    def _create_layout(self, package_root: Path) -> None:
        for rel in [
            "knowledge/RB",
            "knowledge/KB",
            "knowledge/DOC",
            "customer",
            "interface_inventory",
            "quality",
        ]:
            (package_root / rel).mkdir(parents=True, exist_ok=True)

    def _write_customer_contexts(self, package_root: Path, manifest: dict[str, Any]) -> None:
        customers: dict[str, dict[str, Any]] = {}
        for artifact in manifest.get("artifacts", []):
            metadata = artifact.get("metadata", {}) if isinstance(artifact, dict) else {}
            customer_id = str(metadata.get("customer_id", "")).strip()
            if not customer_id:
                continue
            system_id = str(metadata.get("system_id", "")).strip()
            sap_sid = str(metadata.get("sap_sid", "")).strip()
            environment = str(metadata.get("environment", "")).strip() or "unknown"
            entry = customers.setdefault(
                customer_id,
                {
                    "customer_id": customer_id,
                    "customer_name": customer_id,
                    "environment": environment,
                    "systems": {},
                    "governance": {
                        "source": "generated_from_artifact_metadata",
                        "credential_policy": "No credentials are stored in customer context files.",
                    },
                },
            )
            if environment and entry.get("environment") == "unknown":
                entry["environment"] = environment
            if system_id:
                entry["systems"].setdefault(
                    system_id,
                    {
                        "system_id": system_id,
                        "sap_sid": sap_sid,
                        "description": f"System referenced by QDKEP artifacts for customer {customer_id}",
                    },
                )
        for customer_id, data in sorted(customers.items()):
            data["systems"] = [data["systems"][key] for key in sorted(data["systems"])]
            path = package_root / "customer" / f"{customer_id}.yaml"
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _write_interface_inventory(self, package_root: Path, manifest: dict[str, Any]) -> None:
        interfaces: dict[str, dict[str, Any]] = {}
        for artifact in manifest.get("artifacts", []):
            metadata = artifact.get("metadata", {}) if isinstance(artifact, dict) else {}
            interface_id = str(metadata.get("interface_id", "")).strip()
            if not interface_id:
                continue
            interfaces.setdefault(
                interface_id,
                {
                    "interface_id": interface_id,
                    "interface_name": str(metadata.get("interface_name", "")).strip()
                    or interface_id,
                    "customer_id": str(metadata.get("customer_id", "")).strip(),
                    "system_id": str(metadata.get("system_id", "")).strip(),
                    "sap_sid": str(metadata.get("sap_sid", "")).strip(),
                    "integration_flow_id": str(metadata.get("integration_flow_id", "")).strip()
                    or interface_id,
                    "integration_flow_name": str(metadata.get("integration_flow_name", "")).strip()
                    or interface_id,
                    "package_name": str(metadata.get("package_name", "")).strip(),
                    "owner": "AI4BIZ_QDKEP",
                    "source": "generated_from_artifact_metadata",
                    "artifact_references": [],
                },
            )["artifact_references"].append(artifact.get("filename"))
        inventory = {
            "schema_version": "1.0",
            "source": "generated_from_manifest_artifacts",
            "interfaces": [interfaces[key] for key in sorted(interfaces)],
        }
        path = package_root / "interface_inventory" / "interface_inventory.json"
        path.write_text(
            json.dumps(inventory, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    def _zip_folder(self, package_root: Path, output_zip: Path) -> None:
        output_zip.parent.mkdir(parents=True, exist_ok=True)
        if output_zip.exists():
            output_zip.unlink()
        with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(package_root.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(package_root).as_posix())
