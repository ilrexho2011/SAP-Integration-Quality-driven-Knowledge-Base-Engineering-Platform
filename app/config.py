from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    app_name: str = "AI4BIZ Quality-driven Knowledge Engineering Platform"
    app_version: str = "0.1.0"
    default_language: str = "EN"
    score_threshold: float = 80.0
    top_k: int = 5
    chunk_max_chars: int = 1800
    chunk_overlap_chars: int = 220
    api_base_url: str = "http://localhost:8000"
    project_root: Path = PROJECT_ROOT
    upload_dir: Path = PROJECT_ROOT / "upload_packages"
    uploaded_knowledge_dir: Path = PROJECT_ROOT / "uploaded_knowledge_packages"
    benchmark_runs_dir: Path = PROJECT_ROOT / "benchmark_runs"
    reports_dir: Path = PROJECT_ROOT / "reports"
    feedback_dir: Path = PROJECT_ROOT / "feedback"
    exports_dir: Path = PROJECT_ROOT / "exports"
    resources_dir: Path = PROJECT_ROOT / "resources"

    @staticmethod
    def from_env() -> "Settings":
        return Settings(
            app_name=os.getenv("APP_NAME", "AI4BIZ Quality-driven Knowledge Engineering Platform"),
            app_version=os.getenv("APP_VERSION", "0.1.0"),
            default_language=os.getenv("DEFAULT_LANGUAGE", "EN"),
            score_threshold=float(os.getenv("SCORE_THRESHOLD", "80")),
            top_k=int(os.getenv("TOP_K", "5")),
            chunk_max_chars=int(os.getenv("CHUNK_MAX_CHARS", "1800")),
            chunk_overlap_chars=int(os.getenv("CHUNK_OVERLAP_CHARS", "220")),
            api_base_url=os.getenv("API_BASE_URL", "http://localhost:8000"),
        )

    def ensure_directories(self) -> None:
        for directory in [
            self.upload_dir,
            self.uploaded_knowledge_dir,
            self.benchmark_runs_dir,
            self.reports_dir,
            self.feedback_dir,
            self.exports_dir,
            self.resources_dir,
        ]:
            directory.mkdir(parents=True, exist_ok=True)


settings = Settings.from_env()
settings.ensure_directories()
