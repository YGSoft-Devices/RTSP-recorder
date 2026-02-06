from __future__ import annotations

import hashlib
import json
import os
import tarfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Tuple


DEFAULT_EXCLUDES = [".git", "node_modules", "__pycache__"]


def _should_exclude(path: Path, excludes: Iterable[str]) -> bool:
    return any(part in excludes for part in path.parts)


def build_archive(source_dir: Path, output_path: Path, fmt: str = "tar.gz", excludes=DEFAULT_EXCLUDES) -> Path:
    if fmt not in {"tar.gz", "zip"}:
        raise ValueError("Unsupported archive format")

    if fmt == "tar.gz":
        with tarfile.open(output_path, "w:gz") as tar:
            for root, dirs, files in os.walk(source_dir):
                root_path = Path(root)
                if _should_exclude(root_path, excludes):
                    continue
                for f in files:
                    fpath = root_path / f
                    if _should_exclude(fpath, excludes):
                        continue
                    tar.add(fpath, arcname=fpath.relative_to(source_dir))
    else:
        with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for root, dirs, files in os.walk(source_dir):
                root_path = Path(root)
                if _should_exclude(root_path, excludes):
                    continue
                for f in files:
                    fpath = root_path / f
                    if _should_exclude(fpath, excludes):
                        continue
                    zf.write(fpath, fpath.relative_to(source_dir))

    return output_path


def compute_sha256(path: Path) -> Tuple[str, int]:
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
            size += len(chunk)
    return h.hexdigest(), size


def build_manifest(
    device_type: str,
    distribution: str,
    version: str,
    archive_name: str,
    sha256: str,
    size: int,
    notes: str = "",
) -> Dict[str, str | int]:
    return {
        "version": version,
        "device_type": device_type,
        "distribution": distribution,
        "archive": archive_name,
        "sha256": sha256,
        "size": size,
        "notes": notes,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def write_manifest(path: Path, manifest: Dict[str, str | int]) -> Path:
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def validate_manifest(manifest: Dict[str, str | int]) -> bool:
    required = {"version", "device_type", "distribution", "archive", "sha256", "size", "created_at"}
    return required.issubset(manifest.keys())
