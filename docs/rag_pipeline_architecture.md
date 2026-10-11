# AI4CPI RAG Pipeline Architecture

## 1. Purpose

This document defines the architecture of the AI4CPI Retrieval-Augmented Generation (RAG) pipeline. 

The RAG pipeline allows the AI agent to retrieve operational knowledge during incident analysis.

## 2. RAG Pipeline Stages

The pipeline consists of several stages.

Document Upload  
→ Parsing  
→ Chunk Generation  
→ Metadata Assignment  
→ Validation  
→ Embedding Generation  
→ Vector Storage

## 3. Document Parsing

Uploaded documents are parsed into raw text. 

Supported formats:

- md
- txt
- docx
- pdf
- xml
- csv
- xlsx

## 4. Chunk Generation

Parsed text is split into smaller chunks. 

Chunk size should allow efficient retrieval.

Typical configuration:

chunk_size: 500–800 tokens  
overlap: 100 tokens

## 5. Metadata Assignment

Each chunk receives metadata fields. 

Examples:

- customer_id
- system_id
- artifact_type
- interface_name
- priority
- technology

## 6. Embedding Generation

Chunks are converted into vector embeddings. 

Embeddings are stored in the vector database.

## 7. Vector Storage

Embeddings are stored in Qdrant. 

Each stored vector contains:

- embedding vector
- chunk text
- metadata

## 8. Retrieval

During incident analysis: 

event context  
→ embedding generation  
→ vector similarity search  
→ top knowledge chunks returned  
→ AI reasoning
