# Release Notes - QDKEP v1.9.8

## Scope

This release applies the approved Scenario Lab & Generation corrections requested for package v1.9.7.

## Implemented

1. **Send Feedback guidance corrected**
   - Replaced the old reference to `Monitoring & Generation` with `Scenario Lab & Generation -> New-knowledge generation`.
   - Clarified that remediation feedback is applied during `Update existing docs`.

2. **Source-system-aware Scenario Lab paths**
   - Added centralized config in `app/services/scenario_lab_config.py`.
   - `SAP CI` now uses:
     - `iFlow ZIP folder`: `./resources/cpi/input/odata/iflows`
     - `ICO folder`: `./resources/cpi/input/analysis/iflows-bpmn`
   - `SAP PIPO` now uses:
     - `ESR & ID folder`: `./resources/pipo/esr_id`
     - `ICO folder`: `./resources/pipo/ico`

3. **Generation mode radio buttons**
   - Replaced `regenerate/update existing documents` checkbox in `Scenario Lab & Generation` with:
     - `Generate`
     - `Update existing docs`
   - `Update existing docs` requires an existing generated documents folder and enables feedback/remediation controls.
   - `Generate` disables the update-only feedback/remediation path.

4. **Backend traceability**
   - Added `generation_mode` to the generate request and `generation_manifest.json`.
   - Kept the technical execution mode separately as `generation_engine_mode`.

## Validation

Executed successfully:

```powershell
python -m py_compile app/config.py app/main.py app/services/scenario_lab_config.py app/services/iflow_scenario_service.py app/services/generation_service.py dashboard/pages/scenario_lab_generation.py dashboard/pages/send_feedback.py
pytest
```

Result: `31 passed`.

## Security note

The packaged `.env` has been sanitized for secret-like values. Use `.env.example` or your local secret store to restore tenant credentials and API keys.
