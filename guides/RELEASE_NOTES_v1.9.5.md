# Release Notes - v1.9.5

## Scope

This release improves the Monitoring & Generation workflow and operator interactivity.

## Changes

- Made Completed and Failed monitoring totals actionable from the Monitoring & Generation page.
- Added `/api/monitor/messages` to list MPL messages filtered by status and system.
- Message lists include date, time, package name, iFlow name, sender, sender adapter, receiver, receiver adapter, status, MessageGuid, and source file.
- Added regenerate/update mode for existing generated document folders.
- Added existing generated documents path input with example path support.
- Generation keeps the selected MPL source as preferred metadata, but enriches output with both Live MPL and Archived MPL evidence whenever available.
- Generation manifests now include runtime evidence modes, preferred source mode, existing documents path, and existing documents count.
- Kept template-based generation with AI-assisted formulation enabled when `.env` is configured.
- Confirmed resource links point to `resources/` for policies, templates, CPI, PIPO, and MPL evidence.
- Applied RealCore-green styling to Streamlit buttons across the enterprise dashboard.
- Updated backend version to `1.9.5-monitoring-generation-update`.

## Validation

- Python compile check completed for `app`, `dashboard`, and `scripts`.
- Smoke-tested monitor summary, failed-message listing, and KEDB generation with regenerate/update path.
