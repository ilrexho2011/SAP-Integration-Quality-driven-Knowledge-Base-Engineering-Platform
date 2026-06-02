from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from app.services.llm_client import LLMClient, LLMResult


# The deterministic fallbacks below are the exact bullet sets the generator
# emitted before AI enrichment existed. They are reused verbatim whenever AI is
# disabled or a call fails, so behaviour is unchanged in the no-AI path.
FALLBACK_RUNBOOK = {
    "root_causes": [
        "Payload, mapping, adapter connectivity, authentication, endpoint, or script failure indicated by MPL.",
    ],
    "diagnosis": [
        "Filter MPL by MessageGuid and integration flow name.",
        "Compare failing and last successful executions.",
        "Check payload validity, mapping step, adapter response, credentials, and endpoint availability.",
    ],
    "recovery": [
        "Contain the incident and preserve evidence before mutation.",
        "Apply the smallest approved correction to payload, mapping, adapter, credential, or endpoint configuration.",
        "Reprocess one representative message.",
        "Stop replay and rollback if the same signature persists.",
    ],
}

FALLBACK_KEDB = {
    "root_cause": [
        "Determine the root cause from the exact MPL ErrorMessage and recent configuration changes.",
        "Treat missing payload, parsing, connectivity, authentication, and mapping errors as separate incident families.",
    ],
    "resolution": [
        "Preserve MPL evidence before changing runtime configuration.",
        "Correct the failing configuration, payload, mapping, or connectivity item identified by the error signature.",
        "Reprocess one representative message and validate COMPLETED status.",
    ],
}


@dataclass
class EnrichmentEvidence:
    """Factual MPL/inventory evidence handed to the model. Never invented."""

    signature: str
    object_name: str
    error_text: str
    status: str
    integration_flow_name: str
    system_code: str
    priority: str
    sample_errors: list[str] = field(default_factory=list)


@dataclass
class EnrichedSections:
    """Result of enrichment with full traceability of what came from where."""

    fields: dict[str, list[str]]
    enriched: bool
    provider: str
    model: str
    source: str  # "ai" | "template_fallback"
    note: str = ""

    def trace(self) -> dict[str, Any]:
        return {
            "enriched": self.enriched,
            "provider": self.provider,
            "model": self.model,
            "source": self.source,
            "enriched_fields": sorted(self.fields.keys()) if self.enriched else [],
            "note": self.note,
        }


_SYSTEM_PROMPT = (
    "You are an SAP integration operations engineer authoring one knowledge "
    "artifact for a BM25 keyword-retrieval corpus. Strict rules:\n"
    "1. Use ONLY the evidence provided. Never invent MessageGuid values, "
    "endpoints, adapter names, credentials, configuration paths, or numbers.\n"
    "2. Preserve exact technical strings from the evidence (error text, HTTP "
    "status codes, exception class names, adapter and interface names).\n"
    "3. Write short, action-led bullets. Diagnosis bullets confirm the issue; "
    "recovery bullets resolve it; do not mix the two.\n"
    "4. Prefer one canonical term consistently over synonyms.\n"
    "5. If the evidence is insufficient for a field, return fewer bullets "
    "rather than guessing.\n"
    "Return ONLY a JSON object, no prose, no markdown fences."
)


