from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal
from collections.abc import Iterable

from app.config import settings
from app.services.ai_assistance_service import AIAssistanceService
from app.services.document_id_service import DocKind, DocumentIdService
from app.services.document_template_service import DocumentTemplateService
from app.services.scenario_lab_config import (
    normalize_archived_mpl_source,
    normalize_generation_mode,
)
from app.services.section_enrichment_service import (
    EnrichmentEvidence,
    SectionEnrichmentService,
)

DocumentType = Literal["catalog_docs", "kedb", "runbooks"]
SourceMode = Literal["live_mpl", "archived_mpl"]


@dataclass(frozen=True)
class GenerationRequest:
    """Structured request for GenerationService (v2.0.9, fix 2.5).

    Replaces the 19-positional/keyword-argument signature of generate() with a
    single, self-documenting value object. Every field keeps the previous
    default, so behaviour is unchanged. generate(**kwargs) remains as a thin
    backward-compatible wrapper that builds this request, so existing callers
    (API, dashboard, tests) need no change.

    Fields are grouped by concern:
      * what to generate: document_type, version, source_system, source_mode
      * generation mode + update inputs: generation_mode, existing_documents_path
      * feedback loop: feedback_source, feedback_path, apply_remediation_hints
      * scenario lab: scenario_lab_run_id, scenario_manifest_path,
        iflow_analysis_report_path
      * source selection: archived_mpl_source
      * duplicate/ID governance: prevent_duplicate_doc_id, prevent_duplicate_id,
        restart_kedb_id_counting, restart_runbook_id_counting
      * multi-customer: customer_id, environment
    """

    document_type: DocumentType
    version: str
    source_system: str = "sap_ci"
    source_mode: SourceMode = "archived_mpl"
    generation_mode: str = "generate"
    existing_documents_path: str | None = None
    feedback_source: str = "none"
    feedback_path: str | None = None
    apply_remediation_hints: bool = False
    scenario_lab_run_id: str | None = None
    scenario_manifest_path: str | None = None
    iflow_analysis_report_path: str | None = None
    archived_mpl_source: str | None = None
    prevent_duplicate_doc_id: bool = False
    prevent_duplicate_id: bool = False
    restart_kedb_id_counting: bool = False
    restart_runbook_id_counting: bool = False
    customer_id: str = "RCMO"
    environment: str = "demo"


@dataclass(frozen=True)
class RuntimeEvent:
    message_guid: str
    integration_flow_name: str
    status: str
    log_start: str
    log_end: str
    sender: str
    receiver: str
    error_text: str
    source_file: str
    evidence_mode: str = "archived_mpl"
    # v2.0.7 incident-filter metadata. These let the generator distinguish a real
    # failure event from an aggregated statistics rollup (e.g. annual interface
    # export rows whose localizedText reads "success=N, failed=M, ..."). They are
    # populated from the MPL raw_object when present and default to empty otherwise.
    record_type: str = ""
    error_category: str = ""
    failed_count: int | None = None


