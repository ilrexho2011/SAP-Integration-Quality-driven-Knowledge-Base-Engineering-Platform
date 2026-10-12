from __future__ import annotations

import json
from pathlib import Path

import requests
import streamlit as st

from app.config import settings
from dashboard.components.badges import render_badge_grid, render_status_badge
from dashboard.components.downloads import render_downloads
from dashboard.components.issue_tables import render_issues, render_warnings
from dashboard.components.kpi_cards import render_kpis


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


def _default_output(name: str) -> str:
    return str(settings.quality_dir / name)


def _render_action_result(result: dict | None) -> None:
    if not result:
        return
    status = result.get("status", "unknown")
    output = result.get("output_path") or result.get("data", {}).get("output_dir")
    if status in {"success", "completed", "ready", "approved", "generated", "exported", "uploaded"}:
        st.success(f"Status: {status}")
    else:
        st.warning(f"Status: {status}")
    if output:
        st.caption(f"Output: {output}")
    with st.expander("Action response", expanded=False):
        st.json(result)


def _render_action_panel(model, page_key: str, translator) -> None:
    st.subheader("Manual Actions")
    package_path = str(model.package_path or ".")

    if page_key == "overview":
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Refresh dashboard", width="stretch"):
                st.rerun()
        with col2:
            if st.button("Run full platform check", width="stretch"):
                result = _api_post(
                    "/api/dashboard/enterprise-quality-console", {"package_path": package_path}
                )
                _render_action_result(result)
        with col3:
            if st.button("Recalculate KPIs", width="stretch"):
                result = _api_post(
                    "/api/dashboard/enterprise-review", {"package_path": package_path}
                )
                _render_action_result(result)

    elif page_key == "contract_validation":
        col1, col2, col3 = st.columns(3)
        payload = {
            "package_path": package_path,
            "output_json": "quality/contract_validation_report.json",
        }
        with col1:
            if st.button("Run contract validation", width="stretch"):
                _render_action_result(_api_post("/api/contracts/validate-package", payload))
        with col2:
            if st.button("Validate metadata", width="stretch"):
                _render_action_result(_api_post("/api/contracts/validate-package", payload))
        with col3:
            if st.button("Validate folder structure", width="stretch"):
                _render_action_result(_api_post("/api/contracts/validate-package", payload))

    elif page_key == "package_builder":
        output_zip = str(settings.exports_dir / "qdkep_package_v205_manual.zip")
        col1, col2, col3 = st.columns(3)
        payload = {
            "source_root": package_path,
            "output_zip": output_zip,
            "package_version": "2.0.7",
        }
        with col1:
            if st.button("Scan package folder", width="stretch"):
                exists = Path(package_path).exists()
                st.info(f"Package path exists: {exists} | {package_path}")
        with col2:
            if st.button("Build package", width="stretch"):
                _render_action_result(_api_post("/api/packages/build-package", payload))
        with col3:
            if st.button("Create package manifest", width="stretch"):
                _render_action_result(_api_post("/api/packages/build-package", payload))

    elif page_key == "quality_gates":
        col1, col2, col3 = st.columns(3)
        payload = {
            "package_path": package_path,
            "output_json": "quality/package_quality_gate_report.json",
        }
        with col1:
            if st.button("Run all quality gates", width="stretch"):
                _render_action_result(_api_post("/api/packages/package-quality-gate", payload))
        with col2:
            if st.button("Run ingestion policy check", width="stretch"):
                _render_action_result(_api_post("/api/packages/package-quality-gate", payload))
        with col3:
            if st.button("Run promotion decision", width="stretch"):
                _render_action_result(_api_post("/api/packages/package-quality-gate", payload))

    elif page_key == "ai4biz_export":
        col1, col2, col3 = st.columns(3)
        payload = {
            "package_path": package_path,
            "output_root": "exports/ai4biz_rag_console_payload",
        }
        with col1:
            if st.button("Check export readiness", width="stretch"):
                _render_action_result(_api_post("/api/packages/export-ai4biz-ingestion", payload))
        with col2:
            if st.button("Build export package", width="stretch"):
                _render_action_result(_api_post("/api/packages/export-ai4biz-ingestion", payload))
        with col3:
            if st.button("Create release candidate", width="stretch"):
                _render_action_result(_api_post("/api/packages/export-ai4biz-ingestion", payload))

    elif page_key == "evidence_traceability":
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Run traceability scan", width="stretch"):
                _render_action_result(
                    _api_post(
                        "/api/dashboard/enterprise-quality-console", {"package_path": package_path}
                    )
                )
        with col2:
            if st.button("Validate evidence links", width="stretch"):
                _render_action_result(
                    _api_post(
                        "/api/dashboard/enterprise-quality-console", {"package_path": package_path}
                    )
                )
        with col3:
            if st.button("Generate traceability matrix", width="stretch"):
                _render_action_result(
                    _api_post("/api/dashboard/enterprise-review", {"package_path": package_path})
                )

    elif page_key == "generators":
        col1, col2, col3 = st.columns(3)
        payload = {"package_path": package_path, "benchmark_profile": "default"}
        with col1:
            if st.button("Generate golden questions", width="stretch"):
                _render_action_result(
                    _api_post("/api/benchmark/generate-golden-questions", payload)
                )
        with col2:
            if st.button("Generate metadata suggestions", width="stretch"):
                _render_action_result(
                    _api_post("/api/dashboard/enterprise-review", {"package_path": package_path})
                )
        with col3:
            if st.button("Generate remediation hints", width="stretch"):
                _render_action_result(_api_post("/api/benchmark/run", payload))

    elif page_key == "benchmark":
        col1, col2, col3 = st.columns(3)
        payload = {"package_path": package_path, "benchmark_profile": "default"}
        with col1:
            if st.button("Run static benchmark", width="stretch"):
                _render_action_result(_api_post("/api/benchmark/run", payload))
        with col2:
            if st.button("Run retrieval benchmark", width="stretch"):
                _render_action_result(_api_post("/api/benchmark/run", payload))
        with col3:
            if st.button("Generate benchmark report", width="stretch"):
                _render_action_result(_api_post("/api/benchmark/run", payload))

    elif page_key == "settings":
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("Test backend connection", width="stretch"):
                try:
                    response = requests.get(f"{settings.api_base_url}/health", timeout=10)
                    response.raise_for_status()
                    st.success("Backend connection OK")
                    st.json(response.json())
                except Exception as exc:
                    st.error(f"Backend connection failed: {exc}")
        with col2:
            if st.button("Test AI API configuration", width="stretch"):
                from app.services.ai_assistance_service import AIAssistanceService

                st.json(AIAssistanceService().describe())
        with col3:
            if st.button("Reload .env", width="stretch"):
                st.info("Restart backend and dashboard process to reload .env values safely.")


