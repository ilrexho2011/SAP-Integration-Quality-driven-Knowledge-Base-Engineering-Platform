# Release Notes v2.0.3 - Stable Native CPI Download/Analyze/Report

Version v2.0.3 stabilizes the Native Python CPI Evidence flow introduced in v2.0.2.

## Source-backed fixes

- Resolved relative `CPI_NATIVE_INPUT_DIR` / `CPI_NATIVE_OUTPUT_DIR` handling. Values such as `input` and `output` are now resolved relative to `CPI_NATIVE_ROOT`, not the shell working directory.
- Changed the default native root from `./resources/cpi/native` to `./resources/native` while keeping canonical imports under `./resources/cpi/input` and reports under `./resources/cpi/output`.
- Wrote native download progress incrementally to `native_download_progress.json` after core OData, ZIP/BPMN, and child/security phases. Partial evidence is preserved even if a later optional entity set fails.
- Generated Excel reports by default with `CPI_NATIVE_GENERATE_EXCEL=true`.
- Added CPIView-compatible Excel workbooks under `./resources/cpi/output` and mirrored them to the configured native output folder.
- Added parallel child evidence download with `CPI_NATIVE_PARALLEL_WORKERS` to reduce long waits on per-iFlow child collections.
- Preserved the CPIView local-folder integration from v2.0.1 and the manual `Upload iFlow ZIP exports` option.

## New / updated `.env` settings

```env
APP_VERSION=2.0.3-native-cpi-stable-download
CPI_NATIVE_ENABLED=true
CPI_NATIVE_TENANT_ID=03ef4612trial
CPI_NATIVE_ROOT=./resources/native
CPI_NATIVE_INPUT_DIR=
CPI_NATIVE_OUTPUT_DIR=
CPI_NATIVE_DOWNLOAD_CONTENT=true
CPI_NATIVE_MAX_RECORDS=100000
CPI_NATIVE_GENERATE_EXCEL=true
CPI_NATIVE_PARALLEL_WORKERS=8
CPI_NATIVE_DOWNLOAD_CHILDREN=true
```

## Expected output locations

- Native raw OData and ZIP/BPMN evidence: `./resources/native/input/<tenant>`
- Native report mirror: `./resources/native/output`
- Scenario Lab canonical CPI input: `./resources/cpi/input`
- CPI Excel reports for catalog/generation: `./resources/cpi/output`

## Security notes

- OAuth secrets remain in `.env`; they are not copied into manifests or output workbooks.
- Security descriptor rows are redacted where keys indicate password, secret, token, or value fields.

## Validation

- `python -m compileall app dashboard tests`
- `pytest -q`
- Result: `43 passed`
