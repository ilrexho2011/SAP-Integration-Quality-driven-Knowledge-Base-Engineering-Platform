from __future__ import annotations

import pandas as pd
import streamlit as st


def render_issues(issues: list[dict], empty_text: str) -> None:
    if issues:
        st.dataframe(pd.DataFrame(issues), width="stretch")
    else:
        st.success(empty_text)


def render_warnings(warnings: list[str], empty_text: str) -> None:
    if warnings:
        for warning in warnings:
            st.warning(warning)
    else:
        st.info(empty_text)
