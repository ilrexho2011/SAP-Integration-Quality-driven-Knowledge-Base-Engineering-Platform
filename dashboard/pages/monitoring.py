from __future__ import annotations

from datetime import datetime, timedelta
from urllib.parse import urlencode

import requests
import streamlit as st

from app.config import settings

TEXT = {
    "en": {
        "monitor": "Monitoring Events",
        "source": "Data Source",
        "packages": "Packages",
        "iflows": "iFlows",
        "deployed": "Deployed",
        "inventory_actions": "On-demand inventory",
        "inventory_caption": "Monitoring loads only MPL numeric counters. Use these actions only when design/configuration inventory is needed.",
        "inventory_objects": "Inventory design/config objects",
        "inventory_interfaces": "Inventory interfaces / iFlows",
        "inventory_result": "Inventory result",
        "inventory_summary": "Inventory summary",
        "mpl_success": "Success Mes.",
        "mpl_errors": "Failed Mes.",
        "mpl_retry": "Retry Mes.",
        "mpl_total": "Total Mes.",
        "mpl_deployed_iflows": "Deployed iFlows",
        "connection": "Connection Diagnostics",
        "refresh": "Refresh monitor data",
        "time_range": "Monitor time range",
        "past_hour": "Past Hour",
        "past_24_hours": "Past 24 Hours",
        "past_week": "Past Week",
        "past_month": "Past Month",
        "custom": "Custom",
        "display_messages": "Display Messages",
        "last_updated": "Last Updated",
        "log_start": "Log Start",
        "from": "From",
        "to": "To",
        "feedback_source": "Feedback source",
        "feedback_none": "None",
        "feedback_latest": "Latest feedback",
        "feedback_selected": "Select feedback file",
        "feedback_file_path": "Feedback JSON file path",
        "apply_remediation_hints": "Apply remediation hints during regeneration",
        "local_fallback": "Local fallback",
        "sap_cpi_live": "SAP CPI live",
        "sap_pipo_live": "SAP PIPO live",
        "sap_ci": "SAP CI",
        "sap_pipo": "SAP PIPO",
        "sap_s4h": "SAP S4H",
        "sap_s4h_source": "SAP S4H (SM58 / IDoc / Queues)",
        "monitor_system": "Monitoring system",
        "not_configured": "The selected SAP system is not fully configured in .env.",
        "missing_pipo_endpoints": "SAP PIPO credentials are configured, but live endpoint paths are missing in .env.",
        "s4h_not_configured": "SAP S4H is not configured in .env (set SAP_S4H_BASE_URL / USERNAME / PASSWORD).",
        "s4h_disabled": "SAP S4H is configured but EXTERNAL_MONITORING_ENABLED is false, so live SM58/IDoc/queue fetching is skipped.",
        "s4h_ready": "SAP S4H monitoring is enabled. IDoc, SM58, qRFC and SLG1 evidence will populate once the fetcher runs.",
        "s4h_source_caption": "Evidence source: IDoc · SM58 · qRFC · SLG1 | mode: status counters (not MPL)",
        "s4h_idoc_inbound": "IDoc inbound errored",
        "s4h_idoc_outbound": "IDoc outbound errored",
        "s4h_sm58": "SM58 failed RFC",
        "s4h_qrfc": "qRFC stuck",
        "s4h_slg1": "Application Log errors",
        "s4h_total": "Evidence total",
        "s4h_evidence_by_monitor": "Evidence by monitor",
        "s4h_no_evidence": "No S4H evidence rows yet. Counters populate once the credentialed fetcher runs.",
        "s4h_view_idoc_errors": "View IDoc errors",
        "s4h_view_stuck_queues": "View stuck queues",
        "s4h_inventory_idoc": "Inventory: IDoc types / partner profiles",
        "s4h_inventory_rfc": "Inventory: RFC destinations / queues",
        "apim_section": "APIM — API Management",
        "apim_hint": "Analytics: traffic, errors, policy faults",
        "apim_total_calls": "Total calls",
        "apim_success_calls": "Success",
        "apim_error_count": "Error rate 4xx/5xx",
        "apim_policy_faults": "Policy faults",
        "apim_avg_latency": "Avg latency ms",
        "aem_section": "AEM — Advanced Event Mesh",
        "aem_hint": "Broker: queues, DMQ, redelivery",
        "aem_published": "Messages published",
        "aem_delivered": "Messages delivered",
        "aem_dmq": "DMQ messages",
        "aem_backlog": "Queue backlog",
        "aem_disconnects": "Consumer disconnects",
        "aem_spooled": "Spooled total",
        "apim_traffic_group": "API Proxy traffic",
        "apim_quality_group": "API Proxy quality",
        "apim_chart_title": "Success vs Failed (API Proxy calls)",
        "apim_top_proxies": "API Proxy breakdown",
        "apim_proxy_col": "API Proxy",
        "apim_calls_col": "Total",
        "apim_success_col": "Success",
        "apim_failed_col": "Failed",
        "aem_throughput_group": "Broker throughput",
        "aem_health_group": "Broker health",
        "apim_aem_disabled": "APIM / AEM evidence populates once EXTERNAL_MONITORING_ENABLED and the fetcher are active. Counters stay zero until then.",
        "apim_no_data": "APIM analytics connected successfully, but returned no records for this window. Counters fill once API proxies receive traffic and analytics aggregation runs (this can take a few hours on trial).",
        "apim_diagnostics": "APIM analytics diagnostics",
        "apim_diagnostics_hint": "If counters read 0 despite real API proxy traffic, run this to see the actual AnalyticsService entity sets and a raw sample row from your tenant. Use the sample row's field names to confirm the mapping.",
        "apim_diagnostics_run": "Run APIM diagnostics",
        "apim_diag_runtime_host": "The configured base URL looks like the API proxy runtime host, not the apiportal host. Use the 'url' from the apiportal-apiaccess service key (it contains 'apiportal'), then append /api/1.0.",
        "apim_diag_sample_row": "Raw sample row (field names are the source of truth for the counter mapping):",
        "status_breakdown": "MPL status breakdown",
        "message_list": "MPL message list",
        "open_completed": "Open Completed messages in new tab",
        "open_failed": "Open Failed messages in new tab",
        "loading_monitor": "Loading monitor data from backend / selected SAP system...",
        "timeout_hint": "If this appears often, increase API_TIMEOUT_SECONDS in .env or reduce SAP_CPI_MPL_TOP / SAP_PIPO_MPL_TOP.",
        "start_backend": "Start backend with: python -m uvicorn app.main:app --reload",
        "cpi_ok": "SAP CPI live connection is active.",
        "pipo_ok": "SAP PI/PO live connection is active.",
        "pipo_partial": "SAP PI/PO live connection is partially active. MPL may be live while Directory inventory remains local/fallback.",
        "pipo_fallback": "SAP PI/PO live call failed; normalized local fallback metrics are currently displayed.",
        "pipo_local": "SAP PI/PO local MPL fallback mode is active. Live calls are intentionally skipped.",
        "pipo_no_data": "SAP PI/PO endpoints are configured but returned no live records. Check SOAP template/date range/status filters.",
        "generation_section": "New-knowledge generation",
        "generation_caption": "Generate ingestion-ready Markdown documents. The selected MPL source remains the preferred source, while generation enriches documents with both Live MPL and Archived MPL evidence when available.",
        "generation_source": "Preferred generation source",
        "live_mpl": "Live MPL",
        "archived_mpl": "Archived MPL",
        "regenerate": "regenerate/update existing documents",
        "existing_documents_path": "Existing generated documents folder",
        "generation_version": "Document version",
        "generate_interface": "Generate interface_inventory",
        "generate_kedb": "Generate KEDBs",
        "generate_runbooks": "Generate Runbooks",
        "generation_result": "Generation result",
        "generated_count": "Generated files",
    },
    "de": {
        "monitor": "Monitoring Events",
        "source": "Datenquelle",
        "packages": "Packages",
        "iflows": "iFlows",
        "deployed": "Deployed",
        "inventory_actions": "On-demand inventory",
        "inventory_caption": "Monitoring laedt nur MPL-Zaehler. Diese Aktionen nur bei Bedarf fuer Design-/Konfigurationsinventar verwenden.",
        "inventory_objects": "Design-/Konfigurationsobjekte inventarisieren",
        "inventory_interfaces": "Interfaces / iFlows inventarisieren",
        "inventory_result": "Inventory result",
        "inventory_summary": "Inventory summary",
        "mpl_success": "Success Mes.",
        "mpl_errors": "Failed Mes.",
        "mpl_retry": "Retry Mes.",
        "mpl_total": "Total Mes.",
        "mpl_deployed_iflows": "Deployed iFlows",
        "connection": "Verbindungsdiagnose",
        "refresh": "Monitor-Daten aktualisieren",
        "time_range": "Monitor time range",
        "past_hour": "Past Hour",
        "past_24_hours": "Past 24 Hours",
        "past_week": "Past Week",
        "past_month": "Past Month",
        "custom": "Custom",
        "display_messages": "Display Messages",
        "last_updated": "Last Updated",
        "log_start": "Log Start",
        "from": "From",
        "to": "To",
        "feedback_source": "Feedback source",
        "feedback_none": "None",
        "feedback_latest": "Latest feedback",
        "feedback_selected": "Select feedback file",
        "feedback_file_path": "Feedback JSON file path",
        "apply_remediation_hints": "Apply remediation hints during regeneration",
        "local_fallback": "Lokaler Fallback",
        "sap_cpi_live": "SAP CPI live",
        "sap_pipo_live": "SAP PIPO live",
        "sap_ci": "SAP CI",
        "sap_pipo": "SAP PIPO",
        "sap_s4h": "SAP S4H",
        "sap_s4h_source": "SAP S4H (SM58 / IDoc / Queues)",
        "monitor_system": "Monitor-System",
        "not_configured": "Das ausgewaehlte SAP-System ist in .env nicht vollstaendig konfiguriert.",
        "missing_pipo_endpoints": "SAP PIPO-Zugangsdaten sind konfiguriert, aber Live-Endpunktpfade fehlen in .env.",
        "s4h_not_configured": "SAP S4H ist nicht in .env konfiguriert (SAP_S4H_BASE_URL / USERNAME / PASSWORD setzen).",
        "s4h_disabled": "SAP S4H ist konfiguriert, aber EXTERNAL_MONITORING_ENABLED ist false; Live-Abruf wird uebersprungen.",
        "s4h_ready": "SAP S4H-Monitoring ist aktiviert. IDoc-, SM58-, qRFC- und SLG1-Evidenz erscheint, sobald der Fetcher laeuft.",
        "s4h_source_caption": "Evidenzquelle: IDoc · SM58 · qRFC · SLG1 | Modus: Statuszaehler (nicht MPL)",
        "s4h_idoc_inbound": "IDoc inbound fehlerhaft",
        "s4h_idoc_outbound": "IDoc outbound fehlerhaft",
        "s4h_sm58": "SM58 fehlgeschlagene RFC",
        "s4h_qrfc": "qRFC haengt",
        "s4h_slg1": "Application-Log-Fehler",
        "s4h_total": "Evidenz gesamt",
        "s4h_evidence_by_monitor": "Evidenz nach Monitor",
        "s4h_no_evidence": "Noch keine S4H-Evidenzzeilen. Zaehler erscheinen, sobald der Fetcher laeuft.",
        "s4h_view_idoc_errors": "IDoc-Fehler anzeigen",
        "s4h_view_stuck_queues": "Haengende Queues anzeigen",
        "s4h_inventory_idoc": "Inventar: IDoc-Typen / Partnervereinbarungen",
        "s4h_inventory_rfc": "Inventar: RFC-Ziele / Queues",
        "apim_section": "APIM — API Management",
        "apim_hint": "Analytics: Traffic, Fehler, Policy-Faults",
        "apim_total_calls": "Aufrufe gesamt",
        "apim_success_calls": "Erfolgreich",
        "apim_error_count": "Fehlerrate 4xx/5xx",
        "apim_policy_faults": "Policy-Faults",
        "apim_avg_latency": "Latenz ms (Mittel)",
        "aem_section": "AEM — Advanced Event Mesh",
        "aem_hint": "Broker: Queues, DMQ, Redelivery",
        "aem_published": "Nachrichten publiziert",
        "aem_delivered": "Nachrichten zugestellt",
        "aem_dmq": "DMQ-Nachrichten",
        "aem_backlog": "Queue-Rueckstand",
        "aem_disconnects": "Consumer-Trennungen",
        "aem_spooled": "Spooled gesamt",
        "apim_traffic_group": "API-Proxy-Traffic",
        "apim_quality_group": "API-Proxy-Qualitaet",
        "apim_chart_title": "Erfolgreich vs. Fehlgeschlagen (API-Proxy-Aufrufe)",
        "apim_top_proxies": "API-Proxy-Aufschluesselung",
        "apim_proxy_col": "API-Proxy",
        "apim_calls_col": "Gesamt",
        "apim_success_col": "Erfolgreich",
        "apim_failed_col": "Fehlgeschlagen",
        "aem_throughput_group": "Broker-Durchsatz",
        "aem_health_group": "Broker-Zustand",
        "apim_aem_disabled": "APIM-/AEM-Evidenz erscheint, sobald EXTERNAL_MONITORING_ENABLED und der Fetcher aktiv sind. Zaehler bleiben bis dahin null.",
        "apim_no_data": "APIM-Analytics erfolgreich verbunden, aber keine Datensaetze fuer dieses Zeitfenster. Zaehler fuellen sich, sobald API-Proxies Traffic erhalten und die Analytics-Aggregation laeuft (auf Trial ggf. einige Stunden).",
        "apim_diagnostics": "APIM-Analytics-Diagnose",
        "apim_diagnostics_hint": "Wenn Zaehler trotz echtem API-Proxy-Traffic 0 anzeigen, hiermit die tatsaechlichen AnalyticsService-EntitySets und eine Roh-Beispielzeile des Tenants anzeigen. Die Feldnamen der Beispielzeile bestaetigen das Mapping.",
        "apim_diagnostics_run": "APIM-Diagnose ausfuehren",
        "apim_diag_runtime_host": "Die konfigurierte Basis-URL sieht aus wie der API-Proxy-Runtime-Host, nicht der apiportal-Host. Verwenden Sie die 'url' aus dem apiportal-apiaccess Service Key (enthaelt 'apiportal') und haengen Sie /api/1.0 an.",
        "apim_diag_sample_row": "Roh-Beispielzeile (Feldnamen sind die Wahrheitsquelle fuer das Zaehler-Mapping):",
        "status_breakdown": "MPL-Statusverteilung",
        "message_list": "MPL message list",
        "open_completed": "Open Completed messages in new tab",
        "open_failed": "Open Failed messages in new tab",
        "loading_monitor": "Monitor-Daten vom Backend / ausgewaehlten SAP-System werden geladen...",
        "timeout_hint": "Wenn dies haeufig erscheint, API_TIMEOUT_SECONDS in .env erhoehen oder SAP_CPI_MPL_TOP / SAP_PIPO_MPL_TOP reduzieren.",
        "start_backend": "Backend starten mit: python -m uvicorn app.main:app --reload",
        "cpi_ok": "SAP CPI live connection is active.",
        "pipo_ok": "SAP PI/PO live connection is active.",
        "pipo_partial": "SAP PI/PO live connection is partially active. MPL may be live while Directory inventory remains local/fallback.",
        "pipo_fallback": "SAP PI/PO live call failed; normalized local fallback metrics are currently displayed.",
        "pipo_local": "SAP PI/PO local MPL fallback mode is active. Live calls are intentionally skipped.",
        "pipo_no_data": "SAP PI/PO endpoints are configured but returned no live records. Check SOAP template/date range/status filters.",
        "generation_section": "New-knowledge generation",
        "generation_caption": "Generate ingestion-ready Markdown documents enriched with Live MPL and Archived MPL evidence when available.",
        "generation_source": "Preferred generation source",
        "live_mpl": "Live MPL",
        "archived_mpl": "Archived MPL",
        "regenerate": "regenerate/update existing documents",
        "existing_documents_path": "Existing generated documents folder",
        "generation_version": "Document version",
        "generate_interface": "Generate interface_inventory",
        "generate_kedb": "Generate KEDBs",
        "generate_runbooks": "Generate Runbooks",
        "generation_result": "Generation result",
        "generated_count": "Generated files",
    },
}

