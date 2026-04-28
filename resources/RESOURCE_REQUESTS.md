# Required Resources for AI4BIZ Quality-driven Knowledge Engineering Platform

Please upload or place the following resources into the indicated folders before moving from v0.1 to v0.2.

## 1. Ingestion Policy Documents

Place these files under `resources/policies/`:

- `AI4BIZ_Knowledge_Ingestion_Guide.txt`
- `BM25_Runbook_Authoring_Guideline.txt`
- `AI4BIZ_Interface_Inventory_Schema.txt`
- `knowledge_schema_standard.md`

## 2. Authoring Templates

Place these files under `resources/templates/`:

- `Iflow-Catalog_template.md`
- `kedb_template.md`
- `runbook_template.md`
- Optional: enterprise DOCX report template
- Optional: RealCore / AI4BIZ branding guide, color palette, logo assets

## 3. Benchmark Datasets

Place these files under `resources/golden_datasets/`:

- `golden_questions.jsonl`
- `expected_relevant_documents.jsonl`
- `expected_answers.jsonl`
- optional `negative_queries.jsonl`
- optional MPL-noisy-query examples

Expected `golden_questions.jsonl` format:

```json
{"test_id":"RB-P2-0014-Q01","query":"How to resolve HTTP 429 receiver throttling?","expected_doc_id":"RB-P2-0014","expected_keywords":["HTTP 429","rate limit","retry"],"priority":"P2"}
```

## 4. Test Knowledge Packages

Upload representative ZIP files into `upload_packages/` or through the dashboard:

- KEDB-only package
- Runbooks-only package
- Combined KEDB + Runbooks package
- Integration Catalog package
- Historical/legacy package with known defects
- Approved reference package with high quality

## 5. SAP / Runtime Samples

For realistic benchmark and feedback generation, provide:

- Sample `CPI_Message_Processing_Logs.json`
- Sample PI/PO MPL exports
- Sample Catalog export JSON
- Sample generated KEDB and Runbook documents
- Any prior enterprise compliance reports used as format references
