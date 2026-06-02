# AI4BIZ Agent Decision Model

## 1. Purpose

This document defines how the AI4BIZ agent evaluates operational events and decides what action to take.

The decision model ensures that the agent behaves consistently across all customers and environments.

The agent decision process is based on:

- monitoring events
- knowledge retrieval
- ITIL operational practices
- priority evaluation
- automated or assisted resolution

The goal is to support AMS operations and reduce manual effort in incident handling.

## 2. Event Detection Model

The AI agent reacts to operational events generated from monitoring systems.

An event represents a potential operational problem that requires analysis.

Events may originate from multiple sources.

Typical sources include:

- SAP PI/PO message monitoring
- SAP CPI message processing logs
- SAP S/4 IDoc monitoring
- SAP tRFC / qRFC monitoring
- interface error logs
- external monitoring systems

Examples of detected events:

- message failure
- interface processing error
- communication channel failure
- queue backlog
- authentication failure
- system connectivity loss
- mass processing errors

Each detected event must include at least the following information:

- customer_id
- system_id
- event_type
- event_timestamp
- error_message

## 3. Knowledge Retrieval

After detecting an operational event, the AI agent must search for relevant knowledge.

The search is performed using the AI4BIZ RAG system.

The retrieval process follows a strict order.

### Retrieval Order

1. Customer KEDB
2. Customer Runbooks
3. Customer Architecture Knowledge
4. Global Knowledge Base

Customer-specific knowledge always has higher priority than global knowledge.

### Search Input

The search query is constructed from the event information:

- error_message
- interface_name
- system_id
- event_type

### Vector Search

The query is converted into an embedding vector and executed against the vector database.

Vector database:

Qdrant

The search returns the most relevant knowledge entries.

Each result contains:

- artifact_type
- object_name
- priority
- text

## 4. Priority Evaluation

After retrieving relevant knowledge, the AI agent evaluates the operational priority of the incident.

The priority determines the urgency of the response.

Priority may come from different sources.

### Priority Sources

Priority may be defined in:

- customer interface inventory
- KEDB entries
- monitoring configuration
- customer architecture documentation

If no priority is defined, the platform default priority is used.

Default:

P3

### Priority Levels

P1 = Critical business impact
P2 = High priority
P3 = Normal priority
P4 = Low priority

### Customer SLA Model

Each customer has a dedicated SLA configuration that defines the maximum allowed response time for each priority level.

The SLA configuration is stored in the customer configuration.

Example SLA configuration:

P1 = 15 minutes response time
P2 = 1 hour response time
P3 = 4 hours response time
P4 = next business day

The AI agent must always evaluate incidents using the SLA configuration of the specific customer.

Example:

customer_id: RCMO
priority: P2

SLA response time: 1 hour

### SLA Awareness

When an incident is detected, the AI agent must:

1. determine the priority of the incident
2. load the SLA configuration of the customer
3. calculate the allowed response window
4. include SLA information in the created incident ticket

Example ticket metadata:

priority: P2
sla_response_time: 1h
detected_at: 2026-03-08T15:20:00
sla_deadline: 2026-03-08T16:20:00

## 6. Incident Creation

When an operational event requires human intervention, the AI agent must create an incident ticket.

The ticket creation process follows ITIL incident management principles.

The incident must contain structured information collected during the analysis phase.

### Ticket Targets

Incidents may be created in external ITSM systems.

Examples:

- Jira
- ServiceNow
- SAP Solution Manager
- internal ticketing systems

For the AI4BIZ demo environment the default target system is:

Jira Cloud

### Ticket Creation Conditions

A ticket must be created when one of the following conditions is met:

- no known error solution is available
- the incident priority requires human action
- automatic resolution is not possible
- SLA response time must be tracked

### Ticket Payload

Each incident ticket must contain the following fields:

customer_id
system_id
interface_name
event_type
priority
error_message
detected_at
sla_deadline
knowledge_reference

### Example Ticket Payload

customer_id: RCMO
system_id: RO2
interface_name: SalesOrder_Inbound
event_type: message_failure
priority: P2
error_message: OAuth authentication error
detected_at: 2026-03-08T15:20:00
sla_deadline: 2026-03-08T16:20:00
knowledge_reference: PI_OAUTH_CHANNEL_ERROR

## 7. Automated Resolution Model

The AI agent may attempt automated resolution actions when a known solution exists and the action is considered safe.

Automated resolution must always follow strict safety rules.

Automation is only allowed when:

- a known error entry contains a validated resolution procedure
- the action is classified as safe
- the customer configuration allows automated actions

### Resolution Sources

Resolution procedures may originate from:

- KEDB entries
- operational runbooks
- predefined automation scripts
- approved automation libraries

### Resolution Types

Examples of automated actions include:

- SAP PI communication channel restart
- CPI iFlow restart
- IDoc reprocessing
- queue unlock
- message retry
- service restart

### Automation Safety Levels

Automation actions must be classified by safety level.

Level 1 �--> Safe automation
Examples: message retry, queue unlock

Level 2 --> Controlled automation
Examples: channel restart, iFlow restart

Level 3 --> Manual approval required
Examples: system configuration changes

### Automation Logging

Every automated action must be logged.

The log must contain:

- customer_id
- system_id
- action_type
- action_timestamp
- action_result
- related_incident

## 8. Learning and Knowledge Update

The AI4BIZ platform must continuously improve its knowledge base.

Operational incidents generate valuable knowledge that should be captured and reused.

The AI agent must support the creation and improvement of knowledge entries.

### Knowledge Learning Sources

New knowledge may originate from:

- resolved incidents
- manual troubleshooting by engineers
- new integration implementations
- operational runbooks
- architecture documentation

### Knowledge Capture

When an incident is resolved, the system may propose the creation of a new knowledge entry.

The proposed knowledge entry should contain:

- problem description
- root cause
- resolution steps
- affected system
- related interface

### Knowledge Approval Process

New knowledge entries must follow an approval process before being indexed.

Approval roles:

- Engineering team -> prepares knowledge
- AI team -> structures knowledge
- Platform owner -> final approval

### Knowledge Indexing

Only approved knowledge entries may be indexed into the vector database.

Status lifecycle:

- draft
- review_pending
- approved
- indexed
