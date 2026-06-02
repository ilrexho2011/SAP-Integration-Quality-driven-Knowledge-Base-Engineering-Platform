# AI4BIZ Architecture

## Overview

AI4BIZ is an enterprise AI operations platform designed to support SAP landscapes through intelligent monitoring, knowledge retrieval and automated incident handling.

## Core Components

- AI Agent (FastAPI)
- Embedding Service
- Vector Database (Qdrant)
- LLM Inference (Qwen 32B via vLLM)

## Nodes

### Node-A

- AI Agent
- Embedding Service
- Qdrant Vector Database

### Node-B

- vLLM Inference
- Qwen 32B Model

## Data Flow

Event / Monitoring Error  
→ Embedding  
→ Vector Search (Qdrant)  
→ Knowledge Retrieval  
→ LLM Analysis  
→ Recommendation / Action
