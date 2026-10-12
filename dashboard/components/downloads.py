from __future__ import annotations

from pathlib import Path

import streamlit as st


def resolve_download_path(package_path: str, relative_path: str) -> Path:
    source = Path(package_path)
    candidate = Path(relative_path)
    if candidate.exists():
        return candidate
    if source.is_dir() and relative_path:
        return source / relative_path
    return candidate


def render_downloads(
    package_path: str, downloads: list, download_label: str, missing_label: str
) -> None:
    if not downloads:
        st.info(missing_label)
        return
    for item in downloads:
        label = getattr(item, "label", getattr(item, "key", "download"))
        relative_path = getattr(item, "relative_path", "")
        exists = bool(getattr(item, "exists", False))
        if not exists:
            st.caption(f"{missing_label}: `{label}` ({relative_path})")
            continue
        file_path = resolve_download_path(package_path, relative_path)
        if file_path.exists() and file_path.is_file():
            st.download_button(
                label=f"{download_label} {label}",
                data=file_path.read_bytes(),
                file_name=file_path.name,
            )
        else:
            st.write(f"Available in package: `{relative_path}`")
