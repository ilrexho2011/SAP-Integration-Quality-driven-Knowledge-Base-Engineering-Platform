from __future__ import annotations

import streamlit as st

_TONE_ICON = {
    "success": "✅",
    "warning": "⚠️",
    "error": "⛔",
    "info": "ℹ️",
}


def render_status_badge(label: str, status: str, tone: str = "info") -> None:
    icon = _TONE_ICON.get(tone, "ℹ️")
    st.markdown(f"**{label}**: {icon} `{status}`")


def render_badge_grid(badges: list) -> None:
    if not badges:
        st.info("No status badges available.")
        return
    columns = st.columns(3)
    for index, badge in enumerate(badges):
        with columns[index % 3]:
            render_status_badge(
                getattr(badge, "label", "status"),
                getattr(badge, "status", "unknown"),
                getattr(badge, "tone", "info"),
            )