KPI_BLUE = "#0B5CAB"
KPI_GREEN = "#0A7F3F"
KPI_RED = "#C62828"
KPI_AMBER = "#B26A00"


def _inject_monitor_css() -> None:
    st.markdown(
        """
        <style>
        /* v2.0.10.7 — SAP Cloud Integration-style framed tiles. Each metric is a
           bordered white tile with a soft shadow and a colored top accent bar that
           follows the indicator meaning (green/red/amber/blue). The accent color is
           set per tile via an inline --accent variable from _metric_card. */
        .qdkep-metric-card {
            background: #ffffff;
            border: 1px solid #e3e8ef;
            border-top: 5px solid var(--accent, #0B5CAB);
            border-radius: 0.6rem;
            box-shadow: 0 1px 3px rgba(16, 24, 40, 0.08);
            padding: 0.85rem 1rem 0.95rem 1rem;
            height: 120px;
        }
        .qdkep-metric-label { font-size: 0.82rem; color: #475467; margin-bottom: 0.3rem; font-weight: 600; }
        .qdkep-metric-value { font-size: 3.0rem; line-height: 1.1; font-weight: 800; letter-spacing: -0.02em; }
        .qdkep-status-links a { display:inline-block; margin-right:0.75rem; padding:0.55rem 0.9rem; border-radius:0.5rem; background:#eef7e8; color:#111827 !important; font-weight:800; text-decoration:none; border:1px solid #75b843; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _api_get(path: str, timeout: int | None = None, params: dict | None = None) -> dict | None:
    try:
        effective_timeout = timeout if timeout is not None else settings.api_timeout_seconds
        separator = "&" if "?" in path else "?"
        query = f"{separator}{urlencode(params)}" if params else ""
        response = requests.get(f"{settings.api_base_url}{path}{query}", timeout=effective_timeout)
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.warning(f"API unavailable or timed out after {effective_timeout}s: {exc}")
        return None


def _api_post(path: str, payload: dict, timeout: int | None = None) -> dict | None:
    try:
        effective_timeout = timeout if timeout is not None else settings.api_timeout_seconds
        response = requests.post(
            f"{settings.api_base_url}{path}", json=payload, timeout=effective_timeout
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.warning(f"API unavailable or timed out after {effective_timeout}s: {exc}")
        return None


@st.cache_data(ttl=settings.monitor_refresh_ttl_seconds, show_spinner=False)
def _load_monitor_summary(
    system: str, time_range: str, date_from: str | None, date_to: str | None, display_field: str
) -> dict | None:
    return _api_get(
        "/api/monitor/summary",
        timeout=settings.api_timeout_seconds,
        params={
            "system": system,
            "time_range": time_range,
            "date_from": date_from or "",
            "date_to": date_to or "",
            "display_field": display_field,
        },
    )


@st.cache_data(ttl=600, show_spinner=False)
def _load_deployed_iflows(system: str) -> object:
    """Return the deployed-iFlow count for the MPL 'Deployed iFlows' tile.

    Prefers the CPIView/native evidence count (derived from runtimes.json, e.g. 6),
    which the inventory endpoint fills before any live call. The tile requests the
    "objects" inventory type on purpose: that path skips the heavy live get_iflows
    scan yet still returns the evidence-derived deployed count, so the tile is both
    cheap and accurate. Cached 10 minutes to match the auto-refresh cadence.
    Returns an int when known, or the "N/A" sentinel when no deployed count is
    available. Never fabricates a number.
    """
    result = _api_get(
        "/api/monitor/inventory",
        timeout=settings.api_timeout_seconds,
        params={"system": system, "inventory_type": "objects"},
    )
    if not result:
        return "N/A"
    inventory = result.get("data", {}).get("inventory", {})
    return inventory.get("deployed", "N/A")


def _success_failed_bar_svg(
    success: int, failed: int, success_label: str, failed_label: str
) -> str:
    """Return a small inline SVG of two vertical bars (Success green, Failed red).

    Self-contained and dependency-free, so the colors and vertical orientation are
    exact and not subject to st.bar_chart layout quirks. Bars are scaled to the
    larger of the two values; value labels sit above each bar.
    """
    peak = max(success, failed, 1)
    plot_h = 150  # px available for the tallest bar
    s_h = round(success / peak * plot_h)
    f_h = round(failed / peak * plot_h)
    baseline = 170
    green = "#0A7F3F"
    red = "#C62828"
    grey = "#475467"
    return (
        f'<svg viewBox="0 0 220 210" width="100%" height="210" '
        f'xmlns="http://www.w3.org/2000/svg" role="img">'
        # success bar
        f'<rect x="40" y="{baseline - s_h}" width="55" height="{s_h}" rx="3" fill="{green}"/>'
        f'<text x="67" y="{baseline - s_h - 6}" font-size="14" font-weight="700" '
        f'fill="{green}" text-anchor="middle">{success}</text>'
        f'<text x="67" y="{baseline + 18}" font-size="12" fill="{grey}" '
        f'text-anchor="middle">{success_label}</text>'
        # failed bar
        f'<rect x="125" y="{baseline - f_h}" width="55" height="{f_h}" rx="3" fill="{red}"/>'
        f'<text x="152" y="{baseline - f_h - 6}" font-size="14" font-weight="700" '
        f'fill="{red}" text-anchor="middle">{failed}</text>'
        f'<text x="152" y="{baseline + 18}" font-size="12" fill="{grey}" '
        f'text-anchor="middle">{failed_label}</text>'
        # baseline axis
        f'<line x1="30" y1="{baseline}" x2="190" y2="{baseline}" stroke="#e3e8ef" stroke-width="1"/>'
        f"</svg>"
    )


def _metric_card(label: str, value: object, color: str) -> None:
    st.markdown(
        f"""
        <div class="qdkep-metric-card" style="--accent:{color};">
            <div class="qdkep-metric-label">{label}</div>
            <div class="qdkep-metric-value" style="color:{color};">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _dashboard_url(system: str, status: str, monitor_params: dict[str, str]) -> str:
    query = {"monitor_status": status, "monitor_system": system}
    query.update({k: v for k, v in monitor_params.items() if v})
    return f"?{urlencode(query)}"


def _monitor_query_params_from_url() -> dict[str, str]:
    params = st.query_params
    return {
        "time_range": str(params.get("time_range", "past_24_hours") or "past_24_hours"),
        "date_from": str(params.get("date_from", "") or ""),
        "date_to": str(params.get("date_to", "") or ""),
        "display_field": str(params.get("display_field", "last_updated") or "last_updated"),
    }


def _render_time_range_controls(t: dict[str, str]) -> dict[str, str]:
    url_defaults = _monitor_query_params_from_url()
    labels = [t["past_hour"], t["past_24_hours"], t["past_week"], t["past_month"], t["custom"]]
    label_to_value = {
        t["past_hour"]: "past_hour",
        t["past_24_hours"]: "past_24_hours",
        t["past_week"]: "past_week",
        t["past_month"]: "past_month",
        t["custom"]: "custom",
    }
    value_to_label = {value: label for label, value in label_to_value.items()}
    default_label = value_to_label.get(
        url_defaults.get("time_range") or "past_24_hours", t["past_24_hours"]
    )
    selected_label = st.selectbox(
        t["time_range"], labels, index=labels.index(default_label), key="monitor_time_range_select"
    )
    selected_value = label_to_value[selected_label]
    params = {
        "time_range": selected_value,
        "date_from": "",
        "date_to": "",
        "display_field": url_defaults.get("display_field", "last_updated"),
    }
    if selected_value == "custom":
        col_display, col_from, col_to = st.columns([1, 1, 1])
        with col_display:
            display_label = st.selectbox(
                t["display_messages"],
                [t["last_updated"], t["log_start"]],
                index=0,
                key="monitor_display_messages",
            )
            params["display_field"] = (
                "last_updated" if display_label == t["last_updated"] else "log_start"
            )
        now = datetime.now().replace(microsecond=0)
        default_from = now - timedelta(hours=1)
        with col_from:
            from_date = st.date_input(
                t["from"], value=default_from.date(), key="monitor_custom_from_date"
            )
            from_time = st.time_input(
                "From time", value=default_from.time(), key="monitor_custom_from_time"
            )
        with col_to:
            to_date = st.date_input(t["to"], value=now.date(), key="monitor_custom_to_date")
            to_time = st.time_input("To time", value=now.time(), key="monitor_custom_to_time")
        params["date_from"] = datetime.combine(from_date, from_time).isoformat(timespec="seconds")
        params["date_to"] = datetime.combine(to_date, to_time).isoformat(timespec="seconds")
    return params


def _render_message_tab(t: dict[str, str], system: str, status: str) -> bool:
    if not status:
        return False
    st.header(f"{t['message_list']}: {status}")
    monitor_params = _monitor_query_params_from_url()
    result = _api_get(
        "/api/monitor/messages",
        params={"system": system, "status": status, **monitor_params},
        timeout=settings.api_timeout_seconds,
    )
    if not result:
        st.info(t["start_backend"])
        return True
    data = result.get("data", {})
    rows = data.get("messages", [])
    st.caption(
        f"System: {data.get('system')} | status: {data.get('status_filter')} | count: {data.get('count')} | source modes: {', '.join(data.get('source_modes', []))}"
    )
    if rows:
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.info("No matching MPL messages found for this filter.")
    return True


def _render_inventory_buttons(t: dict[str, str], system: str, col_objects, col_interfaces) -> None:
    """Render the two on-demand inventory buttons into the supplied columns.

    v2.0.10.8 — split out of the former standalone _render_inventory_actions so the
    two inventory buttons can sit in the same compact 4-column row as the View
    Completed / View Failed links.

    The fetched inventory result is stored in st.session_state and rendered
    full-width below the row. Persisting it is required because Streamlit buttons
    return True only on the exact click rerun; the background 10-minute
    auto-refresh (or any other rerun) would otherwise clear a result rendered from
    a transient local variable. Keying the stored result by system keeps SAP
    CI/PIPO/S4H results independent.
    """
    actions = [
        (col_objects, "objects", t["inventory_objects"]),
        (col_interfaces, "interfaces", t["inventory_interfaces"]),
    ]
    state_key = f"_inventory_result_{system}"
    for column, inventory_type, label in actions:
        with column:
            if st.button(label, key=f"inventory_{system}_{inventory_type}", width="stretch"):
                with st.spinner(label):
                    result = _api_get(
                        "/api/monitor/inventory",
                        timeout=settings.api_timeout_seconds,
                        params={"system": system, "inventory_type": inventory_type},
                    )
                # Store both the API result and the action label so the result
                # block below survives subsequent reruns (incl. auto-refresh).
                st.session_state[state_key] = {"result": result, "label": label}

    stored = st.session_state.get(state_key)
    if not stored:
        return
    result = stored.get("result")
    if not result:
        st.warning(t["start_backend"])
        return
    data = result.get("data", {})
    inventory = data.get("inventory", {})
    st.success(f"{t['inventory_result']}: {data.get('source', 'unknown')}")
    # Arrow-safe table: the "Value" column mixes counts with an "N/A" sentinel for
    # unknown deployment counts. PyArrow infers a single column type, so a mix of
    # int and the "N/A" string makes serialization fail. Render every value as a
    # string to keep the column homogeneous while preserving the meaningful "N/A".
    st.dataframe(
        [
            {"Metric": "Packages / objects", "Value": str(inventory.get("packages", 0))},
            {
                "Metric": "Interfaces / iFlows",
                "Value": str(inventory.get("interfaces", inventory.get("iflows", 0))),
            },
            {"Metric": "Deployed", "Value": str(inventory.get("deployed", "N/A"))},
            {"Metric": "Local package ZIPs", "Value": str(inventory.get("local_package_zips", 0))},
        ],
        width="stretch",
        hide_index=True,
    )
    with st.expander(t["inventory_summary"], expanded=False):
        st.json(data)


def _render_generation_section(t: dict[str, str], system: str) -> None:
    st.markdown("---")
    st.subheader(t["generation_section"])
    st.caption(t["generation_caption"])
    source_label = st.radio(
        t["generation_source"],
        [t["live_mpl"], t["archived_mpl"]],
        index=1,
        horizontal=True,
        key="generation_source_mode",
    )
    source_mode = "live_mpl" if source_label == t["live_mpl"] else "archived_mpl"
    regenerate = st.checkbox(t["regenerate"], value=False, key="regenerate_existing_documents")
    existing_documents_path = ""
    if regenerate:
        existing_documents_path = st.text_input(
            t["existing_documents_path"],
            value="",
            placeholder="./exports/generated_documents/20260503_001716_live_mpl_v1",
            key="existing_documents_path_input",
        )
    version = st.text_input(t["generation_version"], value="v1", key="generation_version_input")

    feedback_label = st.selectbox(
        t["feedback_source"],
        [t["feedback_none"], t["feedback_latest"], t["feedback_selected"]],
        index=0,
        key="generation_feedback_source",
    )
    feedback_source = "none"
    if feedback_label == t["feedback_latest"]:
        feedback_source = "latest"
    elif feedback_label == t["feedback_selected"]:
        feedback_source = "selected"
    feedback_path = ""
    if feedback_source == "selected":
        feedback_path = st.text_input(
            t["feedback_file_path"],
            value="",
            placeholder="feedback/run_20260429_154356_feedback.json",
            key="generation_feedback_path",
        )
    apply_remediation_hints = st.checkbox(
        t["apply_remediation_hints"], value=False, key="apply_remediation_hints"
    )

    col1, col2, col3 = st.columns(3)
    actions = [
        (col1, "catalog_docs", t["generate_interface"]),
        (col2, "kedb", t["generate_kedb"]),
        (col3, "runbooks", t["generate_runbooks"]),
    ]
    for column, document_type, label in actions:
        with column:
            if st.button(label, key=f"generate_{document_type}_button", width="stretch"):
                payload = {
                    "version": version,
                    "source_system": system,
                    "source_mode": source_mode,
                    "existing_documents_path": existing_documents_path if regenerate else None,
                    "feedback_source": feedback_source,
                    "feedback_path": feedback_path or None,
                    "apply_remediation_hints": apply_remediation_hints,
                }
                with st.spinner(label):
                    result = _api_post(
                        f"/api/monitoring-generation/generate/{document_type}",
                        payload,
                        timeout=settings.api_timeout_seconds,
                    )
                if result:
                    data = result.get("data", {})
                    if result.get("status") == "generated":
                        st.success(f"{t['generation_result']}: {data.get('output_dir')}")
                    else:
                        st.warning(f"{t['generation_result']}: {result.get('status')}")
                    st.caption(f"{t['generated_count']}: {data.get('generated_count', 0)}")
                    st.json(result)


def _render_apim_aem_sections(t: dict[str, str], summary: dict) -> None:
    """Render APIM and AEM indicator sub-sections on the SAP CI page.

    APIM and AEM live in the same Integration Suite tenant as CPI, so they appear
    as sub-sections below the MPL counters rather than as separate systems. The
    MPL section above is untouched.

    v2.0.10.7 — gadgets are grouped (traffic vs quality for APIM; throughput vs
    health for AEM), a Success counter and a Success-vs-Failed bar chart are added
    for API Proxy calls, and a per-proxy breakdown table is shown when the
    analytics service returns proxy-level rows (e.g. 'restcountries · 15 failed').
    All previously existing counters are preserved.
    """
    apim = summary.get("apim", {})
    aem = summary.get("aem", {})

    st.markdown("---")

    # ---------------------------------------------------------------- APIM ----
    st.markdown(f"#### {t['apim_section']}")
    st.caption(t["apim_hint"])
    a_metrics = apim.get("metrics", {})
    total_calls = a_metrics.get("total_calls", 0)
    success_calls = a_metrics.get("success_count", 0)
    failed_calls = a_metrics.get("error_count", 0)

    # Traffic gadgets: total / success / failed (the counters that were missing
    # from the page even though API Proxy clearly had traffic).
    st.markdown(f"**{t['apim_traffic_group']}**")
    tr1, tr2, tr3 = st.columns(3)
    with tr1:
        _metric_card(t["apim_total_calls"], total_calls, KPI_BLUE)
    with tr2:
        _metric_card(t["apim_success_calls"], success_calls, KPI_GREEN)
    with tr3:
        _metric_card(t["apim_error_count"], failed_calls, KPI_RED)

    # Quality gadgets + chart in one row: Policy faults | Avg latency | chart.
    # The Success-vs-Failed chart sits at the end of this second row, beside the
    # two quality tiles, rendered as vertical columns.
    st.markdown(f"**{t['apim_quality_group']}**")
    q1, q2, q3 = st.columns(3)
    with q1:
        _metric_card(t["apim_policy_faults"], a_metrics.get("policy_faults", 0), KPI_AMBER)
    with q2:
        _metric_card(t["apim_avg_latency"], a_metrics.get("avg_latency_ms", 0), KPI_BLUE)
    with q3:
        # Two vertical colored columns (Success green, Failed red) rendered as a
        # small inline SVG. This avoids st.bar_chart's single-row-horizontal quirk
        # and gives exact per-bar colors with no extra dependency. Only drawn when
        # there is real traffic so an empty window shows no misleading chart.
        if (success_calls + failed_calls) > 0:
            st.caption(t["apim_chart_title"])
            st.markdown(
                _success_failed_bar_svg(
                    success_calls,
                    failed_calls,
                    t["apim_success_col"],
                    t["apim_failed_col"],
                ),
                unsafe_allow_html=True,
            )

    # Per-proxy breakdown table (top error proxies first).
    top_proxies = apim.get("top_proxies", []) or []
    if top_proxies:
        st.markdown(f"**{t['apim_top_proxies']}**")
        st.dataframe(
            [
                {
                    t["apim_proxy_col"]: row.get("proxy", "(unknown)"),
                    t["apim_calls_col"]: row.get("total_calls", 0),
                    t["apim_success_col"]: row.get("success_count", 0),
                    t["apim_failed_col"]: row.get("error_count", 0),
                }
                for row in top_proxies
            ],
            width="stretch",
            hide_index=True,
        )

    # ----------------------------------------------------------------- AEM ----
    st.markdown(f"#### {t['aem_section']}")
    st.caption(t["aem_hint"])
    e_metrics = aem.get("metrics", {})

    # Throughput gadgets (published / delivered) — new in v2.0.10.7, stay 0 until
    # the SEMP Monitor fetcher is wired.
    st.markdown(f"**{t['aem_throughput_group']}**")
    th1, th2 = st.columns(2)
    with th1:
        _metric_card(t["aem_published"], e_metrics.get("messages_published", 0), KPI_BLUE)
    with th2:
        _metric_card(t["aem_delivered"], e_metrics.get("messages_delivered", 0), KPI_GREEN)

    # Health gadgets (existing DMQ / backlog / disconnects / spooled, unchanged).
    st.markdown(f"**{t['aem_health_group']}**")
    e1, e2, e3, e4 = st.columns(4)
    with e1:
        _metric_card(t["aem_dmq"], e_metrics.get("dmq_messages", 0), KPI_RED)
    with e2:
        _metric_card(t["aem_backlog"], e_metrics.get("queue_backlog", 0), KPI_AMBER)
    with e3:
        _metric_card(t["aem_disconnects"], e_metrics.get("consumer_disconnects", 0), KPI_AMBER)
    with e4:
        _metric_card(t["aem_spooled"], e_metrics.get("spooled_total", 0), KPI_BLUE)

    if apim.get("status") == "error":
        st.error(f"APIM analytics request failed: {apim.get('error')}")
    elif apim.get("status") == "ok_no_data":
        st.info(t["apim_no_data"])
    elif apim.get("status") == "disabled" or aem.get("status") == "disabled":
        st.info(t["apim_aem_disabled"])

    # v2.0.10.11 — APIM diagnostics panel. When the counters read 0 even though the
    # API proxy clearly has traffic, the cause is almost always that the
    # AnalyticsService row field names differ from what the client reads, or the
    # entity needs $select measures. This read-only panel shows the real entity
    # sets and a raw sample row from the tenant so the correct field names can be
    # confirmed from evidence rather than guessed.
    with st.expander(t["apim_diagnostics"], expanded=False):
        st.caption(t["apim_diagnostics_hint"])
        if st.button(t["apim_diagnostics_run"], key="apim_diagnostics_button"):
            with st.spinner(t["apim_diagnostics_run"]):
                diag = _api_get(
                    "/api/monitor/apim-diagnostics",
                    timeout=settings.api_timeout_seconds,
                )
            st.session_state["_apim_diagnostics"] = diag
        diag = st.session_state.get("_apim_diagnostics")
        if diag:
            data = diag.get("data", {})
            if data.get("looks_like_runtime_host"):
                st.warning(t["apim_diag_runtime_host"])
            st.write(
                {
                    "entity_sets": data.get("entity_sets"),
                    "queried_entity": data.get("queried_entity"),
                    "row_count": data.get("row_count"),
                    "sample_keys": data.get("sample_keys"),
                    "error": data.get("error"),
                }
            )
            if data.get("sample_row") is not None:
                st.caption(t["apim_diag_sample_row"])
                st.json(data["sample_row"])


def _render_s4h_content(t: dict[str, str], summary: dict, monitor_params: dict) -> None:
    """Render the SAP S4H monitoring view.

    S4H is evidence-based (IDoc inbound/outbound, SM58, qRFC, SLG1), not MPL, so
    this view uses error-oriented counters and an 'evidence by monitor' table
    instead of MPL success/fail/total cards and Completed/Failed links.
    """
    connection = summary.get("connection", {})
    s4h = summary.get("s4h", {})
    monitors = {m["key"]: m for m in s4h.get("monitors", [])}

    st.caption(t["s4h_source_caption"])

    # Error-oriented metric cards, one per active monitor (+ total).
    card_specs = [
        ("idoc_inbound", t["s4h_idoc_inbound"], KPI_RED),
        ("idoc_outbound", t["s4h_idoc_outbound"], KPI_RED),
        ("sm58", t["s4h_sm58"], KPI_AMBER),
        ("qrfc", t["s4h_qrfc"], KPI_RED),
        ("slg1", t["s4h_slg1"], KPI_AMBER),
    ]
    active_specs = [spec for spec in card_specs if spec[0] in monitors]
    columns = st.columns(len(active_specs) + 1)
    for column, (key, label, color) in zip(columns, active_specs, strict=False):
        with column:
            _metric_card(label, monitors[key].get("errors", 0), color)
    with columns[-1]:
        _metric_card(t["s4h_total"], s4h.get("total_errors", 0), KPI_BLUE)

    # Connection status.
    status = connection.get("s4h_status")
    if status == "not_configured":
        st.warning(t["s4h_not_configured"])
    elif status == "disabled":
        st.info(t["s4h_disabled"])
    elif status in {"not_checked", "ok"}:
        st.success(t["s4h_ready"])
    elif status == "error":
        st.error(f"SAP S4H connection failed: {connection.get('s4h_error')}")
    active = connection.get("active_monitors") or []
    if active:
        st.caption(
            f"SID {connection.get('sap_sid')} / client {connection.get('client')} "
            f"| monitors: {', '.join(active)}"
        )

    # Evidence-by-monitor table (replaces MPL status breakdown).
    st.subheader(t["s4h_evidence_by_monitor"])
    evidence_rows = s4h.get("evidence_rows", [])
    if evidence_rows:
        rows = [
            {
                "Monitor": row.get("monitor", ""),
                "Object": row.get("monitoring_object", ""),
                "Signature": row.get("taxonomy", ""),
                "Count": row.get("count", 0),
            }
            for row in evidence_rows
        ]
        st.dataframe(rows, width="stretch", hide_index=True)
    else:
        st.caption(t["s4h_no_evidence"])

    with st.expander(t["connection"], expanded=False):
        st.json(summary)

    # S4H-appropriate inventory actions (IDoc types/partner profiles, RFC/queues).
    st.markdown("---")
    st.subheader(t["inventory_actions"])
    inv_col1, inv_col2 = st.columns(2)
    with inv_col1:
        st.button(t["s4h_inventory_idoc"], key="s4h_inventory_idoc_button", width="stretch")
    with inv_col2:
        st.button(t["s4h_inventory_rfc"], key="s4h_inventory_rfc_button", width="stretch")


def _render_monitor_content(t: dict[str, str], system: str) -> None:
    query_params = st.query_params
    requested_status = str(query_params.get("monitor_status", "") or "").upper()
    if requested_status and _render_message_tab(t, system, requested_status):
        return

    st.header(t["monitor"])
    # Keep the time-range selector compact and place the refresh action directly
    # next to it. The selector column is one third of its previous width
    # (previous layout: 2/3 page width; new layout: 2/9 page width).
    control_col, button_col, _ = st.columns([2, 2, 5])
    with control_col:
        monitor_params = _render_time_range_controls(t)
    with button_col:
        st.markdown("<div style='height: 1.7rem;'></div>", unsafe_allow_html=True)
        if st.button(t["refresh"], key="refresh_monitor_button"):
            # Refresh = drop the cached monitor reads so the next read pulls fresh
            # counters, then rerun. Only the monitor data caches are cleared (not
            # the whole app cache). The selected time range is preserved by the
            # time-range control's own widget state, so no query-param round-trip
            # is needed here (writing query params inside the auto-refresh fragment
            # is avoided).
            _load_monitor_summary.clear()
            _load_deployed_iflows.clear()
            st.rerun()

    with st.spinner(t["loading_monitor"]):
        summary = _load_monitor_summary(
            system,
            monitor_params.get("time_range", "past_24_hours"),
            monitor_params.get("date_from"),
            monitor_params.get("date_to"),
            monitor_params.get("display_field", "last_updated"),
        )
    if not summary:
        st.info(t["start_backend"])
        st.caption(t["timeout_hint"])
        return

    if system == "sap_s4h":
        _render_s4h_content(t, summary, monitor_params)
        return

    source = summary.get("source", "local_fallback")
    connection = summary.get("connection", {})
    mpl = summary.get("mpl", {})

    st.caption(f"{t['source']}: {t.get(source, source)} | mode: MPL counters only")

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        _metric_card(t["mpl_success"], mpl.get("success", 0), KPI_GREEN)
    with col2:
        _metric_card(t["mpl_errors"], mpl.get("errors", 0), KPI_RED)
    with col3:
        _metric_card(t["mpl_retry"], mpl.get("retry", 0), KPI_AMBER)
    with col4:
        _metric_card(t["mpl_total"], mpl.get("total", 0), KPI_BLUE)
    with col5:
        # Deployed iFlows comes from the auto-run interfaces inventory (cached
        # 10 min), only for SAP CI which exposes a deployed count; other systems
        # show the inventory's N/A sentinel.
        deployed = _load_deployed_iflows(system) if system == "sap_ci" else "N/A"
        _metric_card(t["mpl_deployed_iflows"], deployed, KPI_AMBER)

    if system == "sap_ci":
        if connection.get("cpi_status") == "ok":
            st.success(t["cpi_ok"])
        elif connection.get("cpi_status") == "not_configured":
            st.warning(t["not_configured"])
        elif connection.get("cpi_status") == "error":
            st.error(f"SAP CPI live connection failed: {connection.get('cpi_error')}")
    else:
        status = connection.get("pipo_status")
        if status == "ok":
            st.success(t["pipo_ok"])
        elif status == "partial_ok":
            st.warning(t["pipo_partial"])
            st.caption(connection.get("pipo_error"))
        elif status == "fallback_ok":
            st.warning(t["pipo_fallback"])
            st.caption(connection.get("pipo_error"))
        elif status == "local_only":
            st.info(t["pipo_local"])
        elif status == "not_configured":
            st.warning(t["not_configured"])
        elif status == "missing_live_endpoints":
            st.warning(t["missing_pipo_endpoints"])
            st.caption(connection.get("pipo_error"))
        elif status == "no_live_data":
            st.warning(t["pipo_no_data"])
            st.caption(connection.get("pipo_error"))
        elif status == "error":
            st.error(f"SAP PI/PO live connection failed: {connection.get('pipo_error')}")

    breakdown = mpl.get("status_breakdown", {})
    if breakdown:
        st.subheader(t["status_breakdown"])
        rows = [{"Status": key, "Count": value} for key, value in sorted(breakdown.items())]

        st.dataframe(rows, width="stretch", hide_index=True)

    # v2.0.10.8 — the four monitoring actions (View Completed, View Failed, and the
    # two on-demand inventory actions) are packed into one compact 4-column row in
    # this zone instead of being split across two separate blocks.
    st.caption(t["inventory_caption"])
    btn_completed, btn_failed, btn_objects, btn_interfaces = st.columns(4)
    with btn_completed:
        st.markdown(
            f"""
            <div class="qdkep-status-links">
                <a href="{_dashboard_url(system, "COMPLETED", monitor_params)}" target="_blank">View Completed: {mpl.get("success", 0)}</a>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with btn_failed:
        st.markdown(
            f"""
            <div class="qdkep-status-links">
                <a href="{_dashboard_url(system, "FAILED", monitor_params)}" target="_blank">View Failed: {mpl.get("errors", 0)}</a>
            </div>
            """,
            unsafe_allow_html=True,
        )
    _render_inventory_buttons(t, system, btn_objects, btn_interfaces)

    if system == "sap_ci":
        _render_apim_aem_sections(t, summary)

    with st.expander(t["connection"], expanded=False):
        st.json(summary)


def _render_monitor_content_autorefresh(t: dict[str, str], system: str) -> None:
    """Render the monitor content, auto-refreshing in the background every 10 min.

    v2.0.10.9.1 — the previous implementation used a separate timer fragment that
    called st.rerun(); inside a run_every fragment that produced an endless
    full-page refresh loop and disrupted the manual Refresh button, the inventory
    buttons, and the PIPO/S4H system radio.

    The corrected approach wraps the content itself in a run_every fragment. Only
    this fragment reruns on the timer; because the monitor data is read through a
    TTL cache, a tick that lands after the TTL pulls fresh counters, while ticks
    within the TTL are cheap cache hits. No st.rerun(), no mid-flow cache clear, so
    the rest of the page (buttons, radio) behaves normally. On Streamlit runtimes
    without fragment-timer support, it degrades to a single render (manual Refresh
    still works).
    """
    fragment = getattr(st, "fragment", None)
    if fragment is None:  # pragma: no cover - depends on runtime version
        _render_monitor_content(t, system)
        return

    @fragment(run_every=600)
    def _content() -> None:
        _render_monitor_content(t, system)

    _content()


def render(model, translator) -> None:
    _inject_monitor_css()
    language = getattr(translator, "language", "en")
    t = TEXT.get(language, TEXT["en"])
    query_system = str(st.query_params.get("monitor_system", "") or "")
    if query_system == "sap_pipo":
        default_index = 1
    elif query_system == "sap_s4h":
        default_index = 2
    else:
        default_index = 0
    monitor_choice = st.sidebar.radio(
        t["monitor_system"],
        [t["sap_ci"], t["sap_pipo"], t["sap_s4h"]],
        index=default_index,
        key="monitor_system_choice",
    )
    if monitor_choice == t["sap_pipo"]:
        monitor_system = "sap_pipo"
    elif monitor_choice == t["sap_s4h"]:
        monitor_system = "sap_s4h"
    else:
        monitor_system = "sap_ci"
    _render_monitor_content_autorefresh(t, monitor_system)
