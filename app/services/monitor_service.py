from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from app.config import settings
from app.services.sap_cpi_client import SAPCPIClient, SAPCPIClientError
from app.services.sap_pipo_client import SAPPIPOClient
from app.services.sap_live_snapshot_service import SAPLiveSnapshotService
from app.services.cpiview_evidence_service import CPIViewEvidenceService
from app.services.cpi_native_evidence_service import NativeCPIEvidenceService

SUCCESS_STATUSES = {
    "COMPLETED",
    "COMPLETE",
    "SUCCESS",
    "SUCCEEDED",
    "DONE",
    "DELIVERED",
    "S",
    "OK",
    "SUCCESS-ONLY",
    "SUCCESS_ONLY",
    "SUCCESSFUL",
}
ERROR_STATUSES = {
    "FAILED",
    "FAIL",
    "ERROR",
    "CANCELLED",
    "CANCELED",
    "ABORTED",
    "E",
    "SYSTEMERROR",
    "SYSTEM_ERROR",
    "ERROR-HEAVY",
    "ERROR_HEAVY",
    "FAULT",
}
MonitorSystem = Literal["sap_ci", "sap_pipo"]


class MonitorService:
    """Build dashboard metrics from live SAP CI or SAP PI/PO, with local fallback."""

    def get_summary(
        self,
        system: str = "sap_ci",
        time_range: str = "past_24_hours",
        date_from: str | None = None,
        date_to: str | None = None,
        display_field: str = "last_updated",
    ) -> dict[str, Any]:
        """Return fast MPL-only monitoring counters for the selected time window.

        The monitoring dashboard must stay lightweight: it should not retrieve SAP
        design-time packages, iFlow/interface inventories, CPIView evidence or live
        snapshots while the operator is only checking message-throughput KPIs.
        Inventory discovery is exposed separately through get_inventory().
        """
        normalized_system = self._normalize_system(system)
        window = self._resolve_time_window(time_range, date_from, date_to, display_field)
        if normalized_system == "sap_pipo":
            return self._get_pipo_mpl_summary(window)
        return self._get_cpi_mpl_summary(window)

    def get_inventory(self, system: str = "sap_ci", inventory_type: str = "all") -> dict[str, Any]:
        """Load slower SAP design/configuration inventory on demand.

        This method is intentionally separated from get_summary() so that opening
        the Monitoring page reads only MPL counters. Operators can trigger this
        heavier inventory workflow explicitly from dashboard buttons.
        """
        normalized_system = self._normalize_system(system)
        requested_type = (inventory_type or "all").strip().lower()
        include_objects = requested_type in {"all", "objects", "packages", "configuration"}
        include_interfaces = requested_type in {"all", "interfaces", "iflows"}
        data: dict[str, Any] = {
            "system": normalized_system,
            "inventory_type": requested_type,
            "source": "local_fallback",
            "connection": {},
            "inventory": {
                "packages": 0,
                "interfaces": 0,
                "deployed": "N/A",
                "local_package_zips": self._count_local_packages(),
            },
            "items": {"packages": [], "interfaces": []},
            "notes": [
                "Inventory discovery is on-demand and is intentionally not executed by the MPL monitoring summary.",
            ],
        }

        if normalized_system == "sap_ci":
            cpiview_service = CPIViewEvidenceService()
            cpiview_status = cpiview_service.status()
            native_cpi_status = NativeCPIEvidenceService().status()
            evidence_available = cpiview_status.available or native_cpi_status.available
            evidence_counts = (
                cpiview_status.counts if cpiview_status.available else native_cpi_status.counts
            )
            if evidence_available:
                data["source"] = "cpiview_local" if cpiview_status.available else "native_cpi_local"
                data["inventory"].update(
                    {
                        "packages": evidence_counts.get(
                            "odata_packages", evidence_counts.get("packages", 0)
                        ),
                        "interfaces": evidence_counts.get(
                            "odata_iflows", evidence_counts.get("iflows", 0)
                        ),
                        "deployed": evidence_counts.get("deployed_iflows", "N/A"),
                        "cpiview_enabled": cpiview_status.enabled,
                        "cpiview_available": cpiview_status.available,
                        "native_cpi_enabled": native_cpi_status.enabled,
                        "native_cpi_available": native_cpi_status.available,
                    }
                )
            data["connection"] = {
                "system": "SAP CI",
                "cpi_configured": settings.cpi_is_configured,
                "cpi_status": "not_configured" if not settings.cpi_is_configured else "not_checked",
                "cpi_error": None,
            }
            if not settings.cpi_is_configured:
                return data
            try:
                client = SAPCPIClient()
                packages = (
                    client.get_integration_packages()
                    if include_objects or include_interfaces
                    else []
                )
                iflows = client.get_iflows(packages) if include_interfaces else []
                data["source"] = "sap_cpi_live"
                data["connection"].update({"cpi_status": "ok", "cpi_error": None})
                data["inventory"].update(
                    {
                        "packages": len(packages)
                        if include_objects
                        else data["inventory"].get("packages", 0),
                        "interfaces": len(iflows)
                        if include_interfaces
                        else data["inventory"].get("interfaces", 0),
                        "iflows": len(iflows)
                        if include_interfaces
                        else data["inventory"].get("interfaces", 0),
                        "deployed": SAPLiveSnapshotService.count_deployed_iflows(iflows)
                        if include_interfaces
                        else data["inventory"].get("deployed", "N/A"),
                    }
                )
                data["items"]["packages"] = packages[:200] if include_objects else []
                data["items"]["interfaces"] = iflows[:500] if include_interfaces else []
            except SAPCPIClientError as exc:
                data["connection"].update({"cpi_status": "error", "cpi_error": str(exc)})
            return data

        data["connection"] = {
            "system": "SAP PIPO",
            "pipo_configured": settings.pipo_is_configured,
            "pipo_live_endpoints_configured": settings.pipo_has_live_endpoints,
            "pipo_status": "not_configured" if not settings.pipo_is_configured else "not_checked",
            "pipo_error": None,
            "component_errors": {},
            "inventory_mode": settings.sap_pipo_inventory_mode,
        }
        if settings.pipo_dir_services and include_interfaces:
            services = [
                part.strip() for part in settings.pipo_dir_services.split(",") if part.strip()
            ]
            data["source"] = "pipo_dir_services"
            data["inventory"].update({"interfaces": len(services), "iflows": len(services)})
            data["items"]["interfaces"] = [{"name": value} for value in services]
        if not settings.pipo_is_configured:
            return data
        pipo_client = SAPPIPOClient()
        component_errors: dict[str, str] = {}
        pipo_packages: list[dict[str, Any]] = []
        interfaces: list[dict[str, Any]] = []
        if include_objects and settings.sap_pipo_packages_endpoint:
            try:
                pipo_packages = pipo_client.get_packages()
            except Exception as exc:
                component_errors["packages"] = str(exc)
        if include_interfaces and settings.sap_pipo_iflows_endpoint:
            try:
                interfaces = pipo_client.get_iflows()
            except Exception as exc:
                component_errors["interfaces"] = str(exc)
        if pipo_packages or interfaces:
            data["source"] = "sap_pipo_live"
        data["connection"].update(
            {
                "pipo_status": "ok" if not component_errors else "partial_ok",
                "pipo_error": None
                if not component_errors
                else "Some SAP PI/PO inventory components could not be read.",
                "component_errors": component_errors,
            }
        )
        data["inventory"].update(
            {
                "packages": len(pipo_packages)
                if include_objects
                else data["inventory"].get("packages", 0),
                "interfaces": len(interfaces)
                if interfaces
                else data["inventory"].get("interfaces", 0),
                "iflows": len(interfaces) if interfaces else data["inventory"].get("interfaces", 0),
            }
        )
        data["items"]["packages"] = pipo_packages[:200]
        data["items"]["interfaces"] = (
            interfaces[:500] if interfaces else data["items"].get("interfaces", [])
        )
        return data

    def _get_cpi_mpl_summary(self, window: dict[str, Any]) -> dict[str, Any]:
        local_mpl = self._read_local_mpl_summary(
            [
                settings.resources_dir / "mpl",
                settings.resources_dir / "cpi",
                settings.project_root / "exported_packages",
            ],
            window,
        )
        summary: dict[str, Any] = {
            "system": "sap_ci",
            "source": "local_fallback",
            "connection": {
                "system": "SAP CI",
                "cpi_configured": settings.cpi_is_configured,
                "cpi_status": "not_configured" if not settings.cpi_is_configured else "not_checked",
                "cpi_error": None,
                "lookback_hours": settings.sap_monitor_lookback_hours,
                "time_window": self._window_public(window),
                "summary_mode": "mpl_only",
            },
            "inventory": {
                "mode": "on_demand",
                "packages": "on demand",
                "iflows": "on demand",
                "deployed": "on demand",
            },
            "mpl": local_mpl,
            "notes": [
                "Monitoring summary is MPL-only for fast page loading.",
                "Design/configuration inventory is loaded separately from explicit dashboard actions.",
            ],
        }
        if not settings.cpi_is_configured:
            return summary
        try:
            logs = SAPCPIClient().get_message_processing_logs(
                start_time=window["start"],
                end_time=window["end"],
                display_field=window["cpi_field"],
            )
            logs = self._filter_records_by_time(logs, window)
            summary.update(
                {
                    "source": "sap_cpi_live",
                    "connection": {
                        "system": "SAP CI",
                        "cpi_configured": True,
                        "cpi_status": "ok",
                        "cpi_error": None,
                        "lookback_hours": settings.sap_monitor_lookback_hours,
                        "time_window": self._window_public(window),
                        "summary_mode": "mpl_only",
                    },
                    "mpl": self._summarize_mpl_records(logs),
                }
            )
        except SAPCPIClientError as exc:
            summary["connection"]["cpi_status"] = "error"
            summary["connection"]["cpi_error"] = str(exc)
        return summary

    def _get_pipo_mpl_summary(self, window: dict[str, Any]) -> dict[str, Any]:
        local_folders = [
            settings.resources_dir / "pipo" / "mpl",
            settings.resources_dir / "mpl" / "pipo",
            settings.project_root / "exported_packages" / "pipo",
        ]
        if settings.pipo_mpl_local_root:
            local_folders.append(Path(settings.pipo_mpl_local_root))
        local_mpl = self._read_local_mpl_summary(local_folders, window)
        summary: dict[str, Any] = {
            "system": "sap_pipo",
            "source": "local_fallback",
            "connection": {
                "system": "SAP PIPO",
                "pipo_configured": settings.pipo_is_configured,
                "pipo_live_endpoints_configured": settings.pipo_has_live_endpoints,
                "pipo_status": "not_configured"
                if not settings.pipo_is_configured
                else "not_checked",
                "pipo_error": None,
                "component_errors": {},
                "inventory_mode": settings.sap_pipo_inventory_mode,
                "mpl_mode": settings.sap_pipo_mpl_mode,
                "lookback_hours": settings.sap_pipo_monitor_lookback_hours,
                "time_window": self._window_public(window),
                "summary_mode": "mpl_only",
            },
            "inventory": {
                "mode": "on_demand",
                "packages": "on demand",
                "iflows": "on demand",
                "deployed": "on demand",
            },
            "mpl": local_mpl,
            "notes": [
                "Monitoring summary is MPL-only for fast page loading.",
                "PI/PO Directory/ESR/interface inventory is loaded separately from explicit dashboard actions.",
            ],
        }
        if not settings.pipo_is_configured:
            return summary
        if settings.pipo_mpl_source_mode == "local":
            summary["connection"]["pipo_status"] = "local_only"
            summary["notes"].append(
                "PIPO_MPL_SOURCE_MODE=local is active; live PI/PO calls are intentionally skipped."
            )
            return summary
        if not settings.sap_pipo_mpl_endpoint:
            summary["connection"]["pipo_status"] = "missing_live_endpoints"
            summary["connection"]["pipo_error"] = "SAP PI/PO MPL endpoint is not configured."
            return summary
        try:
            logs = SAPPIPOClient().get_message_processing_logs(
                start_time=window["start"], end_time=window["end"]
            )
            logs = self._filter_records_by_time(logs, window)
            summary["source"] = "sap_pipo_live"
            summary["connection"].update(
                {"pipo_status": "ok", "pipo_error": None, "component_errors": {}}
            )
            summary["mpl"] = self._summarize_mpl_records(logs)
        except Exception as exc:
            local_total = int(local_mpl.get("total", 0) or 0)
            if local_total > 0 and settings.pipo_mpl_use_local_on_live_error:
                summary["connection"].update(
                    {
                        "pipo_status": "fallback_ok",
                        "pipo_error": "SAP PI/PO live MPL call failed, but local MPL fallback contains usable records.",
                        "component_errors": {"mpl": str(exc)},
                    }
                )
            else:
                summary["connection"].update(
                    {
                        "pipo_status": "error",
                        "pipo_error": str(exc),
                        "component_errors": {"mpl": str(exc)},
                    }
                )
        return summary

    def _get_cpi_summary(self, window: dict[str, Any]) -> dict[str, Any]:
        local_packages = self._count_local_packages()
        local_mpl = self._read_local_mpl_summary(
            [
                settings.resources_dir / "mpl",
                settings.resources_dir / "cpi",
                settings.project_root / "exported_packages",
            ],
            window,
        )

        cpiview_service = CPIViewEvidenceService()
        cpiview_status = cpiview_service.status()
        native_cpi_status = NativeCPIEvidenceService().status()
        evidence_available = cpiview_status.available or native_cpi_status.available
        evidence_counts = (
            cpiview_status.counts if cpiview_status.available else native_cpi_status.counts
        )
        evidence_source = (
            "cpiview_local"
            if cpiview_status.available
            else ("native_cpi_local" if native_cpi_status.available else "local_fallback")
        )
        cpiview_deployed: int | str = (
            evidence_counts.get("deployed_iflows", "N/A") if evidence_available else "N/A"
        )
        cpiview_iflows = (
            evidence_counts.get("odata_iflows", evidence_counts.get("iflows", 0))
            if evidence_available
            else 0
        )
        cpiview_packages = (
            evidence_counts.get("odata_packages", evidence_counts.get("packages", 0))
            if evidence_available
            else 0
        )

        summary: dict[str, Any] = {
            "system": "sap_ci",
            "source": evidence_source,
            "connection": {
                "system": "SAP CI",
                "cpi_configured": settings.cpi_is_configured,
                "cpi_status": "not_configured" if not settings.cpi_is_configured else "not_checked",
                "cpi_error": None,
                "lookback_hours": settings.sap_monitor_lookback_hours,
                "time_window": self._window_public(window),
            },
            "inventory": {
                "packages": cpiview_packages or local_packages,
                "iflows": cpiview_iflows,
                "deployed": cpiview_deployed,
                "local_package_zips": local_packages,
                "cpiview_enabled": cpiview_status.enabled,
                "cpiview_available": cpiview_status.available,
                "native_cpi_enabled": native_cpi_status.enabled,
                "native_cpi_available": native_cpi_status.available,
            },
            "mpl": local_mpl,
            "notes": [
                "Live SAP CPI data is used only when SAP_CPI_* variables are configured and the tenant endpoints respond.",
                "Local fallback reads ZIP packages and resources/mpl/*.json files.",
                "CPIView local evidence is preferred for Deployed KPI and Scenario Lab enrichment when CPIVIEW_ENABLED=true.",
                "Native Python CPI evidence can replace CPIView/JAR after running /api/scenario-lab/download-native-cpi.",
            ],
            "cpiview": cpiview_status.__dict__,
            "native_cpi": native_cpi_status.__dict__,
        }

        if not settings.cpi_is_configured:
            return summary

        client = SAPCPIClient()
        try:
            packages = client.get_integration_packages()
            iflows = client.get_iflows(packages)
            logs = client.get_message_processing_logs(
                start_time=window["start"],
                end_time=window["end"],
                display_field=window["cpi_field"],
            )
            logs = self._filter_records_by_time(logs, window)
            summary.update(
                {
                    "source": "sap_cpi_live",
                    "connection": {
                        "system": "SAP CI",
                        "cpi_configured": True,
                        "cpi_status": "ok",
                        "cpi_error": None,
                        "lookback_hours": settings.sap_monitor_lookback_hours,
                        "time_window": self._window_public(window),
                    },
                    "inventory": {
                        "packages": len(packages),
                        "iflows": len(iflows),
                        "deployed": cpiview_deployed
                        if cpiview_status.available
                        else SAPLiveSnapshotService.count_deployed_iflows(iflows),
                        "local_package_zips": local_packages,
                        "cpiview_enabled": cpiview_status.enabled,
                        "cpiview_available": cpiview_status.available,
                        "native_cpi_enabled": native_cpi_status.enabled,
                        "native_cpi_available": native_cpi_status.available,
                    },
                    "mpl": self._summarize_mpl_records(logs),
                }
            )
            if cpiview_status.available:
                self._attach_snapshot_result(summary, lambda: cpiview_service.import_to_resources())
            else:
                self._attach_snapshot_result(
                    summary, lambda: SAPLiveSnapshotService().snapshot_cpi(packages, iflows, logs)
                )
        except SAPCPIClientError as exc:
            summary["connection"]["cpi_status"] = "error"
            summary["connection"]["cpi_error"] = str(exc)
        return summary

    def _get_pipo_summary(self, window: dict[str, Any]) -> dict[str, Any]:
        local_packages = self._count_local_packages()
        local_folders = [
            settings.resources_dir / "pipo" / "mpl",
            settings.resources_dir / "mpl" / "pipo",
            settings.project_root / "exported_packages" / "pipo",
        ]
        if settings.pipo_mpl_local_root:
            local_folders.append(Path(settings.pipo_mpl_local_root))
        local_mpl = self._read_local_mpl_summary(local_folders, window)

        summary: dict[str, Any] = {
            "system": "sap_pipo",
            "source": "local_fallback",
            "connection": {
                "system": "SAP PIPO",
                "pipo_configured": settings.pipo_is_configured,
                "pipo_live_endpoints_configured": settings.pipo_has_live_endpoints,
                "pipo_status": "not_configured"
                if not settings.pipo_is_configured
                else "not_checked",
                "pipo_error": None,
                "component_errors": {},
                "inventory_mode": settings.sap_pipo_inventory_mode,
                "mpl_mode": settings.sap_pipo_mpl_mode,
                "lookback_hours": settings.sap_pipo_monitor_lookback_hours,
                "time_window": self._window_public(window),
            },
            "inventory": {
                "packages": local_packages,
                "iflows": 0,
                "deployed": "N/A",
                "local_package_zips": local_packages,
            },
            "mpl": local_mpl,
            "notes": [
                "SAP PI/PO live monitor is SOAP-aware. Directory SOAP inventory is non-blocking unless JSON/proxy mode is enabled.",
                "MPL live monitor uses AdapterMessageMonitoring SOAP POST and the legacy PIPO_MPL_LIST_TEMPLATE when available.",
                "Local fallback reads resources/pipo/mpl/*.json, exported_packages/pipo/*.json and PIPO_MPL_LOCAL_ROOT if configured.",
            ],
        }

        if not settings.pipo_is_configured:
            return summary

        if settings.pipo_mpl_source_mode == "local":
            summary["connection"]["pipo_status"] = "local_only"
            summary["connection"]["pipo_error"] = None
            summary["notes"].append(
                "PIPO_MPL_SOURCE_MODE=local is active; live PI/PO calls are intentionally skipped."
            )
            return summary

        if not settings.pipo_has_live_endpoints:
            summary["connection"]["pipo_status"] = "missing_live_endpoints"
            summary["connection"]["pipo_error"] = (
                "SAP PI/PO credentials are configured, but SAP_PIPO_* endpoints or legacy PIPO_MPL_ENDPOINT are empty."
            )
            return summary

        client = SAPPIPOClient()
        live_used = False
        component_errors: dict[str, str] = {}

        packages: list[dict[str, Any]] = []
        if settings.sap_pipo_packages_endpoint:
            try:
                packages = client.get_packages()
                if packages:
                    live_used = True
            except Exception as exc:
                component_errors["packages"] = str(exc)

        iflows: list[dict[str, Any]] = []
        if settings.sap_pipo_iflows_endpoint:
            try:
                iflows = client.get_iflows()
                if iflows:
                    live_used = True
            except Exception as exc:
                component_errors["iflows"] = str(exc)

        logs: list[dict[str, Any]] = []
        if settings.sap_pipo_mpl_endpoint:
            try:
                logs = client.get_message_processing_logs(
                    start_time=window["start"], end_time=window["end"]
                )
                logs = self._filter_records_by_time(logs, window)
                live_used = True
            except Exception as exc:
                component_errors["mpl"] = str(exc)

        if live_used:
            summary["source"] = "sap_pipo_live"
            summary["connection"].update(
                {
                    "pipo_status": "ok" if not component_errors else "partial_ok",
                    "pipo_error": None
                    if not component_errors
                    else "Some SAP PI/PO components could not be read. See component_errors.",
                    "component_errors": component_errors,
                }
            )
            summary["inventory"] = {
                "packages": len(packages) if packages else local_packages,
                "iflows": len(iflows),
                "deployed": "N/A",
                "local_package_zips": local_packages,
            }
            if logs:
                summary["mpl"] = self._summarize_mpl_records(logs)
            self._attach_snapshot_result(
                summary,
                lambda: SAPLiveSnapshotService().snapshot_pipo(
                    packages, iflows, logs, component_errors
                ),
            )
        else:
            local_total = int(local_mpl.get("total", 0) or 0)
            if settings.pipo_dir_services and not component_errors:
                services = [
                    part.strip() for part in settings.pipo_dir_services.split(",") if part.strip()
                ]
                summary["source"] = "sap_pipo_live"
                summary["connection"].update(
                    {
                        "pipo_status": "partial_ok",
                        "pipo_error": "SAP PI/PO credentials and DIR service catalog are configured; no live JSON inventory endpoint returned objects.",
                        "component_errors": {},
                    }
                )
                summary["inventory"] = {
                    "packages": local_packages,
                    "iflows": len(services),
                    "deployed": "N/A",
                    "local_package_zips": local_packages,
                }
                self._attach_snapshot_result(
                    summary, lambda: SAPLiveSnapshotService().snapshot_pipo([], [], [], {})
                )
            elif component_errors and local_total > 0 and settings.pipo_mpl_use_local_on_live_error:
                summary["connection"]["pipo_status"] = "fallback_ok"
                summary["connection"]["pipo_error"] = (
                    "SAP PI/PO live call failed, but local MPL fallback contains usable records. "
                    "See component_errors for the live error."
                )
                summary["connection"]["component_errors"] = component_errors
                summary["notes"].append(
                    "Live PI/PO failed; dashboard is showing normalized local fallback metrics."
                )
            else:
                summary["connection"]["pipo_status"] = (
                    "error" if component_errors else "no_live_data"
                )
                summary["connection"]["pipo_error"] = (
                    "SAP PI/PO live endpoints responded with no usable records. See component_errors."
                    if component_errors
                    else "SAP PI/PO live endpoints are configured, but no live records were returned."
                )
                summary["connection"]["component_errors"] = component_errors
        return summary

    def _attach_snapshot_result(self, summary: dict[str, Any], snapshot_fn: Any) -> None:
        """Run read-only live snapshot without breaking monitor summary."""
        try:
            result = snapshot_fn()
            summary["live_snapshot"] = result
            if result.get("status") == "ok":
                summary.setdefault("notes", []).append(
                    f"Live snapshot saved: {result.get('snapshot_manifest')}"
                )
        except Exception as exc:
            summary["live_snapshot"] = {"status": "error", "error": str(exc)}
            summary.setdefault("notes", []).append(
                "Live snapshot failed; monitoring metrics were still returned."
            )

    def _normalize_time_range(self, value: str | None) -> str:
        raw = (value or "past_24_hours").strip().lower().replace(" ", "_").replace("-", "_")
        aliases = {
            "past_hour": "past_hour",
            "1h": "past_hour",
            "past_1_hour": "past_hour",
            "past_24_hours": "past_24_hours",
            "24h": "past_24_hours",
            "past_day": "past_24_hours",
            "past_week": "past_week",
            "past_wek": "past_week",
            "7d": "past_week",
            "past_month": "past_month",
            "30d": "past_month",
            "custom": "custom",
        }
        return aliases.get(raw, "past_24_hours")

    def _resolve_time_window(
        self,
        time_range: str | None,
        date_from: str | None,
        date_to: str | None,
        display_field: str | None,
    ) -> dict[str, Any]:
        normalized_range = self._normalize_time_range(time_range)
        now = datetime.now(timezone.utc)
        if normalized_range == "custom":
            end = self._parse_datetime(date_to) or now
            start = self._parse_datetime(date_from) or (end - timedelta(hours=24))
        else:
            hours = {
                "past_hour": 1,
                "past_24_hours": 24,
                "past_week": 24 * 7,
                "past_month": 24 * 30,
            }[normalized_range]
            end = now
            start = now - timedelta(hours=hours)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if start > end:
            start, end = end, start
        display = (
            (display_field or "last_updated").strip().lower().replace(" ", "_").replace("-", "_")
        )
        # SAP CPI MPL OData filtering is reliable on LogStart. The dashboard's
        # Display Messages option controls local timestamp preference, but the
        # server-side CPI query must not switch to UI-only labels such as
        # LastUpdated, because some tenants ignore or reject that field and then
        # return the same unfiltered counters for every selected period.
        cpi_field = (settings.sap_cpi_mpl_filter_field or "LogStart").strip() or "LogStart"
        return {
            "range": normalized_range,
            "start": start,
            "end": end,
            "display_field": display,
            "cpi_field": cpi_field,
        }

    def _parse_datetime(self, value: str | None) -> datetime | None:
        if not value:
            return None
        text = str(value).strip()
        if not text:
            return None
        text = text.replace("Z", "+00:00")
        # SAP OData / JSON exports may include /Date(1714823776000)/.
        match = re.search(r"/Date\((\d+)", text)
        if match:
            return datetime.fromtimestamp(int(match.group(1)) / 1000, tz=timezone.utc)
        for candidate in (text, text.replace(" ", "T")):
            try:
                parsed = datetime.fromisoformat(candidate)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
            except ValueError:
                pass
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                return datetime.strptime(text[:19] if "%H" in fmt else text[:10], fmt).replace(
                    tzinfo=timezone.utc
                )
            except ValueError:
                continue
        return None

    def _window_public(self, window: dict[str, Any]) -> dict[str, str]:
        return {
            "range": str(window.get("range", "past_24_hours")),
            "start": window["start"].isoformat(),
            "end": window["end"].isoformat(),
            "display_field": str(window.get("display_field", "last_updated")),
        }

    def _record_datetime(
        self, record: dict[str, Any], display_field: str = "last_updated"
    ) -> datetime | None:
        preferred_keys = (
            ("LastUpdated", "lastUpdated", "last_updated", "UpdatedAt", "updated_at")
            if display_field in {"last_updated", "lastupdated"}
            else ("LogStart", "StartTime", "startTime", "Timestamp", "timestamp", "Date", "date")
        )
        fallback_keys = (
            "LogStart",
            "StartTime",
            "startTime",
            "LastUpdated",
            "lastUpdated",
            "Timestamp",
            "timestamp",
            "Date",
            "date",
            "LogEnd",
            "EndTime",
            "endTime",
        )
        for key in preferred_keys + fallback_keys:
            if key in record:
                parsed = self._parse_datetime(str(record.get(key)))
                if parsed:
                    return parsed
        return None

    def _filter_records_by_time(
        self, records: list[dict[str, Any]], window: dict[str, Any]
    ) -> list[dict[str, Any]]:
        start = window["start"]
        end = window["end"]
        display = str(window.get("display_field", "last_updated"))
        filtered: list[dict[str, Any]] = []
        for record in records:
            record_dt = self._record_datetime(record, display)
            if record_dt is None:
                # Keep records without parseable timestamps so local fallback does not
                # incorrectly hide evidence that lacks a normalized date field.
                filtered.append(record)
                continue
            if record_dt.tzinfo is None:
                record_dt = record_dt.replace(tzinfo=timezone.utc)
            if start <= record_dt <= end:
                filtered.append(record)
        return filtered

    def _normalize_system(self, system: str | None) -> MonitorSystem:
        raw = (system or "sap_ci").strip().lower().replace("-", "_")
        if raw in {"sap_pipo", "pipo", "sap_pi_po", "sap_pi/po"}:
            return "sap_pipo"
        return "sap_ci"

    def _count_local_packages(self) -> int:
        folders = [
            settings.upload_dir,
            settings.uploaded_knowledge_dir,
            settings.project_root / "sample_packages",
        ]
        seen: set[Path] = set()
        for folder in folders:
            if folder.exists():
                seen.update(path.resolve() for path in folder.glob("*.zip"))
        return len(seen)

    def _read_local_mpl_summary(
        self, folders: list[Path], window: dict[str, Any]
    ) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        for folder in folders:
            if not folder.exists():
                continue
            for path in folder.rglob("*.json"):
                records.extend(self._extract_records_from_json_file(path))
        return self._summarize_mpl_records(self._filter_records_by_time(records, window))

    def _extract_records_from_json_file(self, path: Path) -> list[dict[str, Any]]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return []
        return self._extract_records(payload)

    def _extract_records(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        if isinstance(payload.get("value"), list):
            return [item for item in payload["value"] if isinstance(item, dict)]
        if isinstance(payload.get("MessageProcessingLogs"), list):
            return [item for item in payload["MessageProcessingLogs"] if isinstance(item, dict)]
        d = payload.get("d")
        if isinstance(d, dict) and isinstance(d.get("results"), list):
            return [item for item in d["results"] if isinstance(item, dict)]
        if isinstance(payload.get("results"), list):
            return [item for item in payload["results"] if isinstance(item, dict)]
        dict_values = [v for v in payload.values() if isinstance(v, dict)]
        return dict_values

    def _normalize_status(self, record: dict[str, Any]) -> str:
        """Return a normalized monitoring status for SAP CI and SAP PI/PO records.

        SAP CI commonly returns values such as COMPLETED, FAILED or DISCARDED.
        SAP PI/PO local/MPL exports can contain shorter or landscape-specific values
        such as S, E, SYSTEMERROR, SUCCESS-ONLY or ERROR-HEAVY. This helper keeps
        monitor summaries stable across both systems and avoids backend crashes when
        local fallback files are used.
        """
        if not isinstance(record, dict):
            return "UNKNOWN"

        status_keys = (
            "Status",
            "status",
            "MessageStatus",
            "messageStatus",
            "MessageState",
            "messageState",
            "ProcessingStatus",
            "processingStatus",
            "OverallStatus",
            "overallStatus",
            "LogStatus",
            "logStatus",
            "state",
            "State",
        )
        raw_value = None
        for key in status_keys:
            value = record.get(key)
            if value not in (None, ""):
                raw_value = value
                break

        if raw_value in (None, ""):
            # Infer an error state from common error fields if no explicit status exists.
            for key in (
                "ErrorMessage",
                "errorMessage",
                "Error",
                "error",
                "ErrorText",
                "errorText",
                "Fault",
                "fault",
            ):
                value = record.get(key)
                if value not in (None, ""):
                    return "ERROR"
            return "UNKNOWN"

        status = str(raw_value).strip().upper()
        if not status:
            return "UNKNOWN"

        # Normalize noisy status strings that can appear in XML/JSON exports.
        status = status.replace(" ", "_").replace("-", "_")
        status = status.replace("SUCCESS_ONLY", "SUCCESS-ONLY")
        status = status.replace("ERROR_HEAVY", "ERROR-HEAVY")
        if status in {"COMPLETED_SUCCESSFULLY", "SUCCESSFUL", "OK", "DONE"}:
            return "SUCCESS"
        if status in {"SYSTEM_ERROR", "APPLICATION_ERROR", "TECHNICAL_ERROR", "FAULT"}:
            return "SYSTEMERROR"
        if status in {"CANCELED", "CANCELLED", "ABORTED"}:
            return "FAILED"
        return status

    def _summarize_mpl_records(self, records: list[dict[str, Any]]) -> dict[str, Any]:
        success = 0
        errors = 0
        status_breakdown: dict[str, int] = {}
        for record in records:
            status = self._normalize_status(record)
            status_breakdown[status] = status_breakdown.get(status, 0) + 1
            error_message = (
                record.get("ErrorMessage")
                or record.get("errorMessage")
                or record.get("Error")
                or record.get("error")
            )
            if (
                status in ERROR_STATUSES
                or status.startswith("ERROR")
                or status.endswith("ERROR")
                or error_message
            ):
                errors += 1
            elif status in SUCCESS_STATUSES or "COMPLETE" in status or status.startswith("SUCCESS"):
                success += 1
        return {
            "success": success,
            "errors": errors,
            "total": len(records),
            "status_breakdown": status_breakdown,
        }

    def get_messages(
        self,
        system: str = "sap_ci",
        status: str = "COMPLETED",
        time_range: str = "past_24_hours",
        date_from: str | None = None,
        date_to: str | None = None,
        display_field: str = "last_updated",
    ) -> dict[str, Any]:
        """Return operator-facing MPL message rows for a selected normalized status.

        The dashboard uses this endpoint from links opened in a new browser tab.
        It reads local archived MPL evidence from resources/ and, when live clients
        are configured, attempts to include live records before falling back safely.
        """
        normalized_system = self._normalize_system(system)
        window = self._resolve_time_window(time_range, date_from, date_to, display_field)
        requested = (status or "COMPLETED").strip().upper()
        records: list[dict[str, Any]] = []
        source_modes: list[str] = []

        # Attempt live first when configured; fall back without failing the UI.
        try:
            if normalized_system == "sap_ci" and settings.cpi_is_configured:
                records.extend(
                    SAPCPIClient().get_message_processing_logs(
                        start_time=window["start"],
                        end_time=window["end"],
                        display_field=window["cpi_field"],
                    )
                )
                source_modes.append("live_mpl")
            elif (
                normalized_system == "sap_pipo"
                and settings.pipo_is_configured
                and settings.pipo_has_live_endpoints
                and settings.sap_pipo_mpl_endpoint
            ):
                records.extend(
                    SAPPIPOClient().get_message_processing_logs(
                        start_time=window["start"], end_time=window["end"]
                    )
                )
                source_modes.append("live_mpl")
        except Exception:
            pass

        local_folders = self._message_source_folders(normalized_system)
        for folder in local_folders:
            if folder.exists():
                for path in folder.rglob("*.json"):
                    for record in self._extract_records_from_json_file(path):
                        enriched = dict(record)
                        enriched.setdefault(
                            "_source_file",
                            str(path.relative_to(settings.project_root))
                            if path.is_relative_to(settings.project_root)
                            else str(path),
                        )
                        records.append(enriched)
        if local_folders:
            source_modes.append("archived_mpl")

        records = self._filter_records_by_time(records, window)
        rows = []
        for record in records:
            normalized = self._normalize_status(record)
            is_success = (
                normalized in SUCCESS_STATUSES
                or "COMPLETE" in normalized
                or normalized.startswith("SUCCESS")
            )
            error_text = self._first(
                record,
                "ErrorMessage",
                "errorMessage",
                "Error",
                "error",
                "ErrorText",
                "Fault",
                "fault",
            )
            is_error = (
                normalized in ERROR_STATUSES
                or normalized.startswith("ERROR")
                or normalized.endswith("ERROR")
                or bool(error_text)
            )
            include = False
            if requested in {"COMPLETED", "COMPLETE", "SUCCESS", "SUCCESSFUL"}:
                include = is_success and not is_error
            elif requested in {"FAILED", "ERROR", "SYSTEMERROR"}:
                include = is_error
            else:
                include = normalized == requested
            if include:
                rows.append(self._message_row(record, normalized))

        rows = self._dedupe_rows(rows)
        return {
            "system": normalized_system,
            "status_filter": requested,
            "source_modes": sorted(set(source_modes)),
            "time_window": self._window_public(window),
            "count": len(rows),
            "messages": rows,
        }

    def _message_source_folders(self, system: MonitorSystem) -> list[Path]:
        if system == "sap_pipo":
            folders = [
                settings.resources_dir / "pipo" / "mpl",
                settings.resources_dir / "mpl" / "pipo",
            ]
            if settings.pipo_mpl_local_root:
                folders.append(Path(settings.pipo_mpl_local_root))
            return folders
        return [
            settings.resources_dir / "cpi",
            settings.resources_dir / "mpl",
            settings.resources_dir / "mpl" / "cpi",
        ]

    def _first(self, record: dict[str, Any], *names: str) -> str:
        for name in names:
            value = record.get(name)
            if value not in (None, ""):
                return str(value)
        return ""

    def _message_row(self, record: dict[str, Any], normalized_status: str) -> dict[str, Any]:
        start = self._first(
            record, "LogStart", "StartTime", "startTime", "Timestamp", "timestamp", "Date", "date"
        )
        date_part = start[:10] if start else "missing"
        time_part = start[11:19] if len(start) >= 19 else "missing"
        return {
            "date": date_part,
            "time": time_part,
            "status": normalized_status,
            "message_guid": self._first(
                record, "MessageGuid", "messageGuid", "MPL_ID", "MessageId", "message_id"
            )
            or "missing",
            "package_name": self._first(
                record, "PackageName", "packageName", "Package", "package", "IntegrationPackageName"
            )
            or "missing",
            "iflow_name": self._first(
                record,
                "IntegrationFlowName",
                "IFlowName",
                "iflow",
                "Interface",
                "interface_id",
                "IntegrationFlow",
            )
            or "UNKNOWN_IFLOW",
            "sender": self._first(record, "Sender", "sender", "SenderComponent", "senderComponent")
            or "n/a",
            "sender_adapter": self._first(
                record,
                "SenderAdapter",
                "senderAdapter",
                "SenderAdapterType",
                "senderAdapterType",
                "InboundAdapter",
            )
            or "missing",
            "receiver": self._first(
                record, "Receiver", "receiver", "ReceiverComponent", "receiverComponent"
            )
            or "n/a",
            "receiver_adapter": self._first(
                record,
                "ReceiverAdapter",
                "receiverAdapter",
                "ReceiverAdapterType",
                "receiverAdapterType",
                "OutboundAdapter",
            )
            or "missing",
            "log_start": start or "missing",
            "log_end": self._first(record, "LogEnd", "EndTime", "endTime") or "missing",
            "source_file": self._first(record, "_source_file") or "live_mpl",
        }

    def _dedupe_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen: set[tuple[str, str, str]] = set()
        deduped: list[dict[str, Any]] = []
        for row in rows:
            key = (row.get("message_guid", ""), row.get("iflow_name", ""), row.get("log_start", ""))
            if key in seen:
                continue
            seen.add(key)
            deduped.append(row)
        return sorted(
            deduped, key=lambda row: (row.get("date", ""), row.get("time", "")), reverse=True
        )

    def export_latest_local_mpl_zip(self) -> Path:
        target = settings.exports_dir / "Latest_Local_MPL_Export.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            for mpl_dir in [
                settings.resources_dir / "mpl",
                settings.resources_dir / "pipo" / "mpl",
            ]:
                if mpl_dir.exists():
                    for path in mpl_dir.rglob("*"):
                        if path.is_file():
                            archive.write(path, path.relative_to(settings.resources_dir))
        return target
