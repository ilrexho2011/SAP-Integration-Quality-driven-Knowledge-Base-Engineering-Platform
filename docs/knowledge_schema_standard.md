# AI4CPI Knowledge Schema Standard

## 1. Purpose

This document defines the standard knowledge schema used by the AI4CPI platform. 

The schema ensures that all knowledge ingested into the platform is:

- structured
- searchable
- compatible with the RAG system
- safe for multi-customer environments

This schema applies to:

- demo environments
- internal development
- production customers

There is one unified schema across the entire platform.

## 2. Knowledge Domains

The platform distinguishes between two types of knowledge.

### 2.1 Customer Knowledge

Customer-specific operational knowledge. 

Examples:

- KEDB entries
- runbooks
- interface inventories
- monitoring patterns
- customer architecture documentation

Customer knowledge always includes:

- customer_id
- system_id

### 2.2 Global Knowledge

Platform-wide technical knowledge not tied to a specific customer. 

Examples:

- SAP troubleshooting patterns
- CPI design guidelines
- integration architecture principles
- common failure scenarios

Global knowledge does not include:

- customer_id

## 3. Artifact Types

All knowledge entries must belong to one of the following artifact types. 

Allowed artifact types:

- kedb
- runbook
- architecture
- interface_inventory
- monitoring_pattern
- fix
- ticket_template
- troubleshooting

Entries that do not match one of these artifact types must not be indexed into the AI knowledge base.

## 4. Metadata Schema

All knowledge documents indexed into the AI4CPI platform must include metadata. 

Metadata is stored together with the embedding in the vector database (Qdrant).

This metadata allows the AI agent to filter and retrieve relevant knowledge.

### 4.1 Mandatory Metadata Fields

The following fields are mandatory for all customer knowledge.

- environment
- customer_id
- system_id
- sap_sid
- artifact_type
- object_name
- priority

Example metadata payload:

{
  "environment": "demo",
  "customer_id": "RCA",
  "system_id": "PIPO-RCA",
  "sap_sid": "RO2",
  "artifact_type": "kedb",
  "object_name": "PI_OAUTH_CHANNEL_ERROR",
  "priority": "P2"
}

### 4.2 Recommended Metadata Fields

The following metadata fields are recommended to improve search accuracy,
traceability and operational intelligence.

- domain
- interface_name
- technology
- source_file
- author
- reviewer
- review_status
- version
- created_at
- updated_at

These fields are optional but strongly recommended.

### Field Description

domain

Defines the technical domain.

Examples:

PI
CPI
S4
Integration

interface_name

Name of the integration interface.

Examples:

SalesOrder_Inbound
CustomerReplication_Outbound

technology

Integration technology used.

Examples:

SAP PI
SAP CPI
IDoc
SOAP
REST

review_status

Defines the knowledge lifecycle state.

Allowed values:

draft
review_pending
approved
indexed

Only knowledge with status approved may be indexed.

## 5. Optional Knowledge Sources

KEDB is an optional customer knowledge source.

Its absence must not block ingestion, retrieval, or AI reasoning.

If no KEDB exists for a customer, the AI agent must rely on other approved knowledge sources such as:

- runbooks
- architecture documentation
- interface inventory
- monitoring patterns
- fix library
- global knowledge

At least one approved knowledge source should exist for each customer environment.

## 6. Priority Standard

Priority defines the operational criticality of a knowledge object. 

The default priority model used by the AI4CPI platform is:

P1 = Critical business impact
P2 = High priority
P3 = Normal priority
P4 = Low priority

If a customer uses a different priority scheme, a mapping must be defined in the customer configuration.

Example mapping:

Customer Priority -> Platform Priority

High -> P1
Medium -> P2
Low -> P3

If no priority is provided, the system must assign:

default_priority = P3

## 7. Knowledge Ingestion Pipeline

Knowledge must follow a standardized ingestion pipeline before it becomes available to the AI agent. 

The ingestion pipeline ensures that documents are structured, validated and indexed correctly.

Pipeline stages:

Document
-> Parsing
-> Chunking
-> Metadata Assignment
-> Embedding Generation
-> Vector Storage (Qdrant)

Only validated and approved knowledge may enter the vector database.

### Step Description

Document

The source document is provided by the engineering team.

Examples:

- KEDB Excel files
- Runbooks
- Architecture documents
- Interface inventories
- Integration documentation

Parsing

The document is parsed into machine-readable text.

Chunking

Large documents are split into smaller logical knowledge blocks.

Metadata Assignment

Each chunk receives metadata according to the AI4CPI knowledge schema.

Embedding Generation

An embedding vector is generated using the embedding service.

Vector Storage

The vector and metadata are stored in Qdrant for retrieval by the AI agent.

## 8. Roles and Responsibilities

Clear responsibilities are required to maintain high quality knowledge within the AI4CPI platform. 

### SAP Knowledge Preparation

Responsible:

- User03

Responsibilities:

- prepare KEDB entries
- document runbooks
- document integration interfaces
- document architecture information
- validate technical correctness

### AI Structuring and Ingestion

Responsible:

- User02

Responsibilities:

- parse incoming documents
- prepare document chunking
- assign metadata according to the knowledge schema
- prepare ingestion pipeline for RAG

### Final Approval

Responsible:

- User01 (Super Admin)

Responsibilities:

- review knowledge quality
- approve knowledge before indexing
- validate architecture alignment
- ensure production readiness
