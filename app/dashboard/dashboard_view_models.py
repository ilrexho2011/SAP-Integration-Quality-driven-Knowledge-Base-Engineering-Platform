from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class StatusBadge:
    label: str
    status: str
    tone: str


@dataclass(frozen=True)
class KpiCard:
    label: str
    value: str | int | float | None
    help_text: str = ""


@dataclass(frozen=True)
class DownloadItem:
    key: str
    label: str
    relative_path: str
    exists: bool
    size_bytes: int | None = None


@dataclass(frozen=True)
class DashboardPageModel:
    page_key: str
    title: str
    status: str
    summary: str
    source: str | None = None
    metrics: dict[str, Any] = field(default_factory=dict)
    issues: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    downloads: list[DownloadItem] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EnterpriseConsoleModel:
    status: str
    package_path: str
    promotion_decision: str
    kpis: list[KpiCard]
    badges: list[StatusBadge]
    pages: dict[str, DashboardPageModel]
    issues: list[dict[str, Any]]
    warnings: list[str]
    downloads: list[DownloadItem]
    raw_summary: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "package_path": self.package_path,
            "promotion_decision": self.promotion_decision,
            "kpis": [card.__dict__ for card in self.kpis],
            "badges": [badge.__dict__ for badge in self.badges],
            "pages": {key: page.__dict__ for key, page in self.pages.items()},
            "issues": self.issues,
            "warnings": self.warnings,
            "downloads": [item.__dict__ for item in self.downloads],
            "raw_summary": self.raw_summary,
        }
