# Release Notes v1.9.7 - Scenario Lab & Generation

## Summary

v1.9.7 separates operational monitoring from knowledge generation and introduces the first functional Scenario Lab workflow for SAP CPI iFlow reverse engineering.

## Source-backed changes

- Navigation is reordered to: QDKEP Dashboard, Monitoring Events, Scenario Lab & Generation, Contract Validation, Package Builder, Quality Gates, AI4BIZ Export, Evidence & Traceability, Generators, Benchmark, Send feedback, Reports & Downloads, Settings.
- `Monitoring & Generation` is renamed to `Monitoring Events` and keeps only operational monitor functions.
- New page: `dashboard/pages/scenario_lab_generation.py`.
- New backend service: `app/services/iflow_scenario_service.py`.
- New API endpoints:
  - `GET /api/scenario-lab/defaults`
  - `POST /api/scenario-lab/upload-iflow-zip`
  - `POST /api/scenario-lab/run`
- Existing generation endpoint `/api/monitoring-generation/generate/{document_type}` accepts optional Scenario Lab enrichment fields:
  - `scenario_lab_run_id`
  - `scenario_manifest_path`
  - `iflow_analysis_report_path`
- Version is updated to `1.9.7-scenario-lab-generation` in `app/config.py`, `.env`, and `.env.example`.

## Scenario Lab outputs

The workflow writes under `exports/scenario_lab/<run_id>/`:

- `iflow_upload_manifest.json`
- `iflow_analysis_report.json`
- `iflow_analysis_summary.md`
- `scenario_manifest.json`
- `payload_examples/`
- `execution_plan/`
- `expected_mpl_patterns/`
- `mpl_evidence/collected_mpl_evidence.json`
- `mpl_evidence/expected_vs_observed_mpl_matrix.json`

## Safety model

- Read-only inspection of local iFlow ZIP and BPMN evidence.
- No automatic mutation of deployed/live iFlows.
- Negative examples are functional DEV/TEST inputs only.
- MPL evidence is represented as a planned/observed matrix until tests are executed and Live MPL or Archived MPL evidence is provided.

## Tests run

- `python -m compileall app dashboard`
- `pytest -q tests/test_monitor_time_range_hotfix.py`
- `pytest -q tests/test_dashboard_blueprint_v1.py`
- `pytest -q tests/test_v197_scenario_lab_generation.py`
- Manual FastAPI smoke checks for `/health`, `/api/scenario-lab/defaults`, `/api/scenario-lab/run`, and `/api/monitoring-generation/generate/catalog_docs`.

## Open points

- Full `pytest -q` showed completed dots for many tests but the container command timed out in this environment on monitor endpoint tests that can touch live-monitor configuration. Targeted regression tests passed.
- Advanced payload generation should be deepened in a later version using richer adapter- and schema-specific parsers.
