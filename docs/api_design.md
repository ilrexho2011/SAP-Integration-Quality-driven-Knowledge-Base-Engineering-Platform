# AI4CPI API Design

The platform exposes several APIs:

## Monitoring APIs

### PI Monitoring API

Reads SAP PI/PO monitoring data and detects failures.

### CPI Monitoring API

Reads SAP CPI Message Processing Logs (MPL).

### S4 Monitoring API

Reads:

- IDoc errors
- SM58
- Queues

## Incident API

Creates ITSM incidents.

Example targets:

- Jira
- ServiceNow
- SAP ITSM

## Agent API

Central AI decision engine.

Responsibilities:

- error classification
- knowledge retrieval
- priority evaluation
- fix recommendation
