from __future__ import annotations

import hashlib
import json
import zipfile
from dataclasses import dataclass, asdict, field
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from app.config import settings
from app.services.scenario_lab_config import (
    get_archived_mpl_source_options,
    get_scenario_lab_path_config,
    list_scenario_lab_path_configs,
    normalize_source_system,
)
from app.services.cpiview_evidence_service import CPIViewEvidenceService
from app.services.cpi_native_evidence_service import NativeCPIEvidenceService


@dataclass(frozen=True)
class IflowScenarioRecord:
    package_name: str
    iflow_name: str
    source_zip: str
    bpmn_file: str
    checksum_sha256: str
    sender_adapters: list[str]
    receiver_adapters: list[str]
    content_modifiers: list[str]
    groovy_scripts: list[str]
    message_mappings: list[str]
    xslt_mappings: list[str]
    exception_subprocesses: list[str]
    externalized_parameters: list[str]
    endpoints: list[str]
    dependencies: list[str]
    risk_points: list[str]
    runtime_status: str = ""
    deployed_on: str = ""
    configurations: list[str] = field(default_factory=list)
    channel_properties: list[str] = field(default_factory=list)
    scenario_lab_hints: list[str] = field(default_factory=list)


class IflowScenarioService:
    """Read-only Scenario Lab service for SAP CPI iFlow reverse engineering.

    The service never modifies design-time iFlow packages or tenant artifacts. It reads
    local ZIP/BPMN evidence under resources/cpi, produces safe DEV/TEST scenario
    artifacts under exports/scenario_lab, and records source-backed findings plus
    assumptions explicitly in the generated manifests.
    """

    DEFAULT_ZIP_DIR = get_scenario_lab_path_config("sap_ci").primary_path
    DEFAULT_BPMN_DIR = get_scenario_lab_path_config("sap_ci").secondary_path

    def describe_defaults(self, source_system: str = "sap_ci") -> dict[str, Any]:
        system = normalize_source_system(source_system)
        config = get_scenario_lab_path_config(system)
        primary_files = list(config.primary_path.glob("*")) if config.primary_path.exists() else []
        secondary_files = (
            list(config.secondary_path.glob("*")) if config.secondary_path.exists() else []
        )
        zip_files = list(config.primary_path.glob("*.zip")) if config.primary_path.exists() else []
        bpmn_files = (
            list(config.secondary_path.glob("*.iflw")) if config.secondary_path.exists() else []
        )
        cpiview_status = CPIViewEvidenceService().status() if system == "sap_ci" else None
        native_cpi_status = NativeCPIEvidenceService().status() if system == "sap_ci" else None
        return {
            **config.to_dict(),
            "source_system": system,
            "zip_count": len(zip_files),
            "bpmn_count": len(bpmn_files),
            "primary_file_count": len([p for p in primary_files if p.is_file()]),
            "secondary_file_count": len([p for p in secondary_files if p.is_file()]),
            "available_source_systems": list_scenario_lab_path_configs(),
            "archived_mpl_source_options": get_archived_mpl_source_options(system),
            "output_root": str(settings.exports_dir / "scenario_lab"),
            "safety_model": "read_only_static_analysis_plus_dev_test_negative_inputs",
            "cpiview": cpiview_status.__dict__ if cpiview_status else None,
            "native_cpi": native_cpi_status.__dict__ if native_cpi_status else None,
        }

    def save_uploaded_zip(self, filename: str, content: bytes) -> dict[str, Any]:
        if not filename.lower().endswith(".zip"):
            raise ValueError("Only .zip iFlow exports are supported.")
        upload_root = settings.exports_dir / "scenario_lab_uploads"
        upload_root.mkdir(parents=True, exist_ok=True)
        target = upload_root / Path(filename).name
        target.write_bytes(content)
        return {
            "filename": target.name,
            "path": str(target),
            "checksum_sha256": self._checksum(target),
            "size_bytes": target.stat().st_size,
        }

    def run(
        self,
        zip_dir: str | None = None,
        bpmn_dir: str | None = None,
        source_system: str = "sap_ci",
        scenario_lab_run_id: str | None = None,
        collect_mpl_evidence: bool = True,
        max_iflows: int | None = None,
    ) -> dict[str, Any]:
        system = normalize_source_system(source_system)
        config = get_scenario_lab_path_config(system)
        source_zip_dir = self._resolve_path(zip_dir, config.primary_path)
        source_bpmn_dir = self._resolve_path(bpmn_dir, config.secondary_path)
        if not source_zip_dir.exists():
            raise ValueError(f"{config.primary_label} not found: {source_zip_dir}")
        if not source_bpmn_dir.exists():
            raise ValueError(f"{config.secondary_label} not found: {source_bpmn_dir}")
        timestamp = scenario_lab_run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = settings.exports_dir / "scenario_lab" / timestamp
        payload_dir = output_dir / "payload_examples"
        plan_dir = output_dir / "execution_plan"
        mpl_dir = output_dir / "mpl_evidence"
        patterns_dir = output_dir / "expected_mpl_patterns"
        for folder in [payload_dir, plan_dir, mpl_dir, patterns_dir]:
            folder.mkdir(parents=True, exist_ok=True)

        zip_files = sorted(source_zip_dir.glob("*.zip"))
        use_cpiview_default = (
            system == "sap_ci" and source_zip_dir.resolve() == config.primary_path.resolve()
        )
        if max_iflows and max_iflows > 0:
            zip_files = zip_files[:max_iflows]
        bpmn_by_name = self._index_bpmn(source_bpmn_dir)
        records: list[IflowScenarioRecord] = []
        upload_manifest = []
        if system == "sap_ci" and (use_cpiview_default or not zip_files):
            records = self._build_cpi_snapshot_records(source_zip_dir, max_iflows=max_iflows)
            if records and use_cpiview_default:
                zip_files = []
            upload_manifest = [
                {
                    "zip_name": record.source_zip,
                    "package_name": record.package_name,
                    "iflow_name": record.iflow_name,
                    "source_system": system,
                    "upload_timestamp": datetime.now().isoformat(timespec="seconds"),
                    "file_checksum_sha256": record.checksum_sha256,
                    "bpmn_file": record.bpmn_file,
                    "source_backed": True,
                    "source_type": "cpi_live_snapshot",
                }
                for record in records
            ]
        if system == "sap_pipo" and not zip_files:
            records = self._build_pipo_records(max_iflows=max_iflows)
            upload_manifest = [
                {
                    "zip_name": record.source_zip,
                    "package_name": record.package_name,
                    "iflow_name": record.iflow_name,
                    "source_system": system,
                    "upload_timestamp": datetime.now().isoformat(timespec="seconds"),
                    "file_checksum_sha256": record.checksum_sha256,
                    "bpmn_file": record.bpmn_file,
                    "source_backed": True,
                }
                for record in records
            ]
        for zip_path in [] if records and not zip_files else zip_files:
            package_name, iflow_name = self._split_artifact_name(zip_path.stem)
            bpmn_path = bpmn_by_name.get(iflow_name) or bpmn_by_name.get(zip_path.stem) or Path()
            facts = self._analyze_bpmn(bpmn_path) if bpmn_path else {}
            zip_facts = self._inspect_zip(zip_path)
            record = IflowScenarioRecord(
                package_name=package_name,
                iflow_name=iflow_name,
                source_zip=self._rel(zip_path),
                bpmn_file=self._rel(bpmn_path) if bpmn_path else "missing",
                checksum_sha256=self._checksum(zip_path),
                sender_adapters=facts.get("sender_adapters", []),
                receiver_adapters=facts.get("receiver_adapters", []),
                content_modifiers=facts.get("content_modifiers", []),
                groovy_scripts=sorted(
                    set(facts.get("groovy_scripts", []) + zip_facts.get("groovy_scripts", []))
                ),
                message_mappings=sorted(
                    set(facts.get("message_mappings", []) + zip_facts.get("message_mappings", []))
                ),
                xslt_mappings=sorted(
                    set(facts.get("xslt_mappings", []) + zip_facts.get("xslt_mappings", []))
                ),
                exception_subprocesses=facts.get("exception_subprocesses", []),
                externalized_parameters=sorted(
                    set(
                        facts.get("externalized_parameters", [])
                        + zip_facts.get("externalized_parameters", [])
                    )
                ),
                endpoints=facts.get("endpoints", []),
                dependencies=sorted(
                    set(facts.get("dependencies", []) + zip_facts.get("dependencies", []))
                ),
                risk_points=self._risk_points(facts, zip_facts),
            )
            records.append(record)
            upload_manifest.append(
                {
                    "zip_name": zip_path.name,
                    "package_name": package_name,
                    "iflow_name": iflow_name,
                    "source_system": system,
                    "upload_timestamp": datetime.now().isoformat(timespec="seconds"),
                    "file_checksum_sha256": record.checksum_sha256,
                    "bpmn_file": record.bpmn_file,
                }
            )
            self._write_negative_examples(payload_dir, record)
            self._write_execution_plan(plan_dir, record, timestamp)
            self._write_expected_mpl_pattern(patterns_dir, record)
        if records and not zip_files:
            for record in records:
                self._write_negative_examples(payload_dir, record)
                self._write_execution_plan(plan_dir, record, timestamp)
                self._write_expected_mpl_pattern(patterns_dir, record)

        analysis_report = {
            "run_id": timestamp,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "source_system": system,
            "source_zip_dir": str(source_zip_dir),
            "source_bpmn_dir": str(source_bpmn_dir),
            "records_count": len(records),
            "records": [asdict(r) for r in records],
            "source_backed_facts": [
                "zip_name",
                "checksum_sha256",
                "bpmn_file",
                "BPMN tags/properties when present",
                "ZIP contained resources",
            ],
            "assumptions": [
                "Negative payloads are functional DEV/TEST examples only and are not destructive.",
                "When BPMN properties do not expose adapter direction, channels are classified by local tag/property hints.",
                "MPL evidence collection is represented by expected-vs-observed matrix until live/archive MPL records are selected after execution.",
            ],
        }
        (output_dir / "iflow_upload_manifest.json").write_text(
            json.dumps(upload_manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (output_dir / "iflow_analysis_report.json").write_text(
            json.dumps(analysis_report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        self._write_summary(
            output_dir / "iflow_analysis_summary.md",
            records,
            timestamp,
            source_zip_dir,
            source_bpmn_dir,
        )
        scenario_manifest = self._write_scenario_manifest(
            output_dir, timestamp, records, collect_mpl_evidence
        )
        evidence = self._write_mpl_evidence(mpl_dir, records, collect_mpl_evidence)
        return {
            "status": "generated" if records else "blocked",
            "run_id": timestamp,
            "output_dir": str(output_dir),
            "iflow_count": len(records),
            "upload_manifest": str(output_dir / "iflow_upload_manifest.json"),
            "analysis_report": str(output_dir / "iflow_analysis_report.json"),
            "analysis_summary": str(output_dir / "iflow_analysis_summary.md"),
            "scenario_manifest": str(scenario_manifest),
            "payload_examples_dir": str(payload_dir),
            "execution_plan_dir": str(plan_dir),
            "expected_mpl_patterns_dir": str(patterns_dir),
            "mpl_evidence": evidence,
        }

    def _build_cpi_snapshot_records(
        self, source_dir: Path, max_iflows: int | None = None
    ) -> list[IflowScenarioRecord]:
        cpiview_service = CPIViewEvidenceService()
        if cpiview_service.is_available():
            cpiview_service.import_to_resources()
        rich_path = (
            settings.resources_dir / "cpi" / "input" / "analysis" / "iflow_rich_inventory.json"
        )
        rich_records = self._build_cpi_rich_inventory_records(rich_path, max_iflows=max_iflows)
        if rich_records:
            return rich_records

        inventory_path = source_dir / "iflow_inventory.json"
        data = self._read_json_dict(inventory_path)
        iflows_value = data.get("iflows")
        iflows: list[Any] = iflows_value if isinstance(iflows_value, list) else []
        if max_iflows and max_iflows > 0:
            iflows = iflows[:max_iflows]
        records: list[IflowScenarioRecord] = []
        for item in iflows:
            if not isinstance(item, dict):
                continue
            raw_value = item.get("raw")
            raw: dict[str, Any] = raw_value if isinstance(raw_value, dict) else item
            iflow_name = str(
                item.get("name")
                or item.get("id")
                or raw.get("Name")
                or raw.get("Id")
                or "UNKNOWN_CPI_IFLOW"
            )
            package_name = str(
                item.get("package_id")
                or raw.get("PackageId")
                or raw.get("PackageName")
                or "SAP CPI Live Snapshot"
            )
            deployment_status = str(item.get("deployment_status") or "unknown")
            records.append(
                IflowScenarioRecord(
                    package_name=package_name,
                    iflow_name=iflow_name,
                    source_zip=str(inventory_path.relative_to(settings.project_root))
                    if inventory_path.exists()
                    else "cpi_live_snapshot_missing",
                    bpmn_file="metadata_snapshot_only",
                    checksum_sha256=self._checksum(inventory_path)
                    if inventory_path.exists()
                    else "missing",
                    sender_adapters=[],
                    receiver_adapters=[],
                    content_modifiers=[],
                    groovy_scripts=[],
                    message_mappings=[],
                    xslt_mappings=[],
                    exception_subprocesses=[],
                    externalized_parameters=[],
                    endpoints=[],
                    dependencies=[
                        str(
                            raw.get("ArtifactType")
                            or raw.get("Type")
                            or "IntegrationDesigntimeArtifact"
                        )
                    ],
                    risk_points=self._cpi_snapshot_risk_points(deployment_status),
                    runtime_status=deployment_status,
                    scenario_lab_hints=[
                        "Enable CPIVIEW_* local evidence or CPI design content download for richer Scenario Lab outputs."
                    ],
                )
            )
        return records

    def _build_cpi_rich_inventory_records(
        self, rich_path: Path, max_iflows: int | None = None
    ) -> list[IflowScenarioRecord]:
        data = self._read_json_dict(rich_path)
        iflows = data.get("iflows") if isinstance(data.get("iflows"), list) else []
        if not iflows:
            return []
        if max_iflows and max_iflows > 0:
            iflows = iflows[:max_iflows]
        records: list[IflowScenarioRecord] = []
        for item in iflows:
            if not isinstance(item, dict):
                continue
            runtime_value = item.get("runtime")
            runtime: dict[str, Any] = runtime_value if isinstance(runtime_value, dict) else {}
            channels_value = item.get("channels")
            channels: list[dict[str, Any]] = (
                channels_value if isinstance(channels_value, list) else []
            )
            sender_adapters = self._channel_adapters(channels, sender=True)
            receiver_adapters = self._channel_adapters(channels, sender=False)
            endpoints = self._channel_endpoints(channels)
            content_modifiers = self._names(item.get("content_modifiers"), "name", "rowName")
            groovy_scripts = self._names(item.get("groovy_scripts"), "script", "name")
            message_mappings = self._names(item.get("message_mappings"), "mappingname", "name")
            xslt_mappings = self._names(item.get("xslt_mappings"), "mappingname", "name", "xslt")
            timers = self._names(
                item.get("timers"), "cronDescription", "cronExpression", "triggerName"
            )
            configs = self._configuration_names(item.get("configurations"))
            channel_props = self._channel_property_names(item.get("channel_properties"))
            resources = self._names(item.get("resources"), "Name", "ResourceType")
            dependencies = sorted({*resources, *timers, str(item.get("iflow_id") or "")})
            records.append(
                IflowScenarioRecord(
                    package_name=str(
                        item.get("package_name")
                        or item.get("package_id")
                        or "SAP CPI CPIView Evidence"
                    ),
                    iflow_name=str(
                        item.get("iflow_name") or item.get("iflow_id") or "UNKNOWN_CPI_IFLOW"
                    ),
                    source_zip=self._rel(rich_path),
                    bpmn_file=str(item.get("bpmn_file") or "cpiview_bpmn_not_available"),
                    checksum_sha256=self._checksum(rich_path) if rich_path.exists() else "missing",
                    sender_adapters=sender_adapters,
                    receiver_adapters=receiver_adapters,
                    content_modifiers=content_modifiers,
                    groovy_scripts=groovy_scripts,
                    message_mappings=message_mappings,
                    xslt_mappings=xslt_mappings,
                    exception_subprocesses=[],
                    externalized_parameters=configs,
                    endpoints=endpoints,
                    dependencies=dependencies,
                    risk_points=[str(x) for x in item.get("risk_points", []) if str(x).strip()]
                    or self._cpi_snapshot_risk_points(str(runtime.get("status") or "unknown")),
                    runtime_status=str(runtime.get("status") or ""),
                    deployed_on=str(runtime.get("deployed_on") or ""),
                    configurations=configs,
                    channel_properties=channel_props,
                    scenario_lab_hints=[
                        str(x) for x in item.get("scenario_lab_hints", []) if str(x).strip()
                    ],
                )
            )
        return records

    @staticmethod
    def _names(rows: Any, *keys: str) -> list[str]:
        if not isinstance(rows, list):
            return []
        values = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            for key in keys:
                value = row.get(key)
                if value not in (None, ""):
                    values.append(str(value))
                    break
        return sorted(set(values))

    @staticmethod
    def _channel_adapters(channels: list[dict[str, Any]], sender: bool) -> list[str]:
        values = []
        for row in channels:
            typ = str(row.get("type") or "").lower()
            system = str(row.get("system") or row.get("participantName") or "").lower()
            is_sender = "sender" in typ or "sender" in system
            if is_sender == sender:
                value = row.get("componentType") or row.get("name") or row.get("transportProtocol")
                if value:
                    values.append(str(value))
        return sorted(set(values))

    @staticmethod
    def _channel_endpoints(channels: list[dict[str, Any]]) -> list[str]:
        values = []
        for row in channels:
            address = row.get("address") or row.get("resource")
            if address:
                values.append(str(address))
        return sorted(set(values))

    @staticmethod
    def _configuration_names(rows: Any) -> list[str]:
        values = []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    key = row.get("ParameterKey") or row.get("parameterKey") or row.get("Name")
                    if key:
                        values.append(str(key))
        return sorted(set(values))

    @staticmethod
    def _channel_property_names(rows: Any) -> list[str]:
        values = []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    key = row.get("key") or row.get("Key")
                    value = row.get("resolvedValue") or row.get("rawValue")
                    if key:
                        values.append(f"{key}={value}" if value not in (None, "") else str(key))
        return sorted(set(values))

    def _cpi_snapshot_risk_points(self, deployment_status: str) -> list[str]:
        risks = [
            "Live CPI snapshot contains design-time metadata; upload or enable content download for full ZIP/BPMN reverse engineering.",
            "Validate adapter endpoints and externalized parameters before generating executable DEV/TEST scenarios.",
        ]
        if deployment_status == "deployed":
            risks.append(
                "iFlow appears deployed in snapshot; keep runtime testing read-only and use DEV/TEST only."
            )
        elif deployment_status == "unknown":
            risks.append(
                "Deployment status is unknown because the tenant did not expose a recognized status field."
            )
        return risks

    def _build_pipo_records(self, max_iflows: int | None = None) -> list[IflowScenarioRecord]:
        seeds_path = settings.resources_dir / "pipo" / "esr_id" / "interface_seeds.json"
        legacy_seeds_path = (
            settings.resources_dir
            / "pipo"
            / "pipo_rag_pipeline_20260405T134227Z"
            / "dir_normalized_20260405T134229Z"
            / "interface_seeds.json"
        )
        if not seeds_path.exists():
            seeds_path = legacy_seeds_path
        incidents_path = (
            settings.resources_dir
            / "pipo"
            / "pipo_rag_pipeline_20260405T134227Z"
            / "mpl_normalized_20260405T134235Z"
            / "mpl_incidents.json"
        )
        seeds = self._read_json_list(seeds_path)
        incidents = self._read_json_list(incidents_path)
        if max_iflows and max_iflows > 0:
            seeds = seeds[:max_iflows]
        incident_by_key: dict[str, list[dict[str, Any]]] = {}
        for inc in incidents:
            key = str(inc.get("canonical_key") or inc.get("interface_name") or "")
            if key:
                incident_by_key.setdefault(key, []).append(inc)
        records: list[IflowScenarioRecord] = []
        for seed in seeds:
            canonical = str(
                seed.get("canonical_key")
                or seed.get("interface_name")
                or seed.get("object_name")
                or "UNKNOWN_PIPO_INTERFACE"
            )
            name = str(seed.get("interface_name") or seed.get("object_name") or canonical)
            receivers_value = seed.get("receiver_components")
            receivers: list[Any] = receivers_value if isinstance(receivers_value, list) else []
            channels_value = seed.get("communication_channel_names")
            channels: list[Any] = channels_value if isinstance(channels_value, list) else []
            mappings_value = seed.get("operation_mappings")
            mappings: list[Any] = mappings_value if isinstance(mappings_value, list) else []
            matched_incidents = incident_by_key.get(canonical, []) + incident_by_key.get(name, [])
            risk_points = self._pipo_risk_points(seed, matched_incidents)
            records.append(
                IflowScenarioRecord(
                    package_name="SAP PI/PO Directory and ESR",
                    iflow_name=name,
                    source_zip=str(seeds_path.relative_to(settings.project_root)),
                    bpmn_file=str(
                        (settings.resources_dir / "pipo" / "ico" / "objects.json").relative_to(
                            settings.project_root
                        )
                    ),
                    checksum_sha256=self._checksum(seeds_path)
                    if seeds_path.exists()
                    else "missing",
                    sender_adapters=[str(seed.get("sender_component") or "PIPO_SENDER")],
                    receiver_adapters=[str(value) for value in receivers] or ["PIPO_RECEIVER"],
                    content_modifiers=[],
                    groovy_scripts=[],
                    message_mappings=[str(value) for value in mappings],
                    xslt_mappings=[],
                    exception_subprocesses=[
                        str(inc.get("exception_class"))
                        for inc in matched_incidents
                        if inc.get("exception_class")
                    ],
                    externalized_parameters=[str(seed.get("qos"))] if seed.get("qos") else [],
                    endpoints=[str(value) for value in channels],
                    dependencies=[canonical, str(seed.get("interface_namespace") or "")],
                    risk_points=risk_points,
                )
            )
        return records

    def _pipo_risk_points(self, seed: dict[str, Any], incidents: list[dict[str, Any]]) -> list[str]:
        risks = [
            "Validate PI/PO Integrated Configuration receiver determination and interface determination before replay.",
            "Confirm ESR operation mapping, message mapping, and namespace compatibility for this interface.",
        ]
        if seed.get("communication_channel_names"):
            risks.append(
                "Check PI/PO communication channel adapter, authentication, and retry configuration."
            )
        if incidents:
            risks.append(
                "Use normalized MPL incidents to seed KEDB and runbook patterns for this PI/PO interface."
            )
        if not seed.get("operation_mappings"):
            risks.append(
                "Operation mapping evidence is missing; validate ESR dependencies before generating final remediation instructions."
            )
        return sorted(set(risks))

    def _read_json_dict(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    def _read_json_list(self, path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict) and isinstance(data.get("interfaces"), list):
            return [item for item in data["interfaces"] if isinstance(item, dict)]
        return []

    def _resolve_path(self, raw: str | None, default: Path) -> Path:
        if not raw:
            return default
        path = Path(raw)
        return path if path.is_absolute() else settings.project_root / path

    def _index_bpmn(self, bpmn_dir: Path) -> dict[str, Path]:
        index = {}
        for path in sorted(bpmn_dir.glob("*.iflw")):
            package, iflow = self._split_artifact_name(path.stem)
            index[iflow] = path
            index[path.stem] = path
        return index

    def _split_artifact_name(self, stem: str) -> tuple[str, str]:
        if " --- " in stem:
            package, iflow = stem.split(" --- ", 1)
            return package.strip(), iflow.strip()
        return "unassigned_package", stem.strip()

    def _checksum(self, path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def _inspect_zip(self, path: Path) -> dict[str, list[str]]:
        facts: dict[str, list[str]] = {
            "groovy_scripts": [],
            "message_mappings": [],
            "xslt_mappings": [],
            "externalized_parameters": [],
            "dependencies": [],
        }
        try:
            with zipfile.ZipFile(path) as zf:
                for name in zf.namelist():
                    lower = name.lower()
                    base = Path(name).name
                    if lower.endswith(".groovy"):
                        facts["groovy_scripts"].append(base)
                    elif "mapping" in lower and (
                        lower.endswith(".mmap")
                        or lower.endswith(".mmap.zip")
                        or lower.endswith(".map")
                    ):
                        facts["message_mappings"].append(base)
                    elif lower.endswith(".xsl") or lower.endswith(".xslt"):
                        facts["xslt_mappings"].append(base)
                    elif "parameters" in lower or "external" in lower:
                        facts["externalized_parameters"].append(base)
                    elif lower.endswith((".xsd", ".wsdl", ".edmx")):
                        facts["dependencies"].append(base)
        except zipfile.BadZipFile:
            facts["dependencies"].append("BAD_ZIP_FILE")
        return {key: sorted(set(value)) for key, value in facts.items()}

    def _analyze_bpmn(self, path: Path) -> dict[str, list[str]]:
        facts: dict[str, list[str]] = {
            "sender_adapters": [],
            "receiver_adapters": [],
            "content_modifiers": [],
            "groovy_scripts": [],
            "message_mappings": [],
            "xslt_mappings": [],
            "exception_subprocesses": [],
            "externalized_parameters": [],
            "endpoints": [],
            "dependencies": [],
        }
        if not path or not path.exists():
            return facts
        try:
            root = ET.parse(path).getroot()
        except ET.ParseError:
            text = path.read_text(encoding="utf-8", errors="ignore")
            return self._fallback_text_scan(text, facts)
        for elem in root.iter():
            tag = elem.tag.split("}")[-1].lower()
            attrs = {k.split("}")[-1].lower(): str(v) for k, v in elem.attrib.items()}
            text_blob = " ".join([tag, *attrs.values(), elem.text or ""])
            low = text_blob.lower()
            name = attrs.get("name") or attrs.get("id") or attrs.get("componenttype") or tag
            if "contentmodifier" in low or "content modifier" in low:
                facts["content_modifiers"].append(name)
            if "groovy" in low:
                facts["groovy_scripts"].append(name)
            if "message mapping" in low or "messagemapping" in low:
                facts["message_mappings"].append(name)
            if "xslt" in low:
                facts["xslt_mappings"].append(name)
            if "exceptionsubprocess" in low or "exception subprocess" in low:
                facts["exception_subprocesses"].append(name)
            if "externalized" in low or "{{" in text_blob:
                facts["externalized_parameters"].append(name)
            if any(
                proto in low
                for proto in [
                    "http",
                    "https",
                    "sftp",
                    "ftp",
                    "odata",
                    "jdbc",
                    "mail",
                    "smtp",
                    "soap",
                ]
            ):
                adapter = self._adapter_from_text(text_blob)
                if "sender" in low or "start" in low:
                    facts["sender_adapters"].append(adapter)
                elif adapter:
                    facts["receiver_adapters"].append(adapter)
            for value in attrs.values():
                if value.startswith(("http://", "https://", "sftp://", "ftp://", "jdbc:")):
                    facts["endpoints"].append(value)
                if value.endswith((".xsd", ".wsdl", ".edmx")):
                    facts["dependencies"].append(value)
        return {key: sorted(set(value)) for key, value in facts.items()}

    def _fallback_text_scan(self, text: str, facts: dict[str, list[str]]) -> dict[str, list[str]]:
        for marker, key in [
            ("groovy", "groovy_scripts"),
            ("message mapping", "message_mappings"),
            ("xslt", "xslt_mappings"),
            ("content modifier", "content_modifiers"),
        ]:
            if marker in text.lower():
                facts[key].append(marker)
        return facts

    def _adapter_from_text(self, text: str) -> str:
        low = text.lower()
        for name in [
            "sftp",
            "ftp",
            "odata",
            "http",
            "https",
            "jdbc",
            "soap",
            "mail",
            "smtp",
            "processdirect",
            "timer",
        ]:
            if name in low:
                return name.upper()
        return "UNKNOWN_ADAPTER"

    def _risk_points(
        self, facts: dict[str, list[str]], zip_facts: dict[str, list[str]]
    ) -> list[str]:
        risks = []
        if facts.get("groovy_scripts") or zip_facts.get("groovy_scripts"):
            risks.append(
                "Custom Groovy script execution requires payload/error-path test coverage."
            )
        if facts.get("message_mappings") or zip_facts.get("message_mappings"):
            risks.append(
                "Message mapping requires mandatory-field and invalid-format negative tests."
            )
        if facts.get("externalized_parameters") or zip_facts.get("externalized_parameters"):
            risks.append(
                "Externalized parameters require DEV/TEST value verification before execution."
            )
        if facts.get("endpoints"):
            risks.append(
                "Endpoint-dependent integration requires connectivity and authorization validation."
            )
        if not risks:
            risks.append(
                "Static evidence only; confirm adapter-specific runtime behavior using MPL evidence after DEV/TEST execution."
            )
        return sorted(set(risks))

    def _safe_name(self, value: str) -> str:
        safe = (
            "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in value)
            or "UNKNOWN_IFLOW"
        )
        if len(safe) <= 60:
            return safe
        digest = hashlib.sha1(safe.encode("utf-8")).hexdigest()[:6]
        return f"{safe[:53]}_{digest}"

    def _write_negative_examples(self, payload_dir: Path, record: IflowScenarioRecord) -> None:
        folder = payload_dir / self._safe_name(record.iflow_name)
        folder.mkdir(parents=True, exist_ok=True)
        examples = {
            "TC_NEG_001_missing_required_id.xml": "<Root><CustomerId></CustomerId><Payload>missing required id</Payload></Root>\n",
            "TC_NEG_002_invalid_date_format.xml": "<Root><CustomerId>CUST-001</CustomerId><PostingDate>31-99-2099</PostingDate></Root>\n",
            "TC_NEG_003_malformed_xml.xml": "<Root><CustomerId>CUST-001</CustomerId><Broken></Root>\n",
            "TC_NEG_004_empty_payload.xml": "",
        }
        if any(
            a in {"HTTP", "HTTPS", "ODATA", "SOAP"}
            for a in record.sender_adapters + record.receiver_adapters
        ):
            examples["TC_NEG_005_invalid_method_or_query.json"] = (
                json.dumps({"case": "invalid method/query", "value": None}, indent=2) + "\n"
            )
        for name, content in examples.items():
            (folder / name).write_text(content, encoding="utf-8")

    def _write_execution_plan(
        self, plan_dir: Path, record: IflowScenarioRecord, run_id: str
    ) -> None:
        path = plan_dir / f"{self._safe_name(record.iflow_name)}_test_plan.md"
        lines = [
            f"# {record.iflow_name} test execution plan",
            "",
            f"scenario_lab_run_id: `{run_id}`",
            f"package_name: `{record.package_name}`",
            f"source_zip: `{record.source_zip}`",
            f"bpmn_file: `{record.bpmn_file}`",
            "",
            "## Scope",
            "Functional negative testing in DEV/TEST only. The platform does not mutate live iFlows.",
            "",
            "## Preconditions",
            "- iFlow is deployed in DEV/TEST tenant.",
            "- Operator has SAP CI monitoring access and permission to read MPL evidence.",
            "- Externalized parameters and credentials are configured in DEV/TEST.",
            "",
            "## Test cases",
        ]
        cases = [
            (
                "TC_NEG_001_missing_required_id.xml",
                "Missing required business identifier",
                "FAILED or controlled validation error",
                "missing|required|identifier|validation",
            ),
            (
                "TC_NEG_002_invalid_date_format.xml",
                "Invalid date format",
                "FAILED or controlled mapping/validation error",
                "date|format|mapping|validation",
            ),
            (
                "TC_NEG_003_malformed_xml.xml",
                "Malformed XML",
                "FAILED with parser/XML error",
                "xml|parser|well-formed|SAX",
            ),
            (
                "TC_NEG_004_empty_payload.xml",
                "Empty payload",
                "FAILED or controlled validation error",
                "empty|payload|body|required",
            ),
        ]
        for case_id, expected_error, expected_status, signature in cases:
            lines.extend(
                [
                    f"### {case_id}",
                    f"- input file: `payload_examples/{self._safe_name(record.iflow_name)}/{case_id}`",
                    f"- expected error: {expected_error}",
                    f"- expected MPL status: {expected_status}",
                    f"- expected error signature: `{signature}`",
                    "- validation step: compare MessageGuid, status, timestamp, and error text in MPL.",
                    "- rollback / cleanup: delete DEV/TEST test payloads and do not transport test changes.",
                    "- escalation: IntegrationTeam when runtime error differs from expected safe validation behavior.",
                    "",
                ]
            )
        lines.extend(["## Risk points", *[f"- {risk}" for risk in record.risk_points]])
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_expected_mpl_pattern(self, patterns_dir: Path, record: IflowScenarioRecord) -> None:
        data = {
            "iflow_name": record.iflow_name,
            "expected_statuses": ["FAILED", "COMPLETED_WITH_WARNING"],
            "expected_error_signatures": [
                "missing|required|identifier|validation",
                "date|format|mapping|validation",
                "xml|parser|well-formed|SAX",
                "empty|payload|body|required",
            ],
            "evidence_fields": [
                "MessageGuid",
                "IntegrationFlowName",
                "Status",
                "LogStart",
                "LogEnd",
                "ErrorText",
            ],
        }
        (
            patterns_dir / f"{self._safe_name(record.iflow_name)}_expected_mpl_patterns.json"
        ).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _write_summary(
        self,
        path: Path,
        records: list[IflowScenarioRecord],
        run_id: str,
        zip_dir: Path,
        bpmn_dir: Path,
    ) -> None:
        adapters = sorted(
            {a for r in records for a in r.sender_adapters + r.receiver_adapters if a}
        )
        lines = [
            f"# Scenario Lab analysis summary - {run_id}",
            "",
            "## Source Map",
            f"- Primary evidence folder: `{zip_dir}`",
            f"- Secondary evidence folder: `{bpmn_dir}`",
            f"- iFlows analyzed: {len(records)}",
            f"- Adapter hints found: {', '.join(adapters) if adapters else 'not_available_in_static_evidence'}",
            "",
            "## Source-backed facts",
            "- ZIP names, package names, iFlow names, SHA-256 checksums, and available BPMN file matches are source-backed.",
            "- Scripts, mappings, dependencies, endpoints, and adapter hints are source-backed when present in ZIP/BPMN/CPIView evidence.",
            "- CPIView rich inventory records include runtime status, channel properties, configurations, scripts, mappings, timers, and resources when available.",
            "",
            "## Assumptions",
            "- Negative examples are safe functional DEV/TEST inputs, not destructive or security attack payloads.",
            "- Runtime evidence must be collected after execution from Live MPL or Archived MPL.",
            "",
            "## Risks and Open Points",
            "- Some BPMN exports may omit endpoint or adapter direction metadata; validate in deployed artifact view before execution.",
            "- Do not execute examples in production.",
            "",
            "## Top iFlows",
        ]
        for r in records[:50]:
            runtime = f" | runtime `{r.runtime_status}`" if r.runtime_status else ""
            lines.append(
                f"- `{r.iflow_name}` | package `{r.package_name}`{runtime} | risks: {len(r.risk_points)}"
            )
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _write_scenario_manifest(
        self,
        output_dir: Path,
        run_id: str,
        records: list[IflowScenarioRecord],
        collect_mpl_evidence: bool,
    ) -> Path:
        manifest = {
            "scenario_lab_run_id": run_id,
            "generation_mode": "scenario_lab_enriched",
            "runtime_evidence_sources": ["live_mpl", "archived_mpl"]
            if collect_mpl_evidence
            else ["not_collected_yet"],
            "design_evidence_sources": [
                "iflow_zip_analysis",
                "resources/cpi",
                "cpiview_rich_inventory",
            ],
            "policy_sources": [
                "resources/policies/AI4BIZ_Knowledge_Ingestion_Guide.txt",
                "resources/policies/BM25_Runbook_Authoring_Guideline.txt",
            ],
            "iflow_count": len(records),
            "outputs": [
                "iflow_upload_manifest.json",
                "iflow_analysis_report.json",
                "iflow_analysis_summary.md",
                "payload_examples",
                "execution_plan",
                "expected_mpl_patterns",
                "mpl_evidence",
            ],
        }
        path = output_dir / "scenario_manifest.json"
        path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        return path

    def _write_mpl_evidence(
        self, mpl_dir: Path, records: list[IflowScenarioRecord], collect: bool
    ) -> dict[str, str]:
        observed: list[dict[str, Any]] = []
        matrix: list[dict[str, Any]] = []
        for r in records:
            matrix.append(
                {
                    "iflow_name": r.iflow_name,
                    "planned_test_cases": 4,
                    "observed_mpl_records": 0,
                    "status": "pending_execution" if collect else "not_requested",
                    "missing_input": "Run DEV/TEST scenarios and refresh Live MPL or provide Archived MPL export.",
                }
            )
        evidence_path = mpl_dir / "collected_mpl_evidence.json"
        matrix_path = mpl_dir / "expected_vs_observed_mpl_matrix.json"
        evidence_path.write_text(
            json.dumps({"status": "pending_execution", "records": observed}, indent=2),
            encoding="utf-8",
        )
        matrix_path.write_text(json.dumps(matrix, indent=2, ensure_ascii=False), encoding="utf-8")
        return {
            "collected_mpl_evidence": str(evidence_path),
            "expected_vs_observed_mpl_matrix": str(matrix_path),
        }

    def _rel(self, path: Path) -> str:
        if not path:
            return "missing"
        try:
            return str(path.relative_to(settings.project_root))
        except ValueError:
            return str(path)
