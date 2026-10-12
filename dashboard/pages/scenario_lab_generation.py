from __future__ import annotations

import requests
import streamlit as st

from app.config import settings

TEXT: dict[str, dict[str, object]] = {
    "en": {
        "title": "Scenario Lab & Generation",
        "caption": "Scenario-backed generation combines iFlow ZIP/BPMN static analysis, safe negative DEV/TEST examples, test plans, MPL evidence, policies, templates, and existing generation behavior.",
        "scenario_lab": "A. Scenario Lab",
        "new_generation": "B. New-knowledge generation",
        "zip_dir": "iFlow ZIP folder",
        "bpmn_dir": "iFlow BPMN analysis folder",
        "source_system": "Source system",
        "max_iflows": "Max iFlows for preview/testing (0 = all)",
        "collect_mpl": "Collect MPL evidence matrix placeholder",
        "run_lab": "1-5 Run Scenario Lab chain",
        "upload": "Upload iFlow ZIP exports",
        "upload_help": "Optional. Uploaded files are saved under exports/scenario_lab_uploads. For full folder analysis, use the folder path below.",
        "defaults": "Load defaults from resources/cpi",
        "generation_caption": "Choose Generate for new documents or Update existing docs for regeneration with remediation, feedback, and enrichments.",
        "generation_source": "Preferred generation source",
        "live_mpl": "Live MPL",
        "archived_mpl": "Archived MPL",
        "select_mpl_source": "Select MPL Source",
        "prevent_duplicate_doc_id": "prevent dublicate Docs",
        "restart_id_counting": "restart ID counting",
        "generation_mode": "Generation mode",
        "generate_mode": "Generate",
        "update_existing_docs_mode": "Update existing docs",
        "update_existing_docs_help": "Use this mode for regeneration with remediation and enrichments from system feedback.",
        "existing_documents_path": "Existing generated documents folder",
        "generation_version": "Document version",
        "feedback_source": "Feedback source",
        "feedback_none": "None",
        "feedback_latest": "Latest feedback",
        "feedback_selected": "Select feedback file",
        "feedback_file_path": "Feedback JSON file path",
        "apply_remediation_hints": "Apply remediation hints during regeneration",
        "use_scenario": "Use latest Scenario Lab run for enrichment",
        "scenario_run_id": "Scenario Lab run ID",
        "scenario_manifest_path": "scenario_manifest.json path",
        "iflow_analysis_report_path": "iflow_analysis_report.json path",
        "generate_interface": "Generate interface_inventory",
        "update_interface": "Update interface_inventory",
        "generate_kedb": "Generate KEDBs",
        "update_kedb": "Update KEDBs",
        "generate_runbooks": "Generate Runbooks",
        "update_runbooks": "Update Runbooks",
        "result": "Generation result",
        "generated_count": "Generated files",
        "steps": [
            "Generate or Upload iFlow ZIP folder",
            "Analyze iFlows",
            "Generate negative input examples",
            "Generate test execution plan",
            "Collect MPL evidence",
        ],
    },
    "de": {
        "title": "Scenario Lab & Generation",
        "caption": "Scenario-backed generation kombiniert iFlow ZIP/BPMN static analysis, sichere negative DEV/TEST Beispiele, Testplaene, MPL evidence, Policies, Templates und bestehende Generierung.",
        "scenario_lab": "A. Scenario Lab",
        "new_generation": "B. New-knowledge generation",
        "zip_dir": "iFlow ZIP folder",
        "bpmn_dir": "iFlow BPMN analysis folder",
        "source_system": "Source system",
        "max_iflows": "Max iFlows for preview/testing (0 = all)",
        "collect_mpl": "Collect MPL evidence matrix placeholder",
        "run_lab": "1-5 Run Scenario Lab chain",
        "upload": "Upload iFlow ZIP exports",
        "upload_help": "Optional. Uploaded files are saved under exports/scenario_lab_uploads. For full folder analysis, use the folder path below.",
        "defaults": "Load defaults from resources/cpi",
        "generation_caption": "Choose Generate for new documents or Update existing docs for regeneration with remediation, feedback, and enrichments.",
        "generation_source": "Preferred generation source",
        "live_mpl": "Live MPL",
        "archived_mpl": "Archived MPL",
        "select_mpl_source": "Select MPL Source",
        "prevent_duplicate_doc_id": "prevent dublicate ID",
        "restart_id_counting": "restart ID counting",
        "generation_mode": "Generation mode",
        "generate_mode": "Generate",
        "update_existing_docs_mode": "Update existing docs",
        "update_existing_docs_help": "Use this mode for regeneration with remediation and enrichments from system feedback.",
        "existing_documents_path": "Existing generated documents folder",
        "generation_version": "Document version",
        "feedback_source": "Feedback source",
        "feedback_none": "None",
        "feedback_latest": "Latest feedback",
        "feedback_selected": "Select feedback file",
        "feedback_file_path": "Feedback JSON file path",
        "apply_remediation_hints": "Apply remediation hints during regeneration",
        "use_scenario": "Use latest Scenario Lab run for enrichment",
        "scenario_run_id": "Scenario Lab run ID",
        "scenario_manifest_path": "scenario_manifest.json path",
        "iflow_analysis_report_path": "iflow_analysis_report.json path",
        "generate_interface": "Generate interface_inventory",
        "update_interface": "Update interface_inventory",
        "generate_kedb": "Generate KEDBs",
        "update_kedb": "Update KEDBs",
        "generate_runbooks": "Generate Runbooks",
        "update_runbooks": "Update Runbooks",
        "result": "Generation result",
        "generated_count": "Generated files",
        "steps": [
            "Erzeugen oder Upload iFlow ZIP folder",
            "Analyze iFlows",
            "Generate negative input examples",
            "Generate test execution plan",
            "Collect MPL evidence",
        ],
    },
}


