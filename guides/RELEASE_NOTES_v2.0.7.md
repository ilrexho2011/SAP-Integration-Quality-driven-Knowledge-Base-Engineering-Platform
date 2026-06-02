# Release Notes v2.0.7 - Fast MPL Monitoring

Version v2.0.7 starts from the stable v2.0.6 baseline and optimizes the Monitoring page for SAP CPI and SAP PI/PO operational use.

## Changed

- Monitoring summary now loads MPL-only numeric counters for the selected time window.
- SAP CPI monitoring no longer fetches integration packages, iFlows, CPIView evidence, native CPI evidence, or live design snapshots during page load.
- SAP PI/PO monitoring no longer fetches Directory/ESR/interface inventory during page load.
- The Monitoring page KPI row now focuses on message throughput: Success Messages, Failed Messages, and Total Messages.
- Design/configuration/interface inventory is available only through explicit on-demand buttons in the Monitoring page.

## Added

- New backend endpoint: `GET /api/monitor/inventory`.
- New service method: `MonitorService.get_inventory(...)`.
- On-demand inventory actions for design/configuration objects and interfaces/iFlows.

## Operational impact

Opening the Monitoring page should be significantly faster when connected to SAP CPI or SAP PI/PO because only MPL records for the selected time range are requested. Slower inventory retrieval remains available but is operator-triggered.
