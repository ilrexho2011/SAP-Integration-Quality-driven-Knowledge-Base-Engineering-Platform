# AI4CPI Interface Inventory Schema

## 1. Purpose

This document defines the standard interface inventory schema used by the AI4CPI platform.

The schema ensures that all integration interfaces are documented in a consistent and structured way.

This information is required for:

- monitoring correlation
- incident analysis
- priority evaluation
- SLA-aware decision making
- knowledge retrieval
- agent reasoning

Each productive interface should be described before operational knowledge is indexed.

## 2. Core Interface Fields

Each interface entry must define a minimal set of core fields.

These fields allow the AI4CPI platform to identify the interface, determine its technical context and correlate incidents correctly.

Mandatory fields:

- customer_id
- system_id
- interface_id
- interface_name
- source_system
- target_system
- technology
- interface_type
- priority
- status

### Field Description

customer_id

Unique identifier of the customer.

Example: RCA

system_id

Internal system identifier of the owning integration system.

Examples:

PIPO-RCA  
CPI-RCA  

interface_id

Unique technical identifier of the interface.

Example:

IF_SALESORDER_INBOUND

interface_name

Human-readable name of the interface.

Example:

SalesOrder_Inbound

source_system

System where the message originates.

Example:

S4-RCA

target_system

System receiving the message.

Example:

CPI-RCA

technology

Integration technology used by the interface.

Allowed examples:

- SAP PI
- SAP CPI
- IDoc
- REST
- SOAP
- RFC

interface_type

Defines the direction or pattern of the interface.

Allowed examples:

- inbound
- outbound
- synchronous
- asynchronous

priority

Operational priority of the interface.

Allowed values:

- P1
- P2
- P3
- P4

status

Operational state of the interface definition.

Allowed values:

- active
- inactive
- deprecated

## 3. Extended Interface Metadata

In addition to the mandatory fields, interfaces should include extended metadata where available.

These fields improve retrieval quality, operational context and AI-based analysis.

Recommended fields:

- sap_sid
- business_domain
- owner
- support_team
- landscape_role
- monitoring_endpoint
- artifact_reference
- review_status
- version

### Field-Description

sap_sid

Real SAP System ID associated with the interface.

Example:

RO2

business_domain

Business area served by the interface.

Examples:

- sales
- finance
- logistics
- hr

owner

Business or technical owner of the interface.

Example:

Integration Team

support_team

Operational team responsible for incident handling.

Example:

AMS Integration Support

landscape_role

Role of the interface in the system landscape.

Examples:

- development
- quality
- production
- sandbox

monitoring_endpoint

Reference to the monitoring endpoint used for this interface.

Examples:

- PI channel monitoring
- CPI MPL API
- S4 IDoc monitoring

artifact_reference

Reference to related documentation or knowledge objects.

Examples:

- runbook ID
- KEDB entry
- architecture document

review_status

Lifecycle status of the interface entry.

Allowed values:

- draft
- review_pending
- approved
- indexed

version

Version identifier of the interface definition.

Example:

v1.0

## 4. Interface Priority and Criticality Rules

Interfaces may have different operational priorities depending on their business impact.

The AI4CPI platform uses interface priority to determine incident severity and response urgency.

Allowed priority levels:

- P1
- P2
- P3
- P4

Priority meaning example:

P1

Business critical interfaces.  
Failure immediately impacts business operations.

Examples:

- Order processing
- Financial postings

P2

Important interfaces with operational impact.

Examples:

- Master data synchronization

P3

Standard operational interfaces.

P4

Low priority interfaces with limited business impact.

Criticality classification may also be used.

Allowed values:

- high
- medium
- low

## 5. Interface Monitoring Mapping

Each interface should be linked to its monitoring source.

Monitoring sources may include:

- SAP PI message monitoring
- SAP CPI Message Processing Log
- SAP IDoc monitoring
- SAP queue monitoring
- external monitoring systems

Example monitoring fields:

monitoring_source

Example:

SAP CPI MPL

monitoring_object

Example:

iFlow name

monitoring_event_type

Examples:

- message_failure
- authentication_error
- timeout
- connection_failure

## 6. Interface Definition Example

Example interface entry:

customer_id: RCA
system_id: CPI-RCA
interface_id: IF_SALESORDER_INBOUND
interface_name: SalesOrder_Inbound

source_system: S4-RCA
target_system: CPI-RCA

technology: SAP CPI
interface_type: inbound
priority: P1
status: active

business_domain: sales
owner: Integration Team
support_team: AMS Integration Support

review_status: approved
version: v1.0

## 7. Interface Governance Rules

All interface definitions must follow governance rules. 

Rule 1 — Unique Interface Identifier

Each interface must have a unique interface_id within a customer landscape. 

Rule 2 — Stable Interface Names

Interface identifiers should not change after operational deployment. 

Rule 3 — Technology Classification

Interfaces must use one of the predefined technology categories. 

Rule 4 — Priority Definition

Each productive interface must define a priority. 

Rule 5 — Review Process

New or modified interface entries must follow the review lifecycle. 

Lifecycle states:

draft  
review_pending  
approved  
indexed

Rule 6 — Version Tracking

Interface definitions should be versioned and managed through Git. 

Rule 7 — Architecture Alignment

Interface definitions must align with the customer architecture schema. 
