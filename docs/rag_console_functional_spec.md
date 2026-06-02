# AI4BIZ RAG Console Functional Specification

## 1. Purpose

This document defines the functional specification of the AI4BIZ RAG Console.

The RAG Console is the operational user interface used to manage knowledge ingestion for the AI4BIZ platform.

The console is intended primarily for AI knowledge operations.

Its main users are:

- Hafsa
- AI platform operators
- approved reviewers
- platform owner

The purpose of the console is to provide a controlled workflow for:

- document upload
- metadata assignment
- parsing
- chunk preview
- approval workflow
- indexing into Qdrant
- retrieval testing

The RAG Console is not a chat interface.

It is a knowledge operations interface.

## 2. Functional Scope

The RAG Console must support the following functional areas:

- document upload
- metadata management
- parsing and text extraction
- chunk generation
- validation
- review workflow
- indexing
- retrieval test
- audit trail

The console must support controlled knowledge preparation before information becomes available to the AI agent.

## 3. User Roles

The console must support different user roles.

### Knowledge Operator

Primary user:

- Hafsa

Responsibilities:

- upload files
- assign metadata
- run parsing
- review chunks
- set review status to review_pending

### Technical Reviewer

Users:

- Klevis
- Ilirjan

Responsibilities:

- validate technical meaning
- review interface descriptions
- review KEDB mappings
- suggest corrections

### Platform Owner

Primary user:

- Abdel

Responsibilities:

- approve knowledge
- authorize indexing
- validate governance compliance
- monitor final quality

## 4. Main Screens

The MVP RAG Console should include the following screens.

### 4.1 Dashboard

Purpose:

Provide an overview of the knowledge processing status.

Displayed information:

- total uploaded documents
- total parsed documents
- total chunks
- review status counts
- indexed documents
- latest uploads
- latest indexing operations

### 4.2 Upload Screen

Purpose:

Upload new knowledge files.

Functions:

- select file
- assign metadata
- validate mandatory fields
- create initial draft entry

### 4.3 Parsing and Chunk Preview Screen

Purpose:

Display extracted text and generated chunks before indexing.

Functions:

- show raw extracted text
- show chunk list
- show chunk sizes
- allow re-chunking
- display parsing warnings

### 4.4 Review Screen

Purpose:

Review metadata and chunk quality.

Functions:

- update metadata
- add review comments
- set review status
- approve or reject

### 4.5 Retrieval Test Screen

Purpose:

Validate that indexed knowledge can be found correctly.

Functions:

- enter search text
- apply filters
- display top retrieval results
- open matching chunks

## 5. Upload Requirements

The upload process must support the following file formats:

- md
- txt
- docx
- pdf
- csv
- xlsx
- xml

Each upload must require the following metadata fields:

- environment
- customer_id
- system_id
- sap_sid
- artifact_type
- object_name
- priority

Optional metadata fields:

- domain
- interface_name
- technology
- author
- reviewer
- version

All new uploads must initially receive:

review_status = draft

## 6. Validation and Approval

Before indexing, the console must validate the uploaded knowledge.

Validation rules:

- mandatory metadata present
- artifact_type valid
- priority valid
- file format supported
- extracted text not empty
- chunks created successfully

Approval lifecycle:

- draft
- review_pending
- approved
- indexed

Only knowledge with status approved may be indexed into Qdrant.

## 7. Indexing and Retrieval

The console must support controlled indexing into the AI4BIZ vector database.

Indexing steps:

- parse document
- generate chunks
- assign metadata
- generate embeddings
- store vectors in Qdrant

The console must also support retrieval testing.

Retrieval test features:

- search text input
- metadata filters
- top result preview
- score display
- chunk inspection

This allows the operator to validate the quality of the indexed knowledge.

## 7. Indexing_and_Retrieval

The console must support controlled indexing into the AI4BIZ vector database.

Indexing steps:

- parse document
- generate chunks
- assign metadata
- generate embeddings
- store vectors in Qdrant

The console must also support retrieval testing.

Retrieval test features:

- search text input
- metadata filters
- top result preview
- score display
- chunk inspection

This allows the operator to validate the quality of the indexed knowledge.

## 8. Audit Trail

The console must provide traceability for all operations.

Each knowledge object should record:

- uploaded_by
- uploaded_at
- reviewed_by
- reviewed_at
- approved_by
- approved_at
- indexed_at
- source_file

This ensures governance, traceability and auditability.
