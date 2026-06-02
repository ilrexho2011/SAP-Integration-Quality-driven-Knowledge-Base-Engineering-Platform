# Sprint 9 - Dashboard + Enterprise QA

Sprint 9 adds a Streamlit Enterprise QA dashboard and a read-only dashboard summary service on top of the existing QDKEP services.

## Scope

- Dashboard shows contract validation, package builder/metadata, customer/interface gate, AI4BIZ export readiness, evidence/traceability and benchmark readiness.
- Dashboard displays metrics, blocking issues, warnings and promotion decision.
- Dashboard exposes download buttons for package ZIP, manifest, package metadata, quality reports, traceability report and golden questions dataset when present.
- Business logic is not copied into the dashboard. The dashboard calls `DashboardSummaryService`, which only reads outputs produced by existing validators, builders, gates, exporters, traceability and benchmark services.

## Commands

```bash
./qdkep dashboard-summary /path/to/package-or-folder
./qdkep serve-dashboard
python scripts/run_dashboard.py
streamlit run dashboard/qdkep_dashboard.py
```

## API

```http
POST /api/dashboard/enterprise-review
```

Response uses the Sprint 8 unified workflow response contract: `status`, `output_path`, `issues`, `warnings`, `command`, `data`.
