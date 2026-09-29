# AI4CPI RAG Console API Specification

## 1. Purpose

This document defines the backend API specification for the AI4CPI RAG Console.

The API supports the knowledge operations workflow used to prepare, validate, approve and index knowledge into the AI4BIZ platform.

The API is intended for:

- document upload
- metadata handling
- parsing
- chunking
- validation
- approval workflow
- indexing
- retrieval testing

## 2. API Principles

The RAG Console API must follow these principles:

- REST-based design
- clear separation of workflow stages
- explicit validation before indexing
- metadata-first processing
- auditability of all operations

All API responses should return structured JSON.

## 3. Upload Endpoint

### POST /upload

Purpose:

Upload a document and create a draft knowledge object.

Input:

- file
- environment
- customer_id
- system_id
- sap_sid
- artifact_type
- object_name
- priority

Optional input:

- domain
- interface_name
- technology
- author
- reviewer
- version

Output:

- document_id
- upload_status
- review_status
- source_file

Default review status:

draft

## 4. Parsing Endpoint

### POST /parse

Purpose:

Parse the uploaded document into machine-readable text.

Input:

- document_id

Output:

- document_id
- parsing_status
- extracted_text
- parsing_warnings

## 5. Chunking Endpoint

### POST /chunk

Purpose:

Split extracted text into logical chunks for indexing.

Input:

- document_id
- chunking_strategy
- max_chunk_size
- overlap_size

Output:

- document_id
- chunk_count
- chunks
- chunking_status

Each chunk should contain:

- chunk_id
- chunk_text
- chunk_order
- metadata

## 6. Validation Endpoint

### POST /validate

Purpose:

Validate metadata and chunk quality before approval or indexing.

Input:

- document_id

Validation checks:

- mandatory metadata present
- artifact_type valid
- priority valid
- extracted_text not empty
- chunk_count greater than zero
- review_status valid

Output:

- document_id
- validation_status
- validation_errors
- validation_warnings

## 7. Review and Approval Endpoints

### POST /review

Purpose:

Update review information and set review status.

Input:

- document_id
- review_status
- review_comment
- reviewed_by

Allowed review status values:

- draft
- review_pending
- approved
- rejected

Output:

- document_id
- review_status
- review_result

### POST /approve

Purpose:

Mark a document as approved for indexing.

Input:

- document_id
- approved_by

Output:

- document_id
- approval_status
- approved_at

## 8. Index Endpoint

### POST /index

Purpose:

Generate embeddings and store approved chunks in Qdrant.

Precondition:

- review_status must be approved

Input:

- document_id

Output:

- document_id
- indexing_status
- indexed_chunk_count
- qdrant_collection
- indexed_at

## 9. Retrieval Test Endpoint

### POST /search

Purpose:

Test retrieval quality against indexed knowledge.

Input:

- query_text
- customer_id
- system_id
- artifact_type
- top_k

Output:

- query_text
- result_count
- results

Each result should contain:

- score
- object_name
- artifact_type
- chunk_id
- chunk_text
- metadata

## 10. Audit and Listing Endpoints

### GET /documents

Purpose:

List uploaded knowledge documents.

Output:

- document_id
- source_file
- customer_id
- artifact_type
- review_status
- uploaded_at

### GET /documents/{document_id}

Purpose:

Return full details of a single document.

Output:

- metadata
- parsing_status
- chunk_count
- review_status
- indexing_status
- audit trail

### GET /health

Purpose:

Return service health information.

Output:

- service_status
- qdrant_status
- embedding_service_status
- storage_status
