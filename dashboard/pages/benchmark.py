from __future__ import annotations

from dashboard.pages._shared import render_page as _render


def render(model, translator) -> None:
    _render(model, "benchmark", translator)
