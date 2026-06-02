# Sprint 6 - Functional RB/KB/DOC Generators

Implemented over v1.5.

## Added

- `app/services/functional_knowledge_generation.py`
- `scripts/generate_functional_knowledge.py`
- API endpoint `POST /api/packages/generate-functional-knowledge`
- PackageBuilder evidence source embedding for `logs/mpl`, `resources/mpl`, SAP/PI-PO inventory folders
- Generated functional knowledge source under `generated_functional_knowledge/`

## Generation result

```json
{
  "status": "generated",
  "generated_at": "2026-04-30T21:00:00Z",
  "source_package": "/mnt/data/quality-driven-knowledge-engineering-platform-v1.6_functional_knowledge_generation",
  "artifact_count": 237,
  "runbook_count": 93,
  "kedb_count": 93,
  "documentation_count": 51,
  "source_map": {
    "source_ingestion_package": "/mnt/data/quality-driven-knowledge-engineering-platform-v1.6_functional_knowledge_generation/exports/quality-driven-knowledge-engineering-platform-v1.5_evidence-traceability-ingestion-package.zip",
    "metadata_files": 186,
    "mpl_log_files": [
      "logs/mpl/Message_Processing_Logs_2026_Failed_Only_134_No_Dublicate_01.json",
      "logs/mpl/Message_Processing_Logs_April_2026_All_01.json",
      "logs/mpl/Message_Processing_Logs_April_2026_FAILED_only_01.json",
      "logs/mpl/Message_Processing_Logs_March_2026_All_01.json",
      "logs/mpl/Message_Processing_Logs_March_2026_FAILED_only_01.json"
    ]
  },
  "rules": [
    "runtime values are never fabricated",
    "DOC catalog entries generated per unique interface_id/object_name",
    "existing RB/KB artifacts are carried forward and generator code is included for functional regeneration"
  ]
}
```

Runtime values are not fabricated. MessageGuid, MPL ids, endpoint URLs and payload samples are only allowed when present in real evidence.
