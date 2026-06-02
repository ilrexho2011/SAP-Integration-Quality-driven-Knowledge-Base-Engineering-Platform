# Release Notes v1.9.6

## Quality-Driven Knowledge Engineering Platform

### Monitoring time-range controls

- Added a monitor time-range selector next to the existing **Refresh monitor data** button.
- Supported ranges:
  - Past Hour
  - Past 24 Hours (default)
  - Past Week
  - Past Month
  - Custom
- Custom range displays additional controls for:
  - Display Messages: Last Updated or Log Start
  - From timestamp
  - To timestamp
- The selected range is applied only when **Refresh monitor data** is pressed.
- The same time-range parameters are propagated to the Completed/Failed MPL message tabs.
- Backend monitor endpoints now accept `time_range`, `date_from`, `date_to`, and `display_field` query parameters.
- SAP CPI and SAP PI/PO live clients can receive runtime date ranges while preserving the previous 24-hour default behavior.
- Local MPL fallback records are filtered by the selected time range when parseable timestamps are available.

### Corrective feedback workflow

- Added **Send feedback** to the main navigation directly below **Benchmark**.
- Added a new dashboard page: `dashboard/pages/send_feedback.py`.
- Added backend feedback endpoints:
  - `GET /api/feedback/list`
  - `GET /api/feedback/read`
  - `POST /api/feedback/create`
- Added `FeedbackService` for creating, listing, and reading corrective feedback artifacts.
- Feedback JSON files are stored in `feedback/` with the format `run_YYYYMMDD_HHMMSS_feedback.json`.
- Existing feedback schema and `FeedbackGenerator` remain the governance model: feedback does not modify governed documents directly.

### Regeneration with approved feedback

- Monitoring & Generation now includes:
  - Feedback source: None, Latest feedback, Select feedback file
  - Apply remediation hints during regeneration
- Generation API payloads now support:
  - `feedback_source`
  - `feedback_path`
  - `apply_remediation_hints`
- `GenerationService` records the selected feedback file and governance controls in `generation_manifest.json`.
- Default remains no feedback application unless the user explicitly selects feedback and enables remediation hints.

### Quality gates

- Existing test suite passed: 15/15 tests.
- FastAPI smoke checks passed for health, monitor summary, feedback list, and feedback creation endpoints.
