from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Mapping

# Technical constants must remain untranslated. Keep this set aligned with the
# contract vocabulary used by validators, manifests, metadata and reports.
TECHNICAL_CONSTANTS = {
    "interface_id",
    "promotion_decision",
    "manifest.json",
    "package_metadata.json",
    "quality/contract_validation_report.json",
    "quality/package_quality_gate_report.json",
    "quality/ai4biz_ingestion_readiness_report.json",
    "quality/traceability_report.json",
    "quality/benchmark_readiness_report.json",
    "golden_questions.jsonl",
    "metadata",
    "artifact_type",
    "document_type",
    "chunk_mode",
}

_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "app_title": "Quality-Driven Knowledge Engineering Platform",
        "app_caption": "Control tower, monitoring events, scenario-backed generation, and all QDKEP quality-console functions preserved.",
        "package_input": "QDKEP package source from ./exports",
        "custom_package_path": "Custom path...",
        "package_input_hint": "Default source is the latest generated package under ./exports. Use Custom path only for external review packages.",
        "language": "Language",
        "navigation": "Navigation",
        "monitoring": "Monitoring Events",
        "scenario_lab_generation": "Scenario Lab & Generation",
        "overview": "QDKEP Dashboard",
        "contract_validation": "Contract Validation",
        "package_builder": "Package Builder",
        "quality_gates": "Quality Gates",
        "ai4biz_export": "AI4BIZ Export",
        "evidence_traceability": "Evidence & Traceability",
        "generators": "Generators",
        "benchmark": "Benchmark",
        "send_feedback": "Send feedback",
        "reports_downloads": "Reports & Downloads",
        "settings": "Settings",
        "status": "Status",
        "issues": "Blocking Issues",
        "warnings": "Warnings",
        "downloads": "Downloads",
        "metrics": "KPI Overview",
        "workflow": "Workflow Status",
        "no_blockers": "No blocking issues reported by existing services.",
        "no_warnings": "No warnings reported.",
        "source": "Source",
        "summary": "Summary",
        "download": "Download",
        "not_available": "Not available in current package.",
        "service_backed": "Service-backed view: the UI reads QDKEP services/reports and does not duplicate business logic.",
        "technical_constants": "Technical constants are intentionally not translated.",
    },
    "de": {
        "app_title": "Quality-Driven Knowledge Engineering Platform",
        "app_caption": "SAP CPI / SAP PI/PO Monitoring zuerst, mit allen QDKEP Quality-Console Funktionen.",
        "package_input": "QDKEP Package Quelle aus ./exports",
        "custom_package_path": "Benutzerdefinierter Pfad...",
        "package_input_hint": "Standardquelle ist das neueste generierte Package unter ./exports. Benutzerdefinierten Pfad nur fuer externe Review-Packages nutzen.",
        "language": "Sprache",
        "navigation": "Navigation",
        "monitoring": "Monitoring Events",
        "scenario_lab_generation": "Scenario Lab & Generation",
        "overview": "QDKEP Dashboard",
        "contract_validation": "Contract Validation",
        "package_builder": "Package Builder",
        "quality_gates": "Quality Gates",
        "ai4biz_export": "AI4BIZ Export",
        "evidence_traceability": "Evidence & Traceability",
        "generators": "Generators",
        "benchmark": "Benchmark",
        "send_feedback": "Send feedback",
        "reports_downloads": "Reports & Downloads",
        "settings": "Settings",
        "status": "Status",
        "issues": "Blocking Issues",
        "warnings": "Warnings",
        "downloads": "Downloads",
        "metrics": "KPI Uebersicht",
        "workflow": "Workflow Status",
        "no_blockers": "Keine Blocking Issues aus bestehenden Services gemeldet.",
        "no_warnings": "Keine Warnings gemeldet.",
        "source": "Quelle",
        "summary": "Zusammenfassung",
        "download": "Download",
        "not_available": "Im aktuellen Package nicht verfuegbar.",
        "service_backed": "Service-backed View: die UI liest QDKEP Services/Reports und dupliziert keine Business Logic.",
        "technical_constants": "Technical constants werden absichtlich nicht uebersetzt.",
    },
}


@dataclass(frozen=True)
class DashboardTranslator:
    language: str = "en"

    def __post_init__(self) -> None:
        if self.language.lower() not in _TRANSLATIONS:
            object.__setattr__(self, "language", "en")
        else:
            object.__setattr__(self, "language", self.language.lower())

    def text(self, key: str) -> str:
        if key in TECHNICAL_CONSTANTS:
            return key
        return _TRANSLATIONS[self.language].get(key, _TRANSLATIONS["en"].get(key, key))

    def map(self) -> Mapping[str, str]:
        return _TRANSLATIONS[self.language]
