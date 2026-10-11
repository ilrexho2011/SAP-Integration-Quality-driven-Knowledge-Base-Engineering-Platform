# AI4CPI Customer Architecture Schema

## 1. Purpose

This document defines the standard customer architecture schema used by the AI4CPI platform. 

The schema ensures that each customer landscape is described in a consistent and structured way.

This information is required for:

- monitoring integration
- incident analysis
- SLA evaluation
- knowledge retrieval
- agent decision making

Each customer architecture must be defined before productive knowledge ingestion starts.

## 2. Core Customer Fields

Each customer architecture must define a minimal set of core fields. 

These fields ensure that the AI4CPI platform can identify the customer, its systems and the operational context.

Mandatory fields:

- customer_id
- display_name
- environment
- status
- systems
- interfaces
- priority_scheme
- sla
- monitoring_model

### Field Description

customer_id

Unique identifier of the customer.

Example:

RCA

display_name

Human-readable customer name.

Example:

RealCore Albania

environment

Defines the operational environment.

Allowed values:

- demo
- test
- prod

status

Defines whether the customer configuration is active.

Allowed values:

- active
- inactive

systems

List of systems belonging to the customer landscape.

Examples:

- PI/PO
- CPI
- S4

interfaces

Interface inventory reference or embedded interface structure.

priority_scheme

Defines the priority model used by the customer.

Examples:

- P1_P4
- custom

sla

Defines customer-specific response times by priority.

monitoring_model

Defines how monitoring events are collected.

Examples:

- polling
- push
- hybrid

## 3. System Definition Model

Each customer system must be defined using a structured system model. 

This allows the AI4CPI platform to identify systems, correlate monitoring events and retrieve the correct knowledge.

Each system entry must contain the following fields.

Mandatory fields:

- system_id
- sap_sid
- system_type
- landscape_role
- integration_stack
- monitoring_endpoints

### Field-Description

system_id

Unique internal identifier of the system within the customer landscape.

Example:

PIPO-RCA  
CPI-RCA  
S4-RCA

sap_sid

SAP System ID.

This must match the real SAP system identifier.

Example:

RO2

system_type

Defines the system category.

Allowed values:

- SAP_PI
- SAP_PO
- SAP_CPI
- SAP_S4
- NON_SAP

landscape_role

Defines the role of the system in the landscape.

Examples:

- development
- quality
- production
- sandbox

integration_stack

Defines the integration technology used by the system.

Examples:

- PI/PO
- CPI
- IDoc
- SOAP
- REST
- Event Mesh

monitoring_endpoints

Defines the technical endpoints used by the monitoring system.

Examples:

PI:

- channel_monitor_api
- message_monitor_api

CPI:

- message_processing_log_api

S4:

- idoc_monitor_api
- sm58_api
- queue_api

## 4. Interface Landscape Model

Each customer architecture should include a structured description of its integration interfaces. 

This allows the AI4CPI platform to correlate incidents with specific integrations.

Interfaces may represent:

- PI/PO interfaces
- CPI iFlows
- IDoc integrations
- REST APIs
- SOAP services

Each interface entry may contain the following fields.

Recommended fields:

- interface_id
- interface_name
- source_system
- target_system
- technology
- interface_type
- business_domain
- owner
- criticality

### Field_Description

interface_id

Unique identifier of the interface.

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

Integration technology used.

Examples:

- SAP PI
- SAP CPI
- IDoc
- REST
- SOAP

interface_type

Defines the interface pattern.

Examples:

- inbound
- outbound
- synchronous
- asynchronous

business_domain

Business area of the integration.

Examples:

- sales
- finance
- logistics
- hr

owner

Responsible team or system owner.

Example:

Integration Team

criticality

Defines the business criticality of the interface.

Examples:

- high
- medium
- low

## 5. Monitoring Integration Model

The AI4CPI platform relies on operational monitoring events to detect and analyze incidents. 

Each customer architecture must define how monitoring data is collected.

Monitoring may originate from:

- SAP PI/PO monitoring APIs
- SAP CPI message processing logs
- SAP S/4HANA IDoc monitoring
- SAP queue monitoring
- external monitoring systems

### Monitoring Collection Models

monitoring_model

Defines how monitoring events are collected.

Allowed values:

- polling
- push
- hybrid

polling

The AI4CPI platform periodically polls monitoring endpoints.

Example:

- PI channel monitoring API
- CPI message log API
- S/4 IDoc API

push

External monitoring systems send events directly to the AI4BIZ platform.

hybrid

Combination of polling and push mechanisms.

### Monitoring Event Types

Monitoring events may include:

- message failures
- authentication errors
- connection failures
- queue backlogs
- interface downtime
- timeout errors

Each event should include the following metadata:

- customer_id
- system_id
- interface_name
- event_type
- timestamp
- priority
- raw_message

These events are processed by the AI agent to trigger analysis and resolution workflows.

## 6. Customer Architecture Example

The following example illustrates how a customer architecture may be defined. 

This example represents a simplified architecture of the RCA demo environment. 

Example:

customer_id: RCA
display_name: RealCore Albania
environment: demo
status: active

priority_scheme:
  scheme: P1_P4

sla:
  P1: 15m
  P2: 1h
  P3: 4h
  P4: 1d

monitoring_model: polling

systems:

  system_id: PIPO-RCA
    sap_sid: RO2
    system_type: SAP_PI
    landscape_role: production
    integration_stack: PI/PO

  system_id: CPI-RCA
    sap_sid: CPI
    system_type: SAP_CPI
    landscape_role: production
    integration_stack: CPI

  system_id: S4-RCA
    sap_sid: RO2
    system_type: SAP_S4
    landscape_role: production
    integration_stack: IDoc

interfaces:

  interface_id: IF_SALESORDER_INBOUND
    interface_name: SalesOrder_Inbound
    source_system: S4-RCA
    target_system: CPI-RCA
    technology: SAP CPI
    interface_type: inbound
    business_domain: sales
    owner: Integration Team
    criticality: high

## 7. Architecture Governance Rules

Customer architectures must follow a strict governance model to ensure consistency across the AI4CPI platform. 

### Rule 1 – Unique Customer Identifier

Each customer must have a globally unique customer_id.

Example:

RCA  
RDCUST01

### Rule 2 – Stable System Identifiers

System identifiers must remain stable over time.

System identifiers must not change once monitoring and knowledge indexing has started.

### Rule 3 – SAP SID Accuracy

The sap_sid field must always match the real SAP System ID.

Incorrect SAP SID values may break monitoring correlation.

### Rule 4 – Consistent System Typing

System types must follow the predefined list.

Allowed system types:

- SAP_PI
- SAP_PO
- SAP_CPI
- SAP_S4
- NON_SAP

### Rule 5 – Monitoring Endpoints Must Exist

Every productive system must define monitoring endpoints. 

Without monitoring endpoints the AI agent cannot detect operational incidents.

### Rule 6 – Architecture Must Be Defined Before Knowledge Ingestion

Customer architecture must be defined before any knowledge is ingested into the RAG system.

Knowledge without architecture context leads to incorrect retrieval.

### Rule 7 – Architecture Changes Must Be Reviewed

All architecture modifications must follow the standard review process. 

Required approval roles:

- Integration engineering team
- AI platform team
- Platform owner

### Rule 8 – Architecture Versioning

Customer architecture definitions should be versioned.

Changes should be tracked via Git commits.

This ensures traceability and auditability.
