from __future__ import annotations

import shutil
import zipfile
from pathlib import Path

from app.schemas.models import DocumentRecord
from app.services.markdown_parser import parse_markdown_file


def safe_extract_zip(zip_path: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        for member in zf.infolist():
            member_path = destination / member.filename
            if not str(member_path.resolve()).startswith(str(destination.resolve())):
                raise ValueError(f"Unsafe ZIP path detected: {member.filename}")
        zf.extractall(destination)
    return destination


def copy_or_extract_package(package_path: Path, run_input_dir: Path) -> Path:
    run_input_dir.mkdir(parents=True, exist_ok=True)
    if package_path.suffix.lower() == ".zip":
        return safe_extract_zip(package_path, run_input_dir)
    if package_path.is_dir():
        target = run_input_dir / package_path.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(package_path, target)
        return target
    raise ValueError(f"Unsupported package path: {package_path}")


def load_markdown_documents(root: Path) -> list[DocumentRecord]:
    documents: list[DocumentRecord] = []
    for path in sorted(root.rglob("*.md")):
        if ".git" in path.parts:
            continue
        documents.append(parse_markdown_file(path))
    return documents
