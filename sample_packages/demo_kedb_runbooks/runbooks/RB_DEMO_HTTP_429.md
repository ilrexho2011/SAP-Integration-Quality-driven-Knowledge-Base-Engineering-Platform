# Resolve HTTP 429 receiver throttling in SAP CPI

customer_id: "RCMO"
system_id: "CPI-RCMO"
sap_sid: "CPI"
artifact_type: "runbook"
object_name: "HTTP_API_RATE_LIMIT"
priority: "P2"
version: "v1"
error_pattern: "HTTP | API | RATE_LIMIT | THROTTLING"
integration_flow_id: "IR_DEMO_HTTP_429"
integration_flow_name: "Demo HTTP API Rate Limit"

## Trigger

Use this runbook when SAP CPI MPL shows HTTP 429 Too Many Requests, receiver throttled requests, API rate limit, or repeated retry failures for the HTTP receiver adapter.

## Diagnosis

1. Open MPL and identify the failed MessageGuid.
2. Check the HTTP receiver adapter response code.
3. Confirm whether the receiver returned HTTP 429 or a rate-limit message.
4. Review parallel processing and retry configuration.
5. Check if the receiver quota was recently changed.

## Resolution Steps

1. Pause high-volume reprocessing until the receiver rate-limit window resets.
2. Enable or tune retry with exponential backoff.
3. Reduce parallel requests or batch size.
4. Add throttling or pacing before the HTTP receiver call.
5. Coordinate quota increase with the receiver API owner if business volume is expected.

## Validation

Reprocess one failed MessageGuid and verify MPL status Completed. Monitor the next 30 minutes for new HTTP 429 errors.

## Rollback

Restore the previous retry and parallel processing settings if the receiver accepts the original pattern again.

## Evidence

MessageGuid: DEMO-GUID-429-001
HTTP 429 Too Many Requests
Adapter: HTTP Receiver
Integration Flow: IR_DEMO_HTTP_429
