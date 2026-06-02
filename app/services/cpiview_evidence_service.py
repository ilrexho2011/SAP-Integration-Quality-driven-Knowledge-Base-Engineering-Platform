from __future__ import annotations

import json
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings


@dataclass(frozen=True)
class CPIViewEvidenceStatus:
    enabled: bool
    tenant_id: str
    input_dir: str
    output_dir: str
    available: bool
    manifest_path: str
    rich_inventory_path: str
    counts: dict[str, int]
    missing_files: list[str]
    notes: list[str]


class CPIViewEvidenceService:
    """Read CPIView local evidence without invoking CPIView or exposing secrets.

    Supported layout:
      CPIVIEW_INPUT_DIR/<odata,analysis>/... or CPIVIEW_ROOT/input/<tenant>/...
      CPIVIEW_OUTPUT_DIR/*.xlsx is optional and only referenced in manifests.
    """

    ODATA_FILES = {
        "packages": "packages.json",
        "iflows": "iflows.json",
        "runtimes": "runtimes.json",
        "configurations": "configurations.json",
        "resources": "resources.json",
        "message_mappings": "message-mappings.json",
        "script_collections": "script-collections.json",
        "value_mappings": "value-mappings.json",
        "security_keystore_entries": "security-keystore-entries.json",
        "security_oauth2_client_credentials": "security-oauth2-client-credentials.json",
        "security_user_credentials": "security-user-credentials.json",
        "security_secure_parameters": "security-secure-parameters.json",
    }
    ANALYSIS_FILES = {
        "activities": "bpmn-activities.json",
        "activity_properties": "bpmn-activities-properties.json",
        "channels": "bpmn-channels.json",
        "channel_properties": "bpmn-channels-properties.json",
        "content_modifiers": "bpmn-content-modifiers.json",
        "groovy_scripts": "bpmn-groovy-scripts.json",
        "message_mappings": "bpmn-message-mappings.json",
        "xslt_mappings": "bpmn-xslt-mappings.json",
        "timers": "bpmn-timers.json",
        "participants": "bpmn-participants.json",
    }

    def __init__(
        self,
        input_dir: Path | None = None,
        output_dir: Path | None = None,
        tenant_id: str | None = None,
        enabled_override: bool | None = None,
    ) -> None:
        self.enabled_override = enabled_override
        self.tenant_id = tenant_id or settings.cpiview_tenant_id
        self.input_dir = input_dir or settings.cpiview_input_dir_path
        self.output_dir = output_dir or settings.cpiview_output_dir_path
        self.target_odata_dir = settings.resources_dir / "cpi" / "input" / "odata" / "iflows"
        self.target_analysis_dir = settings.resources_dir / "cpi" / "input" / "analysis"
        self.target_rich_inventory = self.target_analysis_dir / "iflow_rich_inventory.json"

    def is_available(self) -> bool:
        enabled = (
            settings.cpiview_enabled if self.enabled_override is None else self.enabled_override
        )
        return bool(enabled and self.input_dir and (self.input_dir / "odata").exists())

    def status(self) -> CPIViewEvidenceStatus:
        counts, missing = self.collect_counts()
        manifest_path = self.target_odata_dir / "cpiview_evidence_manifest.json"
        notes = []
        enabled = (
            settings.cpiview_enabled if self.enabled_override is None else self.enabled_override
        )
        if not enabled:
            notes.append("CPIVIEW_ENABLED=false; CPIView evidence import is disabled.")
        elif not self.input_dir.exists():
            notes.append(f"CPIVIEW_INPUT_DIR does not exist: {self.input_dir}")
        elif not (self.input_dir / "odata").exists():
            notes.append(f"CPIView odata folder not found under: {self.input_dir}")
        else:
            notes.append(
                "CPIView local evidence is available and can enrich Monitoring and Scenario Lab."
            )
        return CPIViewEvidenceStatus(
            enabled=enabled,
            tenant_id=self.tenant_id,
            input_dir=str(self.input_dir),
            output_dir=str(self.output_dir),
            available=self.is_available(),
            manifest_path=self._rel(manifest_path),
            rich_inventory_path=self._rel(self.target_rich_inventory),
            counts=counts,
            missing_files=missing,
            notes=notes,
        )

    def collect_counts(self) -> tuple[dict[str, int], list[str]]:
        counts: dict[str, int] = {}
        missing: list[str] = []
        odata = self.input_dir / "odata"
        analysis = self.input_dir / "analysis"
        for key, name in self.ODATA_FILES.items():
            path = odata / name
            if path.exists():
                counts[f"odata_{key}"] = len(self._read_records(path))
            elif key in {"packages", "iflows", "runtimes"}:
                missing.append(self._display(path))
        for key, name in self.ANALYSIS_FILES.items():
            path = analysis / name
            if path.exists():
                counts[f"analysis_{key}"] = len(self._read_records(path))
        bpmn_dir = analysis / "iflows-bpmn"
        counts["bpmn_files"] = len(list(bpmn_dir.glob("*.iflw"))) if bpmn_dir.exists() else 0
        counts["output_excels"] = (
            len(list(self.output_dir.glob("*.xlsx"))) if self.output_dir.exists() else 0
        )
        counts["deployed_iflows"] = self.count_deployed_iflows_from_runtimes()
        return counts, missing

    def count_deployed_iflows_from_runtimes(self) -> int:
        runtimes = self._read_records(self.input_dir / "odata" / "runtimes.json")
        return self.count_deployed_iflows(runtimes)

    @staticmethod
    def count_deployed_iflows(runtimes: list[dict[str, Any]]) -> int:
        count = 0
        for item in runtimes:
            typ = str(item.get("Type") or item.get("type") or "").upper()
            status = str(item.get("Status") or item.get("status") or "").upper()
            if typ == "INTEGRATION_FLOW" and status in {"STARTED", "DEPLOYED", "RUNNING", "ACTIVE"}:
                count += 1
        return count

    def import_to_resources(self, copy_bpmn: bool = True) -> dict[str, Any]:
        if not self.is_available():
            status = self.status()
            return {
                "status": "skipped",
                "reason": "; ".join(status.notes),
                "cpiview": status.__dict__,
            }
        self.target_odata_dir.mkdir(parents=True, exist_ok=True)
        self.target_analysis_dir.mkdir(parents=True, exist_ok=True)
        written: list[str] = []
        odata_src = self.input_dir / "odata"
        analysis_src = self.input_dir / "analysis"
        for name in self.ODATA_FILES.values():
            src = odata_src / name
            if src.exists():
                dst = self.target_odata_dir / name
                shutil.copy2(src, dst)
                written.append(self._rel(dst))
        for name in self.ANALYSIS_FILES.values():
            src = analysis_src / name
            if src.exists():
                dst = self.target_analysis_dir / name
                shutil.copy2(src, dst)
                written.append(self._rel(dst))
        if copy_bpmn:
            src_bpmn = analysis_src / "iflows-bpmn"
            dst_bpmn = self.target_analysis_dir / "iflows-bpmn"
            if src_bpmn.exists():
                dst_bpmn.mkdir(parents=True, exist_ok=True)
                for src in src_bpmn.glob("*.iflw"):
                    dst = dst_bpmn / src.name
                    shutil.copy2(src, dst)
                    written.append(self._rel(dst))
        # Build the normalized inventory from the copied resources, so stored paths are project-relative
        # and do not leak local operator workstation paths into Scenario Lab outputs.
        rich = CPIViewEvidenceService(
            input_dir=settings.resources_dir / "cpi" / "input",
            output_dir=self.output_dir,
            tenant_id=self.tenant_id,
            enabled_override=True,
        ).build_rich_inventory(write=True)
        manifest = {
            "source_system": "sap_ci",
            "source_type": "cpiview_compatible_evidence",
            "tenant_id": self.tenant_id,
            "generated_at": self._timestamp(),
            "input_dir": self._display(self.input_dir),
            "output_dir": self._display(self.output_dir),
            "counts": rich.get("counts", {}),
            "rich_inventory": self._rel(self.target_rich_inventory),
            "files": written,
            "secret_handling": "Only CPIView evidence JSON/BPMN/Excel references are imported; config/api.json and secrets are not imported.",
        }
        manifest_path = self.target_odata_dir / "cpiview_evidence_manifest.json"
        self._write_json(manifest_path, manifest)
        return {
            "status": "ok",
            "manifest": self._rel(manifest_path),
            "rich_inventory": self._rel(self.target_rich_inventory),
            "counts": rich.get("counts", {}),
            "files": written,
        }

    def build_rich_inventory(self, write: bool = False) -> dict[str, Any]:
        root = self.input_dir
        # Support both native/CPIView layout (<input>/odata/*.json) and the
        # historical v2.0.x resources layout (<input>/odata/iflows/*.json).
        if (root / "odata" / "iflows.json").exists():
            odata_dir = root / "odata"
            analysis_dir = root / "analysis"
        elif (root / "odata" / "iflows" / "iflows.json").exists():
            odata_dir = root / "odata" / "iflows"
            analysis_dir = root / "analysis"
        elif self.target_odata_dir.exists() and (self.target_odata_dir / "iflows.json").exists():
            root = settings.resources_dir / "cpi" / "input"
            odata_dir = self.target_odata_dir
            analysis_dir = self.target_analysis_dir
        else:
            odata_dir = root / "odata"
            analysis_dir = root / "analysis"

        packages = self._read_records(odata_dir / "packages.json")
        iflows = self._read_records(odata_dir / "iflows.json")
        runtimes = self._read_records(odata_dir / "runtimes.json")
        configurations = self._read_records(odata_dir / "configurations.json")
        resources = self._read_records(odata_dir / "resources.json")
        channels = self._read_records(analysis_dir / "bpmn-channels.json")
        channel_properties = self._read_records(analysis_dir / "bpmn-channels-properties.json")
        activities = self._read_records(analysis_dir / "bpmn-activities.json")
        activity_properties = self._read_records(analysis_dir / "bpmn-activities-properties.json")
        content_modifiers = self._read_records(analysis_dir / "bpmn-content-modifiers.json")
        groovy_scripts = self._read_records(analysis_dir / "bpmn-groovy-scripts.json")
        message_mappings = self._read_records(analysis_dir / "bpmn-message-mappings.json")
        xslt_mappings = self._read_records(analysis_dir / "bpmn-xslt-mappings.json")
        timers = self._read_records(analysis_dir / "bpmn-timers.json")
        participants = self._read_records(analysis_dir / "bpmn-participants.json")
        security_refs = []
        for sec_name in [
            "security-keystore-entries.json",
            "security-oauth2-client-credentials.json",
            "security-user-credentials.json",
            "security-secure-parameters.json",
        ]:
            for row in self._read_records(odata_dir / sec_name):
                security_refs.append(self._redact_security_row(row, sec_name))

        by_iflow: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for label, rows in [
            ("configurations", configurations),
            ("resources", resources),
            ("channels", channels),
            ("channel_properties", channel_properties),
            ("activities", activities),
            ("activity_properties", activity_properties),
            ("content_modifiers", content_modifiers),
            ("groovy_scripts", groovy_scripts),
            ("message_mappings", message_mappings),
            ("xslt_mappings", xslt_mappings),
            ("timers", timers),
            ("participants", participants),
        ]:
            for row in rows:
                iflow_id = self._iflow_id(row)
                if iflow_id:
                    by_iflow[iflow_id][label].append(row)

        runtime_by_id = {str(r.get("Id") or r.get("id") or ""): r for r in runtimes}
        runtime_by_name = {str(r.get("Name") or r.get("name") or ""): r for r in runtimes}
        package_by_id = {
            str(p.get("Id") or p.get("PackageId") or p.get("Name") or ""): p for p in packages
        }
        bpmn_dir = analysis_dir / "iflows-bpmn"
        bpmn_by_iflow = self._index_bpmn_files(bpmn_dir)
        records: list[dict[str, Any]] = []
        for item in iflows:
            iflow_id = str(item.get("Id") or item.get("IflowId") or item.get("id") or "")
            if not iflow_id:
                continue
            name = str(item.get("Name") or iflow_id)
            package_id = str(item.get("PackageId") or item.get("packageId") or "")
            grouped = by_iflow.get(iflow_id, {})
            runtime = runtime_by_id.get(iflow_id) or runtime_by_name.get(name) or {}
            bpmn_file = bpmn_by_iflow.get(iflow_id) or bpmn_by_iflow.get(name) or ""
            rec = {
                "package_id": package_id,
                "package_name": str(package_by_id.get(package_id, {}).get("Name") or package_id),
                "iflow_id": iflow_id,
                "iflow_name": name,
                "version": item.get("Version"),
                "description": item.get("Description") or "",
                "runtime": self._runtime_summary(runtime),
                "bpmn_file": bpmn_file,
                "channels": grouped.get("channels", []),
                "channel_properties": grouped.get("channel_properties", []),
                "activities": grouped.get("activities", []),
                "activity_properties": grouped.get("activity_properties", []),
                "content_modifiers": grouped.get("content_modifiers", []),
                "groovy_scripts": grouped.get("groovy_scripts", []),
                "message_mappings": grouped.get("message_mappings", []),
                "xslt_mappings": grouped.get("xslt_mappings", []),
                "timers": grouped.get("timers", []),
                "participants": grouped.get("participants", []),
                "resources": grouped.get("resources", []),
                "configurations": grouped.get("configurations", []),
                "security_references": self._security_refs_for_iflow(
                    security_refs, iflow_id, package_id
                ),
                "scenario_lab_hints": self._scenario_hints(grouped, runtime),
                "risk_points": self._risk_points(grouped, runtime),
                "source_backed": True,
            }
            records.append(rec)
        counts = {
            "packages": len(packages),
            "iflows": len(iflows),
            "runtime_artifacts": len(runtimes),
            "deployed_iflows": self.count_deployed_iflows(runtimes),
            "channels": len(channels),
            "channel_properties": len(channel_properties),
            "activities": len(activities),
            "content_modifiers": len(content_modifiers),
            "groovy_scripts": len(groovy_scripts),
            "message_mappings": len(message_mappings),
            "xslt_mappings": len(xslt_mappings),
            "timers": len(timers),
            "resources": len(resources),
            "configurations": len(configurations),
            "bpmn_files": len(list(bpmn_dir.glob("*.iflw"))) if bpmn_dir.exists() else 0,
        }
        payload = {
            "source_system": "sap_ci",
            "source_type": "cpiview_compatible_evidence",
            "tenant_id": self.tenant_id,
            "generated_at": self._timestamp(),
            "input_dir": self._display(self.input_dir),
            "output_dir": self._display(self.output_dir),
            "counts": counts,
            "iflows": records,
            "source_backed_facts": [
                "CPIView odata JSON records",
                "CPIView analysis JSON records",
                "BPMN .iflw file names when present",
                "IntegrationRuntimeArtifacts from runtimes.json",
            ],
            "assumptions": [
                "Security values are references only; no credential values are copied into rich inventory.",
                "Runtime correlation uses runtime Id first and runtime Name as fallback.",
            ],
        }
        if write:
            self._write_json(self.target_rich_inventory, payload)
        return payload

    @classmethod
    def build_rich_inventory_from_resources(cls) -> dict[str, Any]:
        service = cls(input_dir=settings.resources_dir / "cpi" / "input")
        return service.build_rich_inventory(write=True)

    @staticmethod
    def _read_records(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
        if isinstance(data, dict):
            d = data.get("d")
            if isinstance(d, dict) and isinstance(d.get("results"), list):
                return [x for x in d["results"] if isinstance(x, dict)]
            if isinstance(data.get("results"), list):
                return [x for x in data["results"] if isinstance(x, dict)]
            if isinstance(data.get("value"), list):
                return [x for x in data["value"] if isinstance(x, dict)]
        return []

    @staticmethod
    def _iflow_id(row: dict[str, Any]) -> str:
        for key in ("iflowId", "IflowId", "IntegrationFlowId", "ArtifactId", "artifactId"):
            value = row.get(key)
            if value not in (None, ""):
                return str(value)
        return ""

    def _index_bpmn_files(self, bpmn_dir: Path) -> dict[str, str]:
        index: dict[str, str] = {}
        if not bpmn_dir.exists():
            return index
        for path in bpmn_dir.glob("*.iflw"):
            stem = path.stem
            if " --- " in stem:
                package, iflow = stem.split(" --- ", 1)
                index[iflow] = self._display(path)
                index[stem] = self._display(path)
                index[f"{package}/{iflow}"] = self._display(path)
            else:
                index[stem] = self._display(path)
        return index

    @staticmethod
    def _runtime_summary(runtime: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": runtime.get("Id") or runtime.get("id") or "",
            "name": runtime.get("Name") or runtime.get("name") or "",
            "type": runtime.get("Type") or runtime.get("type") or "",
            "status": runtime.get("Status") or runtime.get("status") or "",
            "deployed_by": runtime.get("DeployedBy") or "",
            "deployed_on": runtime.get("DeployedOn") or "",
            "source_backed": bool(runtime),
        }

    @staticmethod
    def _redact_security_row(row: dict[str, Any], source_file: str) -> dict[str, Any]:
        allowed = {}
        for key, value in row.items():
            low = key.lower()
            if any(
                secret in low for secret in ("password", "secret", "token", "value", "credential")
            ):
                if low in {"credentialname", "credential_name"}:
                    allowed[key] = value
                else:
                    allowed[key] = "***redacted***" if value not in (None, "") else value
            else:
                allowed[key] = value
        allowed["source_file"] = source_file
        return allowed

    @staticmethod
    def _security_refs_for_iflow(
        security_refs: list[dict[str, Any]], iflow_id: str, package_id: str
    ) -> list[dict[str, Any]]:
        refs: list[dict[str, Any]] = []
        for row in security_refs:
            blob = json.dumps(row, ensure_ascii=False)
            if iflow_id in blob or package_id in blob:
                refs.append(row)
        return refs[:50]

    @staticmethod
    def _scenario_hints(
        grouped: dict[str, list[dict[str, Any]]], runtime: dict[str, Any]
    ) -> list[str]:
        hints = []
        if grouped.get("channels"):
            hints.append(
                "Generate adapter-specific DEV/TEST scenarios from CPIView channel evidence."
            )
        if grouped.get("content_modifiers"):
            hints.append("Include header/property assertions from content modifier rows.")
        if grouped.get("groovy_scripts"):
            hints.append("Add script edge-case tests and MPL error signature checks.")
        if grouped.get("message_mappings") or grouped.get("xslt_mappings"):
            hints.append("Add mapping negative tests for mandatory fields and invalid formats.")
        if grouped.get("timers"):
            hints.append("Include schedule/timer validation and manual trigger strategy.")
        if str(runtime.get("Status") or "").upper() in {"STARTED", "DEPLOYED", "RUNNING"}:
            hints.append(
                "Runtime is deployed; correlate generated test plan with MPL after DEV/TEST execution."
            )
        return hints or [
            "Static CPIView evidence available; validate adapter details before execution."
        ]

    @staticmethod
    def _risk_points(
        grouped: dict[str, list[dict[str, Any]]], runtime: dict[str, Any]
    ) -> list[str]:
        risks = []
        channels = grouped.get("channels", [])
        if channels:
            adapters = sorted(
                {
                    str(c.get("componentType") or c.get("type") or "")
                    for c in channels
                    if c.get("componentType") or c.get("type")
                }
            )
            risks.append(
                "Adapter evidence found: "
                + ", ".join(adapters[:12])
                + "; validate connectivity, credentials, and endpoint reachability in DEV/TEST."
            )
        if grouped.get("groovy_scripts"):
            risks.append(
                "Groovy scripts require branch/error-path coverage and runtime log validation."
            )
        if grouped.get("message_mappings") or grouped.get("xslt_mappings"):
            risks.append(
                "Mappings require mandatory-field, datatype, and namespace negative tests."
            )
        if grouped.get("configurations"):
            risks.append(
                "Externalized parameters must be checked for DEV/TEST values before running scenarios."
            )
        if str(runtime.get("Status") or "").upper() not in {"STARTED", "DEPLOYED", "RUNNING"}:
            risks.append(
                "Runtime status is not confirmed as STARTED; deployment status must be verified before MPL-based testing."
            )
        return sorted(set(risks)) or [
            "Review CPIView evidence and confirm tenant/runtime scope before execution."
        ]

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )

    def _display(self, path: Path) -> str:
        return self._rel(path)

    @staticmethod
    def _rel(path: Path) -> str:
        try:
            return str(path.relative_to(settings.project_root)).replace("\\", "/")
        except Exception:
            return str(path)
