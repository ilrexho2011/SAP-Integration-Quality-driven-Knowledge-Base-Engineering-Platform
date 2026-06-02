from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from app.config import settings

DocKind = Literal["catalog_docs", "kedb", "runbooks"]


@dataclass(frozen=True)
class IdDecision:
    document_id: str
    next_sequence: int
    duplicate_path: str | None = None
    action: str = "create_new"


class DocumentIdService:
    """Govern generated DOC/KEDB/RUNBOOK IDs using existing sample_packages evidence."""

    SAMPLE_DIRS = {
        "sap_ci": {
            "catalog_docs": settings.project_root
            / "sample_packages"
            / "sap_cpi"
            / "cpi_interface_catalog_docs",
            "kedb": settings.project_root / "sample_packages" / "sap_cpi" / "cpi_demo_kedbs",
            "runbooks": settings.project_root / "sample_packages" / "sap_cpi" / "cpi_demo_runbooks",
        },
        "sap_pipo": {
            "catalog_docs": settings.project_root
            / "sample_packages"
            / "sap_pipo"
            / "pipo_interface_catalog_docs",
            "kedb": settings.project_root / "sample_packages" / "sap_pipo" / "pipo_demo_kedbs",
            "runbooks": settings.project_root
            / "sample_packages"
            / "sap_pipo"
            / "pipo_demo_runbooks",
        },
    }

    GLOBAL_SAMPLE_DIRS = {
        "catalog_docs": settings.project_root / "sample_packages" / "interface_catalog_docs",
        "kedb": settings.project_root / "sample_packages" / "kedbs",
        "runbooks": settings.project_root / "sample_packages" / "runbooks",
    }

    def ensure_sample_dirs(self) -> None:
        for by_kind in self.SAMPLE_DIRS.values():
            for folder in by_kind.values():
                folder.mkdir(parents=True, exist_ok=True)
        for folder in self.GLOBAL_SAMPLE_DIRS.values():
            folder.mkdir(parents=True, exist_ok=True)

    def sample_dir(self, source_system: str, kind: DocKind) -> Path:
        system = "sap_pipo" if source_system == "sap_pipo" else "sap_ci"
        folder = self.SAMPLE_DIRS[system][kind]
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    def decide_doc_id(
        self, source_system: str, object_name: str, prevent_duplicate: bool = False
    ) -> IdDecision:
        code = "PIPO" if source_system == "sap_pipo" else "CPI"
        doc_id = f"CAT-{code}-{self._token(object_name)}"
        dup = self.find_id(source_system, "catalog_docs", doc_id)
        if dup and prevent_duplicate:
            return IdDecision(
                document_id=doc_id,
                next_sequence=0,
                duplicate_path=str(dup),
                action="skip_duplicate",
            )
        return IdDecision(
            document_id=doc_id,
            next_sequence=0,
            duplicate_path=str(dup) if dup else None,
            action="create_new",
        )

    def decide_numbered_id(
        self,
        source_system: str,
        kind: Literal["kedb", "runbooks"],
        priority: str,
        restart: bool = False,
    ) -> IdDecision:
        prefix = "KEDB" if kind == "kedb" else "RB"
        if restart:
            seq = 1
        else:
            # v2.0.4 corrected: numbering is global for the document kind, not per
            # selected system and not per priority. A new KEDB/RUNBOOK always uses
            # the next value after the highest existing KEDB-P*-NNNN/RB-P*-NNNN.
            seq = self.last_document_sequence(source_system, kind, prefix) + 1
        return IdDecision(
            document_id=f"{prefix}-{priority}-{seq:04d}",
            next_sequence=seq,
            action="restart_counting" if restart else "continue_after_last",
        )

    def last_sequence(self, source_system: str, kind: DocKind, prefix: str, priority: str) -> int:
        # Backward-compatible method name. For KEDB and Runbook governance the
        # sequence is intentionally global across all priorities and source systems.
        if kind in {"kedb", "runbooks"}:
            return self.last_document_sequence(source_system, kind, prefix)
        pattern = re.compile(rf"\b{re.escape(prefix)}-{re.escape(priority)}-(\d{{4,}})\b", re.I)
        max_seq = 0
        for path in self._iter_files(source_system, kind):
            text = self._safe_text(path)
            for match in pattern.finditer(text + "\n" + path.name):
                max_seq = max(max_seq, int(match.group(1)))
        return max_seq

    def last_document_sequence(self, source_system: str, kind: DocKind, prefix: str) -> int:
        pattern = re.compile(rf"\b{re.escape(prefix)}-P\d+-(\d{{4,}})\b", re.I)
        max_seq = 0
        for path in self._iter_files(source_system, kind):
            text = self._safe_text(path)
            for match in pattern.finditer(text + "\n" + path.name):
                max_seq = max(max_seq, int(match.group(1)))
        return max_seq

    def find_signature(
        self, source_system: str, kind: Literal["kedb", "runbooks"], signature: str
    ) -> Path | None:
        needle = self._normalize_signature(signature)
        if not needle:
            return None
        for path in self._iter_files(source_system, kind):
            text = self._safe_text(path)
            haystack = self._normalize_signature(path.stem + "\n" + text)
            if needle and needle in haystack:
                return path
        return None

    def find_id(self, source_system: str, kind: DocKind, document_id: str) -> Path | None:
        needle = document_id.strip()
        if not needle:
            return None
        for path in self._iter_files(source_system, kind):
            if needle in path.name or needle in self._safe_text(path):
                return path
        return None

    def _iter_files(self, source_system: str, kind: DocKind):
        folders: list[Path] = []
        global_folder = self.GLOBAL_SAMPLE_DIRS.get(kind)
        if global_folder is not None:
            global_folder.mkdir(parents=True, exist_ok=True)
            folders.append(global_folder)

        # Keep legacy CPI/PIPO folders in the scan for backward compatibility, but
        # do not make KEDB/RUNBOOK numbering depend on the selected system.
        if kind in {"kedb", "runbooks"}:
            for system_dirs in self.SAMPLE_DIRS.values():
                folder = system_dirs.get(kind)
                if folder is not None:
                    folder.mkdir(parents=True, exist_ok=True)
                    folders.append(folder)
        else:
            folders.append(self.sample_dir(source_system, kind))

        # Also scan already generated exports so repeated generation runs do not
        # reuse IDs before the user copies documents back into sample_packages.
        generated_root = settings.exports_dir / "generated_documents"
        export_subdir = {
            "catalog_docs": "interface_inventory",
            "kedb": "kedb",
            "runbooks": "runbooks",
        }.get(kind)
        if export_subdir and generated_root.exists():
            folders.extend(sorted(generated_root.glob(f"*/{export_subdir}")))

        seen: set[Path] = set()
        for folder in folders:
            if not folder.exists():
                continue
            for path in sorted(
                p
                for p in folder.rglob("*")
                if p.is_file() and p.suffix.lower() in {".md", ".json", ".yaml", ".yml", ".txt"}
            ):
                resolved = path.resolve()
                if resolved in seen:
                    continue
                seen.add(resolved)
                yield path

    def _safe_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return ""

    def _normalize_signature(self, value: str) -> str:
        return re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9]+", " ", value or "")).strip().lower()

    def _token(self, value: str) -> str:
        return re.sub(r"[^A-Za-z0-9]+", "_", value or "UNKNOWN").strip("_").upper() or "UNKNOWN"
