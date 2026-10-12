from __future__ import annotations

import requests
import streamlit as st

from app.config import settings


def _api_get(path: str, params: dict | None = None) -> dict | None:
    try:
        response = requests.get(
            f"{settings.api_base_url}{path}",
            params=params or {},
            timeout=settings.api_timeout_seconds,
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.warning(f"API unavailable or timed out after {settings.api_timeout_seconds}s: {exc}")
        return None


def _api_post(path: str, payload: dict) -> dict | None:
    try:
        response = requests.post(
            f"{settings.api_base_url}{path}", json=payload, timeout=settings.api_timeout_seconds
        )
        response.raise_for_status()
        return response.json()
    except Exception as exc:
        st.warning(f"API unavailable or timed out after {settings.api_timeout_seconds}s: {exc}")
        return None


def render(model, translator) -> None:
    st.header("Send feedback")
    st.caption(
        "Create and review controlled remediation feedback. Feedback JSON files are stored in the feedback folder and can be used by the document regenerators after user approval."
    )

    st.subheader("Create feedback")
    package_id = st.text_input("Package ID", value="quality-driven-knowledge-engineering-platform")
    benchmark_report_path = st.text_input(
        "Benchmark report path",
        value=str(settings.project_root / "quality" / "benchmark_readiness_report.json"),
        help="Use the latest benchmark report or provide a specific benchmark JSON path.",
    )
    output_filename = st.text_input(
        "Output filename", value="", placeholder="run_YYYYMMDD_HHMMSS_feedback.json"
    )
    if st.button("Generate feedback", width="stretch"):
        payload = {
            "package_id": package_id,
            "benchmark_report_path": benchmark_report_path or None,
            "output_filename": output_filename or None,
        }
        result = _api_post("/api/feedback/create", payload)
        if result:
            st.success(f"Feedback generated: {result.get('output_path')}")
            with st.expander("Generated feedback JSON", expanded=False):
                st.json(result.get("data", {}).get("feedback", {}))

    st.markdown("---")
    st.subheader("Available feedback artifacts")
    listing_result = _api_get("/api/feedback/list")
    listing = listing_result.get("data", {}).get("feedback", []) if listing_result else []
    if listing:
        st.dataframe(listing, width="stretch", hide_index=True)
        options = [item["filename"] for item in listing]
        selected = st.selectbox("Open feedback file", options=options)
        if st.button("Open selected feedback", width="stretch"):
            result = _api_get("/api/feedback/read", params={"filename": selected})
            if result:
                st.json(result.get("data", {}).get("payload", {}))
    else:
        st.info(
            "No feedback JSON files found yet. Generate feedback from a benchmark report first."
        )

    st.markdown("---")
    st.subheader("How regenerators use feedback")
    st.write(
        "In Scenario Lab & Generation → New-knowledge generation, choose Generation mode = Update existing docs, choose Feedback source = Latest feedback or Select feedback file, then enable Apply remediation hints during Update existing docs. The generator records the selected feedback path and governance controls in generation_manifest.json."
    )
