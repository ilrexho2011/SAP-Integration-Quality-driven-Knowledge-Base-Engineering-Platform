# Release Notes — v2.0.9 (Architecture Refactor)

Successor to v2.0.8. Completes the two remaining review points (2.5 and 1.1) and
integrates the user-improved `dashboard_summary.py`. Full suite passes
(**104 tests**); `ruff check` and `ruff format --check` are clean.

## v2.0.9.1 hotfix — dashboard Arrow serialization

Fixes a runtime error reported from the Streamlit dashboard:

    pyarrow.lib.ArrowInvalid: Could not convert 'N/A' with type str:
    tried to convert to int64 ... Conversion failed for column Value

Cause: the monitoring **inventory table** (`dashboard/pages/monitoring.py`) built
a "Value" column mixing integer counts with the string `"N/A"` (used when the
deployed-iFlow count is unknown). PyArrow infers one type per column, so the mix
of int and "N/A" failed serialization. Note this was a *different* table from the
one fixed in `dashboard_summary.py` — the metrics service was already Arrow-safe;
this hand-built inventory table was not.

Fix: render every value in that column as a string, which keeps the column
homogeneous while preserving the meaningful "N/A" for unknown deployment. The
`st.metric()` calls in `scenario_lab_generation.py` that also use "N/A" are
unaffected (metrics accept strings). Added regression tests
(`tests/test_v209_dashboard_arrow_safe.py`) that reproduce the original failure
and assert the table is now Arrow-serializable both with and without a deployed
count.

Backend (FastAPI) was confirmed healthy in the report — all endpoints returned
200 OK; only the dashboard table was affected.

## How to install and run

    # from the project root
    python -m venv .venv && source .venv/bin/activate   # optional
    pip install -e ".[dev]"

    ruff check .
    ruff format --check .
    pytest                       # 101 tests
    mypy app                     # informational

    python scripts/run_dashboard.py

## What changed from v2.0.8

### 2.5 — `generate()` refactor (22-argument God-method)

- Introduced **`GenerationRequest`** (frozen dataclass) that carries all
  generation parameters with their original defaults, grouped by concern
  (what to generate, generation mode, feedback, scenario lab, source selection,
  duplicate/ID governance, multi-customer).
- Added **`generate_from_request(request)`** holding the orchestration logic.
- `generate(**kwargs)` is now a thin, fully backward-compatible wrapper that
  builds a `GenerationRequest` and delegates — existing callers (API, dashboard,
  tests) are unchanged.
- Extracted the ~45-key manifest literal into **`_build_manifest_data()`**, so
  orchestration and manifest assembly are separated.
- Verified: keyword `generate()` and `generate_from_request()` produce
  equivalent results.

### 1.1 — UI consolidation

- Removed the **orphaned `app/ui/` Streamlit app** (`streamlit_app.py`) — a third
  UI entry point that nothing imported or launched.
- Relocated the still-used `logo.png` from `app/ui/` to **`dashboard/assets/`**
  and updated the single reference in `dashboard/components/navigation.py`.
- Added **`dashboard/UI_ARCHITECTURE.md`** documenting the single canonical UI
  (the Streamlit multi-page dashboard) so the surface does not drift again.
- Kept (intentionally) the Enterprise Quality Console and the two i18n
  mechanisms: on inspection they are wired into the canonical dashboard and
  serve distinct roles (translation data vs translation helper), so force-merging
  them would have been high-risk with no functional gain. Only the genuinely
  redundant `app/ui/` was removed.

### Integrated: improved `dashboard_summary.py`

- The user-provided version is now in the tree. It makes the dashboard metrics
  **Arrow-safe**: all `*_count` metrics are coerced to int (never None), fixing a
  PyArrow "Could not convert 'N/A' with type str" failure when the metrics are
  rendered in a single Arrow-backed table column. Also hardens report handling
  (`reports.get(name) or {}`).

## Cumulative state (Waves 1-3 + this release)

- Wave 1: incident filter, exact-match duplicate detection, evidence warnings,
  dead-code/`.env` cleanup, single-source version.
- Wave 2: real optional AI enrichment, multi-customer, inventory-driven priority,
  Jinja2 template engine (byte-identical output).
- Wave 3: ruff lint+format gate, mypy (informational), pyproject + editable
  install, GitHub Actions CI, **2.5 generate() refactor**, **1.1 UI consolidation**.

All review points from the original v2.0.7 assessment are now addressed.

## Dependencies

- `Jinja2>=3.1` (since v2.0.8).
