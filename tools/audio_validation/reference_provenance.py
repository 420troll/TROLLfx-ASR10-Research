#!/usr/bin/env python3
"""Private, content-addressed provenance for factory reference captures."""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


SCHEMA = "trollfx-factory-reference-provenance-v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def describe_file(path: Path) -> dict:
    path = path.expanduser().resolve(strict=True)
    return {"path": str(path), "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path)}


def _git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()


def source_fingerprint(root: Path) -> dict:
    root = root.resolve(strict=True)
    tracked = _git(root, "ls-files", "-z").split("\0")
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z").split("\0")
    files = []
    digest = hashlib.sha256()
    for relative in sorted({x for x in tracked + untracked if x}):
        path = root / relative
        if not path.is_file():
            continue
        file_hash = sha256_file(path)
        files.append({"path": relative, "size_bytes": path.stat().st_size, "sha256": file_hash})
        digest.update(relative.encode("utf-8", errors="surrogateescape"))
        digest.update(b"\0")
        digest.update(file_hash.encode("ascii"))
        digest.update(b"\n")
    status = _git(root, "status", "--porcelain=v1", "--untracked-files=all")
    diff = subprocess.check_output(["git", "-C", str(root), "diff", "--binary", "HEAD", "--"])
    return {
        "root": str(root),
        "branch": _git(root, "branch", "--show-current"),
        "commit": _git(root, "rev-parse", "HEAD"),
        "clean": not bool(status),
        "status_porcelain": status,
        "diff_from_head_sha256": hashlib.sha256(diff).hexdigest(),
        "working_tree_sha256": digest.hexdigest(),
        "file_count": len(files),
        "files": files,
    }


def environment_facts() -> dict:
    try:
        os_release = platform.freedesktop_os_release()
    except (AttributeError, OSError):
        os_release = {}
    return {
        "python": sys.version,
        "python_executable": str(Path(sys.executable).resolve()),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "os_release": {k: os_release[k] for k in ("ID", "VERSION_ID", "PRETTY_NAME") if k in os_release},
        "wsl_distro_name": os.environ.get("WSL_DISTRO_NAME"),
    }


def compiler_facts() -> dict:
    resolved = subprocess.check_output(["bash", "-lc", "command -v c++"], text=True).strip()
    binary = Path(resolved).resolve(strict=True)
    version = subprocess.check_output([str(binary), "--version"], text=True, stderr=subprocess.STDOUT)
    return {"path": str(binary), "sha256": sha256_file(binary), "version": version.splitlines()[:4]}


def artifact_inventory(root: Path, exclude: set[str] | None = None) -> dict[str, dict]:
    root = root.resolve(strict=True)
    exclude = exclude or set()
    result = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in exclude:
            continue
        result[relative] = {"size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
    return result


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def verify_provenance(path: Path, check_inputs: bool = True, check_source: bool = True) -> dict:
    path = path.expanduser().resolve(strict=True)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA:
        raise ValueError("unsupported provenance schema")
    errors = []
    for item in data.get("inputs", {}).values():
        if item is None:
            continue
        entries = item if isinstance(item, list) else [item]
        for entry in entries:
            file_path = Path(entry["path"])
            if check_inputs and file_path.is_file():
                if sha256_file(file_path) != entry["sha256"]:
                    errors.append(f"input hash mismatch: {file_path}")
    source = data.get("source", {})
    if check_source and source.get("root") and source.get("working_tree_sha256"):
        root = Path(source["root"])
        if root.is_dir():
            try:
                now = source_fingerprint(root)
                if now["working_tree_sha256"] != source["working_tree_sha256"]:
                    errors.append("working source tree hash mismatch")
            except (OSError, subprocess.CalledProcessError) as exc:
                errors.append(f"source tree could not be verified: {exc}")
    output_root = Path(data["output_root"])
    for relative, expected in data.get("output_artifacts", {}).items():
        artifact = output_root / relative
        if not artifact.is_file():
            errors.append(f"missing output artifact: {relative}")
        elif artifact.stat().st_size != expected["size_bytes"] or sha256_file(artifact) != expected["sha256"]:
            errors.append(f"output artifact hash mismatch: {relative}")
    boots = data.get("boots", [])
    if len(boots) != 2 or len({x.get("pid") for x in boots}) != 2:
        errors.append("reference capture does not record two distinct process IDs")
    if not data.get("validation", {}).get("two_boots_identical"):
        errors.append("two-boot reference validation is absent or failed")
    return {"valid": not errors, "errors": errors, "schema": data["schema"],
            "profile": data.get("profile"), "run_frame": data.get("run_frame"),
            "dsp_frames": data.get("dsp_frames"), "boot_count": len(boots),
            "output_artifact_count": len(data.get("output_artifacts", {}))}
