# Sprint 8 - CLI/API Workflow Hardening

Sprint 8 makes QDKEP practical for developer and AMS operator workflows by adding a unified command-line facade and matching API response model.

## Unified response model

All hardened CLI/API workflows return:

```json
{
  "status": "approved|ready|success|completed|blocked|needs_remediation",
  "output_path": "path/to/output",
  "issues": [],
  "warnings": [],
  "command": "qdkep-command-name",
  "data": {}
}
```

## CLI commands

```bash
./qdkep validate-contract <package_path> --output-json quality/contract_validation_report.json
./qdkep build-package --source-root generated_functional_knowledge --output-zip exports/package.zip --package-version 1.9
./qdkep quality-gate <package_path> --output-json quality/package_quality_gate_report.json
./qdkep export-ai4biz <package_path> --output-root exports/ai4biz_rag_console_payload
./qdkep generate-runbooks --source-package package.zip --output-root generated_functional_knowledge
./qdkep generate-kedb --source-package package.zip --output-root generated_functional_knowledge
./qdkep generate-docs --source-package package.zip --output-root generated_functional_knowledge
./qdkep benchmark-package <package_path>
```

The equivalent Python entrypoint is:

```bash
python -m app.cli.qdkep <command> [options]
```

## API endpoints

The API endpoints use the same `OperatorWorkflowService` as the CLI:

- `POST /api/contracts/validate-package`
- `POST /api/packages/build-package`
- `POST /api/packages/package-quality-gate`
- `POST /api/packages/export-ai4biz-ingestion`
- `POST /api/packages/generate-runbooks`
- `POST /api/packages/generate-kedb`
- `POST /api/packages/generate-docs`
- `POST /api/benchmark/run`

## Operator policy

- CLI and API use the same services; no duplicated business logic.
- Runtime/MPL values are not fabricated.
- Benchmark package does not compute a combined final score without AI4BIZ retrieval traces and answer traces.
- Blocking issues are surfaced in `issues`; non-blocking operational context is surfaced in `warnings`.
