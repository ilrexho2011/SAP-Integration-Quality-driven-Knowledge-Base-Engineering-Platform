# AI4CPI Event Schema Standard

## 1. Purpose

This document defines the standard event structure used by the AI4CPI platform.

Events represent operational incidents detected in monitored systems.

## 2. Event Structure

Example event:

event_id: EVT-123456
timestamp: 2026-03-09T15:30:00Z
event_type: message_failure
customer_id: RCA
system_id: CPI-RCA
sap_sid: RO2
interface_id: IF_SALESORDER_INBOUND
priority: P1

## 3. Mandatory Fields

Each event must contain:

- event_id
- timestamp
- event_type
- customer_id
- system_id
- priority

## 4. Event Types

Examples:

- message_failure
- authentication_error
- timeout
- connection_failure
- queue_block
- processing_error

## 5. Priority Levels

Events must include priority classification.

Allowed values:

- P1
- P2
- P3
- P4

## 6. Optional Fields

Additional context may include:

- error_message
- message_id
- interface_name
- payload_reference
- retry_count
