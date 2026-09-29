# AI4CPI Knowledge Ingestion Guide

> For internal use — Knowledge Engineers and AMS Team
> Version: 1.0 | Date: 2026-06-09

---

## Core Principle

**One file = One knowledge artifact.**

Each uploaded document must represent exactly one runbook, one KEDB entry, or one documentation artifact. Collection files (multiple runbooks in one file) are not supported and will cause indexing issues.

---

## Knowledge Granularity Rule

Each document must represent a **single atomic knowledge unit**.

This means:

- One incident pattern
- One error scenario
- One resolution flow

Do NOT combine multiple error scenarios in one runbook, even if they are related.

> **Why this matters:** The AI agent uses each document as a single decision unit. Mixed content leads to mixed decisions — the agent cannot reliably distinguish between two error scenarios packed into one file.

---

## File Naming Convention

### Format

```md
<TYPE>_<CUSTOMER>_<SYSTEM>_<ERROR_CODE>_<PRIORITY>_<VERSION>.md
```

### Segments

| Segment | Description | Example |
| ------- | ----------- | ------- |
| `TYPE` | Artifact type prefix | `RB` (Runbook), `KB` (KEDB), `DOC` (Documentation) |
| `CUSTOMER` | Customer ID | `RCMO` |
| `SYSTEM` | System ID | `CPI`, `PIPO`, `S4H` |
| `ERROR_CODE` | Normalized error identifier — use uppercase, underscores, no spaces. Must reflect the specific error pattern, not a generic category. | `ODATA_404`, `MPL_AUTH_ERROR`, `QUEUE_BACKLOG`, `CERT_EXPIRY` |
| `PRIORITY` | Incident priority | `P1`, `P2`, `P3`, `P4` |
| `VERSION` | Document version | `v1`, `v2` |

### Examples

```md
RB_RCMO_CPI_ODATA_404_P2_v1.md
RB_RCMO_CPI_MPL_AUTH_ERROR_P2_v1.md
RB_RCMO_PIPO_CHANNEL_DOWN_P1_v1.md
KB_RCMO_CPI_QUEUE_BACKLOG_P2_v1.md
DOC_RCMO_CPI_ARCHITECTURE_OVERVIEW_P3_v1.md
```

---

## Document Types

| Type | Document Type in System | Default Chunk Mode | Use For |
| ---- | --------------------- | ------------------ | ------- |
| `RB` | `runbook` | `bm25_typed` | Operational runbooks, incident procedures |
| `KB` | `kedb` | `paragraph` | Known error entries, problem-solution pairs |
| `DOC` | `documentation` | `paragraph` | Architecture docs, technical references |

---

## Required Document Structure (Runbook)

Each runbook must follow this structure:

```markdown
# <RUNBOOK_TITLE>

RUNBOOK ID
<ID>

RUNBOOK TITLE
<Title>

1. PURPOSE
...

2. BUSINESS CONTEXT
...

3. TECHNICAL LANDSCAPE
...

4. MONITORING AND MPL EVIDENCE
...

5. ERROR SIGNATURE
...

6. KNOWN ROOT CAUSES
...

7. PREREQUISITES FOR INVESTIGATION
...

8. DIAGNOSIS STEPS
...

9. RECOVERY STEPS
...

10. ESCALATION CRITERIA
...

11. POST-FIX VALIDATION
...
```

---

## Writing Style Guidelines

- Do NOT write long paragraphs or essays
- Use short, structured sentences
- Prefer bullet points over text blocks
- Each step must be clear and independently executable

**Bad:**
> "Sometimes issues may occur due to configuration inconsistencies in the adapter settings or related components."

**Good:**
> "Check destination configuration in CPI → Security Material → verify certificate is not expired."
>
> **Why this matters:** Chunk quality directly drives LLM output quality and agent decision quality. Vague text produces vague answers.

---

> ⚠️ **IMPORTANT — Section Names are Sacred**
>
> The system uses section names to classify knowledge automatically (BM25 engine).
> If you rename sections, retrieval quality will silently degrade.
>
> Do NOT rename:
>
> - `ERROR SIGNATURE`
> - `DIAGNOSIS STEPS`
> - `RECOVERY STEPS`
> - `ESCALATION CRITERIA`
>
> These names are hardcoded into the classification engine.

---

## Optional Metadata Block

Adding a metadata block at the top of the document provides redundancy and improves parser reliability.
It is optional but strongly recommended.

```md
RUNBOOK ID
RB_RCA_CPI_MPL_AUTH_ERROR_P2

CUSTOMER
RCA

SYSTEM
CPI

PRIORITY
P2

VERSION
v1
```

> This metadata is independent from the upload form fields. It acts as a safety net if the file is processed outside the standard upload flow.

---

## Upload Checklist

Before uploading a document, verify:

- [ ] File contains exactly **one** runbook / KEDB entry / documentation artifact
- [ ] Filename follows the naming convention
- [ ] Document type is correctly selected in the upload form
- [ ] Version is set correctly (e.g. `v1`, `v2`)
- [ ] Customer ID and System ID match the document content
- [ ] Priority matches the incident priority of the runbook
- [ ] All required sections are present and correctly named

---

## What NOT to Upload

| ❌ Not allowed | ✅ Correct approach |
| ----------------- | --------------------- |
| Collection file with 19 runbooks | 19 separate files, one per runbook |
| One file mixing KEDB + Runbook | Two separate files |
| File without version | Always set version (start with `v1`) |
| Generic filename like `runbooks_march.md` | Follow naming convention |

---

## Section Types (BM25 Classification)

The system automatically classifies each chunk into one of the following section types.
This classification drives the 8-signal reranking engine.

| Section Type | Maps To | Weight in Reranking |
| -------------- | --------- | --------------------- |
| `error_signature` | ERROR SIGNATURE section | High |
| `diagnosis_step` | DIAGNOSIS STEPS section | High |
| `recovery` | RECOVERY STEPS section | High |
| `escalation` | ESCALATION CRITERIA section | Medium |
| `context` | BUSINESS CONTEXT, TECHNICAL LANDSCAPE | Low |
| `generic` | Unclassified content | Lowest |

**The better the document structure, the better the retrieval quality.**

---

## Questions

Contact the AI4CPI platform team for questions about ingestion, document structure, or chunk quality validation.
