from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class InterfaceInventoryIssue:
    interface_id: str
    category: str
    severity: str
    message: str
    recommendation: str

    def to_dict(self) -> dict[str, str]:
        return self.__dict__.copy()


@dataclass
class InterfaceInventoryValidationReport:
    status: str = "approved"
    required_interface_ids: list[str] = field(default_factory=list)
    checked_interface_ids: list[str] = field(default_factory=list)
    inventory_path: str | None = None
    issues: list[InterfaceInventoryIssue] = field(default_factory=list)

    def add_issue(
        self, interface_id: str, category: str, severity: str, message: str, recommendation: str
    ) -> None:
        self.issues.append(
            InterfaceInventoryIssue(interface_id, category, severity, message, recommendation)
        )
        if severity in {"critical", "high"}:
            self.status = "blocked"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "inventory_path": self.inventory_path,
            "required_interface_ids": self.required_interface_ids,
            "checked_interface_ids": self.checked_interface_ids,
            "issues": [issue.to_dict() for issue in self.issues],
        }


class InterfaceInventoryValidator:
    """Validates the interface inventory for every interface_id used by artifacts."""

    REQUIRED_FIELDS = ("interface_id", "customer_id", "system_id", "integration_flow_id")

    def validate(
        self, package_root: str | Path, manifest: dict[str, Any] | None = None
    ) -> InterfaceInventoryValidationReport:
        root = Path(package_root)
        manifest = manifest or self._load_manifest(root)
        report = InterfaceInventoryValidationReport()
        required = self._requirements_from_manifest(manifest)
        report.required_interface_ids = sorted(required)
        if not required:
            report.add_issue(
                "*",
                "interface_inventory_contract",
                "high",
                "No interface_id values were found in artifact metadata",
                "Add interface_id metadata to interface-bound artifacts before package promotion",
            )
            return report
        inventory_path = self._find_inventory_path(root)
        if inventory_path is None:
            report.add_issue(
                "*",
                "interface_inventory_contract",
                "high",
                "Missing interface inventory file under interface_inventory/",
                "Generate interface_inventory/interface_inventory.json or .yaml",
            )
            return report
        report.inventory_path = inventory_path.relative_to(root).as_posix()
        inventory = self._load_inventory(inventory_path, report)
        if inventory is None:
            return report
        entries = self._normalize_entries(inventory)
        for interface_id, expected in sorted(required.items()):
            entry = entries.get(interface_id)
            if not entry:
                report.add_issue(
                    interface_id,
                    "interface_inventory_contract",
                    "high",
                    "interface_id used by artifacts is missing from interface_inventory",
                    "Add a deterministic inventory entry for the interface_id",
                )
                continue
            report.checked_interface_ids.append(interface_id)
            self._validate_entry(interface_id, expected, entry, report)
        return report

    def _load_manifest(self, root: Path) -> dict[str, Any]:
        path = root / "manifest.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def _requirements_from_manifest(
        self, manifest: dict[str, Any]
    ) -> dict[str, dict[str, set[str]]]:
        requirements: dict[str, dict[str, set[str]]] = {}
        for artifact in manifest.get("artifacts", []):
            if not isinstance(artifact, dict):
                continue
            metadata = (
                artifact.get("metadata", {}) if isinstance(artifact.get("metadata"), dict) else {}
            )
            interface_id = str(metadata.get("interface_id", "")).strip()
            if not interface_id:
                continue
            bucket = requirements.setdefault(
                interface_id,
                {"customer_id": set(), "system_id": set(), "integration_flow_id": set()},
            )
            for key in bucket:
                value = str(metadata.get(key, "")).strip()
                if value:
                    bucket[key].add(value)
        return requirements

    def _find_inventory_path(self, root: Path) -> Path | None:
        candidates = [
            root / "interface_inventory" / "interface_inventory.json",
            root / "interface_inventory" / "interface_inventory.yaml",
            root / "interface_inventory" / "interface_inventory.yml",
        ]
        return next((path for path in candidates if path.exists()), None)

    def _load_inventory(self, path: Path, report: InterfaceInventoryValidationReport) -> Any | None:
        try:
            if path.suffix.lower() == ".json":
                return json.loads(path.read_text(encoding="utf-8"))
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - validator must report parser exceptions
            report.add_issue(
                "*",
                "interface_inventory_contract",
                "critical",
                f"Invalid inventory file: {exc}",
                "Regenerate valid JSON/YAML",
            )
            return None

    def _normalize_entries(self, inventory: Any) -> dict[str, dict[str, Any]]:
        raw_entries: list[Any]
        if isinstance(inventory, dict):
            if isinstance(inventory.get("interfaces"), list):
                raw_entries = inventory["interfaces"]
            elif isinstance(inventory.get("interface_inventory"), list):
                raw_entries = inventory["interface_inventory"]
            else:
                raw_entries = (
                    list(inventory.values())
                    if all(isinstance(v, dict) for v in inventory.values())
                    else []
                )
        elif isinstance(inventory, list):
            raw_entries = inventory
        else:
            raw_entries = []
        entries: dict[str, dict[str, Any]] = {}
        for item in raw_entries:
            if not isinstance(item, dict):
                continue
            interface_id = str(item.get("interface_id", "")).strip()
            if interface_id:
                entries[interface_id] = item
        return entries

    def _validate_entry(
        self,
        interface_id: str,
        expected: dict[str, set[str]],
        entry: dict[str, Any],
        report: InterfaceInventoryValidationReport,
    ) -> None:
        for field_name in self.REQUIRED_FIELDS:
            if not str(entry.get(field_name, "")).strip():
                report.add_issue(
                    interface_id,
                    "interface_inventory_contract",
                    "high",
                    f"Missing required field: {field_name}",
                    f"Add {field_name} to the inventory entry",
                )
        for field_name, expected_values in expected.items():
            value = str(entry.get(field_name, "")).strip()
            if expected_values and value not in expected_values:
                report.add_issue(
                    interface_id,
                    "interface_inventory_contract",
                    "high",
                    f"{field_name} does not match artifact metadata",
                    f"Use one of the artifact-declared values: {sorted(expected_values)}",
                )
        if not str(entry.get("owner", "")).strip():
            report.add_issue(
                interface_id,
                "interface_inventory_contract",
                "medium",
                "owner is recommended for operational accountability",
                "Add an owner or support group",
            )
