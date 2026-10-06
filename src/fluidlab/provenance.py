"""Portable framed hashes and Git metadata tied to the explicit project root."""
from pathlib import Path
import hashlib
import json
import platform
import subprocess
import numpy as np
import scipy


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SOURCE_INCLUSION = ("src/**/*.py", "scripts/**/*.py", "schemas/*.json", "pyproject.toml", "uv.lock")
UNITS = dict(time_s="s", sample_time_s="s", receipt_time_s="s", measurement_age_s="s",
             level_m="m", measured_level_m="m", target_m="m", flow_m3_s="m3/s",
             volume_residual_m3="m3", pump_command="1", requested_valve_command="1",
             applied_pump_command="1", applied_valve_command="1", valve_opening="1")


def canonical_json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                      allow_nan=False).encode("utf-8")


def file_sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hash(root=PROJECT_ROOT, paths=None):
    """path UTF-8 + NUL + 8-byte BE byte length + raw bytes, sorted POSIX paths."""
    root = Path(root).resolve()
    if paths is None:
        paths = {path for pattern in SOURCE_INCLUSION for path in root.glob(pattern) if path.is_file()}
    entries = sorted((Path(path).relative_to(root).as_posix(), Path(path)) for path in paths)
    digest = hashlib.sha256()
    hashes = {}
    for relative, path in entries:
        raw = path.read_bytes()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(len(raw).to_bytes(8, "big"))
        digest.update(raw)
        hashes[relative] = hashlib.sha256(raw).hexdigest()
    return digest.hexdigest(), hashes


def git_metadata(root=PROJECT_ROOT):
    root = Path(root).resolve()
    result = dict(git_revision="unversioned", git_dirty=True, git_root_matches=False)
    try:
        def git(*args):
            return subprocess.check_output(["git", *args], cwd=root,
                                           stderr=subprocess.DEVNULL, text=True).strip()
        top = Path(git("rev-parse", "--show-toplevel")).resolve()
        if top != root:
            result["git_diagnostic"] = "Git top-level does not match project root"
            return result
        result.update(git_revision=git("rev-parse", "HEAD"),
                      git_dirty=bool(git("status", "--porcelain")), git_root_matches=True)
    except (subprocess.CalledProcessError, FileNotFoundError, OSError) as exc:
        result["git_diagnostic"] = type(exc).__name__
    return result


def execution_provenance(root=PROJECT_ROOT):
    root = Path(root).resolve()
    digest, hashes = source_hash(root)
    lock = root / "uv.lock"
    controller = root / "src/fluidlab/control.py"
    return dict(source_sha256=digest, source_files_sha256=hashes,
                source_inclusion=list(SOURCE_INCLUSION),
                source_hash_framing="POSIX UTF-8 path, NUL, uint64 BE raw-byte length, raw bytes",
                source_line_endings="raw bytes; repository .gitattributes specifies LF",
                lock_sha256=file_sha256(lock) if lock.is_file() else None,
                controller_sha256=file_sha256(controller) if controller.is_file() else None,
                controller_implementation="python_tank_baseline", firmware_execution="NOT_EXECUTED",
                python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__,
                units=UNITS.copy(), **git_metadata(root))
