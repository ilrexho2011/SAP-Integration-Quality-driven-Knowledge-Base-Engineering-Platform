from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CustomerContextIssue:
    customer_id: str
    category: str
    severity: str
    message: str
    recommendation: str

    def to_dict(self) -> dict[str, str]:
        return self.__dict__.copy()


@dataclass
class CustomerContextValidationReport:
    status: str = "approved"
    checked_customers: list[str] = field(default_factory=list)
    required_customers: list[str] = field(default_factory=list)
    issues: list[CustomerContextIssue] = field(default_factory=list)

    def add_issue(
        self, customer_id: str, category: str, severity: str, message: str, recommendation: str
    ) -> None:
        self.issues.append(
            CustomerContextIssue(customer_id, category, severity, message, recommendation)
        )
        if severity in {"critical", "high"}:
            self.status = "blocked"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "required_customers": self.required_customers,
            "checked_customers": self.checked_customers,
            "issues": [issue.to_dict() for issue in self.issues],
        }


class CustomerContextValidator:
    """Validates customer/<CUSTOMER>.yaml against artifact metadata.

    The validator is intentionally deterministic and file-system local. It does
    not infer customer approval from naming alone: every customer_id used by an
    artifact must have an explicit context file.
    """

    REQUIRED_FIELDS = ("customer_id", "customer_name", "environment", "systems")

    def validate(
        self, package_root: str | Path, manifest: dict[str, Any] | None = None
    ) -> CustomerContextValidationReport:
        root = Path(package_root)
        manifest = manifest or self._load_manifest(root)
        report = CustomerContextValidationReport()
        requirements = self._requirements_from_manifest(manifest)
        report.required_customers = sorted(requirements)
        if not requirements:
            report.add_issue(
                "*",
                "customer_context_contract",
                "high",
                "No customer_id values were found in artifact metadata",
                "Ensure each artifact has customer_id metadata before package promotion",
            )
            return report
        for customer_id, required_systems in sorted(requirements.items()):
            path = root / "customer" / f"{customer_id}.yaml"
            if not path.exists():
                report.add_issue(
                    customer_id,
                    "customer_context_contract",
                    "high",
                    f"Missing customer context file: customer/{customer_id}.yaml",
                    "Generate one customer context YAML per customer_id used by artifacts",
                )
                continue
            data = self._load_yaml(path, report, customer_id)
            if data is None:
                continue
            report.checked_customers.append(customer_id)
            self._validate_customer_file(customer_id, required_systems, data, report)
        return report

    def _load_manifest(self, root: Path) -> dict[str, Any]:
        path = root / "manifest.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _requirements_from_manifest(self, manifest: dict[str, Any]) -> dict[str, set[str]]:
        requirements: dict[str, set[str]] = {}
        for artifact in manifest.get("artifacts", []):
            if not isinstance(artifact, dict):
                continue
            metadata = (
                artifact.get("metadata", {}) if isinstance(artifact.get("metadata"), dict) else {}
            )
            customer_id = str(metadata.get("customer_id", "")).strip()
            system_id = str(metadata.get("system_id", "")).strip()
            if customer_id:
                requirements.setdefault(customer_id, set())
                if system_id:
                    requirements[customer_id].add(system_id)
        return requirements

    def _load_yaml(
        self, path: Path, report: CustomerContextValidationReport, customer_id: str
    ) -> dict[str, Any] | None:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - validator must surface parse errors deterministically
            report.add_issue(
                customer_id,
                "customer_context_contract",
                "critical",
                f"Invalid YAML in {path.name}: {exc}",
                "Regenerate valid YAML",
            )
            return None
        if not isinstance(raw, dict):
            report.add_issue(
                customer_id,
                "customer_context_contract",
                "critical",
                f"{path.name} must contain a YAML mapping",
                "Regenerate the customer context as a mapping",
            )
            return None
        return raw

    def _validate_customer_file(
        self,
        customer_id: str,
        required_systems: set[str],
        data: dict[str, Any],
        report: CustomerContextValidationReport,
    ) -> None:
        for field_name in self.REQUIRED_FIELDS:
            if field_name not in data or data[field_name] in (None, "", []):
                report.add_issue(
                    customer_id,
                    "customer_context_contract",
                    "high",
                    f"Missing required field: {field_name}",
                    f"Add {field_name} to customer/{customer_id}.yaml",
                )
        if str(data.get("customer_id", "")).strip() != customer_id:
            report.add_issue(
                customer_id,
                "customer_context_contract",
                "high",
                "customer_id does not match the filename and artifact metadata",
                "Align customer_id with the artifact metadata value",
            )
        declared_systems = self._extract_system_ids(data.get("systems"))
        missing_systems = sorted(required_systems - declared_systems)
        for system_id in missing_systems:
            report.add_issue(
                customer_id,
                "customer_context_contract",
                "high",
                f"Required system_id is not declared in customer context: {system_id}",
                "Add the system to the systems list with system_id and description",
            )
        if self._contains_secret_like_values(data):
            report.add_issue(
                customer_id,
                "security_contract",
                "high",
                "Customer context appears to contain secret-like keys",
                "Remove credentials/secrets and reference a secret store instead",
            )

    def _extract_system_ids(self, systems: Any) -> set[str]:
        if not isinstance(systems, list):
            return set()
        ids: set[str] = set()
        for item in systems:
            if isinstance(item, str):
                ids.add(item.strip())
            elif isinstance(item, dict):
                value = item.get("system_id") or item.get("id") or item.get("system")
                if value:
                    ids.add(str(value).strip())
        return ids

    def _contains_secret_like_values(self, data: Any) -> bool:
        secret_terms = ("password", "secret", "token", "apikey", "api_key")
        if isinstance(data, dict):
            for key, value in data.items():
                if any(term in str(key).lower() for term in secret_terms):
                    return True
                if self._contains_secret_like_values(value):
                    return True
        if isinstance(data, list):
            return any(self._contains_secret_like_values(item) for item in data)
        return False