class SectionEnrichmentService:
    """Optionally enrich the diagnostic knowledge sections with an LLM.

    Scope is deliberately narrow: only Known Root Causes / Diagnosis / Recovery
    for runbooks and Root Cause / Resolution for KEDBs. All other fields
    (metadata, IDs, titles, evidence samples, traceability) stay 100%
    deterministic. When AI is disabled or fails, the platform-standard template
    bullets are returned unchanged, so generation remains non-blocking.
    """

    MIN_BULLET_CHARS = 4
    MAX_BULLETS_PER_FIELD = 6

    def __init__(self, client: LLMClient | None = None) -> None:
        self.client = client or LLMClient()

    def enabled(self) -> bool:
        return self.client.is_enabled()

    # --- runbook -----------------------------------------------------------

    def enrich_runbook(self, evidence: EnrichmentEvidence) -> EnrichedSections:
        if not self.enabled():
            return self._fallback(FALLBACK_RUNBOOK, "ai disabled")
        prompt = self._runbook_prompt(evidence)
        result = self.client.complete(_SYSTEM_PROMPT, prompt)
        parsed = self._parse(result, expected_keys=("root_causes", "diagnosis", "recovery"))
        if parsed is None:
            return self._fallback(FALLBACK_RUNBOOK, result.error or "unparseable response")
        # Backfill any field the model omitted with the template default.
        merged = {key: parsed.get(key) or FALLBACK_RUNBOOK[key] for key in FALLBACK_RUNBOOK}
        return EnrichedSections(
            fields=merged, enriched=True, provider=result.provider, model=result.model, source="ai"
        )

    # --- kedb --------------------------------------------------------------

    def enrich_kedb(self, evidence: EnrichmentEvidence) -> EnrichedSections:
        if not self.enabled():
            return self._fallback(FALLBACK_KEDB, "ai disabled")
        prompt = self._kedb_prompt(evidence)
        result = self.client.complete(_SYSTEM_PROMPT, prompt)
        parsed = self._parse(result, expected_keys=("root_cause", "resolution"))
        if parsed is None:
            return self._fallback(FALLBACK_KEDB, result.error or "unparseable response")
        merged = {key: parsed.get(key) or FALLBACK_KEDB[key] for key in FALLBACK_KEDB}
        return EnrichedSections(
            fields=merged, enriched=True, provider=result.provider, model=result.model, source="ai"
        )

    # --- prompts -----------------------------------------------------------

    def _evidence_block(self, evidence: EnrichmentEvidence) -> str:
        samples = "\n".join(f"  - {s}" for s in evidence.sample_errors[:3]) or "  - (none)"
        return (
            f"system: {evidence.system_code}\n"
            f"interface/integration_flow: {evidence.integration_flow_name}\n"
            f"priority: {evidence.priority}\n"
            f"object_name (canonical): {evidence.object_name}\n"
            f"error_signature: {evidence.signature}\n"
            f"last_status: {evidence.status}\n"
            f"error_text: {evidence.error_text}\n"
            f"sample_error_texts:\n{samples}\n"
        )

    def _runbook_prompt(self, evidence: EnrichmentEvidence) -> str:
        return (
            "Produce the diagnostic knowledge sections for ONE SAP integration "
            "runbook from this evidence.\n\n"
            f"EVIDENCE:\n{self._evidence_block(evidence)}\n"
            "Return JSON with exactly these keys, each a list of short bullet "
            "strings (no leading '*' or '-'):\n"
            '{ "root_causes": [...], "diagnosis": [...], "recovery": [...] }\n'
            "root_causes: the most likely technical causes for THIS error "
            "signature (1-4 bullets).\n"
            "diagnosis: ordered steps to confirm the cause from MPL/SAP "
            "evidence (2-5 bullets).\n"
            "recovery: ordered remediation steps, evidence-preserving and "
            "reversible (2-5 bullets)."
        )

    def _kedb_prompt(self, evidence: EnrichmentEvidence) -> str:
        return (
            "Produce the diagnostic knowledge sections for ONE SAP integration "
            "KEDB (known-error) entry from this evidence.\n\n"
            f"EVIDENCE:\n{self._evidence_block(evidence)}\n"
            "Return JSON with exactly these keys, each a list of short bullet "
            "strings (no leading '*' or '-'):\n"
            '{ "root_cause": [...], "resolution": [...] }\n'
            "root_cause: the underlying cause(s) of THIS known error (1-4 "
            "bullets).\n"
            "resolution: the standard fix, evidence-preserving and validated "
            "(2-5 bullets)."
        )

    # --- parsing / safety --------------------------------------------------

    def _parse(
        self, result: LLMResult, expected_keys: tuple[str, ...]
    ) -> dict[str, list[str]] | None:
        if not result.ok or not result.text:
            return None
        payload = self._extract_json(result.text)
        if not isinstance(payload, dict):
            return None
        cleaned: dict[str, list[str]] = {}
        for key in expected_keys:
            bullets = self._clean_bullets(payload.get(key))
            if bullets:
                cleaned[key] = bullets
        return cleaned or None

    def _extract_json(self, text: str) -> Any:
        text = text.strip()
        # Tolerate ```json fences or surrounding prose.
        fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
        if fenced:
            text = fenced.group(1)
        else:
            brace = re.search(r"\{.*\}", text, re.DOTALL)
            if brace:
                text = brace.group(0)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    def _clean_bullets(self, value: Any) -> list[str]:
        if isinstance(value, str):
            value = [value]
        if not isinstance(value, list):
            return []
        out: list[str] = []
        for item in value:
            text = re.sub(r"^\s*[\*\-•]\s*", "", str(item)).strip()
            text = re.sub(r"\s+", " ", text)
            if len(text) >= self.MIN_BULLET_CHARS:
                out.append(text)
            if len(out) >= self.MAX_BULLETS_PER_FIELD:
                break
        return out

    def _fallback(self, defaults: dict[str, list[str]], note: str) -> EnrichedSections:
        return EnrichedSections(
            fields=dict(defaults),
            enriched=False,
            provider=self.client.provider,
            model=self.client.model,
            source="template_fallback",
            note=note,
        )
