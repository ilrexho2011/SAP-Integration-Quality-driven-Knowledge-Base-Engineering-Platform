from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from app.config import settings
from dashboard.components.downloads import render_downloads
from dashboard.components.issue_tables import render_issues, render_warnings


def render(model, translator) -> None:
    page = model.pages["reports_downloads"]
    st.header(page.title)
    st.caption(translator.text("service_backed"))

    st.subheader("Manual Actions")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Refresh reports list", width="stretch"):
            st.rerun()
    with col2:
        latest_reports = (
            sorted(
                Path(settings.reports_dir).glob("*"), key=lambda p: p.stat().st_mtime, reverse=True
            )
            if Path(settings.reports_dir).exists()
            else []
        )
        if st.button("Open latest report", width="stretch"):
            if latest_reports:
                st.info(str(latest_reports[0]))
                st.code(latest_reports[0].read_text(encoding="utf-8", errors="ignore")[:5000])
            else:
                st.warning("No report files found.")
    with col3:
        generated_root = Path(settings.exports_dir) / "generated_documents"
        if st.button("Show generated documents", width="stretch"):
            files = (
                sorted(generated_root.rglob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[
                    :50
                ]
                if generated_root.exists()
                else []
            )
            st.json([str(path) for path in files])

    st.subheader(translator.text("downloads"))
    render_downloads(
        model.package_path,
        page.downloads,
        translator.text("download"),
        translator.text("not_available"),
    )
    st.subheader(translator.text("issues"))
    render_issues(page.issues, translator.text("no_blockers"))
    st.subheader(translator.text("warnings"))
    render_warnings(page.warnings, translator.text("no_warnings"))
    with st.expander("Raw dashboard summary"):
        st.code(
            json.dumps(model.raw_summary, indent=2, ensure_ascii=False, default=str),
            language="json",
        )
