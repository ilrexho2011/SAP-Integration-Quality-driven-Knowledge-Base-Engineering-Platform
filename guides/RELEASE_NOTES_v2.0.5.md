# Release Notes v2.0.5 - Dashboard Export Review UX

Version v2.0.5 improves the QDKEP dashboard review flow based on the v2.0.4 platform backup and presentation review.

## Changes

- Reordered the sidebar navigation to match the factual Knowledge Base build sequence: Monitoring Events, Scenario Lab & Generation, Contract Validation, Package Builder, Quality Gates, AI4BIZ Export, Evidence & Traceability, Generators, Benchmark, Reports & Downloads and Settings.
- Replaced the free-text package path default with an export-first package source selector. The dashboard now defaults to `./exports/qdkep_package_with_benchmark.zip` when present and lists available ZIP/folder package candidates from `./exports`.
- Added a custom path fallback for external ZIP or extracted folder review packages.
- Removed non-actionable overview badges for `retrieval_readiness` and `answer_readiness`; those checks require target AI4BIZ/RAG index and answer traces.
- Suppressed the dashboard warnings that said retrieval or answer readiness was not scored because traces were missing. The raw benchmark report remains available for review.
- Normalized Windows-style ZIP member paths during dashboard review so historical packages containing `quality\traceability_report.json` are read correctly on Linux/Unix.
- Added a generation safety guard so shortened KEDB/Runbook filenames cannot overwrite earlier artifacts in the same run; governed IDs remain sequential and unique.
- Updated manual package output naming/versioning from the legacy v1.9.6 value to v2.0.5.

## Validation

- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests -q`
- Result: 51 passed, 2 non-blocking openpyxl style warnings.

