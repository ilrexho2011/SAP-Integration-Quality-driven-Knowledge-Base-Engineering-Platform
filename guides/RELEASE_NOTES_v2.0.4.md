# Release Notes v2.0.4 - Scenario Lab MPL Source and Duplicate Governance

Version v2.0.4 extends Scenario Lab & Generation without removing v2.0.3 behavior.

## Improvements

- `Select MPL Source` now includes `All CPI archived MPL sources` and JSON files discovered dynamically under `./resources/mpl` for SAP CI/CPI; the redundant `Live MPLs` option was removed from the dropdown.
- SAP PIPO MPL source selection preserves existing PIPO sources and also supports dynamic JSON file discovery from PIPO MPL folders when present.
- Selected MPL source keys are used by the generation backend, including single JSON files selected from `./resources/mpl`.
- UI label changed to `prevent dublicate ID` as requested.
- Duplicate governance now applies to interface inventory, KEDB, and Runbook generation.
- When duplicate governance is enabled, matching existing documents are skipped/ignored instead of being regenerated or updated.
- KEDB and Runbook ID continuation is global and reads from `./sample_packages/kedbs` and `./sample_packages/runbooks`, independent of the selected system (`sap_ci` or `sap_pipo`).
- Multiple KEDB/Runbook documents generated in the same run now receive unique incrementing IDs after the current maximum existing ID.
- Existing legacy CPI/PIPO sample package folders are still scanned for backward compatibility.

## Environment

```bash
APP_VERSION=2.0.4-scenario-lab-mpl-duplicate-governance
```

## Verification update

- Confirmed global max-ID scan for `KEDB-P*-NNNN` and `RB-P*-NNNN` patterns.
- Confirmed new generation starts at the next sequence after the highest existing document ID, regardless of selected source system or priority bucket.
- Confirmed duplicate governance records `action: skip_duplicate` and does not update existing documents in generate mode.
- Test result: `48 passed`.
