# Release Notes v2.0.6 - Document Generation Governance

Version v2.0.6 improves QDKEP document generation naming governance and readability for AI4BIZ ingestion.

## Changes

- Enforced maximum generated Markdown filename length of 80 characters.
- Enforced maximum generated `object_name` metadata length of 80 characters.
- Removed hash noise from generated filenames and preserved the governed pattern `<TYPE>_<CUSTOMER>_<SYSTEM>_<ERROR_CODE>_<PRIORITY>_<VERSION>.md`.
- Added token-boundary shortening so long object names are shortened predictably instead of being cut in the middle of a token.
- Added canonical incident naming for common SAP CPI/PI patterns such as API throttling/rate limits, authentication/authorization failures, connection timeouts, SSL certificate/handshake failures, XML parse failures, and mapping/script failures.
- Improved generated document titles so KEDB/runbook titles are readable operator-facing phrases while exact MPL ErrorMessage evidence remains preserved in evidence sections.
- Updated functional knowledge generation filename/object_name constraints to match the same 80-character governance.

## Policy Alignment

- AI4BIZ Knowledge Ingestion Guide: one file remains one atomic knowledge artifact; filenames stay in the approved segment order.
- BM25 Runbook Authoring Guideline: titles now prioritize canonical retrieval phrases and reduce vague/noisy exception class names.
- Knowledge Schema Standard: `object_name` remains stable, uppercase, underscore-delimited metadata suitable for filtering and retrieval.

## Example

Input ErrorMessage:

```text
com.sap.gateway.core.ip.component.exceptions.OData4Exception: Receiver rejects or delays calls because request volume exceeds the allowed threshold
```

Generated filename pattern:

```text
KB_RCMO_CPI_API_THROTTLING_RATE_LIMIT_EXCEEDED_P2_v1.md
```

Generated `object_name`:

```text
CPI_API_THROTTLING_RATE_LIMIT_EXCEEDED
```

Generated title:

```text
Receiver throttled requests due to API rate limit
```
