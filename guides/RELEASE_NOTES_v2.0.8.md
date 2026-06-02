# Release Notes — v2.0.8 (Quality Review)

This release applies the architecture and code-quality improvements from the
v2.0.7 review. It is a drop-in successor to v2.0.7: all original folders and
files are retained, with the changes below applied. The full test suite passes
(**93 tests**), and `ruff check` / `ruff format --check` are clean.

## How to install and run

```bash
# from the project root
python -m venv .venv && source .venv/bin/activate   # optional but recommended
pip install -e ".[dev]"        # editable install (no sys.path hacks)

# quality gates
ruff check .                   # lint (hard gate)
ruff format --check .          # format (hard gate)
pytest                         # 93 tests
mypy app                       # informational

# run the platform
python scripts/run_dashboard.py            # Streamlit dashboard
# or the FastAPI app per the existing README
```

Optional AI enrichment (off by default) — set in a local `.env`:

```bash
AI_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
# AI_MODEL=claude-3-5-haiku-latest   # optional override
```

## What changed from v2.0.7

### Wave 1 — generation quality and hygiene

- **Incident filter fixed**: aggregated statistics rollups (e.g. annual
  "success=N, failed=M" rows) and success events no longer become KEDB/runbook
  documents. Note: the bundled PI/PO MPL evidence is entirely aggregate
  statistics, so PI/PO generation from it is now correctly blocked — supply real
  incident MPL data for PI/PO documents.
- **Duplicate detection** now keys on the canonical `object_name` (exact match),
  replacing the whole-body substring scan that produced false positives.
- **Evidence warnings**: unreadable/corrupt JSON is reported in the generation
  manifest (`evidence_warnings`) instead of being silently swallowed.
- Removed ~1,400 lines of dead `_old`/`_old1` files; removed committed `.env`;
  added `.gitignore`; version is now a single source of truth in code.

### Wave 2 — generation depth

- **Real, optional AI enrichment** of the diagnostic sections (Root Cause /
  Diagnosis / Recovery) — evidence-only, BM25-aware, non-blocking, with full
  traceability in the manifest. Falls back to deterministic templates when no
  provider/key is configured. No new runtime dependency (stdlib urllib).
- **Multi-customer**: `customer_id` and `environment` are parameters (defaults
  RCMO/demo) that flow into metadata, `system_id`, filenames and the manifest.
- **Inventory-driven priority**: priority is taken from the Interface Inventory
  (with customer High/Medium/Low → P1/P2/P3 mapping), then keyword fallback,
  then the schema default P3. Rate-limit/throttle now maps to P2.
- **Template engine**: KEDB and runbook structure moved to Jinja2 templates
  (`app/templates/knowledge/*.j2`). Output is byte-identical to v2.0.7.

### Wave 3 (partial) — long-term health

- **Ruff** (lint + format) configured as a hard gate; the codebase was formatted
  in a single behavior-preserving pass (verified by the test suite).
- **Mypy** configured, currently informational while types are added
  incrementally; the new v2.0.7+ modules are held to a stricter standard.
- **pyproject.toml** with editable install; **GitHub Actions CI**
  (`.github/workflows/ci.yml`) running ruff + pytest on Python 3.10/3.11/3.12.
- Lint caught and fixed real bugs: 3 duplicate dictionary keys (silent
  overwrites) and an f-string backslash invalid on Python 3.10/3.11.

## Not yet applied (candidates for v2.0.9)

- 2.5 — refactor of `GenerationService.generate()` (22 parameters) into a
  request dataclass + manifest builder.
- 1.1 — consolidation of the three parallel UI surfaces.

## New dependency

- `Jinja2>=3.1` (added to requirements.txt and pyproject.toml).
