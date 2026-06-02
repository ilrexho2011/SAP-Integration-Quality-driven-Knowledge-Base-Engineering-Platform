# Release Notes - v2.0.0 live scenario snapshot

## Source-backed changes

- Updated platform version to `2.0.0-live-scenario-snapshot`.
- Monitoring Events now shows `Packages`, `iFlows`, `Deployed`, `Success Mes.`, `Failed Mes.`, and `Total Mes.`.
- Scenario Lab default display paths are relative:
  - SAP CI `iFlow ZIP folder`: `./resources/cpi/input/odata/iflows`
  - SAP CI `ICO folder`: `./resources/cpi/input/analysis/iflows-bpmn`
  - SAP PI/PO `ESR & ID folder`: `./resources/pipo/esr_id`
  - SAP PI/PO `ICO folder`: `./resources/pipo/ico`
- Added read-only `SAPLiveSnapshotService` to persist SAP CPI and SAP PI/PO live evidence after successful monitor connections.
- Added `.env` aliases for tested `CPI_DEMO_*`, `PIPO_DEMO_*`, and `PIPO_MPL_*` patterns without removing existing `SAP_CPI_*` / `SAP_PIPO_*` names.
- Scenario Lab can now use CPI live metadata snapshots and PI/PO `interface_seeds.json` evidence when uploaded ZIP exports are not present.

## Assumptions and safety controls

- Live snapshot execution is best-effort and does not block Monitoring Events if snapshot persistence fails.
- Snapshot files do not persist username, password, OAuth client secret, or token values.
- `Upload iFlow ZIP exports` remains available and unchanged.
- CPI `Deployed` is derived from common status fields such as `IsDeployed`, `DeployState`, `DeploymentStatus`, `RuntimeStatus`, or `Status`; if no recognizable field exists, the KPI shows `N/A`.

## Validation performed

- `python -m compileall app dashboard tests`
- `pytest -q tests/test_monitor_time_range_hotfix.py`
- `pytest -q tests/test_v196_monitor_feedback.py`
- `pytest -q tests/test_v198_scenario_lab_generation_ui.py`
- `pytest -q tests/test_v199_generation_governance.py`
- `pytest -q tests/test_v200_live_snapshot.py`

## Open points

- Full CPI iFlow ZIP content download remains controlled by `SAP_CPI_DESIGN_DOWNLOAD_CONTENT` / `CPI_DEMO_DESIGN_DOWNLOAD_CONTENT`; the current implementation safely persists metadata snapshots by default.
- PI/PO Directory SOAP object extraction remains landscape-dependent; v2.0.0 persists configured DIR service evidence and any JSON/proxy endpoint results that are available.