def _api_get(path: str, timeout: int | None = None) -> dict | None:
    try:
        response = requests.get(
            f"{settings.api_base_url}{path}", timeout=timeout or settings.api_timeout_seconds
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.warning(f"API unavailable or timed out: {exc}")
        return None


def _api_post(path: str, payload: dict, timeout: int | None = None) -> dict | None:
    try:
        response = requests.post(
            f"{settings.api_base_url}{path}",
            json=payload,
            timeout=timeout or settings.api_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.warning(f"API unavailable or timed out: {exc}")
        return None


def _api_upload(path: str, file_obj) -> dict | None:
    try:
        response = requests.post(
            f"{settings.api_base_url}{path}",
            files={"file": (file_obj.name, file_obj.getvalue(), "application/zip")},
            timeout=settings.api_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.warning(f"Upload failed: {exc}")
        return None


def _system_code(system_label: str) -> str:
    from app.services.source_system_registry import normalize_source_system_key

    return normalize_source_system_key(system_label)


def _defaults_for_system(system_code: str) -> dict:
    defaults = _api_get(f"/api/scenario-lab/defaults?source_system={system_code}") or {}
    data = defaults.get("data", {}) if isinstance(defaults, dict) else {}
    return data if isinstance(data, dict) else {}


def _render_scenario_lab(t: dict[str, object], system: str) -> dict:
    st.subheader(str(t["scenario_lab"]))
    st.caption(str(t["caption"]))
    steps = t["steps"]
    steps_list = steps if isinstance(steps, list) else []
    st.write(" → ".join(str(step) for step in steps_list))

    from app.services.source_system_registry import (
        SOURCE_SYSTEM_DISPLAY_ORDER,
        SOURCE_SYSTEM_ORDER,
        display_name,
        get_source_spec,
    )

    current_key = system if system in SOURCE_SYSTEM_ORDER else "sap_ci"
    initial_label = display_name(current_key)
    system_label = st.selectbox(
        str(t["source_system"]),
        SOURCE_SYSTEM_DISPLAY_ORDER,
        index=SOURCE_SYSTEM_DISPLAY_ORDER.index(initial_label),
        key="scenario_source_system",
    )
    system_code = _system_code(system_label)
    default_data = _defaults_for_system(system_code)
    spec = get_source_spec(system_code)
    is_evidence_source = system_code in {"sap_apim", "sap_aem", "sap_s4h"}
    if spec.note:
        st.info(spec.note)

    if not is_evidence_source:
        with st.expander(str(t["upload"]), expanded=False):
            st.caption(str(t["upload_help"]))
            uploads = st.file_uploader(
                str(t["upload"]), type=["zip"], accept_multiple_files=True, key="scenario_upload_zips"
            )
            if uploads and st.button("Save uploaded ZIP exports", key="scenario_save_uploads"):
                uploaded = []
                for file_obj in uploads:
                    result = _api_upload("/api/scenario-lab/upload-iflow-zip", file_obj)
                    if result:
                        uploaded.append(result.get("data", {}))
                st.success(f"Uploaded {len(uploaded)} ZIP file(s).")
                st.json(uploaded)

    primary_label = str(
        default_data.get("primary_label") or default_data.get("zip_label") or t["zip_dir"]
    )
    secondary_label = str(
        default_data.get("secondary_label") or default_data.get("bpmn_label") or t["bpmn_dir"]
    )
    primary_path = str(default_data.get("primary_path") or default_data.get("zip_dir") or "")
    secondary_path = str(default_data.get("secondary_path") or default_data.get("bpmn_dir") or "")

    if system_code == "sap_ci" and isinstance(default_data.get("cpiview"), dict):
        cpiview = default_data["cpiview"]
        with st.expander("CPIView Evidence Source", expanded=bool(cpiview.get("available"))):
            st.caption(
                "Optional read-only enrichment from CPIVIEW_* .env paths. When available, Scenario Lab uses CPIView rich inventory before metadata-only snapshots."
            )
            c1, c2, c3, c4 = st.columns(4)
            counts = cpiview.get("counts", {}) if isinstance(cpiview.get("counts"), dict) else {}
            c1.metric("CPIView enabled", "yes" if cpiview.get("enabled") else "no")
            c2.metric("Available", "yes" if cpiview.get("available") else "no")
            c3.metric("iFlows", counts.get("odata_iflows", 0))
            c4.metric("Deployed", counts.get("deployed_iflows", "N/A"))
            st.text_input(
                "CPIView input folder",
                value=str(cpiview.get("input_dir", "")),
                disabled=True,
                key="cpiview_input_display",
            )
            st.text_input(
                "CPIView output folder",
                value=str(cpiview.get("output_dir", "")),
                disabled=True,
                key="cpiview_output_display",
            )
            if st.button(
                "Refresh/import CPIView evidence",
                key="scenario_import_cpiview",
                disabled=not bool(cpiview.get("available")),
            ):
                result = _api_post(
                    "/api/scenario-lab/import-cpiview", {}, timeout=settings.api_timeout_seconds
                )
                if result and result.get("status") in {"success", "ok"}:
                    st.success(
                        "CPIView evidence imported into resources/cpi/input for Scenario Lab."
                    )
                    st.json(result.get("data", {}))
                elif result:
                    st.warning("CPIView evidence import skipped.")
                    st.json(result)
            if counts:
                st.caption("CPIView evidence counts")
                st.json(counts)
            for note in cpiview.get("notes", []) or []:
                st.info(str(note))

    if system_code == "sap_ci" and isinstance(default_data.get("native_cpi"), dict):
        native_cpi = default_data["native_cpi"]
        with st.expander("Native Python CPI Evidence", expanded=bool(native_cpi.get("enabled"))):
            st.caption(
                "Optional Java-free SAP CPI downloader. It writes CPIView-compatible evidence and then imports it into resources/cpi/input for Scenario Lab."
            )
            counts = (
                native_cpi.get("counts", {}) if isinstance(native_cpi.get("counts"), dict) else {}
            )
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Native enabled", "yes" if native_cpi.get("enabled") else "no")
            c2.metric("CPI configured", "yes" if native_cpi.get("configured") else "no")
            c3.metric("iFlows", counts.get("iflows", 0))
            c4.metric("Deployed", counts.get("deployed_iflows", "N/A"))
            st.text_input(
                "Native CPI input folder",
                value=str(native_cpi.get("input_dir", "")),
                disabled=True,
                key="native_cpi_input_display",
            )
            st.text_input(
                "Native CPI output folder",
                value=str(native_cpi.get("output_dir", "")),
                disabled=True,
                key="native_cpi_output_display",
            )
            max_native = st.number_input(
                "Native download max iFlows (0 = all)",
                min_value=0,
                value=0,
                step=1,
                key="native_cpi_max_iflows",
            )
            download_content = st.checkbox(
                "Download iFlow $value ZIP content", value=True, key="native_cpi_download_content"
            )
            if st.button(
                "Run native CPI download/analyze/report",
                key="scenario_native_cpi_download",
                disabled=not bool(native_cpi.get("enabled") and native_cpi.get("configured")),
            ):
                payload: dict[str, object] = {
                    "download_content": bool(download_content),
                    "max_iflows": int(max_native) if int(max_native) > 0 else None,
                }
                result = _api_post(
                    "/api/scenario-lab/download-native-cpi",
                    payload,
                    timeout=settings.api_timeout_seconds,
                )
                if result and result.get("status") in {"success", "ok"}:
                    st.success(
                        "Native CPI evidence downloaded, analyzed, reported and imported into Scenario Lab resources."
                    )
                    st.json(result.get("data", {}))
                elif result:
                    st.warning("Native CPI evidence download skipped or completed with warnings.")
                    st.json(result)
            for note in native_cpi.get("notes", []) or []:
                st.info(str(note))

    zip_dir = st.text_input(
        primary_label, value=primary_path, key=f"scenario_zip_dir_{system_code}"
    )
    bpmn_dir = st.text_input(
        secondary_label, value=secondary_path, key=f"scenario_bpmn_dir_{system_code}"
    )
    col2, col3 = st.columns([1, 1])
    with col2:
        max_iflows = st.number_input(
            str(t["max_iflows"]), min_value=0, value=0, step=1, key="scenario_max_iflows"
        )
    with col3:
        collect_mpl = st.checkbox(str(t["collect_mpl"]), value=True, key="scenario_collect_mpl")

    if st.button(str(t["run_lab"]), key="run_scenario_lab", width="stretch"):
        payload = {
            "zip_dir": zip_dir,
            "bpmn_dir": bpmn_dir,
            "source_system": system_code,
            "collect_mpl_evidence": collect_mpl,
            "max_iflows": int(max_iflows) if int(max_iflows) > 0 else None,
        }
        with st.spinner(str(t["run_lab"])):
            result = _api_post(
                "/api/scenario-lab/run", payload, timeout=settings.api_timeout_seconds
            )
        if result:
            data = result.get("data", {})
            st.session_state["scenario_lab_latest"] = data
            st.success(f"Scenario Lab output: {data.get('output_dir')}")
            st.caption(f"Objects analyzed: {data.get('iflow_count', 0)}")
            st.json(result)
    latest = st.session_state.get("scenario_lab_latest", {})
    if latest:
        st.info(f"Latest Scenario Lab run: {latest.get('run_id')} | {latest.get('output_dir')}")
    latest["selected_source_system"] = system_code
    return latest


def _render_generation(t: dict[str, object], system: str, latest: dict) -> None:
    st.markdown("---")
    st.subheader(str(t["new_generation"]))
    st.caption(str(t["generation_caption"]))
    selected_system = latest.get("selected_source_system") or system
    source_label = st.radio(
        str(t["generation_source"]),
        [str(t["live_mpl"]), str(t["archived_mpl"])],
        index=1,
        horizontal=True,
        key="scenario_generation_source_mode",
    )
    source_mode = "live_mpl" if source_label == t["live_mpl"] else "archived_mpl"
    archived_mpl_source = "all_sources"
    if source_mode == "archived_mpl":
        defaults_for_generation = _defaults_for_system(selected_system)
        source_options = (
            defaults_for_generation.get("archived_mpl_source_options", [])
            if isinstance(defaults_for_generation, dict)
            else []
        )
        labels = [item.get("label", item.get("key", "all_sources")) for item in source_options] or [
            "all_sources"
        ]
        keys = [item.get("key", "all_sources") for item in source_options] or ["all_sources"]
        selected_label = st.selectbox(
            str(t.get("select_mpl_source", "Select MPL Source")),
            labels,
            index=0,
            key="scenario_archived_mpl_source",
        )
        archived_mpl_source = (
            keys[labels.index(selected_label)] if selected_label in labels else "all_sources"
        )

    mode_label = st.radio(
        str(t["generation_mode"]),
        [str(t["generate_mode"]), str(t["update_existing_docs_mode"])],
        index=0,
        horizontal=True,
        key="scenario_generation_mode",
        help=str(t.get("update_existing_docs_help", "")),
    )
    generation_mode = (
        "update_existing_docs" if mode_label == t["update_existing_docs_mode"] else "generate"
    )
    update_existing = generation_mode == "update_existing_docs"

    existing_documents_path = ""
    if update_existing:
        existing_documents_path = st.text_input(
            str(t["existing_documents_path"]),
            value="",
            placeholder="./exports/generated_documents/20260503_001716_live_mpl_v1",
            key="scenario_existing_documents_path_input",
        )
    version = st.text_input(
        str(t["generation_version"]), value="v1", key="scenario_generation_version_input"
    )

    feedback_label = st.selectbox(
        str(t["feedback_source"]),
        [str(t["feedback_none"]), str(t["feedback_latest"]), str(t["feedback_selected"])],
        index=0,
        key="scenario_generation_feedback_source",
        disabled=not update_existing,
    )
    feedback_source = (
        "latest"
        if feedback_label == t["feedback_latest"]
        else "selected"
        if feedback_label == t["feedback_selected"]
        else "none"
    )
    feedback_path = ""
    if update_existing and feedback_source == "selected":
        feedback_path = st.text_input(
            str(t["feedback_file_path"]),
            value="",
            placeholder="feedback/run_20260429_154356_feedback.json",
            key="scenario_generation_feedback_path",
        )
    apply_remediation_hints = st.checkbox(
        str(t["apply_remediation_hints"]),
        value=update_existing,
        key="scenario_apply_remediation_hints",
        disabled=not update_existing,
    )

    use_scenario = st.checkbox(
        str(t["use_scenario"]), value=bool(latest), key="scenario_use_latest"
    )
    scenario_run_id = latest.get("run_id", "") if latest else ""
    scenario_manifest_path = latest.get("scenario_manifest", "") if latest else ""
    iflow_analysis_report_path = latest.get("analysis_report", "") if latest else ""
    if use_scenario:
        scenario_run_id = st.text_input(
            str(t["scenario_run_id"]), value=scenario_run_id, key="generation_scenario_run_id"
        )
        scenario_manifest_path = st.text_input(
            str(t["scenario_manifest_path"]),
            value=scenario_manifest_path,
            key="generation_scenario_manifest",
        )
        iflow_analysis_report_path = st.text_input(
            str(t["iflow_analysis_report_path"]),
            value=iflow_analysis_report_path,
            key="generation_iflow_analysis_report",
        )

    prevent_duplicate_id = st.checkbox(
        str(t.get("prevent_duplicate_doc_id", "prevent dublicate ID")),
        value=True,
        key="scenario_prevent_duplicate_id",
    )

    col1, col2, col3 = st.columns(3)
    if update_existing:
        actions = [
            (col1, "catalog_docs", str(t["update_interface"])),
            (col2, "kedb", str(t["update_kedb"])),
            (col3, "runbooks", str(t["update_runbooks"])),
        ]
    else:
        actions = [
            (col1, "catalog_docs", str(t["generate_interface"])),
            (col2, "kedb", str(t["generate_kedb"])),
            (col3, "runbooks", str(t["generate_runbooks"])),
        ]
    for column, document_type, label in actions:
        with column:
            prevent_duplicate_doc_id = bool(prevent_duplicate_id)
            restart_kedb_id_counting = False
            restart_runbook_id_counting = False
            if document_type == "kedb":
                restart_kedb_id_counting = st.checkbox(
                    str(t.get("restart_id_counting", "restart ID counting")),
                    value=False,
                    key="scenario_restart_kedb_id_counting",
                )
            elif document_type == "runbooks":
                restart_runbook_id_counting = st.checkbox(
                    str(t.get("restart_id_counting", "restart ID counting")),
                    value=False,
                    key="scenario_restart_runbook_id_counting",
                )
            if st.button(label, key=f"scenario_generate_{document_type}_button", width="stretch"):
                if update_existing and not existing_documents_path.strip():
                    st.warning(
                        "Existing generated documents folder is required when Generation mode = Update existing docs."
                    )
                    continue
                payload = {
                    "version": version,
                    "source_system": selected_system,
                    "source_mode": source_mode,
                    "archived_mpl_source": archived_mpl_source,
                    "generation_mode": generation_mode,
                    "prevent_duplicate_doc_id": bool(prevent_duplicate_doc_id),
                    "prevent_duplicate_id": bool(prevent_duplicate_id),
                    "restart_kedb_id_counting": bool(restart_kedb_id_counting),
                    "restart_runbook_id_counting": bool(restart_runbook_id_counting),
                    "existing_documents_path": existing_documents_path if update_existing else None,
                    "feedback_source": feedback_source if update_existing else "none",
                    "feedback_path": feedback_path or None,
                    "apply_remediation_hints": bool(apply_remediation_hints and update_existing),
                    "scenario_lab_run_id": scenario_run_id if use_scenario else None,
                    "scenario_manifest_path": scenario_manifest_path if use_scenario else None,
                    "iflow_analysis_report_path": iflow_analysis_report_path
                    if use_scenario
                    else None,
                }
                with st.spinner(label):
                    if selected_system in {"sap_apim", "sap_aem", "sap_s4h"}:
                        if document_type == "catalog_docs":
                            st.info(
                                "interface_inventory generation applies to SAP CI / SAP PIPO. "
                                "For APIM/AEM/S4H, use Generate KEDBs / Generate Runbooks "
                                "(produced together from approved signatures)."
                            )
                            result = None
                        elif selected_system == "sap_apim":
                            # APIM documents are CPI knowledge.
                            apim_payload = {
                                "source_system": "sap_apim",
                                "live": source_mode == "live_mpl",
                                "archived_source": archived_mpl_source,
                                "version": version,
                                "prevent_duplicate_id": bool(prevent_duplicate_id),
                            }
                            result = _api_post(
                                "/api/apim/generate-knowledge",
                                apim_payload,
                                timeout=settings.api_timeout_seconds,
                            )
                        else:
                            evidence_payload = {
                                "source_system": selected_system,
                                "archived_source": archived_mpl_source,
                                "version": version,
                                "prevent_duplicate_id": bool(prevent_duplicate_id),
                            }
                            result = _api_post(
                                "/api/evidence/generate-knowledge",
                                evidence_payload,
                                timeout=settings.api_timeout_seconds,
                            )
                    else:
                        result = _api_post(
                            f"/api/monitoring-generation/generate/{document_type}",
                            payload,
                            timeout=settings.api_timeout_seconds,
                        )
                if result:
                    data = result.get("data", {})
                    if result.get("status") == "generated":
                        st.success(f"{t['result']}: {data.get('output_dir')}")
                    else:
                        st.warning(f"{t['result']}: {result.get('status')}")
                    st.caption(f"{t['generated_count']}: {data.get('generated_count', 0)}")
                    st.json(result)


def render(model, translator) -> None:
    language = getattr(translator, "language", "en")
    t = TEXT.get(language, TEXT["en"])
    st.header(str(t["title"]))
    query_system = str(st.query_params.get("monitor_system", "") or "")
    system = "sap_pipo" if query_system == "sap_pipo" else "sap_ci"
    latest = _render_scenario_lab(t, system)
    _render_generation(t, system, latest)