def render_page(model, page_key: str, translator) -> None:
    page = model.pages[page_key]
    st.header(page.title)
    st.caption(translator.text("service_backed"))
    render_status_badge(
        translator.text("status"),
        page.status,
        "success"
        if page.status in {"approved", "ready", "success", "review_ready", "completed"}
        else "warning",
    )
    st.write(page.summary)
    if page.source:
        st.caption(f"{translator.text('source')}: `{page.source}`")
    _render_action_panel(model, page_key, translator)
    if page_key == "overview":
        st.subheader(translator.text("metrics"))
        render_kpis(model.kpis)
        st.subheader(translator.text("workflow"))
        render_badge_grid(model.badges)
    else:
        st.subheader(translator.text("metrics"))
        st.json(page.metrics)
    st.subheader(translator.text("issues"))
    render_issues(page.issues, translator.text("no_blockers"))
    st.subheader(translator.text("warnings"))
    render_warnings(page.warnings, translator.text("no_warnings"))
    if page.downloads:
        st.subheader(translator.text("downloads"))
        render_downloads(
            model.package_path,
            page.downloads,
            translator.text("download"),
            translator.text("not_available"),
        )
    with st.expander("Raw page model"):
        st.code(json.dumps(page.raw, indent=2, ensure_ascii=False, default=str), language="json")
