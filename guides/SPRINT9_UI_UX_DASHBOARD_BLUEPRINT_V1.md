# Sprint 9 Extension: UI/UX Dashboard Blueprint v1

## Scope

This extension adds an Enterprise Quality Console on top of QDKEP v1.9 Dashboard + Enterprise QA.

The dashboard provides a service-backed Streamlit UI for:

- Overview KPI review
- Contract Validation
- Package Builder
- Quality Gates
- AI4BIZ Export
- Evidence & Traceability
- Generators
- Benchmark
- Reports & Downloads
- Settings

## Business Logic Boundary

The UI does not duplicate QDKEP validation, package build, quality gate, export, traceability, generator or benchmark logic. It uses:

- `DashboardSummaryService`
- `EnterpriseConsoleService`
- existing quality reports and package metadata

## Language Policy

The UI supports EN/DE labels. Technical constants are intentionally not translated, including:

- `interface_id`
- `promotion_decision`
- `metadata`
- `artifact_type`
- `document_type`
- `chunk_mode`
- `manifest.json`
- `package_metadata.json`
- `quality/traceability_report.json`
- `golden_questions.jsonl`

## Startup

```bash
qdkep serve-dashboard
```

or:

```bash
streamlit run dashboard/qdkep_enterprise_quality_console.py
```

## API

```text
POST /api/dashboard/enterprise-quality-console
```

The API returns the same unified operator response model as existing QDKEP endpoints.
