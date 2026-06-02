from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Literal

from app.config import settings

SourceSystem = Literal["sap_ci", "sap_pipo"]
GenerationMode = Literal["generate", "update_existing_docs"]


@dataclass(frozen=True)
class ScenarioLabPathConfig:
    source_system: SourceSystem
    display_name: str
    primary_label: str
    primary_path: Path
    secondary_label: str
    secondary_path: Path

    def to_dict(self) -> dict[str, str]:
        data = asdict(self)
        data["primary_path"] = self._display_path(self.primary_path)
        data["secondary_path"] = self._display_path(self.secondary_path)
        data["primary_absolute_path"] = str(self.primary_path)
        data["secondary_absolute_path"] = str(self.secondary_path)
        # Backward-compatible aliases consumed by the existing Scenario Lab API/UI.
        data["zip_dir"] = data["primary_path"]
        data["bpmn_dir"] = data["secondary_path"]
        data["zip_label"] = self.primary_label
        data["bpmn_label"] = self.secondary_label
        return data

    @staticmethod
    def _display_path(path: Path) -> str:
        try:
            rel = path.relative_to(settings.project_root)
            return "./" + str(rel).replace("\\", "/")
        except ValueError:
            return str(path)


SCENARIO_LAB_PATH_CONFIG: dict[SourceSystem, ScenarioLabPathConfig] = {
    "sap_ci": ScenarioLabPathConfig(
        source_system="sap_ci",
        display_name="SAP CI",
        primary_label="iFlow ZIP folder",
        primary_path=settings.resources_dir / "cpi" / "input" / "odata" / "iflows",
        secondary_label="ICO folder",
        secondary_path=settings.resources_dir / "cpi" / "input" / "analysis" / "iflows-bpmn",
    ),
    "sap_pipo": ScenarioLabPathConfig(
        source_system="sap_pipo",
        display_name="SAP PIPO",
        primary_label="ESR & ID folder",
        primary_path=settings.resources_dir / "pipo" / "esr_id",
        secondary_label="ICO folder",
        secondary_path=settings.resources_dir / "pipo" / "ico",
    ),
}


def _display_rel(path: Path) -> str:
    try:
        return str(path.relative_to(settings.project_root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _json_file_options(key_prefix: str, folder: Path) -> list[dict[str, str]]:
    if not folder.exists():
        return []
    options: list[dict[str, str]] = []
    for path in sorted(folder.glob("*.json")):
        rel = _display_rel(path)
        options.append({"key": f"{key_prefix}:{path.name}", "label": path.name, "path": rel})
    return options


def _base_archived_mpl_source_options(source_system: SourceSystem) -> list[dict[str, str]]:
    if source_system == "sap_pipo":
        return [
            {"key": "all_sources", "label": "All PIPO archived MPL sources", "path": "all_sources"},
            {
                "key": "resources_pipo_mpl",
                "label": "resources/pipo/mpl",
                "path": "resources/pipo/mpl",
            },
            {
                "key": "pipo_pipeline_mpl",
                "label": "resources/pipo/pipo_rag_pipeline_20260405T134227Z/mpl_normalized_20260405T134235Z",
                "path": "resources/pipo/pipo_rag_pipeline_20260405T134227Z/mpl_normalized_20260405T134235Z",
            },
            {"key": "logs_pipo", "label": "logs/pipo_*", "path": "logs/pipo_*"},
        ]
    return [
        {"key": "all_sources", "label": "All CPI archived MPL sources", "path": "all_sources"},
        {"key": "resources_mpl", "label": "resources/mpl", "path": "resources/mpl"},
        {"key": "resources_cpi", "label": "resources/cpi", "path": "resources/cpi"},
        {"key": "logs_mpl", "label": "logs/mpl", "path": "logs/mpl"},
    ]


ARCHIVED_MPL_SOURCE_OPTIONS: dict[SourceSystem, list[dict[str, str]]] = {
    "sap_ci": _base_archived_mpl_source_options("sap_ci"),
    "sap_pipo": _base_archived_mpl_source_options("sap_pipo"),
}


def get_archived_mpl_source_options(source_system: str | None = None) -> list[dict[str, str]]:
    system = normalize_source_system(source_system)
    options = list(_base_archived_mpl_source_options(system))
    if system == "sap_ci":
        options.extend(_json_file_options("resources_mpl_file", settings.resources_dir / "mpl"))
    else:
        options.extend(
            _json_file_options("resources_pipo_mpl_file", settings.resources_dir / "pipo" / "mpl")
        )
        options.extend(
            _json_file_options(
                "pipo_pipeline_mpl_file",
                settings.resources_dir
                / "pipo"
                / "pipo_rag_pipeline_20260405T134227Z"
                / "mpl_normalized_20260405T134235Z",
            )
        )
    return options


def normalize_archived_mpl_source(
    source_system: str | None, archived_mpl_source: str | None
) -> str:
    options = get_archived_mpl_source_options(source_system)
    allowed = {item["key"] for item in options}
    raw = (archived_mpl_source or "all_sources").strip()
    return raw if raw in allowed else "all_sources"


def normalize_source_system(source_system: str | None) -> SourceSystem:
    raw = (source_system or "sap_ci").strip().lower().replace("-", "_").replace(" ", "_")
    if raw in {"sap_pipo", "pipo", "sap_pi_po", "sap_pi/po"}:
        return "sap_pipo"
    return "sap_ci"


def get_scenario_lab_path_config(source_system: str | None = None) -> ScenarioLabPathConfig:
    return SCENARIO_LAB_PATH_CONFIG[normalize_source_system(source_system)]


def list_scenario_lab_path_configs() -> dict[str, dict[str, str]]:
    return {key: value.to_dict() for key, value in SCENARIO_LAB_PATH_CONFIG.items()}


def normalize_generation_mode(generation_mode: str | None) -> GenerationMode:
    raw = (generation_mode or "generate").strip().lower().replace("-", "_").replace(" ", "_")
    if raw in {"update", "update_existing", "update_existing_docs", "regenerate", "regeneration"}:
        return "update_existing_docs"
    return "generate"
