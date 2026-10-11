AI4CPI Platform Architecture

1. Purpose
This document describes the overall system architecture of the AI4CPI platform.

The architecture supports:

AI-assisted SAP operations
RAG-based knowledge retrieval
operational incident analysis
automated remediation actions
The platform is designed as a modular AI operations system.

2. Core Components
The AI4CPI platform consists of the following components:

Monitoring Event Sources
AI Agent
RAG Knowledge System
Vector Database
Embedding Service
Inference Engine
Knowledge Management Console
Automation Execution Layer

3. System Layers
Monitoring Layer
Generates operational events.

Examples:

SAP PI monitoring
SAP CPI message logs
SAP IDoc monitoring
external monitoring systems
AI Agent Layer
The AI agent evaluates operational events.

Responsibilities:

event interpretation
knowledge retrieval
root cause reasoning
action recommendation
RAG Knowledge Layer
Responsible for retrieving operational knowledge.

Components:

knowledge repository
chunk storage
metadata filtering
vector search
Vector Database
Stores knowledge embeddings.

Current implementation:

Qdrant

Embedding Service
Generates vector embeddings for knowledge chunks.

Used during:

indexing
retrieval
Inference Engine
Executes reasoning with large language models.

Examples:

Qwen
LLaMA
Knowledge Console
User interface used to manage knowledge ingestion.

Main functions:

document upload
parsing
chunk validation
knowledge approval
indexing
Automation Layer
Executes operational actions based on agent decisions.

Examples:

message retry
queue unlock
communication channel restart
iFlow restart
4. Data Flow
Typical operational flow:

Event generated
→ AI agent receives event
→ embedding of event context
→ vector search in knowledge base
→ knowledge retrieval
→ AI reasoning
→ recommended resolution
→ optional automation action

5. Deployment Model
The platform runs as containerized services.

Main services include:

inference service
rag ingestion service
vector database
agent service
rag console
monitoring integration
