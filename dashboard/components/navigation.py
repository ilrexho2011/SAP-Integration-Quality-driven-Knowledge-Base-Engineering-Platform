from __future__ import annotations

from pathlib import Path

try:
    import streamlit as st
except (
    ModuleNotFoundError
):  # pragma: no cover - allows constants to be unit-tested without Streamlit
    st = None  # type: ignore[assignment]

PAGE_KEYS = [
    "monitoring",
    "scenario_lab_generation",
    "contract_validation",
    "package_builder",
    "quality_gates",
    "ai4biz_export",
    "evidence_traceability",
    "generators",
    "benchmark",
    "send_feedback",
    "reports_downloads",
    "overview",
    "settings",
]


def _package_candidates(project_root: Path) -> list[Path]:
    exports_dir = project_root / "exports"
    candidates: list[Path] = []
    if exports_dir.exists():
        candidates.extend(
            sorted(exports_dir.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        )
        candidates.extend(
            sorted(
                (p for p in exports_dir.iterdir() if p.is_dir()),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
        )
    fallback = project_root / "exports" / "qdkep_package_with_benchmark.zip"
    if fallback.exists() and fallback not in candidates:
        candidates.insert(0, fallback)
    return candidates


def _format_package_option(path: Path, project_root: Path) -> str:
    try:
        rel = path.relative_to(project_root)
    except ValueError:
        rel = path
    suffix = "ZIP" if path.is_file() else "folder"
    return f"{rel.as_posix()} ({suffix})"


def _render_logo() -> None:
    if st is None:
        return
    logo_path = Path(__file__).resolve().parents[1] / "assets" / "logo.png"
    if logo_path.exists():
        st.sidebar.image(str(logo_path), width="stretch")
        st.sidebar.markdown("<div style='height: 0.25rem;'></div>", unsafe_allow_html=True)


def render_sidebar(translator, default_package_path: str | None = None) -> tuple[str, str, str]:
    """Render the enterprise sidebar.

    Navigation follows the factual Knowledge Base build sequence: observe,
    generate, validate, package, gate, export, trace, benchmark and download.
    Package selection is export-first so the latest generated QDKEP packages in
    ./exports remain the normal review source instead of the project root.
    """
    from app.config import settings

    if st is None:
        raise RuntimeError("Streamlit is required to render the QDKEP sidebar")

    _render_logo()
    language = st.sidebar.selectbox(
        translator.text("language"),
        options=["en", "de"],
        index=0,
        format_func=lambda value: "EN" if value == "en" else "DE",
    )
    nav_translator = translator.__class__(language)
    page = st.sidebar.radio(
        nav_translator.text("navigation"),
        PAGE_KEYS,
        index=0,
        format_func=nav_translator.text,
    )

    candidates = _package_candidates(settings.project_root)
    if default_package_path:
        default_path = Path(default_package_path)
    elif candidates:
        preferred = settings.project_root / "exports" / "qdkep_package_with_benchmark.zip"
        default_path = preferred if preferred.exists() else candidates[0]
    else:
        default_path = settings.exports_dir

    package_path = str(default_path)
    if page not in {"monitoring", "scenario_lab_generation"}:
        options = [str(path) for path in candidates]
        labels = {
            str(path): _format_package_option(path, settings.project_root) for path in candidates
        }
        custom_label = nav_translator.text("custom_package_path")
        if package_path not in options:
            options.insert(0, package_path)
            labels[package_path] = _format_package_option(Path(package_path), settings.project_root)
        options.append(custom_label)

        selected = st.sidebar.selectbox(
            nav_translator.text("package_input"),
            options=options,
            index=options.index(package_path) if package_path in options else 0,
            format_func=lambda value: str(
                custom_label if value == custom_label else labels.get(value, value)
            ),
        )
        if selected == custom_label:
            package_path = st.sidebar.text_input(
                nav_translator.text("custom_package_path"), value=str(default_path)
            )
        else:
            package_path = selected
        st.sidebar.caption(nav_translator.text("package_input_hint"))
        st.sidebar.caption(nav_translator.text("service_backed"))
    return package_path, language, page
