from __future__ import annotations

import shutil
import zipfile
from pathlib import Path


class PackagePublisher:
    def publish(self, source_dir: Path, output_zip: Path) -> Path:
        output_zip.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in source_dir.rglob("*"):
                if path.is_file():
                    zf.write(path, path.relative_to(source_dir))
        return output_zip
