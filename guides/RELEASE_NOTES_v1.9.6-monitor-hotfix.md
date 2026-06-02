# Release Notes - v1.9.6 Monitor Hotfix

## Scope

This hotfix keeps the application version at v1.9.6 and corrects the SAP CPI monitoring time-range behavior.

## Fixes

- SAP CPI Message Processing Log requests now use the technical `LogStart` OData timestamp field for server-side filtering.
- The dashboard `Display Messages` option remains a UI/local-filter preference and no longer changes the CPI OData filter field to `LastUpdated`.
- Live SAP CPI and SAP PI/PO MPL records are filtered again in `MonitorService` before KPI counters are calculated, so `MPL Success`, `MPL Errors`, and `MPL Total` reflect the selected range.
- The `Refresh monitor data` button persists the selected monitor query parameters and clears Streamlit cached monitor data.
- Added regression tests for time-window filtering and CPI OData filter generation.

## Validation

Targeted validation executed successfully:

```text
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest tests/test_monitor_time_range_hotfix.py tests/test_v196_monitor_feedback.py -q
7 passed in 14.12s
```
