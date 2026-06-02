# QDKEP v1.9.4 Release Notes

## Monitoring & Generation

- Renamed `Monitoring Event Status` to `Monitoring & Generation`.
- Added generation source selector: `Live MPL` or `Archived MPL`.
- Added document version input with `v1`, `v2`, ... validation.
- Added horizontal generation buttons:
  - Generate interface_inventory
  - Generate KEDBs
  - Generate Runbooks
- Generated documents are Markdown files under `exports/generated_documents/<timestamp>_<source_mode>_<version>/`.
- Each generation run writes `generation_manifest.json` with source mode, source system, version, policy files, template files, AI provider status, and generated file list.

## Policy and template grounding

- Ingestion policy source: `resources/policies/AI4BIZ_Knowledge_Ingestion_Guide.txt`.
- Supporting policy files are loaded from `resources/policies`.
- Ready-made examples are loaded from `resources/templates`.
- CPI and PI/PO integration resources are included under `resources/cpi` and `resources/pipo`.

## Generation mode

- Default mode is deterministic template-based generation.
- AI provider configuration is read from `.env` and recorded as non-blocking AI assistance when configured.
- The generator does not fabricate MPL fields; missing values remain marked as `missing` or `n/a`.

## Manual action panels

- Added manual action buttons to dashboard pages for refresh, validation, package build, quality gates, traceability, generation, benchmark, export, downloads, and settings diagnostics.
