# QDKEP v1.9.9 - Scenario Lab & Generation Governance Update

## Source-backed changes

- Updated application version to `1.9.9-scenario-lab-generation`.
- Added Archived MPL source selection for `sap_ci` and `sap_pipo`, including `all_sources` plus three source-specific options per system.
- Added `DocumentIdService` for governed `DOC ID`, `KEDB ID`, and `RUNBOOK ID` discovery against `sample_packages`.
- Corrected `sample_packages/sap_pipo/pipo_inteeface_catalog_docs` to `sample_packages/sap_pipo/pipo_interface_catalog_docs` while preserving folder content.
- Added `prevent duplicate ID (interface_inventory)` behavior: when a duplicate `DOC ID` is found, generation updates the existing document path instead of creating a duplicate.
- Added `restart ID counting` controls for KEDB and Runbook generation; when inactive, IDs continue after existing sample package IDs.
- Kept interface catalog priority fixed at `P3`; KEDB and Runbook priorities are classified from MPL error text/signature.
- Enforced short generated Markdown filenames with a 60-character limit and stable hash suffixes.
- Added runbook chunking traceability: `bm25_typed`, `size=400`, `overlap=80`.
- Improved SAP PIPO Scenario Lab generation using real `resources/pipo/*` structures, especially normalized DIR seeds and MPL incidents.

## API/UI additions

`GenerateDocumentsRequest` now supports:

```text
archived_mpl_source
prevent_duplicate_doc_id
restart_kedb_id_counting
restart_runbook_id_counting
```

The Streamlit `Scenario Lab & Generation` page now shows:

- `Select MPL Source` when `Archived MPL` is selected.
- `prevent duplicate ID (interface_inventory)` next to interface inventory generation.
- `restart ID counting` next to KEDB and Runbook generation.

## Quality checks executed

Passed targeted regression tests:

```text
pytest -q tests/test_v197_scenario_lab_generation.py tests/test_v198_scenario_lab_generation_ui.py tests/test_v199_generation_governance.py
# 15 passed
```

A full `pytest -q` run was attempted, but exceeded the execution timeout in this environment before completion. No failure output was produced before timeout.

## Assumptions

- CPI Archived MPL sources are represented by `resources/mpl`, `resources/cpi`, and `logs/mpl`.
- PIPO Archived MPL sources are represented by `resources/pipo/mpl`, `resources/pipo/pipo_rag_pipeline_20260405T134227Z/mpl_normalized_20260405T134235Z`, and `logs/pipo_*`.
- AI priority classification is deterministic/local in this package and uses MPL error text/signature heuristics unless an external AI provider is later wired in.

## Risks and open points

- Live SAP tenant calls were not executed; validation used local resources and archived MPL evidence from the uploaded package.
- Full regression test suite needs a longer local CI window because the complete `pytest -q` exceeded this environment timeout.
