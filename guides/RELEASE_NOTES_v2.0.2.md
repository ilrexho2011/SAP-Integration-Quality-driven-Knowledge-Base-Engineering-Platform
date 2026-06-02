# Release Notes v2.0.2 - Native Python CPI Evidence

## Goal

Version v2.0.2 adds a Java-free SAP Cloud Integration evidence pipeline inside QDKEP. The new pipeline can download SAP CPI design/runtime evidence through the existing SAP_CPI_* OAuth configuration, write CPIView-compatible local evidence, parse downloaded iFlow `.iflw` BPMN files, and enrich Scenario Lab without requiring CPIView.jar.

## Source-backed changes

- Added `app/services/cpi_native_evidence_service.py`.
- Extended `app/services/sap_cpi_client.py` with native CPI evidence helpers:
  - `get_integration_runtime_artifacts()`
  - artifact child collection helpers for `Configurations`, `Resources`, `MessageMappings`, and `ScriptCollections`
  - `$value` ZIP download helper for design-time artifacts
  - generic binary and collection readers
- Added FastAPI endpoint:
  - `POST /api/scenario-lab/download-native-cpi`
- Added Streamlit UI section:
  - `Native Python CPI Evidence`
- Extended `Scenario Lab defaults` with `native_cpi` status.
- Extended Monitoring Events source metadata with native CPI status and availability.
- Added `.env.example` settings:
  - `CPI_NATIVE_ENABLED`
  - `CPI_NATIVE_TENANT_ID`
  - `CPI_NATIVE_ROOT`
  - `CPI_NATIVE_INPUT_DIR`
  - `CPI_NATIVE_OUTPUT_DIR`
  - `CPI_NATIVE_DOWNLOAD_CONTENT`
  - `CPI_NATIVE_MAX_RECORDS`
  - `CPI_NATIVE_GENERATE_EXCEL`
- Added regression test:
  - `tests/test_v202_native_cpi_evidence.py`

## Behavior

When `CPI_NATIVE_ENABLED=true` and SAP CPI OAuth settings are configured, the platform can:

1. download `IntegrationPackages`;
2. download `IntegrationDesigntimeArtifacts`;
3. download `IntegrationRuntimeArtifacts`;
4. download per-iFlow `Configurations`, `Resources`, `MessageMappings`, and `ScriptCollections` where the tenant exposes them;
5. download iFlow `$value` ZIP content when `CPI_NATIVE_DOWNLOAD_CONTENT=true`;
6. extract `.iflw` files from the downloaded ZIP packages;
7. parse BPMN XML into CPIView-compatible analysis JSON files;
8. generate `iflow_rich_inventory.json`;
9. optionally generate compact Excel evidence views when `CPI_NATIVE_GENERATE_EXCEL=true`;
10. import the evidence into `resources/cpi/input` for Scenario Lab.

## Compatibility

- Existing CPIView local-folder integration from v2.0.1 remains supported.
- Existing `Upload iFlow ZIP exports` remains supported.
- Existing Monitoring Events, Scenario Lab, and PI/PO features remain backward-compatible.

## Security

- OAuth secrets remain in `.env`; they are not written into generated evidence.
- Security descriptor records are redacted when keys indicate password/secret/token/value fields.
- Tenant evidence generated during testing is not bundled with the release package. Users should generate evidence locally via `.env` configuration.

## Missing Inputs / Assumptions

- SAP CPI tenant OData capabilities vary. Optional entity sets such as security descriptors, artifact child collections, and `$value` download may not be exposed for every tenant or role.
- BPMN parsing is intentionally best-effort and namespace-tolerant. It extracts channels, channel properties, activities, content modifiers, Groovy/script hints, message mappings, XSLT mapping hints, timers, and participants from `.iflw` XML when present.
- Native Excel generation is available as a compact evidence workbook when `CPI_NATIVE_GENERATE_EXCEL=true`; JSON analysis remains the primary supported Scenario Lab input in v2.0.2.

## Quality Gates

Validated with:

```bash
python -m compileall app dashboard tests
pytest -q
```

Result: `43 passed`.
