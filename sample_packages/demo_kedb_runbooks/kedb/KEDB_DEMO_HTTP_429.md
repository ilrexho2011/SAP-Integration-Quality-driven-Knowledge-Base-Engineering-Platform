# HTTP 429 receiver throttled requests due to API rate limit

customer_id: "RCA"
system_id: "CPI-RCA"
sap_sid: "CPI"
artifact_type: "kedb"
object_name: "HTTP_API_RATE_LIMIT"
priority: "P2"
version: "v1"
error_pattern: "HTTP | API | RATE_LIMIT | THROTTLING"
integration_flow_id: "IR_DEMO_HTTP_429"
integration_flow_name: "Demo HTTP API Rate Limit"

## Symptoms

The SAP CPI iFlow fails intermittently with HTTP 429 Too Many Requests. The receiver throttles requests due to API rate limit. MPL MessageGuid examples and HTTP status codes should be captured for runtime evidence.

## Root Cause

The receiver API enforces a rate limit and rejects excessive requests. Retry behavior or request pacing is not aligned with the receiver quota.

## Evidence

MessageGuid: DEMO-GUID-429-001
HTTP 429 Too Many Requests
Adapter: HTTP Receiver
Sender: SAP CPI
Receiver: External REST API

## Resolution

Apply controlled retry with exponential backoff. Reduce parallel processing if configured. Coordinate quota and rate-limit settings with the receiver owner.

## Validation

Reprocess failed message after rate-limit window. Confirm successful MPL status and absence of new HTTP 429 errors.

## References

SAP CPI MPL, receiver API rate-limit documentation, internal runbook.
