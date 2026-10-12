from __future__ import annotations

import importlib

import streamlit as st

from app.dashboard.dashboard_i18n import DashboardTranslator, TECHNICAL_CONSTANTS
from app.dashboard.enterprise_console_service import EnterpriseConsoleService
from dashboard.components.navigation import render_sidebar


def _hide_streamlit_native_pages_navigation() -> None:
    """Hide Streamlit's auto-generated multipage menu.

    The QDKEP console owns the sidebar navigation so the logo appears first,
    followed by Monitoring & Generation, QDKEP Dashboard, and the remaining
    commands in one merged navigation group.
    """
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"],
        [data-testid="stSidebarNavItems"],
        section[data-testid="stSidebar"] nav {
            display: none !important;
            visibility: hidden !important;
            height: 0 !important;
            min-height: 0 !important;
            max-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
            overflow: hidden !important;
        }
        section[data-testid="stSidebar"] > div:first-child {
            padding-top: 1rem !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _inject_global_button_style() -> None:
    """Apply the RealCore-green button style to all Streamlit buttons."""
    st.markdown(
        """
        <style>
        div[data-testid="stButton"] > button {
            background-color: #E8F9EE !important;
            color: #000000 !important;
            font-weight: 800 !important;
            font-size: 1.05rem !important;
            min-height: 3.2rem !important;
            border-radius: 0.55rem !important;
            border: 1px solid #5fa334 !important;
            box-shadow: 0 1px 2px rgba(16, 24, 40, 0.16) !important;
        }
        div[data-testid="stButton"] > button:hover {
            background-color: #88C85A !important;
            color: #000000 !important;
            border-color: #4f8f2b !important;
        }
        div[data-testid="stButton"] > button:focus {
            color: #000000 !important;
            border-color: #3f7f22 !important;
            box-shadow: 0 0 0 0.2rem rgba(117, 184, 67, 0.25) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


st.set_page_config(page_title="Quality-Driven Knowledge Engineering Platform", layout="wide")
_hide_streamlit_native_pages_navigation()
_inject_global_button_style()

initial_translator = DashboardTranslator("en")
package_path, language, page_key = render_sidebar(initial_translator)
translator = DashboardTranslator(language)
model = EnterpriseConsoleService().build_model(package_path, language=language)

st.title(translator.text("app_title"))
status_hint = None
try:
    import requests
    from app.config import settings

    response = requests.get(f"{settings.api_base_url}/health", timeout=5)
    response.raise_for_status()
    status = response.json()
    st.success(f"API Status: {status.get('status')} - v{status.get('version')}")
except Exception:
    status_hint = "Start backend with: python -m uvicorn app.main:app --reload"
    st.info(status_hint)

if page_key != "monitoring":
    st.caption(translator.text("app_caption"))
    st.markdown(f"**promotion_decision**: `{model.promotion_decision}`")

try:
    page_module = importlib.import_module(f"dashboard.pages.{page_key}")
    page_module.render(model, translator)
# Streamlit should show a user-readable error without hiding diagnostics.
except Exception as exc:
    st.error(f"Dashboard page failed: {page_key}")
    st.exception(exc)

with st.sidebar.expander(translator.text("technical_constants")):
    for constant in sorted(TECHNICAL_CONSTANTS):
        st.code(constant)
