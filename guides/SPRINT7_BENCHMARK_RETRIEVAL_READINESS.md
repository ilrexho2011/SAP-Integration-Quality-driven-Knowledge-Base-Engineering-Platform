# Sprint 7 - Golden Questions + Benchmark Upgrade

Sprint 7 adds deterministic golden-question generation and separates benchmark readiness into three dimensions.

## Added components

- `GoldenQuestionGenerator`
- `resources/golden_datasets/golden_questions.jsonl`
- `quality/golden_questions_generation_report.json`
- upgraded `BenchmarkOrchestrator`
- `quality/benchmark_readiness_report.json`
- CLI `scripts/generate_golden_questions.py`
- CLI `scripts/run_benchmark_readiness.py`

## Golden-question policy

Each RB and KB receives:

- diagnosis query
- recovery query
- root-cause query
- dirty MPL/log query
- synonym-heavy query
- negative/distractor query

Runtime values are not fabricated. Dirty MPL/log queries use only known metadata and normalized error terms unless real MPL values exist.

## Benchmark scoring policy

The benchmark now separates:

- `static_package_readiness`
- `retrieval_readiness`
- `answer_readiness`

No combined final score is produced unless AI4BIZ index retrieval traces and answer traces are present.
