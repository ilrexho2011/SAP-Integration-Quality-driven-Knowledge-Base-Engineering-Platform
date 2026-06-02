# Release Notes - v2.0.1

## Scope

Version `v2.0.1` adds a CPIView-compatible evidence ingestion layer on top of the live SAP CPI snapshot introduced in `v2.0.0`. The goal is to enrich Scenario Lab with local CPIView evidence while preserving existing live and upload-based workflows.

## Added

- New `.env` settings for CPIView local evidence integration:
  - `CPIVIEW_ENABLED`
  - `CPIVIEW_ROOT`
  - `CPIVIEW_TENANT_ID`
  - `CPIVIEW_INPUT_DIR`
  - `CPIVIEW_OUTPUT_DIR`
- New service: `app/services/cpiview_evidence_service.py`.
- New API endpoint: `POST /api/scenario-lab/import-cpiview`.
- New Scenario Lab UI section: `CPIView Evidence Source`.
- New generated rich inventory target:
  - `resources/cpi/input/analysis/iflow_rich_inventory.json`
- New tests:
  - `tests/test_v201_cpiview_evidence.py`

## Changed

- Monitoring Events now uses CPIView `runtimes.json`, when available, as the preferred source for the `Deployed` KPI.
- Scenario Lab now prefers `iflow_rich_inventory.json` for SAP CI/CPI when available, before falling back to ZIP/BPMN/manual metadata paths.
- CPI live monitoring can trigger CPIView evidence import when `CPIVIEW_ENABLED=true` and the configured local folders exist.

## Evidence Inputs Supported

The CPIView-compatible importer reads the following local evidence files when present:

- `odata/packages.json`
- `odata/iflows.json`
- `odata/runtimes.json`
- `odata/configurations.json`
- `odata/resources.json`
- `odata/message-mappings.json`
- `odata/script-collections.json`
- `odata/value-mappings.json`
- `analysis/bpmn-activities.json`
- `analysis/bpmn-channels.json`
- `analysis/bpmn-channels-properties.json`
- `analysis/bpmn-content-modifiers.json`
- `analysis/bpmn-groovy-scripts.json`
- `analysis/bpmn-message-mappings.json`
- `analysis/bpmn-xslt-mappings.json`
- `analysis/bpmn-timers.json`
- `analysis/iflows-bpmn/*.iflw`

## Security Notes

- CPIView import is read-only.
- Credential values are not required for import.
- Generated manifests and inventories are designed to keep only evidence references and counts, not secret values.
- Existing upload-based Scenario Lab functionality remains available.

## Validation

Validated with targeted regression tests:

- `python -m compileall app dashboard tests`
- `pytest -q tests/test_v198_scenario_lab_generation_ui.py tests/test_v199_generation_governance.py tests/test_v200_live_snapshot.py tests/test_v201_cpiview_evidence.py`
- `pytest -q tests/test_monitor_time_range_hotfix.py`

