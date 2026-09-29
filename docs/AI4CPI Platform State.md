AI4CPI Platform State
1. Current Platform Goal
AI4CPI is being built as an enterprise AI knowledge and operations platform focused on SAP-related incident analysis, knowledge retrieval, and guided remediation.

The current implementation focus is the RAG knowledge platform.

2. Current Core Components
The following components are already implemented or operational:

RAG Console API
RAG Web UI
Embedding Service
Qdrant Vector Database
NAS-based upload storage
Streamlit-based knowledge interface
FastAPI-based backend services
3. Current Runtime Services
RAG Console API
Service name: ai4cpi-rag-console
Port: 8200
Status: systemd managed
RAG Web UI
Service name: ai4cpi-rag-ui
Port: 8501
Status: systemd managed
Embedding Service
Port: 8100
Qdrant
Port: 6333
Open WebUI
Port: 3001
4. Current Data Flow
The current RAG pipeline works as follows:

Upload -> Parsing -> Chunking -> Embedding -> Qdrant Indexing -> Search

5. Current Storage Model
NAS Mount
Mount point: /nas
AI4CPI Storage Root
/nas/ai4cpi
Current Upload Directory
/nas/ai4cpi/uploads
Uploaded files are now stored on the NAS.

6. Current RAG Collection
Current collection in Qdrant:

ai4cpi_rag
Planned future collection structure:

ai4cpi_customer_rag
ai4cpi_global_rag
This separation is preferred for the medium-term architecture.

7. Current UI Scope
The current Streamlit UI is being evolved into a multipage knowledge console.

Planned pages:

Dashboard
Upload
Documents
Indexes
Search
8. Current Role Model
knowledge_operator
Current user:

User01
Responsibilities:

document upload
parsing
preparing documents for review
technical_reviewer
Current users:

User02
User03
Responsibilities:

technical validation of knowledge
checking document quality
verifying operational correctness
platform_owner
Current users:

Abdel
Daut
Responsibilities:

final approval
indexing authorization
architecture decisions
knowledge governance
9. Current Security Model
The platform is intended to be reachable only through the internal WireGuard network.

Important principles:

no public exposure of RAG UI
no public exposure of RAG API
internal network access only
firewall restrictions remain mandatory
10. Current Completed Work
The following capabilities are already working:

document upload
metadata capture
raw text extraction
chunk generation
embedding generation
vector indexing
semantic search
Streamlit UI access
systemd background services
NAS upload integration
11. Immediate Next Steps
The next implementation priorities are:

Complete multipage RAG Console
Extend document lifecycle handling
Persist parsed output and chunks on NAS
Introduce collection split:
ai4cpi_customer_rag
ai4cpi_global_rag
Add stronger access control for UI and API
12. Strategic Direction
The RAG platform is not the final product. It is the foundation for a broader AI4CPI platform that will later support:

operational knowledge retrieval
incident reasoning
guided troubleshooting
customer-specific knowledge separation
automation support
AI-assisted SAP operations
