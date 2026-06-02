# QDKEP v1.9.8 - Scenario Lab & Generation UI fixes

## Source-backed changes

The following changes implement the approved requirements from the supplied screenshots and Albanian request notes.

### 1. Send Feedback copy

The guidance at the bottom of **Send Feedback** now references **Scenario Lab & Generation -> New-knowledge generation** instead of **Monitoring & Generation**.

### 2. Source-system-aware Scenario Lab paths

`app/services/scenario_lab_config.py` centralizes source-system path configuration.

| Source system | Primary label | Primary path | Secondary label | Secondary path |
|---|---|---|---|---|
| SAP CI | iFlow ZIP folder | `./resources/cpi/input/odata/iflows` | ICO folder | `./resources/cpi/input/analysis/iflows-bpmn` |
| SAP PIPO | ESR & ID folder | `./resources/pipo/esr_id` | ICO folder | `./resources/pipo/ico` |

### 3. Generation mode radio buttons

The old `regenerate/update existing documents` checkbox has been replaced with a `Generation mode` radio group:

- `Generate` creates new documents.
- `Update existing docs` updates existing generated documents with remediation, enrichment, and optional feedback.

## Assumptions

- SAP/Python technical terms remain in English to preserve implementation identifiers.
- SAP PIPO evidence paths are prepared in the UI and service defaults; deep PI/PO ESR/ID and ICO parsing remains a separate analyzer extension.

## Quality gates

- `python -m py_compile` completed for changed modules.
- `pytest` completed successfully: `31 passed`.