class GenerationService:
    """Generate ingestion-ready Markdown knowledge from MPL evidence and resources.

    The generator is deterministic and template-based. AI provider configuration is
    detected from .env and recorded in the manifest; the deterministic output remains
    non-blocking when no AI key is present. Factual values come only from MPL and
    resources/cpi or resources/pipo evidence.
    """

    OUTPUT_SUBDIR = {
        "catalog_docs": "interface_inventory",
        "kedb": "kedb",
        "runbooks": "runbooks",
    }
    OUTPUT_LABEL = {
        "catalog_docs": "interface_inventory_docs",
        "kedb": "kedb",
        "runbooks": "runbooks",
    }
    OUTPUT_PREFIX = {
        "catalog_docs": "DOC",
        "kedb": "KB",
        "runbooks": "RB",
    }
    MAX_FILENAME_LENGTH = 80
    MAX_OBJECT_NAME_LENGTH = 80

    # Instance attributes initialised per-run (in generate_from_request) or lazily
    # (in _ensure_enrichment_ready). Declared here so static type checkers know
    # their types at the use sites that read them via getattr/hasattr.
    _enrichment_service: SectionEnrichmentService
    _template_service: DocumentTemplateService
    _enrichment_traces: list[dict[str, Any]]
    _evidence_warnings: list[str]
    _duplicate_governance: dict[str, Any]
    _customer_id: str
    _environment: str

    def generate(
        self,
        document_type: DocumentType,
        version: str,
        source_system: str = "sap_ci",
        source_mode: SourceMode = "archived_mpl",
        generation_mode: str = "generate",
        existing_documents_path: str | None = None,
        feedback_source: str = "none",
        feedback_path: str | None = None,
        apply_remediation_hints: bool = False,
        scenario_lab_run_id: str | None = None,
        scenario_manifest_path: str | None = None,
        iflow_analysis_report_path: str | None = None,
        archived_mpl_source: str | None = None,
        prevent_duplicate_doc_id: bool = False,
        prevent_duplicate_id: bool = False,
        restart_kedb_id_counting: bool = False,
        restart_runbook_id_counting: bool = False,
        customer_id: str = "RCMO",
        environment: str = "demo",
    ) -> dict:
        """Backward-compatible wrapper around generate_from_request().

        Existing callers pass keyword arguments exactly as before. New callers
        may build a GenerationRequest and call generate_from_request() directly.
        """
        request = GenerationRequest(
            document_type=document_type,
            version=version,
            source_system=source_system,
            source_mode=source_mode,
            generation_mode=generation_mode,
            existing_documents_path=existing_documents_path,
            feedback_source=feedback_source,
            feedback_path=feedback_path,
            apply_remediation_hints=apply_remediation_hints,
            scenario_lab_run_id=scenario_lab_run_id,
            scenario_manifest_path=scenario_manifest_path,
            iflow_analysis_report_path=iflow_analysis_report_path,
            archived_mpl_source=archived_mpl_source,
            prevent_duplicate_doc_id=prevent_duplicate_doc_id,
            prevent_duplicate_id=prevent_duplicate_id,
            restart_kedb_id_counting=restart_kedb_id_counting,
            restart_runbook_id_counting=restart_runbook_id_counting,
            customer_id=customer_id,
            environment=environment,
        )
        return self.generate_from_request(request)

    def generate_from_request(self, request: GenerationRequest) -> dict:
        # Unpack request into locals so the existing logic below is untouched.
        document_type = request.document_type
        version = request.version
        source_system = request.source_system
        source_mode = request.source_mode
        generation_mode = request.generation_mode
        existing_documents_path = request.existing_documents_path
        feedback_source = request.feedback_source
        feedback_path = request.feedback_path
        apply_remediation_hints = request.apply_remediation_hints
        scenario_lab_run_id = request.scenario_lab_run_id
        scenario_manifest_path = request.scenario_manifest_path
        iflow_analysis_report_path = request.iflow_analysis_report_path
        archived_mpl_source = request.archived_mpl_source
        prevent_duplicate_doc_id = request.prevent_duplicate_doc_id
        prevent_duplicate_id = request.prevent_duplicate_id
        restart_kedb_id_counting = request.restart_kedb_id_counting
        restart_runbook_id_counting = request.restart_runbook_id_counting
        customer_id = request.customer_id
        environment = request.environment

        version = self._validate_version(version)
        if document_type not in self.OUTPUT_SUBDIR:
            raise ValueError(f"Unsupported document type: {document_type}")
        # v2.0.7 (2.8): customer_id and environment are now parameters instead of
        # being hardcoded to RCMO/demo. Defaults preserve existing behaviour; a
        # multi-customer caller supplies the real values (typically resolved from
        # the customer/<CUSTOMER>.yaml context used by CustomerContextValidator).
        customer_id = self._normalize_customer_id(customer_id)
        environment = self._normalize_environment(environment)
        self._customer_id = customer_id
        self._environment = environment
        source_system = self._normalize_system(source_system)
        source_mode = self._normalize_source_mode(source_mode)
        archived_mpl_source = normalize_archived_mpl_source(
            source_system, archived_mpl_source)
        DocumentIdService().ensure_sample_dirs()
        generation_mode = normalize_generation_mode(generation_mode)
        if generation_mode == "generate":
            existing_documents_path = None
            feedback_source = "none"
            feedback_path = None
            apply_remediation_hints = False
        elif not (existing_documents_path or "").strip():
            raise ValueError(
                "Existing generated documents folder is required when generation_mode=update_existing_docs"
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"gen_{self.OUTPUT_LABEL[document_type]}_{source_system}_{source_mode}_{version}_{timestamp}"
        output_dir = (
            settings.exports_dir / "generated_documents" /
            f"{timestamp}_{source_mode}_{version}"
        )
        doc_dir = output_dir / self.OUTPUT_SUBDIR[document_type]
        doc_dir.mkdir(parents=True, exist_ok=True)

        # v2.0.7: collect evidence-loading warnings instead of swallowing them.
        # Corrupt or unreadable MPL/JSON files would previously be skipped
        # silently, producing "successful" but evidence-poor documents. We now
        # surface them in the generation manifest so the operator knows the
        # evidence base was incomplete.
        self._evidence_warnings: list[str] = []

        # v2.0.7 (2.1): optional, non-blocking AI enrichment of the diagnostic
        # sections only. When no provider/key is configured the service reports
        # disabled and the generator keeps emitting the deterministic template
        # bullets. Per-document enrichment outcomes are collected for the manifest.
        self._enrichment_service = SectionEnrichmentService()
        self._enrichment_traces: list[dict[str, Any]] = []

        policies = self._load_policies()
        templates = self._load_template_names()
        events = self._load_combined_runtime_events(
            source_system=source_system,
            preferred_source_mode=source_mode,
            archived_mpl_source=archived_mpl_source,
        )
        inventory = self._load_inventory(source_system)
        existing_documents = self._load_existing_documents(
            existing_documents_path)
        ai_assistance = AIAssistanceService().describe()
        feedback_context = self._load_feedback_context(
            feedback_source, feedback_path, apply_remediation_hints
        )
        scenario_context = self._load_scenario_context(
            scenario_lab_run_id, scenario_manifest_path, iflow_analysis_report_path
        )

        effective_prevent_duplicate_id = bool(
            prevent_duplicate_id or prevent_duplicate_doc_id)
        self._duplicate_governance = {
            "skipped_duplicate_count": 0, "skipped_duplicates": []}
        if document_type == "catalog_docs":
            generated = self._generate_interface_inventory(
                doc_dir,
                events,
                inventory,
                version,
                source_system,
                source_mode,
                existing_documents,
                prevent_duplicate_doc_id=effective_prevent_duplicate_id,
            )
        elif document_type == "kedb":
            generated = self._generate_kedb(
                doc_dir,
                events,
                version,
                source_system,
                source_mode,
                existing_documents,
                restart_id_counting=restart_kedb_id_counting,
                prevent_duplicate_id=effective_prevent_duplicate_id,
                inventory=inventory,
            )
        else:
            generated = self._generate_runbooks(
                doc_dir,
                events,
                version,
                source_system,
                source_mode,
                existing_documents,
                restart_id_counting=restart_runbook_id_counting,
                prevent_duplicate_id=effective_prevent_duplicate_id,
                inventory=inventory,
            )

        manifest_data = self._build_manifest_data(
            request,
            {
                "run_id": run_id,
                "source_system": source_system,
                "source_mode": source_mode,
                "generation_mode": generation_mode,
                "version": version,
                "customer_id": customer_id,
                "environment": environment,
                "archived_mpl_source": archived_mpl_source,
                "effective_prevent_duplicate_id": effective_prevent_duplicate_id,
                "output_dir": output_dir,
                "doc_dir": doc_dir,
                "generated": generated,
                "events": events,
                "inventory": inventory,
                "existing_documents": existing_documents,
                "existing_documents_path": existing_documents_path,
                "feedback_context": feedback_context,
                "scenario_context": scenario_context,
                "policies": policies,
                "templates": templates,
                "ai_assistance": ai_assistance,
            },
        )
        output_dir.mkdir(parents=True, exist_ok=True)
        manifest = output_dir / "generation_manifest.json"
        manifest.write_text(
            json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        generated_with_manifest = [*generated, manifest]
        return {
            "status": manifest_data["status"],
            "mode": manifest_data["generation_mode"],
            "generation_engine_mode": manifest_data["generation_engine_mode"],
            "run_id": run_id,
            "document_type": document_type,
            "document_label": self.OUTPUT_LABEL[document_type],
            "version": version,
            "source_system": source_system,
            "customer_id": customer_id,
            "environment": environment,
            "source_mode": source_mode,
            "preferred_source_mode": source_mode,
            "archived_mpl_source": archived_mpl_source,
            "runtime_evidence_modes": sorted({event.evidence_mode for event in events}),
            "existing_documents_path": str(existing_documents_path or ""),
            "existing_documents_count": len(existing_documents),
            "feedback_source": feedback_context.get("source", "none"),
            "feedback_path": feedback_context.get("path", ""),
            "apply_remediation_hints": bool(feedback_context.get("apply_remediation_hints", False)),
            "feedback_documents_needing_remediation": feedback_context.get(
                "documents_needing_remediation", 0
            ),
            "scenario_lab": scenario_context,
            "scenario_lab_run_id": scenario_context.get("scenario_lab_run_id", ""),
            "output_dir": str(output_dir),
            "document_dir": str(doc_dir),
            "generated_count": len(generated),
            "skipped_duplicate_count": int(
                getattr(self, "_duplicate_governance", {}).get(
                    "skipped_duplicate_count", 0)
            ),
            "skipped_duplicates": list(
                getattr(self, "_duplicate_governance", {}).get(
                    "skipped_duplicates", [])
            ),
            "prevent_duplicate_id": bool(effective_prevent_duplicate_id),
            "generated_files": [str(path) for path in generated_with_manifest],
            "ai_assistance": ai_assistance,
            "message": "Markdown documents generated under exports/generated_documents using combined Live MPL, Archived MPL, Scenario Lab analysis, resources, policies, and templates when available.",
        }

    def _build_manifest_data(
        self, request: GenerationRequest, ctx: dict[str, Any]
    ) -> dict[str, Any]:
        """Assemble the generation manifest from the request and computed context.

        v2.0.9 (2.5): extracted from generate() so the orchestration method no
        longer also owns the ~45-key manifest literal. This method does pure
        assembly; all computation happens in generate_from_request and is passed
        in via ctx.
        """
        generated = ctx["generated"]
        events = ctx["events"]
        feedback_context = ctx["feedback_context"]
        scenario_context = ctx["scenario_context"]
        existing_documents = ctx["existing_documents"]
        skipped_count = int(
            getattr(self, "_duplicate_governance", {}).get(
                "skipped_duplicate_count", 0)
        )
        return {
            "run_id": ctx["run_id"],
            "status": "generated" if (generated or skipped_count) else "blocked",
            "document_type": request.document_type,
            "document_label": self.OUTPUT_LABEL[request.document_type],
            "source_mode": ctx["source_mode"],
            "source_system": ctx["source_system"],
            "customer_id": ctx["customer_id"],
            "environment": ctx["environment"],
            "generation_mode": ctx["generation_mode"],
            "version": ctx["version"],
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "output_dir": str(ctx["output_dir"]),
            "document_dir": str(ctx["doc_dir"]),
            "generated_files": [str(path) for path in generated],
            "generated_count": len(generated),
            "skipped_duplicate_count": skipped_count,
            "skipped_duplicates": list(
                getattr(self, "_duplicate_governance", {}).get(
                    "skipped_duplicates", [])
            ),
            "prevent_duplicate_id": bool(ctx["effective_prevent_duplicate_id"]),
            "runtime_event_count": len(events),
            "runtime_evidence_modes": sorted({event.evidence_mode for event in events}),
            "preferred_source_mode": ctx["source_mode"],
            "archived_mpl_source": ctx["archived_mpl_source"],
            "prevent_duplicate_doc_id": bool(request.prevent_duplicate_doc_id),
            "restart_kedb_id_counting": bool(request.restart_kedb_id_counting),
            "restart_runbook_id_counting": bool(request.restart_runbook_id_counting),
            "existing_documents_path": str(ctx["existing_documents_path"] or ""),
            "existing_documents_count": len(existing_documents),
            "feedback_source": feedback_context.get("source", "none"),
            "feedback_path": feedback_context.get("path", ""),
            "apply_remediation_hints": bool(feedback_context.get("apply_remediation_hints", False)),
            "feedback_documents_needing_remediation": feedback_context.get(
                "documents_needing_remediation", 0
            ),
            "feedback_disqualified_documents": feedback_context.get("disqualified_documents", 0),
            "feedback_governance": feedback_context.get("governance", {}),
            "inventory_object_count": len(ctx["inventory"]),
            "policy_profile": "AI4BIZ_Knowledge_Ingestion_Guide.txt",
            "policy_files": ctx["policies"],
            "template_files": ctx["templates"],
            "ai_assistance": ctx["ai_assistance"],
            "ai_enrichment": self._ai_enrichment_summary(),
            "scenario_lab": scenario_context,
            "scenario_lab_run_id": scenario_context.get("scenario_lab_run_id", ""),
            "scenario_manifest_path": scenario_context.get("scenario_manifest_path", ""),
            "iflow_analysis_report_path": scenario_context.get("iflow_analysis_report_path", ""),
            "generation_engine_mode": self._generation_engine_mode(scenario_context),
            "warnings": self._compose_warnings(generated),
            "evidence_warnings": list(getattr(self, "_evidence_warnings", [])),
        }

    def _load_scenario_context(
        self,
        scenario_lab_run_id: str | None,
        scenario_manifest_path: str | None,
        iflow_analysis_report_path: str | None,
    ) -> dict[str, Any]:
        run_id = (scenario_lab_run_id or "").strip()
        manifest = Path(
            scenario_manifest_path) if scenario_manifest_path else None
        report = Path(
            iflow_analysis_report_path) if iflow_analysis_report_path else None
        if run_id and not manifest:
            candidate = settings.exports_dir / "scenario_lab" / \
                run_id / "scenario_manifest.json"
            if candidate.exists():
                manifest = candidate
        if run_id and not report:
            candidate = (
                settings.exports_dir / "scenario_lab" / run_id / "iflow_analysis_report.json"
            )
            if candidate.exists():
                report = candidate
        context: dict[str, Any] = {
            "enabled": bool(run_id or manifest or report),
            "scenario_lab_run_id": run_id,
            "scenario_manifest_path": str(manifest or ""),
            "iflow_analysis_report_path": str(report or ""),
            "iflow_count": 0,
            "design_evidence_sources": [],
            "runtime_evidence_sources": [],
            "warnings": [],
        }
        if manifest and manifest.exists():
            try:
                payload = json.loads(manifest.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    context["scenario_lab_run_id"] = context["scenario_lab_run_id"] or str(
                        payload.get("scenario_lab_run_id", "")
                    )
                    context["design_evidence_sources"] = payload.get(
                        "design_evidence_sources", [])
                    context["runtime_evidence_sources"] = payload.get(
                        "runtime_evidence_sources", []
                    )
                    context["iflow_count"] = payload.get("iflow_count", 0)
            except Exception:
                context["warnings"].append(
                    "scenario_manifest could not be parsed")
        elif manifest:
            context["warnings"].append("scenario_manifest not found")
        if report and report.exists():
            try:
                payload = json.loads(report.read_text(encoding="utf-8"))
                if isinstance(payload, dict):
                    context["iflow_count"] = payload.get(
                        "records_count", context.get("iflow_count", 0)
                    )
            except Exception:
                context["warnings"].append(
                    "iflow_analysis_report could not be parsed")
        elif report:
            context["warnings"].append("iflow_analysis_report not found")
        return context

    def _load_feedback_context(
        self, feedback_source: str, feedback_path: str | None, apply_remediation_hints: bool
    ) -> dict[str, Any]:
        source = (feedback_source or "none").strip().lower()
        if source not in {"none", "latest", "selected"}:
            source = "none"
        if source == "none" or not apply_remediation_hints:
            return {"source": "none", "apply_remediation_hints": False}
        target: Path | None = None
        if source == "selected" and feedback_path:
            target = Path(feedback_path)
        elif source == "latest":
            candidates = (
                sorted(
                    settings.feedback_dir.glob("*_feedback.json"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                if settings.feedback_dir.exists()
                else []
            )
            target = candidates[0] if candidates else None
        if not target or not target.exists():
            return {
                "source": source,
                "path": str(target or ""),
                "apply_remediation_hints": False,
                "warning": "feedback file not found",
            }
        try:
            payload = json.loads(target.read_text(encoding="utf-8"))
        except Exception:
            return {
                "source": source,
                "path": str(target),
                "apply_remediation_hints": False,
                "warning": "feedback file could not be parsed",
            }
        if not isinstance(payload, dict):
            payload = {}
        return {
            "source": source,
            "path": str(target),
            "apply_remediation_hints": bool(apply_remediation_hints),
            "documents_needing_remediation": payload.get("documents_needing_remediation", 0),
            "disqualified_documents": payload.get("disqualified_documents", 0),
            "governance": payload.get("governance", {}),
            "document_feedback_count": len(payload.get("document_feedback", []))
            if isinstance(payload.get("document_feedback"), list)
            else 0,
        }

    def _generate_interface_inventory(
        self,
        out: Path,
        events: list[RuntimeEvent],
        inventory: list[dict[str, Any]],
        version: str,
        system: str,
        source_mode: str,
        existing_documents: list[dict[str, str]] | None = None,
        prevent_duplicate_doc_id: bool = False,
    ) -> list[Path]:
        by_iflow: dict[str, list[RuntimeEvent]] = defaultdict(list)
        for event in events:
            by_iflow[event.integration_flow_name or "UNKNOWN_IFLOW"].append(
                event)
        for item in inventory:
            iflow = str(item.get("iflow_name") or item.get(
                "integration_flow_name") or "").strip()
            if iflow and iflow not in by_iflow:
                by_iflow[iflow] = []
        files: list[Path] = []
        for index, iflow_name in enumerate(sorted(by_iflow), start=1):
            grouped_events = by_iflow[iflow_name]
            inv = self._find_inventory(inventory, iflow_name)

            # Prefer exact interface/MPL matches. When an interface has no direct MPL record,
            # attach tenant-level MPL evidence explicitly as fallback instead of leaving core
            # traceability fields as "missing". This preserves truthfulness while keeping the
            # generated inventory useful for ingestion, audit, and follow-up monitoring.
            evidence_events = grouped_events if grouped_events else events
            evidence_scope = (
                "interface_specific"
                if grouped_events
                else "tenant_level_fallback_no_exact_interface_match"
            )
            status_counts = Counter(event.status for event in evidence_events)
            sample = self._latest_event(evidence_events)
            object_name = self._object_name_from_text(
                iflow_name, system=system)
            package_name = self._value(
                inv.get("package_name") or inv.get(
                    "package_id"), "unassigned_package"
            )
            package_id = self._value(inv.get("package_id"), package_name)
            sender = self._value(
                inv.get("sender") or (sample.sender if sample else ""),
                "not_available_in_design_or_mpl",
            )
            receiver = self._value(
                inv.get("receiver") or (sample.receiver if sample else ""),
                "not_available_in_design_or_mpl",
            )
            sender_adapter = self._value(
                inv.get("sender_adapter") or inv.get("sender_protocol"),
                "not_available_in_design_export",
            )
            receiver_adapter = self._value(
                inv.get("receiver_adapter") or inv.get("receiver_protocol"),
                "not_available_in_design_export",
            )
            runtime_source = self._value(
                sample.source_file if sample else inv.get("source"),
                "not_available_in_loaded_sources",
            )
            runtime_modes = (
                ", ".join(
                    sorted({event.evidence_mode for event in evidence_events}))
                if evidence_events
                else "not_available_in_loaded_runtime_evidence"
            )
            last_guid = self._value(
                sample.message_guid if sample else "", "not_available_in_loaded_runtime_evidence"
            )
            last_timestamp = self._value(
                sample.log_start if sample else "", "not_available_in_loaded_runtime_evidence"
            )
            status_breakdown = (
                dict(status_counts) if status_counts else {
                    "NO_RUNTIME_EVENTS_LOADED": 0}
            )
            if grouped_events:
                mpl_total_line = str(len(grouped_events))
            else:
                mpl_total_line = f"0 exact interface events; tenant-level fallback events available: {len(events)}"
            inventory_sources = self._join_values(
                inv.get("sources") or inv.get(
                    "source"), "not_available_in_design_export"
            )
            description = self._value(
                inv.get("description") or inv.get("short_text"),
                "No design-time description available in resources/cpi or resources/pipo.",
            )
            doc_decision = DocumentIdService().decide_doc_id(
                system, object_name, prevent_duplicate=prevent_duplicate_doc_id
            )
            if doc_decision.action == "skip_duplicate" and doc_decision.duplicate_path:
                self._record_duplicate_skip(
                    "catalog_docs", iflow_name, doc_decision.duplicate_path)
                continue
            file_path = out / \
                self._safe_filename("DOC", system, object_name, "P3", version)
            lines = [
                f"# {self._readable_title(iflow_name)}",
                "",
                f'environment: "{self._active_environment()}"',
                f'customer_id: "{self._active_customer_id()}"',
                f'system_id: "{self._system_id(system)}"',
                f'sap_sid: "{self._system_code(system)}"',
                'artifact_type: "documentation"',
                f'object_name: "{object_name}"',
                'priority: "P3"',
                f'version: "{version}"',
                f'interface_id: "{iflow_name}"',
                f'integration_flow_id: "{self._value(inv.get("iflow_id"), iflow_name)}"',
                f'integration_flow_name: "{iflow_name}"',
                f'package_name: "{package_name}"',
                'review_cycle: "monthly"',
                f'source_mode: "{source_mode}"',
                f'runtime_evidence_scope: "{evidence_scope}"',
                f'runtime_evidence_modes: "{runtime_modes}"',
                "",
                "DOC ID",
                doc_decision.document_id,
                "",
                "DOC TITLE",
                self._readable_title(iflow_name),
                "",
                "1. PURPOSE",
                f"* Maintain an atomic integration inventory reference for interface {iflow_name}.",
                "* Use this document for discovery, impact analysis, monitoring, and RAG retrieval.",
                "2. SCOPE",
                f"* Package: {package_name}",
                f"* Package ID: {package_id}",
                f"* System: `{self._system_code(system)}`",
                f"* Design-time present: {bool(inv)}",
                f"* Runtime present for this interface: {bool(grouped_events)}",
                f"* Runtime evidence scope: {evidence_scope}",
                f"* Evidence coverage level: {'high' if inv and grouped_events else 'medium' if inv and evidence_events else 'tenant_fallback' if evidence_events else 'low'}",
                f"* Description: {description}",
                "3. KEY TERMS",
                f"* {iflow_name}",
                f"* {object_name}",
                f"* {package_name}",
                f"* {source_mode}",
                "* combined_live_and_archived_mpl_evidence",
                "4. CORE EXPLANATION",
                f"* Runtime binding: {iflow_name}",
                f"* Participants: Sender={sender}, Receiver={receiver}",
                f"* Adapters: Sender adapter={sender_adapter}, Receiver adapter={receiver_adapter}",
                f"* Activities: Process SAP integration messages for {iflow_name}; preserve runtime evidence from MPL before changing configuration.",
                f"* Resources: Package={package_name}; source-backed fields are derived from resources/cpi, resources/pipo, and MPL JSON files.",
                "5. OPERATIONAL RELEVANCE",
                f"* MPL total observed: {mpl_total_line}",
                f"* MPL status breakdown: {status_breakdown}",
                f"* Last observed MessageGuid: {last_guid}",
                f"* Last observed timestamp: {last_timestamp}",
                f"* Last runtime status: {self._value(sample.status if sample else '', 'not_available_in_loaded_runtime_evidence')}",
                "6. RELATED ARTIFACTS",
                f"* Recommended KEDB family seed: {self._error_signature(sample.error_text if sample else '')}",
                "* Recommended runbook: generate from Monitoring & Generation when an error pattern is observed.",
                "7. TRACEABILITY",
                f"* Source mode: {source_mode}",
                f"* Runtime source file: {runtime_source}",
                f"* Runtime evidence modes: {runtime_modes}",
                f"* Runtime evidence scope: {evidence_scope}",
                f"* Design source files: {inventory_sources}",
                f"* Existing documents considered: {len(existing_documents or [])}",
                f"* ID governance action: {doc_decision.action}",
                "* Policy source: resources/policies/AI4BIZ_Knowledge_Ingestion_Guide.txt",
                "8. RISKS AND OPEN POINTS",
                "* If runtime evidence scope is tenant_level_fallback_no_exact_interface_match, run a targeted MPL extraction for this interface before operational release.",
                "* Complete sender, receiver, adapter, endpoint, and credential alias fields from tenant export when not present in design or MPL evidence.",
            ]
            file_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            files.append(file_path)
        return files

    def _generate_kedb(
        self,
        out: Path,
        events: list[RuntimeEvent],
        version: str,
        system: str,
        source_mode: str,
        existing_documents: list[dict[str, str]] | None = None,
        restart_id_counting: bool = False,
        prevent_duplicate_id: bool = False,
        inventory: list[dict[str, Any]] | None = None,
    ) -> list[Path]:
        self._ensure_enrichment_ready()
        error_events = [event for event in events if self._is_error(event)]
        groups = self._group_error_patterns(error_events)
        files: list[Path] = []
        id_sequence = (
            0
            if restart_id_counting
            else DocumentIdService().last_document_sequence(system, "kedb", "KEDB")
        )
        existing_signature_index = (
            self._existing_signature_index(
                system, "kedb") if prevent_duplicate_id else {}
        )
        for index, (signature, grouped) in enumerate(groups.items(), start=1):
            sample = grouped[0]
            inventory_item = self._find_inventory(
                inventory or [], sample.integration_flow_name)
            priority = self._classify_priority(
                signature, sample.error_text, inventory_item=inventory_item
            )
            object_name = self._object_name_from_text(
                signature, system=system, error_text=sample.error_text
            )
            existing_signature_path = (
                self._find_existing_signature_path(
                    object_name, existing_signature_index)
                if prevent_duplicate_id
                else None
            )
            if existing_signature_path:
                self._record_duplicate_skip(
                    "kedb", signature, str(existing_signature_path))
                continue
            id_sequence += 1
            base_decision = DocumentIdService().decide_numbered_id(
                system, "kedb", priority, restart=True
            )
            id_decision = type(base_decision)(
                document_id=f"KEDB-{priority}-{id_sequence:04d}",
                next_sequence=id_sequence,
                action="restart_counting" if restart_id_counting else "continue_after_last",
            )
            file_path = self._unique_output_path(
                out /
                self._safe_filename("KB", system, object_name,
                                    priority, version), id_sequence
            )
            evidence = self._build_enrichment_evidence(
                signature, object_name, priority, system, grouped
            )
            enriched = self._enrichment_service.enrich_kedb(evidence)
            self._record_enrichment_trace(
                id_decision.document_id, object_name, enriched)
            runtime_modes = sorted({event.evidence_mode for event in grouped})
            context = {
                "title": self._readable_title(signature, sample.error_text),
                "environment": self._active_environment(),
                "customer_id": self._active_customer_id(),
                "system_id": self._system_id(system),
                "sap_sid": self._system_code(system),
                "object_name": object_name,
                "priority": priority,
                "interface_id": sample.integration_flow_name,
                "integration_flow_id": sample.integration_flow_name,
                "integration_flow_name": sample.integration_flow_name,
                "package_name": "Multiple packages",
                "review_cycle": "monthly",
                "version": version,
                "source_mode": source_mode,
                "runtime_evidence_modes": ", ".join(runtime_modes) if grouped else "missing",
                "runtime_evidence_modes_joined": ", ".join(runtime_modes),
                "document_id": id_decision.document_id,
                "signature": signature,
                "symptom": self._symptom_from_signature(signature, sample.error_text),
                "observed_count": len(grouped),
                "evidence_lines": [
                    f"Evidence: {ev.log_start} | MessageGuid {ev.message_guid} | Interface {ev.integration_flow_name} | Status {ev.status} | Error: {self._short(ev.error_text, 280)}"
                    for ev in grouped[:3]
                ],
                "root_cause": self._clean_bullet_text(enriched.fields["root_cause"]),
                "resolution": self._clean_bullet_text(enriched.fields["resolution"]),
                "related_runbook": self._safe_filename(
                    "RB", system, object_name, priority, version
                ),
                "existing_documents_count": len(existing_documents or []),
                "id_governance_action": id_decision.action,
            }
            file_path.write_text(self._template_service.render(
                "kedb", context), encoding="utf-8")
            files.append(file_path)
        return files

    def _generate_runbooks(
        self,
        out: Path,
        events: list[RuntimeEvent],
        version: str,
        system: str,
        source_mode: str,
        existing_documents: list[dict[str, str]] | None = None,
        restart_id_counting: bool = False,
        prevent_duplicate_id: bool = False,
        inventory: list[dict[str, Any]] | None = None,
    ) -> list[Path]:
        self._ensure_enrichment_ready()
        error_events = [event for event in events if self._is_error(event)]
        groups = self._group_error_patterns(error_events)
        files: list[Path] = []
        id_sequence = (
            0
            if restart_id_counting
            else DocumentIdService().last_document_sequence(system, "runbooks", "RB")
        )
        existing_signature_index = (
            self._existing_signature_index(
                system, "runbooks") if prevent_duplicate_id else {}
        )
        for index, (signature, grouped) in enumerate(groups.items(), start=1):
            sample = grouped[0]
            inventory_item = self._find_inventory(
                inventory or [], sample.integration_flow_name)
            priority = self._classify_priority(
                signature, sample.error_text, inventory_item=inventory_item
            )
            object_name = self._object_name_from_text(
                signature, system=system, error_text=sample.error_text
            )
            existing_signature_path = (
                self._find_existing_signature_path(
                    object_name, existing_signature_index)
                if prevent_duplicate_id
                else None
            )
            if existing_signature_path:
                self._record_duplicate_skip(
                    "runbooks", signature, str(existing_signature_path))
                continue
            id_sequence += 1
            base_decision = DocumentIdService().decide_numbered_id(
                system, "runbooks", priority, restart=True
            )
            id_decision = type(base_decision)(
                document_id=f"RB-{priority}-{id_sequence:04d}",
                next_sequence=id_sequence,
                action="restart_counting" if restart_id_counting else "continue_after_last",
            )
            file_path = self._unique_output_path(
                out /
                self._safe_filename("RB", system, object_name,
                                    priority, version), id_sequence
            )
            evidence = self._build_enrichment_evidence(
                signature, object_name, priority, system, grouped
            )
            enriched = self._enrichment_service.enrich_runbook(evidence)
            self._record_enrichment_trace(
                id_decision.document_id, object_name, enriched)
            runtime_modes = sorted({event.evidence_mode for event in grouped})
            context = {
                "title": self._readable_title(signature, sample.error_text),
                "environment": self._active_environment(),
                "customer_id": self._active_customer_id(),
                "system_id": self._system_id(system),
                "sap_sid": self._system_code(system),
                "object_name": object_name,
                "priority": priority,
                "interface_id": sample.integration_flow_name,
                "integration_flow_id": sample.integration_flow_name,
                "integration_flow_name": sample.integration_flow_name,
                "package_name": "Multiple packages",
                "review_cycle": "monthly",
                "version": version,
                "source_mode": source_mode,
                "runtime_evidence_modes": ", ".join(runtime_modes) if grouped else "missing",
                "runtime_evidence_modes_joined": ", ".join(runtime_modes),
                "document_id": id_decision.document_id,
                "signature": signature,
                "observed_count": len(grouped),
                "existing_documents_count": len(existing_documents or []),
                "evidence_lines": [
                    f"Sample {i} | {ev.log_start} | MessageGuid {ev.message_guid} | Interface {ev.integration_flow_name} | Error: {self._short(ev.error_text, 260)}"
                    for i, ev in enumerate(grouped[:3], start=1)
                ],
                "root_causes": self._clean_bullet_text(enriched.fields["root_causes"]),
                "diagnosis": self._clean_bullet_text(enriched.fields["diagnosis"]),
                "recovery": self._clean_bullet_text(enriched.fields["recovery"]),
            }
            file_path.write_text(
                self._template_service.render("runbook", context), encoding="utf-8"
            )
            files.append(file_path)
        return files

    def _ensure_enrichment_ready(self) -> None:
        """Lazily initialise enrichment state so the per-document generators can
        be called directly (e.g. in unit tests) without going through generate()."""
        if not hasattr(self, "_enrichment_service") or self._enrichment_service is None:
            self._enrichment_service = SectionEnrichmentService()
        if not hasattr(self, "_enrichment_traces"):
            self._enrichment_traces = []
        if not hasattr(self, "_template_service") or self._template_service is None:
            self._template_service = DocumentTemplateService()

    def _build_enrichment_evidence(
        self,
        signature: str,
        object_name: str,
        priority: str,
        system: str,
        grouped: list[RuntimeEvent],
    ) -> EnrichmentEvidence:
        sample = grouped[0]
        sample_errors = [
            self._short(ev.error_text, 280)
            for ev in grouped[:3]
            if ev.error_text and ev.error_text != "missing"
        ]
        return EnrichmentEvidence(
            signature=signature,
            object_name=object_name,
            error_text=self._short(sample.error_text, 600),
            status=sample.status,
            integration_flow_name=sample.integration_flow_name,
            system_code=self._system_code(system),
            priority=priority,
            sample_errors=sample_errors,
        )

    def _bullets(self, items: list[str]) -> list[str]:
        """Render a list of bullet strings as governed Markdown bullet lines."""
        return [f"* {text}" for text in self._clean_bullet_text(items)]

    def _clean_bullet_text(self, items: list[str]) -> list[str]:
        """Return bullet texts without the leading marker (templates add '* ')."""
        return [re.sub(r"^[*-]\s*", "", item).strip() for item in items if item and item.strip()]

    def _record_enrichment_trace(self, document_id: str, object_name: str, sections: Any) -> None:
        trace = getattr(self, "_enrichment_traces", None)
        if trace is None:
            return
        entry = {"document_id": document_id, "object_name": object_name}
        entry.update(sections.trace())
        trace.append(entry)

    def _ai_enrichment_summary(self) -> dict[str, Any]:
        """Aggregate per-document enrichment outcomes for the manifest.

        This is the real traceability for fix 2.1: it reports the provider/model
        actually used and exactly how many documents were AI-enriched versus
        served from the deterministic template fallback.
        """
        traces = list(getattr(self, "_enrichment_traces", []))
        service = getattr(self, "_enrichment_service", None)
        enriched = [t for t in traces if t.get("enriched")]
        return {
            "enabled": bool(service.enabled()) if service is not None else False,
            "provider": service.client.provider if service is not None else "none",
            "model": service.client.model if service is not None else "",
            "documents_total": len(traces),
            "documents_ai_enriched": len(enriched),
            "documents_template_fallback": len(traces) - len(enriched),
            "scope": ["root_cause", "diagnosis", "recovery"],
            "non_blocking": True,
            "traces": traces,
        }

    def _generation_engine_mode(self, scenario_context: dict[str, Any]) -> str:
        if scenario_context.get("enabled"):
            return "scenario_lab_enriched"
        traces = getattr(self, "_enrichment_traces", [])
        if any(t.get("enriched") for t in traces):
            return "template_based_ai_enriched"
        return "template_based"

    def _record_duplicate_skip(
        self, document_type: str, signature: str, existing_path: str
    ) -> None:
        governance = getattr(self, "_duplicate_governance", None)
        if not isinstance(governance, dict):
            governance = {"skipped_duplicate_count": 0,
                          "skipped_duplicates": []}
            self._duplicate_governance = governance
        governance["skipped_duplicate_count"] = (
            int(governance.get("skipped_duplicate_count", 0)) + 1
        )
        governance.setdefault("skipped_duplicates", []).append(
            {
                "document_type": document_type,
                "signature": signature,
                "existing_path": existing_path,
                "action": "skip_duplicate",
            }
        )

    def _normalize_signature_for_duplicate_check(self, value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9]+", " ", value or "")).strip().lower()

    def _extract_object_name_value(self, text: str) -> str:
        """Return the governed object_name metadata value from a document body."""
        match = re.search(
            r'^\s*object_name\s*:\s*"?([^"\n]+)"?\s*$', text, re.MULTILINE | re.IGNORECASE
        )
        return match.group(1).strip() if match else ""

    def _existing_signature_index(self, system: str, kind: DocKind) -> dict[str, Path]:
        """Index existing documents by their canonical object_name.

        v2.0.7 fix: the previous implementation concatenated the whole document
        body and used a substring test, which produced false positives (a short
        signature such as "unauthorized" matched any document merely mentioning
        the word) and false negatives (minor word-order changes). Keying on the
        stable object_name metadata gives O(1), exact, governance-grade matching.
        When a document predates object_name metadata, we fall back to the
        normalized title line so older corpora still de-duplicate.
        """
        index: dict[str, Path] = {}
        svc = DocumentIdService()
        for path in svc._iter_files(system, kind):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            object_name = self._extract_object_name_value(text)
            if not object_name:
                # Fallback: first markdown title line.
                title = next(
                    (
                        line.lstrip("# ").strip()
                        for line in text.splitlines()
                        if line.startswith("#")
                    ),
                    path.stem,
                )
                object_name = self._object_name_from_text(title, system=system)
            key = self._normalize_signature_for_duplicate_check(object_name)
            if key:
                index.setdefault(key, path)
        return index

    def _find_existing_signature_path(
        self, object_name: str, index: dict[str, Path]
    ) -> Path | None:
        """Return the path of an existing document with the same canonical object_name."""
        if not isinstance(index, dict):
            return None
        key = self._normalize_signature_for_duplicate_check(object_name)
        if not key:
            return None
        return index.get(key)

    def _extract_existing_document_id(self, path: Path, marker: str) -> str:
        try:
            lines = path.read_text(
                encoding="utf-8", errors="ignore").splitlines()
        except Exception:
            return ""
        for index, line in enumerate(lines):
            if line.strip().lower() == marker.lower() and index + 1 < len(lines):
                return lines[index + 1].strip()
        return ""

    def _load_policies(self) -> list[str]:
        policy_dir = settings.resources_dir / "policies"
        primary = policy_dir / "AI4BIZ_Knowledge_Ingestion_Guide.txt"
        files = []
        if primary.exists():
            files.append(str(primary.relative_to(settings.project_root)))
        if policy_dir.exists():
            for path in sorted(policy_dir.glob("*")):
                if path.is_file() and path != primary and not path.name.startswith("."):
                    files.append(str(path.relative_to(settings.project_root)))
        return files

    def _load_template_names(self) -> list[str]:
        template_dir = settings.resources_dir / "templates"
        if not template_dir.exists():
            return []
        return [
            str(path.relative_to(settings.project_root))
            for path in sorted(template_dir.glob("*.md"))
        ]

    def _load_inventory(self, source_system: str) -> list[dict[str, Any]]:
        """Load design/configuration evidence from resources.

        CPI inventory is built primarily from resources/cpi/output Excel exports because
        they contain concrete iFlow, participant, and channel data. Package-list JSON is
        used as package metadata, not as standalone interface records when iFlow exports
        exist. This avoids generating package-level interface docs with empty MPL fields.
        """
        items_by_name: dict[str, dict[str, Any]] = {}
        package_names: dict[str, str] = {}

        def add_source(item: dict[str, Any], source: str) -> None:
            sources = item.setdefault("sources", [])
            if source and source not in sources:
                sources.append(source)
            if source and not item.get("source"):
                item["source"] = source

        if source_system == "sap_ci":
            packages_path = settings.resources_dir / \
                "cpi" / "available_packages_and_iflows.json"
            if packages_path.exists():
                data = self._read_json(packages_path)
                for package in data.get("packages", []) if isinstance(data, dict) else []:
                    package_id = str(package.get("package_id") or "").strip()
                    package_name = str(package.get(
                        "name") or package_id).strip()
                    if package_id:
                        package_names[package_id] = package_name

            output_dir = settings.resources_dir / "cpi" / "output"
            if output_dir.exists():
                for path in sorted(output_dir.glob("*_iflow.xlsx")):
                    for row in self._read_xlsx_rows(path):
                        iflow_name = self._value(row.get("ifw_name"), "")
                        if not iflow_name:
                            continue
                        package_id = self._value(
                            row.get("ifw_package_id"), "unassigned_package")
                        item = items_by_name.setdefault(
                            iflow_name, {"iflow_name": iflow_name})
                        item.update(
                            {
                                "iflow_id": self._value(row.get("ifw_id"), iflow_name),
                                "package_id": package_id,
                                "package_name": package_names.get(package_id, package_id),
                                "description": self._value(row.get("ifw_description"), ""),
                                "sender": self._value(
                                    row.get("ifw_sender"), item.get(
                                        "sender", "")
                                ),
                                "receiver": self._value(
                                    row.get("ifw_receiver"), item.get(
                                        "receiver", "")
                                ),
                                "iflow_version": self._value(row.get("ifw_version"), ""),
                                "created_at": self._value(row.get("ifw_created_at"), ""),
                                "modified_at": self._value(row.get("ifw_modified_at"), ""),
                            }
                        )
                        # v2.0.7 (2.9): capture interface priority/criticality when the
                        # inventory carries it (Interface Inventory schema field). Used
                        # as the authoritative priority source for KEDB/runbook docs.
                        inventory_priority = self._value(
                            row.get("ifw_priority"), ""
                        ) or self._value(row.get("priority"), "")
                        inventory_criticality = self._value(
                            row.get("ifw_criticality"), ""
                        ) or self._value(row.get("criticality"), "")
                        if inventory_priority:
                            item["priority"] = inventory_priority
                        if inventory_criticality:
                            item["criticality"] = inventory_criticality
                        add_source(
                            item, str(path.relative_to(settings.project_root)))

                for path in sorted(output_dir.glob("*_iflow_participant.xlsx")):
                    for row in self._read_xlsx_rows(path):
                        iflow_name = self._value(row.get("par_iflow_name"), "")
                        if not iflow_name:
                            continue
                        item = items_by_name.setdefault(
                            iflow_name, {"iflow_name": iflow_name})
                        package_id = self._value(
                            row.get("par_package_id"), item.get(
                                "package_id", "unassigned_package")
                        )
                        item.setdefault("package_id", package_id)
                        item.setdefault("package_name", package_names.get(
                            package_id, package_id))
                        participant_name = self._value(row.get("par_name"), "")
                        participant_type = self._value(
                            row.get("par_type"), "").lower()
                        if "sender" in participant_type and participant_name:
                            item["sender"] = participant_name
                        if "receiver" in participant_type and participant_name:
                            item["receiver"] = participant_name
                        add_source(
                            item, str(path.relative_to(settings.project_root)))

                for path in sorted(output_dir.glob("*_iflow_channel.xlsx")):
                    for row in self._read_xlsx_rows(path):
                        iflow_name = self._value(row.get("chn_iflow_name"), "")
                        if not iflow_name:
                            continue
                        item = items_by_name.setdefault(
                            iflow_name, {"iflow_name": iflow_name})
                        package_id = self._value(
                            row.get("chn_package_id"), item.get(
                                "package_id", "unassigned_package")
                        )
                        item.setdefault("package_id", package_id)
                        item.setdefault("package_name", package_names.get(
                            package_id, package_id))
                        participant_type = self._value(
                            row.get("chn_type"), "").lower()
                        participant_name = self._value(
                            row.get("chn_participant_name"), "").lower()
                        adapter = self._value(
                            row.get("chn_component_type")
                            or row.get("chn_transport_protocol")
                            or row.get("chn_name"),
                            "",
                        )
                        protocol = self._value(
                            row.get("chn_transport_protocol") or row.get(
                                "chn_message_protocol"), ""
                        )
                        address = self._value(row.get("chn_address"), "")
                        if "sender" in participant_type or "sender" in participant_name:
                            item["sender_adapter"] = adapter or item.get(
                                "sender_adapter", "")
                            item["sender_protocol"] = protocol or item.get(
                                "sender_protocol", "")
                            item["sender_endpoint"] = address or item.get(
                                "sender_endpoint", "")
                            item.setdefault("sender", self._value(
                                row.get("chn_system"), "Sender"))
                        elif adapter or protocol or address:
                            item["receiver_adapter"] = adapter or item.get(
                                "receiver_adapter", "")
                            item["receiver_protocol"] = protocol or item.get(
                                "receiver_protocol", ""
                            )
                            item["receiver_endpoint"] = address or item.get(
                                "receiver_endpoint", "")
                            item.setdefault(
                                "receiver", self._value(
                                    row.get("chn_system"), "Receiver")
                            )
                        add_source(
                            item, str(path.relative_to(settings.project_root)))

            bpmn_dir = settings.resources_dir / "cpi" / "input"
            if bpmn_dir.exists():
                for path in sorted(bpmn_dir.rglob("*.iflw")):
                    name = path.stem.split(" --- ")[-1]
                    package = (
                        path.stem.split(" --- ")[0]
                        if " --- " in path.stem
                        else "unassigned_package"
                    )
                    item = items_by_name.setdefault(name, {"iflow_name": name})
                    item.setdefault("package_name", package)
                    item.setdefault("package_id", package)
                    add_source(
                        item, str(path.relative_to(settings.project_root)))

            # Fallback only when no concrete iFlow inventory exists.
            if not items_by_name and packages_path.exists():
                data = self._read_json(packages_path)
                for package in data.get("packages", []) if isinstance(data, dict) else []:
                    package_name = package.get(
                        "name") or package.get("package_id")
                    if package_name:
                        items_by_name[str(package_name)] = {
                            "iflow_name": str(package_name),
                            "package_id": package.get("package_id"),
                            "package_name": package_name,
                            "short_text": package.get("short_text"),
                            "source": str(packages_path.relative_to(settings.project_root)),
                            "sources": [str(packages_path.relative_to(settings.project_root))],
                        }
        else:
            config_path = settings.resources_dir / "pipo" / "config_used.redacted.json"
            if config_path.exists():
                data = self._read_json(config_path)
                services = str(data.get("PIPO_DIR_SERVICES", "")
                               if isinstance(data, dict) else "")
                for service in [s.strip() for s in services.split(",") if s.strip()]:
                    items_by_name[service] = {
                        "iflow_name": service,
                        "package_name": "PI/PO Directory",
                        "package_id": "PIPO_DIR",
                        "source": str(config_path.relative_to(settings.project_root)),
                        "sources": [str(config_path.relative_to(settings.project_root))],
                    }
        return list(items_by_name.values())

    def _read_xlsx_rows(self, path: Path) -> list[dict[str, Any]]:
        try:
            openpyxl = __import__("openpyxl")
            load_workbook = getattr(openpyxl, "load_workbook")
        except Exception:
            return []
        try:
            workbook = load_workbook(path, read_only=True, data_only=True)
            sheet = workbook.active
            if sheet is None:
                return []
            rows = list(sheet.iter_rows(values_only=True))
        except Exception:
            return []
        if not rows:
            return []
        headers = [str(value or "").strip() for value in rows[0]]
        result: list[dict[str, Any]] = []
        for row in rows[1:]:
            record = {
                headers[index]: row[index] if index < len(row) else None
                for index in range(len(headers))
                if headers[index]
            }
            if any(value not in (None, "") for value in record.values()):
                result.append(record)
        return result

    def _latest_event(self, events: Iterable[RuntimeEvent]) -> RuntimeEvent | None:
        available = list(events)
        if not available:
            return None
        return max(
            available,
            key=lambda event: (
                event.log_start if event.log_start and event.log_start != "missing" else ""
            ),
        )

    def _value(self, value: Any, fallback: str = "not_available") -> str:
        if value is None:
            return fallback
        text = str(value).strip()
        if not text or text.lower() in {"none", "null", "nan", "missing", "n/a"}:
            return fallback
        return text

    def _join_values(self, value: Any, fallback: str = "not_available") -> str:
        if isinstance(value, list):
            cleaned = [self._value(item, "") for item in value]
            cleaned = [item for item in cleaned if item]
            return "; ".join(cleaned) if cleaned else fallback
        return self._value(value, fallback)

    def _load_combined_runtime_events(
        self,
        source_system: str,
        preferred_source_mode: str,
        archived_mpl_source: str = "all_sources",
    ) -> list[RuntimeEvent]:
        """Load both live-designated and archived MPL evidence for every generation.

        The selected source_mode remains a preference and is preserved in output folder
        names/metadata, but generated documents are enriched with evidence from both
        Live MPL and Archived MPL whenever those folders contain records.
        """
        ordered_modes = [
            preferred_source_mode,
            "archived_mpl" if preferred_source_mode == "live_mpl" else "live_mpl",
        ]
        events: list[RuntimeEvent] = []
        for mode in ordered_modes:
            events.extend(
                self._load_runtime_events(
                    source_system=source_system,
                    source_mode=mode,
                    archived_mpl_source=archived_mpl_source,
                )
            )
        seen = set()
        deduped: list[RuntimeEvent] = []
        for event in events:
            key = (
                event.message_guid,
                event.integration_flow_name,
                event.log_start,
                event.error_text[:80],
                event.evidence_mode,
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(event)
        return deduped

    def _load_existing_documents(self, existing_documents_path: str | None) -> list[dict[str, str]]:
        raw = (existing_documents_path or "").strip()
        if not raw:
            return []
        folder = Path(raw)
        if not folder.is_absolute():
            folder = settings.project_root / folder
        if not folder.exists() or not folder.is_dir():
            return []
        docs: list[dict[str, str]] = []
        for path in sorted(folder.rglob("*.md")):
            try:
                text = path.read_text(encoding="utf-8")
            except Exception:
                text = ""
            docs.append(
                {
                    "path": str(path.relative_to(settings.project_root))
                    if path.is_relative_to(settings.project_root)
                    else str(path),
                    "name": path.name,
                    "title": next(
                        (
                            line.lstrip("# ").strip()
                            for line in text.splitlines()
                            if line.startswith("#")
                        ),
                        path.stem,
                    ),
                    "excerpt": self._short(text, 500),
                }
            )
        return docs

    def _load_runtime_events(
        self, source_system: str, source_mode: str, archived_mpl_source: str = "all_sources"
    ) -> list[RuntimeEvent]:
        folders: list[Path] = []
        glob_patterns: list[str] = []
        if source_mode == "live_mpl" or archived_mpl_source == "live_mpls":
            folders.append(
                settings.resources_dir / "cpi"
                if source_system == "sap_ci"
                else settings.resources_dir / "pipo" / "mpl"
            )
        else:
            if source_system == "sap_pipo":
                if archived_mpl_source.startswith("resources_pipo_mpl_file:"):
                    folders.append(
                        settings.resources_dir
                        / "pipo"
                        / "mpl"
                        / archived_mpl_source.split(":", 1)[1]
                    )
                elif archived_mpl_source.startswith("pipo_pipeline_mpl_file:"):
                    folders.append(
                        settings.resources_dir
                        / "pipo"
                        / "pipo_rag_pipeline_20260405T134227Z"
                        / "mpl_normalized_20260405T134235Z"
                        / archived_mpl_source.split(":", 1)[1]
                    )
                else:
                    source_map = {
                        "all_sources": [
                            settings.resources_dir / "pipo" / "mpl",
                            settings.resources_dir
                            / "pipo"
                            / "pipo_rag_pipeline_20260405T134227Z"
                            / "mpl_normalized_20260405T134235Z",
                        ],
                        "resources_pipo_mpl": [settings.resources_dir / "pipo" / "mpl"],
                        "pipo_pipeline_mpl": [
                            settings.resources_dir
                            / "pipo"
                            / "pipo_rag_pipeline_20260405T134227Z"
                            / "mpl_normalized_20260405T134235Z"
                        ],
                        "logs_pipo": [],
                    }
                    folders.extend(source_map.get(
                        archived_mpl_source, source_map["all_sources"]))
                    if archived_mpl_source in {"all_sources", "logs_pipo"}:
                        glob_patterns.append("logs/pipo*.json")
            else:
                if archived_mpl_source.startswith("resources_mpl_file:"):
                    folders.append(
                        settings.resources_dir / "mpl" /
                        archived_mpl_source.split(":", 1)[1]
                    )
                else:
                    source_map = {
                        "all_sources": [
                            settings.resources_dir / "mpl",
                            settings.resources_dir / "cpi",
                            settings.project_root / "logs" / "mpl",
                        ],
                        "resources_mpl": [settings.resources_dir / "mpl"],
                        "resources_cpi": [settings.resources_dir / "cpi"],
                        "logs_mpl": [settings.project_root / "logs" / "mpl"],
                    }
                    folders.extend(source_map.get(
                        archived_mpl_source, source_map["all_sources"]))
        events: list[RuntimeEvent] = []
        for folder in folders:
            if not folder.exists():
                continue
            paths = (
                [folder]
                if folder.is_file() and folder.suffix.lower() == ".json"
                else sorted(folder.rglob("*.json"))
            )
            for path in paths:
                payload = self._read_json(path)
                for record in self._extract_records(payload):
                    events.append(self._event_from_record(
                        record, path, source_mode))
        for pattern in glob_patterns:
            for path in sorted(settings.project_root.glob(pattern)):
                payload = self._read_json(path)
                for record in self._extract_records(payload):
                    events.append(self._event_from_record(
                        record, path, source_mode))
        seen = set()
        deduped = []
        for event in events:
            key = (
                event.message_guid,
                event.integration_flow_name,
                event.log_start,
                event.error_text[:80],
            )
            if key not in seen:
                seen.add(key)
                deduped.append(event)
        return deduped

    def _extract_records(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        for key in ("MessageErrors", "MessageProcessingLogs", "value", "results"):
            if isinstance(payload.get(key), list):
                return [item for item in payload[key] if isinstance(item, dict)]
        d = payload.get("d")
        if isinstance(d, dict) and isinstance(d.get("results"), list):
            return [item for item in d["results"] if isinstance(item, dict)]
        return []

    def _event_from_record(
        self, record: dict[str, Any], path: Path, evidence_mode: str = "archived_mpl"
    ) -> RuntimeEvent:
        def first(*names: str) -> str:
            inner_raw = record.get("raw_object")
            raw_object: dict[str, Any] = inner_raw if isinstance(
                inner_raw, dict) else {}
            for name in names:
                value = record.get(name)
                if value in (None, "") and raw_object:
                    value = raw_object.get(name)
                if value not in (None, ""):
                    return str(value)
            return ""

        raw_object_value = record.get("raw_object")
        raw_object: dict[str, Any] = raw_object_value if isinstance(
            raw_object_value, dict) else {}

        def _int_or_none(value: Any) -> int | None:
            try:
                return int(value)
            except (TypeError, ValueError):
                return None

        return RuntimeEvent(
            message_guid=first(
                "MessageGuid", "messageGuid", "MPL_ID", "MessageId", "message_id", "message_guid"
            )
            or "missing",
            integration_flow_name=first(
                "IntegrationFlowName",
                "IFlowName",
                "iflow",
                "Interface",
                "interface_id",
                "interface_name",
                "canonical_key",
                "interface",
                "scenario_identifier",
            )
            or "UNKNOWN_IFLOW",
            status=first("Status", "status") or "UNKNOWN",
            log_start=first(
                "LogStart", "StartTime", "startTime", "timestamp", "start_time", "timeStamp"
            )
            or "missing",
            log_end=first("LogEnd", "EndTime", "endTime",
                          "end_time") or "missing",
            sender=first("Sender", "sender", "sender_component",
                         "sender_partner") or "n/a",
            receiver=first("Receiver", "receiver",
                           "receiver_component", "receiver_partner")
            or "n/a",
            error_text=first(
                "ErrorMessage",
                "ErrorDetails",
                "error",
                "Exception",
                "Message",
                "error_message",
                "error_signature",
                "exception_class",
                "localizedText",
                "errorCategory",
                "errorCode",
                "status_details",
            )
            or "missing",
            source_file=str(path.relative_to(settings.project_root))
            if path.is_relative_to(settings.project_root)
            else str(path),
            evidence_mode=evidence_mode,
            record_type=str(
                record.get("record_type")
                or raw_object.get("record_type")
                or raw_object.get("source_type")
                or ""
            )
            .strip()
            .lower(),
            error_category=str(record.get("errorCategory")
                               or raw_object.get("errorCategory") or "")
            .strip()
            .upper(),
            failed_count=_int_or_none(
                raw_object.get("failed_count") if raw_object else record.get(
                    "failed_count")
            ),
        )

    def _group_error_patterns(
        self, events: Iterable[RuntimeEvent]
    ) -> dict[str, list[RuntimeEvent]]:
        groups: dict[str, list[RuntimeEvent]] = defaultdict(list)
        for event in events:
            groups[self._error_signature(event.error_text)].append(event)
        return dict(sorted(groups.items(), key=lambda item: (-len(item[1]), item[0]))[:50])

    def _error_signature(self, text: str) -> str:
        raw = re.sub(r"\s+", " ", text or "").strip()
        if not raw or raw == "missing":
            return "MPL_ERROR_DETAILS_MISSING"
        raw = re.sub(r"AG[a-zA-Z0-9_\-]{10,}", "<MessageGuid>", raw)
        raw = re.sub(r"\b\d{3,}\b", "<number>", raw)
        raw = raw.split("\n")[0]
        raw = raw.split(". The MPL ID")[0]
        return self._short(raw, 120).rstrip(" .")

    def _symptom_from_signature(self, signature: str, error_text: str = "") -> str:
        if signature == "MPL_ERROR_DETAILS_MISSING":
            return "MPL event failed without a populated technical error detail."
        return f"MPL event failed with signature: {self._readable_title(signature, error_text)}."

    def _find_inventory(self, inventory: list[dict[str, Any]], iflow_name: str) -> dict[str, Any]:
        token = self._token(iflow_name)
        for item in inventory:
            if self._token(str(item.get("iflow_name", ""))) == token:
                return item
        return {}

    # Status values that unambiguously denote a failed processing event.
    ERROR_STATUSES = {
        "FAILED",
        "ERROR",
        "SYSTEMERROR",
        "CANCELLED",
        "ABANDONED",
        "RETRY",
        "ESCALATED",
    }
    # Status values that denote a healthy / non-incident event and must never
    # produce a KEDB or runbook on their own.
    SUCCESS_STATUSES = {
        "COMPLETED",
        "SUCCESS",
        "SUCCESSFUL",
        "OK",
        "DELIVERED",
        "PROCESSED",
        "DONE",
    }
    # record_type / errorCategory markers for aggregated rollups (e.g. annual
    # interface export statistics) that summarise many messages and are not a
    # single atomic incident pattern.
    AGGREGATE_MARKERS = {
        "aggregate_interface_stats",
        "annual_interface_export",
        "aggregated_interface_stats",
    }

    def _is_aggregate_statistic(self, event: RuntimeEvent) -> bool:
        """Return True for aggregated statistics rollups, not single incidents.

        These rows (record_type=aggregate_interface_stats / errorCategory=
        AGGREGATED_INTERFACE_STATS) carry a localizedText such as
        "Annual aggregate for interface X: success=N, failed=M, ...". Turning
        them into runbooks pollutes the BM25 corpus with documents that answer
        no real incident query, so they are excluded from KEDB/runbook
        generation regardless of their failed_count.
        """
        if event.record_type in self.AGGREGATE_MARKERS:
            return True
        if event.error_category in {"AGGREGATED_INTERFACE_STATS"}:
            return True
        text = (event.error_text or "").lower()
        # Defensive lexical fallback for sources that do not carry the metadata.
        if "aggregate for interface" in text and "success=" in text and "failed=" in text:
            return True
        return False

    def _is_success_event(self, event: RuntimeEvent) -> bool:
        """Return True when the event clearly represents a healthy execution."""
        if event.status.upper() in self.SUCCESS_STATUSES:
            return True
        # "success=N, failed=0, error=0" style summaries are not incidents.
        text = (event.error_text or "").lower()
        if re.search(r"failed\s*=\s*0\b", text) and re.search(r"error\s*=\s*0\b", text):
            return True
        return False

    def _has_error_text(self, event: RuntimeEvent) -> bool:
        """Return True only when error_text carries a real failure signal."""
        text = (event.error_text or "").strip()
        if not text or text.lower() in {"missing", "n/a", "none", "null"}:
            return False
        # An aggregate/summary line is descriptive, not a failure signal.
        if self._is_aggregate_statistic(event) or self._is_success_event(event):
            return False
        return True

    def _is_error(self, event: RuntimeEvent) -> bool:
        """Decide whether an event is a real incident worth documenting.

        v2.0.7 fix: previously any non-empty error_text was treated as an error,
        which turned success rollups (e.g. "success=6, failed=0") into P2
        runbooks. Now an event is an incident only when its status is an error
        status, or when it carries a genuine failure signal in error_text, and
        never when it is an aggregated statistic or a clear success event.
        """
        if self._is_aggregate_statistic(event):
            return False
        if self._is_success_event(event):
            return False
        if event.status.upper() in self.ERROR_STATUSES:
            return True
        return self._has_error_text(event)

    def _read_json(self, path: Path) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self._record_evidence_warning(
                f"Evidence file not found: {self._relpath(path)}")
            return {}
        except json.JSONDecodeError as exc:
            self._record_evidence_warning(
                f"Could not parse JSON evidence (skipped): {self._relpath(path)} ({exc.msg} at line {exc.lineno})"
            )
            return {}
        except (OSError, UnicodeDecodeError) as exc:
            self._record_evidence_warning(
                f"Could not read evidence file (skipped): {self._relpath(path)} ({exc.__class__.__name__})"
            )
            return {}

    def _record_evidence_warning(self, message: str) -> None:
        warnings = getattr(self, "_evidence_warnings", None)
        if warnings is None:
            warnings = []
            self._evidence_warnings = warnings
        if message not in warnings:
            warnings.append(message)

    def _compose_warnings(self, generated: list[Path]) -> list[str]:
        """Combine the no-evidence notice with any evidence-loading warnings."""
        warnings: list[str] = []
        skipped = int(getattr(self, "_duplicate_governance",
                      {}).get("skipped_duplicate_count", 0))
        if not (generated or skipped):
            warnings.append(
                "No runtime or inventory evidence found for selected source.")
        warnings.extend(getattr(self, "_evidence_warnings", []))
        return warnings

    def _relpath(self, path: Path) -> str:
        try:
            return str(path.relative_to(settings.project_root))
        except (ValueError, OSError):
            return str(path)

    def _validate_version(self, version: str) -> str:
        version = (version or "").strip()
        if not re.match(r"^v[1-9][0-9]*$", version):
            raise ValueError("Generation version must match v1, v2, ...")
        return version

    def _normalize_system(self, source_system: str) -> str:
        raw = (source_system or "sap_ci").strip(
        ).lower().replace("-", "_").replace("/", "_")
        if raw in {"sap_pipo", "pipo", "sap_pi_po", "sap_pi__po"}:
            return "sap_pipo"
        if raw in {"sap_s4h", "sap_s4", "s4h", "s4", "s_4hana", "s4hana"}:
            return "sap_s4h"
        return "sap_ci"

    def _normalize_source_mode(self, source_mode: str) -> SourceMode:
        raw = (source_mode or "archived_mpl").strip(
        ).lower().replace("-", "_").replace(" ", "_")
        if raw in {"live", "live_mpl"}:
            return "live_mpl"
        if raw in {"archive", "archived", "archived_mpl", "local_mpl"}:
            return "archived_mpl"
        raise ValueError("source_mode must be live_mpl or archived_mpl")

    # Customer priority scheme mapping (knowledge_schema_standard.md §6).
    PRIORITY_WORD_MAP = {
        "high": "P1",
        "critical": "P1",
        "p1": "P1",
        "medium": "P2",
        "med": "P2",
        "important": "P2",
        "p2": "P2",
        "normal": "P3",
        "standard": "P3",
        "low": "P3",
        "p3": "P3",
        "minimal": "P4",
        "p4": "P4",
    }

    def _normalize_priority_value(self, value: str) -> str:
        """Map an inventory priority/criticality value to the canonical P1-P4.

        Accepts both the platform scheme (P1..P4) and the customer scheme
        (High/Medium/Low/...). Returns "" when the value is unrecognised so the
        caller can fall back to keyword classification.
        """
        raw = str(value or "").strip().lower()
        if not raw:
            return ""
        if re.fullmatch(r"p[1-4]", raw):
            return raw.upper()
        return self.PRIORITY_WORD_MAP.get(raw, "")

    def _priority_from_inventory(self, inventory_item: dict[str, Any] | None) -> str:
        """Return the authoritative priority from an inventory item, or ""."""
        if not inventory_item:
            return ""
        for key in ("priority", "criticality"):
            mapped = self._normalize_priority_value(
                inventory_item.get(key, ""))
            if mapped:
                return mapped
        return ""

    def _classify_priority(
        self, signature: str, error_text: str = "", inventory_item: dict[str, Any] | None = None
    ) -> str:
        """Decide the document priority.

        v2.0.7 (2.9) precedence, anchored to the AI4BIZ schema:
          1. Interface Inventory priority/criticality for the matched interface
             (authoritative, SLA-aware). Customer schemes (High/Medium/Low) are
             mapped to P1/P2/P3 per knowledge_schema_standard.md §6.
          2. Keyword classification of the error signature (heuristic fallback).
          3. Schema default P3 when no signal matches (was P2 before).
        """
        inventory_priority = self._priority_from_inventory(inventory_item)
        if inventory_priority:
            return inventory_priority

        text = f"{signature} {error_text}".lower()
        p1_terms = [
            "authentication",
            "unauthorized",
            "forbidden",
            "certificate",
            "ssl",
            "timeout",
            "timed out",
            "service unavailable",
            "internal server error",
            "duplicate key",
            "soap fault",
            "idoc",
            "mapping",
            "xml parse",
            "connection refused",
            "httpresponseexception",
        ]
        # Important-but-not-critical signals. Throttling/rate limiting degrades
        # throughput rather than breaking processing outright, so it maps to P2
        # rather than the bare P3 default.
        p2_terms = [
            "rate limit",
            "throttl",
            "too many requests",
            "allowed threshold",
            "request volume",
            "429",
            "backpressure",
            "queue full",
            "retry exhausted",
        ]
        p3_terms = [
            "warning",
            "optional",
            "pagination",
            "default branch",
            "observability",
            "missing details",
        ]
        if any(term in text for term in p1_terms):
            return "P1"
        if any(term in text for term in p2_terms):
            return "P2"
        if any(term in text for term in p3_terms):
            return "P3"
        # Schema default when no inventory and no keyword signal matches.
        return "P3"

    def _unique_output_path(self, path: Path, sequence: int) -> Path:
        """Return a non-colliding output path inside a generation run.

        Long normalized error signatures can produce the same shortened filename.
        The document ID sequence remains the governed identifier, while this
        suffix prevents later artifacts from overwriting earlier ones.
        """
        if not path.exists():
            return path

        def with_capped_suffix(extra: str) -> Path:
            max_len = self.MAX_FILENAME_LENGTH
            suffix = path.suffix
            room = max(8, max_len - len(extra) - len(suffix))
            stem = self._short_token(path.stem, room)
            return path.with_name(f"{stem}{extra}{suffix}")

        candidate = with_capped_suffix(f"_{sequence:04d}")
        counter = 2
        while candidate.exists():
            candidate = with_capped_suffix(f"_{sequence:04d}_{counter}")
            counter += 1
        return candidate

    def _safe_filename(
        self,
        prefix: str,
        system: str,
        object_name: str,
        priority: str,
        version: str,
        limit: int | None = None,
    ) -> str:
        """Return an AI4BIZ-compliant Markdown filename not longer than 80 chars.

        Policy alignment: keep the governed naming pattern
        <TYPE>_<CUSTOMER>_<SYSTEM>_<ERROR_CODE>_<PRIORITY>_<VERSION>.md, avoid
        hash noise in the filename, and shorten only the object segment at token
        boundaries. In-run collisions are still handled by _unique_output_path().
        """
        max_len = limit or self.MAX_FILENAME_LENGTH
        suffix = f"_{priority}_{version}.md"
        system_code = self._system_code(system)
        customer = self._active_customer_id()
        token_source = self._object_name_from_text(object_name, system=system)
        base = (
            f"{prefix}_{customer}_"
            if token_source.startswith(f"{system_code}_")
            else f"{prefix}_{customer}_{system_code}_"
        )
        room = max(8, max_len - len(base) - len(suffix))
        token = self._short_token(token_source, room)
        name = f"{base}{token}{suffix}"
        if len(name) <= max_len:
            return name
        token = self._short_token(token, max(8, room - (len(name) - max_len)))
        return f"{base}{token}{suffix}"

    def _object_name_from_text(
        self, value: Any, system: str = "sap_ci", error_text: str = ""
    ) -> str:
        """Create a concise, stable object_name with max 80 chars.

        The object_name is optimized for retrieval and filename readability. Exact
        technical terms are preserved, while noisy Java/SAP exception namespaces
        and long prose are reduced to canonical incident phrases.
        """
        text = " ".join(str(x or "") for x in [value, error_text]).strip()
        canonical = self._canonical_error_object(text)
        if canonical:
            token = f"{self._system_code(system)}_{canonical}"
        else:
            token = self._token(
                self._strip_exception_prefix(str(value or error_text)))
            token = self._remove_low_value_tokens(token)
        return self._short_token(token or "INTERFACE_CATALOG", self.MAX_OBJECT_NAME_LENGTH)

    def _canonical_error_object(self, text: str) -> str:
        lowered = (text or "").lower()
        if any(
            term in lowered
            for term in [
                "rate limit",
                "allowed threshold",
                "too many requests",
                "request volume",
                "throttl",
                "http 429",
                " 429",
            ]
        ):
            return "API_THROTTLING_RATE_LIMIT_EXCEEDED"
        if any(
            term in lowered
            for term in [
                "unauthorized",
                "401",
                "authentication",
                "oauth",
                "token expired",
                "forbidden",
                "403",
            ]
        ):
            return "AUTHENTICATION_AUTHORIZATION_FAILURE"
        if any(
            term in lowered for term in ["timeout", "timed out", "read timed", "connection timed"]
        ):
            return "CONNECTION_TIMEOUT"
        if any(
            term in lowered
            for term in ["certificate", "ssl", "handshake", "keystore", "truststore"]
        ):
            return "SSL_CERTIFICATE_HANDSHAKE_FAILURE"
        if any(
            term in lowered for term in ["xml parse", "saxparse", "not well-formed", "invalid xml"]
        ):
            return "XML_PARSE_FAILURE"
        if any(term in lowered for term in ["mapping", "message mapping", "xsl", "xslt", "groovy"]):
            return "MAPPING_SCRIPT_FAILURE"
        return ""

    def _readable_title(self, value: Any, error_text: str = "") -> str:
        text = self._strip_exception_prefix(
            str(error_text or value or "")).strip()
        lowered = text.lower()
        if any(
            term in lowered
            for term in [
                "rate limit",
                "allowed threshold",
                "too many requests",
                "request volume",
                "throttl",
            ]
        ):
            return "Receiver throttled requests due to API rate limit"
        if any(
            term in lowered
            for term in ["unauthorized", "401", "authentication", "oauth", "token expired"]
        ):
            return "Authentication failed on receiver call"
        if any(term in lowered for term in ["forbidden", "403"]):
            return "Receiver rejected call due to missing authorization"
        if any(
            term in lowered for term in ["timeout", "timed out", "read timed", "connection timed"]
        ):
            return "Receiver call failed due to connection timeout"
        if any(
            term in lowered
            for term in ["certificate", "ssl", "handshake", "keystore", "truststore"]
        ):
            return "SSL certificate handshake failed on integration call"
        if any(
            term in lowered for term in ["xml parse", "saxparse", "not well-formed", "invalid xml"]
        ):
            return "Message processing failed due to invalid XML"
        if any(term in lowered for term in ["mapping", "message mapping", "xsl", "xslt", "groovy"]):
            return "Message processing failed in mapping or script step"
        text = re.sub(r"[_]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip(" .:-")
        if not text or text.lower() == "missing":
            return "MPL error details missing"
        return self._short(text[:1].upper() + text[1:], 96).rstrip(" .")

    def _strip_exception_prefix(self, value: str) -> str:
        text = re.sub(r"\s+", " ", value or "").strip()
        if ":" in text:
            left, right = text.split(":", 1)
            if "." in left or left.lower().endswith("exception"):
                text = right.strip()
        return text

    def _remove_low_value_tokens(self, token: str) -> str:
        low_value = {
            "COM",
            "SAP",
            "GATEWAY",
            "CORE",
            "IP",
            "COMPONENT",
            "EXCEPTIONS",
            "EXCEPTION",
            "ERROR",
            "MESSAGE",
            "DETAILS",
            "MISSING",
            "REJECTS",
            "DELAYS",
            "CALLS",
            "BECAUSE",
            "REQUEST",
            "VOLUME",
            "EXCEEDS",
            "ALLOWED",
            "THRESHOLD",
            "THE",
            "DUE",
            "TO",
            "WITH",
            "FROM",
            "AND",
        }
        parts = [part for part in token.split(
            "_") if part and part not in low_value]
        return "_".join(parts) or token

    def _short_token(self, token: str, limit: int) -> str:
        token = re.sub(r"_+", "_", (token or "").strip("_")) or "OBJECT"
        if len(token) <= limit:
            return token
        parts = token.split("_")
        kept: list[str] = []
        for part in parts:
            candidate = "_".join([*kept, part]) if kept else part
            if len(candidate) > limit:
                break
            kept.append(part)
        if kept and len("_".join(kept)) >= 8:
            return "_".join(kept).rstrip("_")
        return token[:limit].rstrip("_") or "OBJECT"

    def _system_code(self, system: str) -> str:
        if system == "sap_pipo":
            return "PIPO"
        if system == "sap_s4h":
            return "S4H"
        return "CPI"

    def _system_id(self, system: str) -> str:
        """Return the governed customer system identifier used in generated docs."""
        return f"{self._system_code(system)}-{self._active_customer_id()}"

    def _active_customer_id(self) -> str:
        return getattr(self, "_customer_id", None) or "RCMO"

    def _active_environment(self) -> str:
        return getattr(self, "_environment", None) or "demo"

    def _normalize_customer_id(self, value: str) -> str:
        """Customer IDs follow the same token rules as elsewhere (uppercase,
        alphanumeric/underscore). Empty input falls back to the RCMO default."""
        token = re.sub(r"[^A-Za-z0-9]+", "_",
                       str(value or "")).strip("_").upper()
        return token or "RCMO"

    def _normalize_environment(self, value: str) -> str:
        env = str(value or "").strip().lower()
        allowed = {
            "demo",
            "development",
            "dev",
            "quality",
            "qa",
            "test",
            "production",
            "prod",
            "sandbox",
        }
        return env if env in allowed else "demo"

    def _token(self, value: str, fallback: str = "UNKNOWN") -> str:
        token = re.sub(r"[^A-Za-z0-9]+", "_", value or "").strip("_").upper()
        return token or fallback

    def _short(self, value: str, length: int) -> str:
        value = re.sub(r"\s+", " ", value or "").strip()
        return value if len(value) <= length else value[: length - 3].rstrip() + "..."
