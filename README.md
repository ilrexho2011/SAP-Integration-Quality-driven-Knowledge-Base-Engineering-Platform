# Quality-driven Knowledge Engineering Platform

This project is the implementation scaffold for the AI4BIZ closed-loop knowledge engineering ecosystem.

It contains:

- Knowledge Retrieval Quality Assessment backend
- Dynamic Corrective Feedback JSON contract
- Streamlit dashboard with English default and German language switch
- Markdown KEDB/Runbook parsing
- Heading-aware chunking
- Dependency-free BM25-style retrieval benchmark
- Policy compliance scoring
- Enterprise report generation hooks
- Approved RAG package publication flow

<img width="1154" height="645" alt="image" src="https://github.com/user-attachments/assets/a4b425df-8fa0-4837-bf34-30b660e8d71c" />

## Architecture

```text
Knowledge Generation Platform
        -> KEDB / Runbooks / Catalog Docs
        -> Retrieval Quality Assessment Platform
        -> Benchmark Report + Feedback JSON
        -> Controlled Regeneration
        -> Approved RAG Ingestion Package
        -> UI Monitor & Dashboard Platform
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate  # Windows PowerShell: .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Start Backend

```bash
uvicorn app.main:app --reload
```

## Start Dashboard

```bash
streamlit run app/ui/streamlit_app.py
```

## Run Local Benchmark with Sample Package

```bash
python scripts/run_local_benchmark.py
```

## Required User Resources

See:

```text
resources/RESOURCE_REQUESTS.md
```

Upload the ingestion policies, templates, golden questions and representative knowledge packages before v0.2 integration.

## Governance Rule

The evaluator does **not** directly modify KEDB or Runbook documents. It creates corrective feedback only. The generator applies remediation after user approval.
