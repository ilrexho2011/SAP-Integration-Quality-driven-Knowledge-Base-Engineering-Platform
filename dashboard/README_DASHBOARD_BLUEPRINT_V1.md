# QDKEP UI/UX Dashboard Blueprint v1

This blueprint extends Sprint 9 with an Enterprise Quality Console for developer, AMS and enterprise review workflows.

## Goals

- Provide sidebar navigation for the complete QDKEP workflow.
- Provide EN/DE UI language switch.
- Show KPI overview, `promotion_decision`, status badges, warnings, blocking issues and downloads.
- Reuse existing QDKEP services and generated reports.
- Avoid duplicating business logic in Streamlit UI code.
- Preserve technical constants without translation, including `interface_id`, metadata fields, file names and sacred headings.

## Pages

- Overview
- Contract Validation
- Package Builder
- Quality Gates
- AI4CPI Export
- Evidence & Traceability
- Generators
- Benchmark
- Reports & Downloads
- Settings

## Start

```bash
qdkep serve-dashboard
```

or

```bash
streamlit run dashboard/qdkep_enterprise_quality_console.py
```

## Service boundary

The dashboard reads `DashboardSummaryService` through `EnterpriseConsoleService`. It does not implement validation, package build, quality gate, AI4CPI export, evidence mapping, generator or benchmark rules in UI code.
