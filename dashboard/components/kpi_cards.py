from __future__ import annotations

import streamlit as st


def render_kpis(kpis: list) -> None:
    if not kpis:
        st.info("No KPI data available.")
        return
    columns = st.columns(min(4, max(1, len(kpis))))
    for index, card in enumerate(kpis):
        with columns[index % len(columns)]:
            st.metric(
                label=str(getattr(card, "label", "KPI")),
                value=getattr(card, "value", None)
                if getattr(card, "value", None) is not None
                else "n/a",
                help=getattr(card, "help_text", ""),
            )
