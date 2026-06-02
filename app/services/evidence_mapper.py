from __future__ import annotations

import json
import re
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from collections.abc import Iterable


@dataclass(frozen=True)
class EvidenceMappingResult:
    status: str
    artifact_count: int
    source_backed_count: int
    derived_count: int
    missing_count: int
    assumption_count: int
    mappings: list[dict[str, Any]]
    source_map: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "artifact_count": self.artifact_count,
            "evidence_status_counts": {
                "source-backed": self.source_backed_count,
                "derived": self.derived_count,
                "missing": self.missing_count,
                "assumption": self.assumption_count,
            },
            "source_map": self.source_map,
            "mappings": self.mappings,
        }


class EvidenceMapper:
    """Maps each QDKEP artifact to available evidence without fabricating runtime values.

    Evidence status semantics:
    - source-backed: a value is backed by a concrete package source such as manifest metadata,
      customer config, interface_inventory, SAP inventory export, or MPL/log file content.
    - derived: a value is deterministic from filename/path/prefix only.
    - missing: an expected evidence source or field is not present.
    - assumption: retained only for explicit upstream fields whose source says generated/placeholder.
    """

    SAP_CI_CPI_PATTERNS = (
        "sap_ci_inventory*.json",
        "sap_cpi_inventory*.json",
        "cpi_inventory*.json",
        "integration_suite_inventory*.json",
        "ci_cpi_inventory*.json",
    )
    SAP_PIPO_PATTERNS = (
        "sap_pipo_inventory*.json",
        "pipo_inventory*.json",
        "pi_po_inventory*.json",
        "esr_dir_inventory*.json",
    )
    MPL_PATTERNS = ("*.json", "*.log", "*.txt", "*.csv")

    def map_package(self, package_path: str | Path) -> EvidenceMappingResult:
        source = Path(package_path)
        if source.is_file() and source.suffix.lower() == ".zip":
            with tempfile.TemporaryDirectory(prefix="qdkep_traceability_map_") as tmp:
                with zipfile.ZipFile(source) as zf:
                    zf.extractall(tmp)
                return self._map_folder(self._detect_root(Path(tmp)))
        return self._map_folder(source)

    def _map_folder(self, package_root: Path) -> EvidenceMappingResult:
        manifest = self._load_json(package_root / "manifest.json")
        package_metadata = self._load_json(package_root / "package_metadata.json")
        interface_inventory = self._load_json(
            package_root / "interface_inventory" / "interface_inventory.json"
        )
        customer_contexts = self._load_customer_contexts(package_root / "customer")
        sap_ci_inventory = self._load_inventory(
            package_root,
            self.SAP_CI_CPI_PATTERNS,
            [
                "sap_ci_inventory",
                "sap_cpi_inventory",
                "cpi_inventory",
                "inventories/sap_ci",
                "inventories/cpi",
            ],
        )
        sap_pipo_inventory = self._load_inventory(
            package_root,
            self.SAP_PIPO_PATTERNS,
            [
                "sap_pipo_inventory",
                "pipo_inventory",
                "pi_po_inventory",
                "inventories/sap_pipo",
                "inventories/pipo",
            ],
        )
        mpl_sources = self._load_mpl_sources(package_root)

        source_map = {
            "package_root": str(package_root),
            "manifest": self._source_entry(package_root / "manifest.json"),
            "package_metadata": self._source_entry(package_root / "package_metadata.json"),
            "customer_contexts": {
                "count": len(customer_contexts),
                "files": [ctx["source_path"] for ctx in customer_contexts.values()],
            },
            "interface_inventory": {
                "available": bool(interface_inventory),
                "path": "interface_inventory/interface_inventory.json"
                if interface_inventory
                else None,
                "interface_count": len(self._interface_entries(interface_inventory)),
            },
            "sap_ci_cpi_inventory": {
                "available": bool(sap_ci_inventory),
                "files": [item["source_path"] for item in sap_ci_inventory],
            },
            "sap_pipo_inventory": {
                "available": bool(sap_pipo_inventory),
                "files": [item["source_path"] for item in sap_pipo_inventory],
            },
            "mpl_logs": {
                "available": bool(mpl_sources),
                "files": [item["source_path"] for item in mpl_sources],
            },
        }

        interface_index = self._index_interfaces(interface_inventory)
        mappings: list[dict[str, Any]] = []
        counts = {"source-backed": 0, "derived": 0, "missing": 0, "assumption": 0}
        artifacts = manifest.get("artifacts", []) if isinstance(manifest, dict) else []
        if not isinstance(artifacts, list):
            artifacts = []

        for artifact in artifacts:
            if not isinstance(artifact, dict):
                continue
            mapping = self._map_artifact(
                package_root=package_root,
                artifact=artifact,
                package_metadata=package_metadata,
                interface_index=interface_index,
                customer_contexts=customer_contexts,
                sap_ci_inventory=sap_ci_inventory,
                sap_pipo_inventory=sap_pipo_inventory,
                mpl_sources=mpl_sources,
            )
            mappings.append(mapping)
            for evidence in mapping["evidence"]:
                counts[evidence["status"]] = counts.get(evidence["status"], 0) + 1

        status = (
            "traceable"
            if mappings and counts.get("missing", 0) == 0
            else ("partial_traceability" if mappings else "blocked")
        )
        return EvidenceMappingResult(
            status=status,
            artifact_count=len(mappings),
            source_backed_count=counts.get("source-backed", 0),
            derived_count=counts.get("derived", 0),
            missing_count=counts.get("missing", 0),
            assumption_count=counts.get("assumption", 0),
            mappings=mappings,
            source_map=source_map,
        )

    def _map_artifact(
        self,
        package_root: Path,
        artifact: dict[str, Any],
        package_metadata: dict[str, Any],
        interface_index: dict[str, dict[str, Any]],
        customer_contexts: dict[str, dict[str, Any]],
        sap_ci_inventory: list[dict[str, Any]],
        sap_pipo_inventory: list[dict[str, Any]],
        mpl_sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        rel = str(artifact.get("filename", "")).strip()
        metadata = (
            artifact.get("metadata", {}) if isinstance(artifact.get("metadata", {}), dict) else {}
        )
        interface_id = str(metadata.get("interface_id", "")).strip()
        customer_id = str(metadata.get("customer_id", "")).strip()
        object_name = str(metadata.get("object_name", "")).strip()
        integration_flow_id = str(metadata.get("integration_flow_id", "")).strip()
        prefix = str(artifact.get("artifact_type_prefix", "")).strip().upper()
        artifact_path = package_root / rel
        evidence: list[dict[str, Any]] = []

        evidence.append(
            self._evidence(
                "artifact_file",
                "source-backed" if artifact_path.exists() else "missing",
                rel,
                "manifest.json",
                "Manifest references a package artifact file."
                if artifact_path.exists()
                else "Manifest references a file that is not present.",
                {"sha256": artifact.get("sha256"), "bytes": artifact.get("bytes")},
            )
        )
        evidence.append(
            self._evidence(
                "artifact_type",
                "source-backed" if metadata.get("artifact_type") else "derived",
                str(metadata.get("artifact_type") or artifact.get("artifact_type") or prefix),
                "artifact metadata" if metadata.get("artifact_type") else "filename prefix/router",
                "Artifact type comes from metadata when present; otherwise from deterministic RB/KB/DOC routing.",
            )
        )
        for field in [
            "environment",
            "customer_id",
            "system_id",
            "sap_sid",
            "object_name",
            "priority",
            "version",
            "interface_id",
        ]:
            value = str(metadata.get(field, "")).strip()
            evidence.append(
                self._evidence(
                    f"metadata.{field}",
                    "source-backed" if value else "missing",
                    value,
                    "artifact metadata block",
                    f"Artifact metadata field {field} is {'present' if value else 'missing'}.",
                )
            )

        customer = customer_contexts.get(customer_id)
        evidence.append(
            self._evidence(
                "customer_context",
                "source-backed" if customer else "missing",
                customer_id,
                customer.get("source_path") if customer else "customer/<CUSTOMER>.yaml",
                "Customer context file exists for artifact customer_id."
                if customer
                else "No customer context file found for artifact customer_id.",
                {
                    "customer_name": customer.get("customer_name"),
                    "environment": customer.get("environment"),
                }
                if customer
                else {},
            )
        )

        interface = interface_index.get(interface_id)
        evidence.append(
            self._evidence(
                "interface_inventory",
                "source-backed" if interface else "missing",
                interface_id,
                "interface_inventory/interface_inventory.json",
                "Interface id is present in interface inventory."
                if interface
                else "Interface id is absent from interface inventory.",
                self._redact_large(interface) if interface else {},
            )
        )

        ci_match = self._find_inventory_match(
            sap_ci_inventory, [interface_id, integration_flow_id, object_name]
        )
        pipo_match = self._find_inventory_match(
            sap_pipo_inventory, [interface_id, integration_flow_id, object_name]
        )
        evidence.append(
            self._evidence(
                "sap_ci_cpi_inventory",
                "source-backed" if ci_match else "missing",
                interface_id or integration_flow_id or object_name,
                ci_match.get("source_path") if ci_match else "sap_ci/cpi inventory export",
                "Artifact identifiers matched SAP CI/CPI inventory export."
                if ci_match
                else "No SAP CI/CPI inventory export entry matched artifact identifiers.",
                ci_match.get("match", {}) if ci_match else {},
            )
        )
        evidence.append(
            self._evidence(
                "sap_pipo_inventory",
                "source-backed" if pipo_match else "missing",
                interface_id or integration_flow_id or object_name,
                pipo_match.get("source_path") if pipo_match else "sap_pi_po inventory export",
                "Artifact identifiers matched SAP PI/PO inventory export."
                if pipo_match
                else "No SAP PI/PO inventory export entry matched artifact identifiers.",
                pipo_match.get("match", {}) if pipo_match else {},
            )
        )
        mpl_match = self._find_text_match(
            mpl_sources,
            [
                interface_id,
                integration_flow_id,
                object_name,
                str(metadata.get("error_pattern", "")).strip(),
            ],
        )
        evidence.append(
            self._evidence(
                "mpl_runtime_logs",
                "source-backed" if mpl_match else "missing",
                interface_id or integration_flow_id or object_name,
                mpl_match.get("source_path") if mpl_match else "logs/mpl or resources/mpl",
                "Artifact identifiers matched MPL/log evidence."
                if mpl_match
                else "No MPL/log file matched artifact identifiers; runtime fields must not be fabricated.",
                {"matched_terms": mpl_match.get("matched_terms", [])} if mpl_match else {},
            )
        )

        generated_sources = []
        for source in [
            interface.get("source") if interface else None,
            customer.get("governance", {}).get("source")
            if customer and isinstance(customer.get("governance"), dict)
            else None,
        ]:
            if source and "generated" in str(source):
                generated_sources.append(str(source))
        if generated_sources:
            evidence.append(
                self._evidence(
                    "generated_source_notice",
                    "assumption",
                    ", ".join(generated_sources),
                    "customer/interface generated metadata",
                    "Some package support files were generated from artifact metadata; treat them as traceable but not independent runtime evidence.",
                )
            )

        return {
            "artifact_path": rel,
            "artifact_type_prefix": prefix,
            "document_id": self._document_id(metadata, rel),
            "customer_id": customer_id,
            "interface_id": interface_id,
            "object_name": object_name,
            "evidence_summary": self._summary(evidence),
            "evidence": evidence,
        }

    def _load_json(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _load_customer_contexts(self, customer_dir: Path) -> dict[str, dict[str, Any]]:
        result: dict[str, dict[str, Any]] = {}
        if not customer_dir.exists():
            return result
        for path in sorted(customer_dir.glob("*.yaml")):
            # Sprint 3 writes JSON-compatible YAML; parse as JSON deterministically.
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                data = self._parse_simple_yaml(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                customer_id = str(data.get("customer_id") or path.stem).strip()
                data["source_path"] = path.relative_to(customer_dir.parent).as_posix()
                result[customer_id] = data
        return result

    def _parse_simple_yaml(self, text: str) -> dict[str, Any]:
        data: dict[str, Any] = {}
        for line in text.splitlines():
            if ":" in line and not line.startswith(" "):
                key, value = line.split(":", 1)
                data[key.strip()] = value.strip().strip('"').strip("'")
        return data

    def _load_inventory(
        self, package_root: Path, patterns: Iterable[str], folders: Iterable[str]
    ) -> list[dict[str, Any]]:
        files: set[Path] = set()
        for pattern in patterns:
            files.update(package_root.glob(pattern))
            files.update(package_root.glob(f"**/{pattern}"))
        for folder in folders:
            base = package_root / folder
            if base.exists():
                files.update(path for path in base.rglob("*.json") if path.is_file())
        result: list[dict[str, Any]] = []
        for path in sorted(files):
            if self._is_generated_ai4biz_or_quality(path):
                continue
            text = path.read_text(encoding="utf-8", errors="replace")[:5_000_000]
            try:
                parsed = json.loads(text)
            except Exception:
                parsed = None
            result.append(
                {
                    "source_path": path.relative_to(package_root).as_posix(),
                    "text": text,
                    "json": parsed,
                }
            )
        return result

    def _load_mpl_sources(self, package_root: Path) -> list[dict[str, Any]]:
        candidates: set[Path] = set()
        for folder in ["logs/mpl", "resources/mpl", "mpl", "runtime/mpl", "evidence/mpl"]:
            base = package_root / folder
            if base.exists():
                for pattern in self.MPL_PATTERNS:
                    candidates.update(path for path in base.rglob(pattern) if path.is_file())
        result = []
        for path in sorted(candidates):
            text = path.read_text(encoding="utf-8", errors="replace")[:5_000_000]
            result.append({"source_path": path.relative_to(package_root).as_posix(), "text": text})
        return result

    def _interface_entries(self, inventory: dict[str, Any]) -> list[dict[str, Any]]:
        entries = inventory.get("interfaces", []) if isinstance(inventory, dict) else []
        return entries if isinstance(entries, list) else []

    def _index_interfaces(self, inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
        index = {}
        for entry in self._interface_entries(inventory):
            if not isinstance(entry, dict):
                continue
            interface_id = str(entry.get("interface_id", "")).strip()
            if interface_id:
                index[interface_id] = entry
        return index

    def _find_inventory_match(
        self, inventories: list[dict[str, Any]], terms: Iterable[str]
    ) -> dict[str, Any] | None:
        clean_terms = [term for term in (str(t).strip() for t in terms) if term]
        if not clean_terms:
            return None
        for inventory in inventories:
            text = inventory.get("text", "")
            for term in clean_terms:
                if term and term in text:
                    return {
                        "source_path": inventory["source_path"],
                        "match": {"matched_term": term},
                    }
        return None

    def _find_text_match(
        self, sources: list[dict[str, Any]], terms: Iterable[str]
    ) -> dict[str, Any] | None:
        clean_terms = [term for term in (str(t).strip() for t in terms) if term]
        if not clean_terms:
            return None
        for source in sources:
            text = source.get("text", "")
            matched = [term for term in clean_terms if term and term in text]
            if matched:
                return {"source_path": source["source_path"], "matched_terms": matched[:10]}
        return None

    def _evidence(
        self,
        category: str,
        status: str,
        value: str,
        source: str | None,
        rationale: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return {
            "category": category,
            "status": status,
            "value": value,
            # source may arrive as None when a dict.get("source_path") returns
            # None; normalize to an empty string so the evidence record always
            # carries a string source.
            "source": source or "",
            "rationale": rationale,
            "details": details or {},
        }

    def _summary(self, evidence: list[dict[str, Any]]) -> dict[str, int]:
        counts = {"source-backed": 0, "derived": 0, "missing": 0, "assumption": 0}
        for item in evidence:
            counts[item["status"]] = counts.get(item["status"], 0) + 1
        return counts

    def _source_entry(self, path: Path) -> dict[str, Any]:
        return {"available": path.exists(), "path": path.name if path.exists() else None}

    def _document_id(self, metadata: dict[str, Any], rel: str) -> str:
        base = "|".join(
            str(metadata.get(k, "")).strip()
            for k in ["customer_id", "system_id", "interface_id", "object_name", "version"]
        )
        if not base.strip("|"):
            base = rel
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", base).strip("_")[:160]

    def _detect_root(self, extracted: Path) -> Path:
        if (extracted / "manifest.json").exists():
            return extracted
        candidates = [
            path
            for path in extracted.iterdir()
            if path.is_dir() and (path / "manifest.json").exists()
        ]
        return candidates[0] if candidates else extracted

    def _is_generated_ai4biz_or_quality(self, path: Path) -> bool:
        text = path.as_posix()
        return (
            "/metadata/" in text
            or "/quality/" in text
            or text.endswith("upload_manifest.json")
            or text.endswith("manifest.json")
            or text.endswith("package_metadata.json")
        )

    def _redact_large(self, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        allowed = [
            "interface_id",
            "interface_name",
            "customer_id",
            "system_id",
            "sap_sid",
            "integration_flow_id",
            "integration_flow_name",
            "package_name",
            "source",
        ]
        return {key: value.get(key) for key in allowed if key in value}

    def now(self) -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
