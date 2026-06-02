# IR01_IF06_Test_SMS_Message test execution plan

scenario_lab_run_id: `20260601_000335`
package_name: `01 - Configurations in Cloud Integration`
source_zip: `resources\cpi\input\analysis\iflow_rich_inventory.json`
bpmn_file: `resources/cpi/input/analysis/iflows-bpmn/FIRST --- IR01_IF06_Test_SMS_Message.iflw`

## Scope
Functional negative testing in DEV/TEST only. The platform does not mutate live iFlows.

## Preconditions
- iFlow is deployed in DEV/TEST tenant.
- Operator has SAP CI monitoring access and permission to read MPL evidence.
- Externalized parameters and credentials are configured in DEV/TEST.

## Test cases
### TC_NEG_001_missing_required_id.xml
- input file: `payload_examples/IR01_IF06_Test_SMS_Message/TC_NEG_001_missing_required_id.xml`
- expected error: Missing required business identifier
- expected MPL status: FAILED or controlled validation error
- expected error signature: `missing|required|identifier|validation`
- validation step: compare MessageGuid, status, timestamp, and error text in MPL.
- rollback / cleanup: delete DEV/TEST test payloads and do not transport test changes.
- escalation: IntegrationTeam when runtime error differs from expected safe validation behavior.

### TC_NEG_002_invalid_date_format.xml
- input file: `payload_examples/IR01_IF06_Test_SMS_Message/TC_NEG_002_invalid_date_format.xml`
- expected error: Invalid date format
- expected MPL status: FAILED or controlled mapping/validation error
- expected error signature: `date|format|mapping|validation`
- validation step: compare MessageGuid, status, timestamp, and error text in MPL.
- rollback / cleanup: delete DEV/TEST test payloads and do not transport test changes.
- escalation: IntegrationTeam when runtime error differs from expected safe validation behavior.

### TC_NEG_003_malformed_xml.xml
- input file: `payload_examples/IR01_IF06_Test_SMS_Message/TC_NEG_003_malformed_xml.xml`
- expected error: Malformed XML
- expected MPL status: FAILED with parser/XML error
- expected error signature: `xml|parser|well-formed|SAX`
- validation step: compare MessageGuid, status, timestamp, and error text in MPL.
- rollback / cleanup: delete DEV/TEST test payloads and do not transport test changes.
- escalation: IntegrationTeam when runtime error differs from expected safe validation behavior.

### TC_NEG_004_empty_payload.xml
- input file: `payload_examples/IR01_IF06_Test_SMS_Message/TC_NEG_004_empty_payload.xml`
- expected error: Empty payload
- expected MPL status: FAILED or controlled validation error
- expected error signature: `empty|payload|body|required`
- validation step: compare MessageGuid, status, timestamp, and error text in MPL.
- rollback / cleanup: delete DEV/TEST test payloads and do not transport test changes.
- escalation: IntegrationTeam when runtime error differs from expected safe validation behavior.

## Risk points
- Adapter evidence found: HTTP; validate connectivity, credentials, and endpoint reachability in DEV/TEST.
- Groovy scripts require branch/error-path coverage and runtime log validation.
- Runtime status is not confirmed as STARTED; deployment status must be verified before MPL-based testing.
