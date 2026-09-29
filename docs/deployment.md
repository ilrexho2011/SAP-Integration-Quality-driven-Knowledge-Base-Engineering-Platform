# Deployment

## Node Architecture

### Node-A

- AI Agent 
- Embedding Service
- Qdrant

### Node-B

- LLM Inference ( vLLM )

## Ports

- Agent API: 8002
- Embedding Service: 8100
- Qdrant: 6333
- LLM: 8000 (direct on Node-B), 8000/8001 via gateway on Node-A
