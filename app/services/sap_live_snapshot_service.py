from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.scenario_lab_config import get_scenario_lab_path_config


class SAPLiveSnapshotService:
    """Persist read-only SAP live evidence for later Scenario Lab execution.

    Snapshot files intentionally exclude secrets. The service is best-effort:
    failures are returned to the caller and must not block monitoring.
    """

    CPI_DEPLOYED_KEYS = (
        "Deployed",
        "IsDeployed",
        "IsActive",
        "Active",
        "DeploymentStatus",
        "DeployState",
        "RuntimeStatus",
        "Status",
        "LifeCycleStatus",
    )

    def snapshot_cpi(
        self,
        packages: list[dict[str, Any]],
        iflows: list[dict[str, Any]],
        logs: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        if not settings.sap_live_snapshot_enabled:
            return {"status": "skipped", "reason": "SAP_LIVE_SNAPSHOT_ENABLED=false"}
        config = get_scenario_lab_path_config("sap_ci")
        root = config.primary_path
        root.mkdir(parents=True, exist_ok=True)
        timestamp = self._timestamp()
        deployed_count = self.count_deployed_iflows(iflows)
        normalized_iflows = [self._normalize_cpi_iflow(item) for item in iflows]
        inventory = {
            "source_system": "sap_ci",
            "generated_at": timestamp,
            "packages_count": len(packages),
            "iflows_count": len(iflows),
            "deployed_count": deployed_count,
            "download_content_enabled": bool(settings.sap_cpi_design_download_content),
            "artifact_types": settings.sap_cpi_design_artifact_types,
            "iflows": normalized_iflows,
        }
        files = {
            "integration_packages.json": packages,
            "integration_designtime_artifacts.json": iflows,
            "iflow_inventory.json": inventory,
        }
        if logs is not None:
            files["message_processing_logs_sample.json"] = logs[:1000]
        written: list[str] = []
        for name, payload in files.items():
            path = root / name
            self._write_json(path, payload)
            written.append(self._rel(path))
        manifest = {
            "source_system": "sap_ci",
            "generated_at": timestamp,
            "target_dir": self._rel(root),
            "packages_count": len(packages),
            "iflows_count": len(iflows),
            "deployed_count": deployed_count,
            "files": written,
            "secret_handling": "credentials are read from .env only and are not persisted in snapshot files",
        }
        manifest_path = root / "snapshot_manifest.json"
        self._write_json(manifest_path, manifest)
        return {
            "status": "ok",
            "snapshot_manifest": self._rel(manifest_path),
            "deployed_count": deployed_count,
            "files": written,
        }

    def snapshot_pipo(
        self,
        packages: list[dict[str, Any]] | None = None,
        iflows: list[dict[str, Any]] | None = None,
        logs: list[dict[str, Any]] | None = None,
        component_errors: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if not settings.sap_live_snapshot_enabled:
            return {"status": "skipped", "reason": "SAP_LIVE_SNAPSHOT_ENABLED=false"}
        config = get_scenario_lab_path_config("sap_pipo")
        esr_id_root = config.primary_path
        ico_root = config.secondary_path
        esr_id_root.mkdir(parents=True, exist_ok=True)
        ico_root.mkdir(parents=True, exist_ok=True)
        timestamp = self._timestamp()
        packages = packages or []
        iflows = iflows or []
        logs = logs or []
        services = self._pipo_service_names()
        interface_seeds = self._build_pipo_interface_seeds(packages, iflows, logs, services)
        esr_manifest = {
            "source_system": "sap_pipo",
            "generated_at": timestamp,
            "dir_base_url_configured": bool(settings.sap_pipo_base_url),
            "esr_tpz_configured": bool(settings.pipo_demo_esr_tpz),
            "esr_tpz_reference": self._safe_path_reference(settings.pipo_demo_esr_tpz),
            "dir_services": services,
            "packages_count": len(packages),
            "interface_seeds_count": len(interface_seeds),
            "component_errors": component_errors or {},
            "secret_handling": "credentials are read from .env only and are not persisted in snapshot files",
        }
        ico_payload = {
            "source_system": "sap_pipo",
            "generated_at": timestamp,
            "objects_count": len(iflows),
            "objects": iflows,
            "derived_from": "SAP_PIPO_IFLOWS_ENDPOINT when configured, otherwise DIR service names and MPL records",
        }
        files = []
        for path, payload in [
            (
                esr_id_root / "dir_services_snapshot.json",
                {"generated_at": timestamp, "services": services},
            ),
            (esr_id_root / "interface_seeds.json", interface_seeds),
            (esr_id_root / "esr_metadata_manifest.json", esr_manifest),
            (ico_root / "integrated_configurations.json", ico_payload),
            (ico_root / "objects.json", ico_payload),
        ]:
            self._write_json(path, payload)
            files.append(self._rel(path))
        if logs:
            mpl_path = esr_id_root / "message_processing_logs_sample.json"
            self._write_json(mpl_path, logs[:1000])
            files.append(self._rel(mpl_path))
        manifest_path = ico_root / "snapshot_manifest.json"
        self._write_json(
            manifest_path,
            {
                "source_system": "sap_pipo",
                "generated_at": timestamp,
                "files": files,
                "component_errors": component_errors or {},
            },
        )
        return {
            "status": "ok",
            "snapshot_manifest": self._rel(manifest_path),
            "interface_seeds_count": len(interface_seeds),
            "files": files,
        }

    @classmethod
    def count_deployed_iflows(cls, iflows: list[dict[str, Any]]) -> int | str:
        known = 0
        deployed = 0
        for item in iflows:
            status = cls._deployment_status(item)
            if status == "unknown":
                continue
            known += 1
            if status == "deployed":
                deployed += 1
        return deployed if known else "N/A"

    @classmethod
    def _deployment_status(cls, item: dict[str, Any]) -> str:
        for key in cls.CPI_DEPLOYED_KEYS:
            if key not in item:
                continue
            raw = item.get(key)
            if isinstance(raw, bool):
                return "deployed" if raw else "not_deployed"
            text = str(raw).strip().lower()
            if not text:
                continue
            if text in {
                "true",
                "yes",
                "y",
                "1",
                "active",
                "deployed",
                "started",
                "running",
                "ok",
                "success",
            }:
                return "deployed"
            if text in {
                "false",
                "no",
                "n",
                "0",
                "inactive",
                "undeployed",
                "not_deployed",
                "stopped",
                "draft",
            }:
                return "not_deployed"
        return "unknown"

    def _normalize_cpi_iflow(self, item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": self._first(item, "Id", "ID", "Name", "TechnicalName"),
            "name": self._first(item, "Name", "Id", "ID", "TechnicalName"),
            "package_id": self._first(item, "PackageId", "PackageID", "PackageName"),
            "version": self._first(item, "Version", "ArtifactVersion"),
            "deployment_status": self._deployment_status(item),
            "raw": item,
        }

    def _build_pipo_interface_seeds(
        self,
        packages: list[dict[str, Any]],
        iflows: list[dict[str, Any]],
        logs: list[dict[str, Any]],
        services: list[str],
    ) -> list[dict[str, Any]]:
        records = iflows or packages
        seeds: list[dict[str, Any]] = []
        for idx, item in enumerate(records):
            name = (
                self._first(item, "Name", "name", "ObjectName", "object_name", "Id", "ID")
                or f"PIPO_OBJECT_{idx + 1}"
            )
            seeds.append(
                {
                    "canonical_key": self._slug(str(name)),
                    "interface_name": str(name),
                    "object_name": str(name),
                    "interface_namespace": self._first(
                        item, "Namespace", "namespace", "InterfaceNamespace"
                    )
                    or "",
                    "sender_component": self._first(
                        item, "Sender", "SenderComponent", "sender_component"
                    )
                    or "PIPO_SENDER",
                    "receiver_components": self._list_from(
                        item, "Receivers", "ReceiverComponents", "receiver_components"
                    ),
                    "communication_channel_names": self._list_from(
                        item, "Channels", "CommunicationChannels", "communication_channel_names"
                    ),
                    "operation_mappings": self._list_from(
                        item, "OperationMappings", "operation_mappings", "Mappings"
                    ),
                    "qos": self._first(item, "QoS", "qos", "QualityOfService") or "",
                    "source_backed": True,
                    "raw": item,
                }
            )
        if not seeds and logs:
            names = sorted(
                {
                    str(
                        self._first(
                            log,
                            "Interface",
                            "InterfaceName",
                            "interface_name",
                            "SenderInterface",
                            "ReceiverInterface",
                        )
                        or ""
                    ).strip()
                    for log in logs
                }
            )
            for name in [n for n in names if n]:
                seeds.append(
                    {
                        "canonical_key": self._slug(name),
                        "interface_name": name,
                        "object_name": name,
                        "source_backed": True,
                        "raw_source": "MPL",
                    }
                )
        if not seeds and services:
            for service in services:
                seeds.append(
                    {
                        "canonical_key": self._slug(service),
                        "interface_name": service,
                        "object_name": service,
                        "source_backed": False,
                        "raw_source": "PIPO_DEMO_DIR_SERVICES",
                    }
                )
        return seeds

    def _pipo_service_names(self) -> list[str]:
        raw = settings.pipo_dir_services or ""
        return [part.strip() for part in raw.split(",") if part.strip()]

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
        )

    @staticmethod
    def _first(item: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            value = item.get(key)
            if value not in (None, ""):
                return value
        return ""

    @staticmethod
    def _list_from(item: dict[str, Any], *keys: str) -> list[str]:
        for key in keys:
            value = item.get(key)
            if isinstance(value, list):
                return [str(v) for v in value if str(v).strip()]
            if isinstance(value, str) and value.strip():
                return [part.strip() for part in value.split(",") if part.strip()]
        return []

    @staticmethod
    def _slug(value: str) -> str:
        text = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
        return text.strip("_") or "UNKNOWN"

    @staticmethod
    def _safe_path_reference(value: str) -> str:
        if not value:
            return ""
        try:
            return str(Path(value))
        except Exception:
            return str(value)

    @staticmethod
    def _rel(path: Path) -> str:
        try:
            return str(path.relative_to(settings.project_root)).replace("\\", "/")
        except ValueError:
            return str(path)
