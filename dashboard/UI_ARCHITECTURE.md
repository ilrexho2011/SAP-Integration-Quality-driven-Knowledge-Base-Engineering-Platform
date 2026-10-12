# QDKEP UI Architecture (v2.0.9)

This document describes the **single, canonical** user-interface stack after the
v2.0.9 consolidation (review point 1.1). It exists so the UI surface does not
drift back into parallel, competing entry points.

## One canonical UI

The platform has exactly one interactive UI: the **Streamlit multi-page
dashboard**, launched by:

```bash
python scripts/run_dashboard.py
# (which runs: streamlit run dashboard/qdkep_dashboard.py)
```

### Components

| Path | Role |
| ------ | ------ |
| `dashboard/qdkep_dashboard.py` | Dashboard entry point. Also embeds the Enterprise Quality Console. |
| `dashboard/pages/` | The 14 dashboard pages (overview, monitoring, scenario_lab_generation, contract_validation, package_builder, quality_gates, ai4cpi_export, evidence_traceability, generators, benchmark, reports_downloads, send_feedback, settings, plus `_shared.py`). |
| `dashboard/components/` | Shared UI components (e.g. `navigation.py`). |
| `dashboard/assets/` | UI assets (e.g. `logo.png`). |
| `dashboard/qdkep_enterprise_quality_console.py` | Enterprise QA console, embedded by the dashboard and used by `app/main.py` and the CLI. |
| `dashboard/i18n/` | Translation **data** (`en.json`, `de.json`) used by the console and `enterprise_console_service`. |
| `app/dashboard/dashboard_i18n.py` | Translation **helper** (Python) used by the console. Distinct role from `dashboard/i18n/` (data vs logic). |

### Backend

The dashboard talks to the FastAPI app (`app/main.py`) and the service layer in
`app/services/`. The API is the programmatic entry point; the dashboard is the
human entry point. Both share the same services — there is no duplicated
business logic in the UI layer.

## What was removed in v2.0.9 (1.1)

- **`app/ui/streamlit_app.py`** and the whole `app/ui/` package — a third,
  fully-orphaned Streamlit app that nothing imported or launched. Removing it
  eliminates a competing UI entry point and the confusion of "which Streamlit
  app is the real one".
- `app/ui/logo.png` was the only still-referenced asset there (the active
  dashboard navigation read it). It was relocated to `dashboard/assets/logo.png`
  and the single reference in `dashboard/components/navigation.py` was updated.

## What was intentionally kept

The original review flagged "three parallel UIs". On inspection, only `app/ui/`
was truly redundant. The Enterprise Quality Console and the two i18n mechanisms
are **wired into** the canonical dashboard and serve distinct roles, so they
were kept rather than force-merged (which would have been high-risk for no
functional gain).

## Guidance for future work

- Add new screens as pages under `dashboard/pages/`, not as new top-level apps.
- Keep business logic in `app/services/`; pages should orchestrate and render.
- Put new UI assets in `dashboard/assets/`.
- Do not reintroduce a second Streamlit entry point.
