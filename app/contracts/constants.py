from __future__ import annotations

CONTRACT_VERSION = "QDKEP_OUTPUT_CONTRACT_v1.1"
CONTRACT_SOURCE_EN = "docs/contracts/QDKEP_Output_Ingestion_Contract_v1_EN.md"
CONTRACT_SOURCE_SQ = "docs/contracts/QDKEP_Output_Ingestion_Contract_v1_SQ.md"

ARTIFACT_TYPES = {"RB": "runbook", "KB": "kedb", "DOC": "documentation"}
ALLOWED_PRIORITIES = {"P1", "P2", "P3", "P4"}

MANDATORY_METADATA_ORDER = [
    "environment",
    "customer_id",
    "system_id",
    "sap_sid",
    "artifact_type",
    "object_name",
    "priority",
    "version",
]

RECOMMENDED_METADATA_ORDER = [
    "interface_id",
    "interface_name",
    "integration_flow_id",
    "integration_flow_name",
    "package_name",
    "review_cycle",
    "review_status",
    "doc_subtype",
    "source_file",
    "generated_at",
    "generator_version",
]

STABLE_METADATA_ORDER = MANDATORY_METADATA_ORDER + RECOMMENDED_METADATA_ORDER

RUNBOOK_REQUIRED_HEADINGS = [
    "1. PURPOSE",
    "2. BUSINESS CONTEXT",
    "3. TECHNICAL LANDSCAPE",
    "4. MONITORING AND MPL EVIDENCE",
    "5. ERROR SIGNATURE",
    "6. KNOWN ROOT CAUSES",
    "7. PREREQUISITES FOR INVESTIGATION",
    "8. DIAGNOSIS STEPS",
    "9. RECOVERY STEPS",
    "10. ESCALATION CRITERIA",
    "11. POST-FIX VALIDATION",
]

RUNBOOK_SACRED_HEADINGS = {
    "5. ERROR SIGNATURE",
    "8. DIAGNOSIS STEPS",
    "9. RECOVERY STEPS",
    "10. ESCALATION CRITERIA",
}

KEDB_REQUIRED_HEADINGS = [
    "1. SYMPTOM",
    "2. ERROR PATTERN",
    "3. ROOT CAUSE",
    "4. DIAGNOSIS SIGNALS",
    "5. RESOLUTION",
    "6. VALIDATION",
    "7. WORKAROUND",
    "8. RELATED ARTIFACTS",
]

KEDB_REQUIRED_BLOCKS = ["KEDB ID", "KEDB TITLE", "CUSTOMER", "SYSTEM", "PRIORITY", "VERSION"]

DOC_REQUIRED_HEADINGS = [
    "1. PURPOSE",
    "2. SCOPE",
    "3. KEY TERMS",
    "4. CORE EXPLANATION",
    "5. OPERATIONAL RELEVANCE",
    "6. RELATED ARTIFACTS",
]

DOC_REQUIRED_BLOCKS = ["DOC ID", "DOC TITLE"]
