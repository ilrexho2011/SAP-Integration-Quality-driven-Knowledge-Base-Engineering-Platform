from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.contracts.constants import ALLOWED_PRIORITIES, ARTIFACT_TYPES

FILENAME_RE = re.compile(
    r"^(?P<type>RB|KB|DOC)_(?P<customer>[A-Z0-9]+)_(?P<system>[A-Z0-9]+)_(?P<object>[A-Z0-9][A-Z0-9_]*?)_(?P<priority>P[1-4])_(?P<version>v[1-9][0-9]*)\.md$"
)
GENERIC_OBJECT_CODES = {"ERROR", "OBJECT", "DOC", "RUNBOOK", "KEDB", "UNKNOWN", "GENERAL", "MISC"}


@dataclass(frozen=True)
class FilenameValidationResult:
    valid: bool
    filename: str
    artifact_type_prefix: str | None = None
    customer: str | None = None
    system: str | None = None
    object_code: str | None = None
    priority: str | None = None
    version: str | None = None
    issues: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "valid": self.valid,
            "filename": self.filename,
            "artifact_type_prefix": self.artifact_type_prefix,
            "customer": self.customer,
            "system": self.system,
            "object_code": self.object_code,
            "priority": self.priority,
            "version": self.version,
            "issues": list(self.issues),
        }


class FilenameValidator:
    """Validates QDKEP Markdown artifact names from the v1.1 EN/SQ contract."""

    def validate(self, filename_or_path: str | Path) -> FilenameValidationResult:
        filename = Path(filename_or_path).name
        match = FILENAME_RE.match(filename)
        if not match:
            return FilenameValidationResult(
                valid=False,
                filename=filename,
                issues=(
                    "Filename must follow <TYPE>_<CUSTOMER>_<SYSTEM>_<ERROR_CODE_OR_OBJECT_CODE>_<PRIORITY>_<VERSION>.md",
                ),
            )
        data = match.groupdict()
        issues: list[str] = []
        prefix = data["type"]
        object_code = data["object"]
        priority = data["priority"]
        if prefix not in ARTIFACT_TYPES:
            issues.append("TYPE must be one of RB, KB, DOC")
        if priority not in ALLOWED_PRIORITIES:
            issues.append("PRIORITY must be one of P1, P2, P3, P4")
        if object_code in GENERIC_OBJECT_CODES or len(object_code.split("_")) < 2:
            issues.append(
                "ERROR_CODE_OR_OBJECT_CODE must be specific, uppercase and underscore-separated, not generic"
            )
        if "__" in object_code:
            issues.append("ERROR_CODE_OR_OBJECT_CODE must not contain repeated underscores")
        return FilenameValidationResult(
            valid=not issues,
            filename=filename,
            artifact_type_prefix=prefix,
            customer=data["customer"],
            system=data["system"],
            object_code=object_code,
            priority=priority,
            version=data["version"],
            issues=tuple(issues),
        )

    def validate_path_folder_alignment(self, relative_path: str | Path) -> list[str]:
        path = Path(relative_path)
        result = self.validate(path.name)
        if not result.valid or not result.artifact_type_prefix:
            return list(result.issues)
        expected = {"RB": "knowledge/RB", "KB": "knowledge/KB", "DOC": "knowledge/DOC"}[
            result.artifact_type_prefix
        ]
        normalized_parent = str(path.parent).replace("\\", "/")
        if normalized_parent != expected:
            return [f"{path.name} must be located under {expected}"]
        return []
