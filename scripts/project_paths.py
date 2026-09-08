"""Portable project-root and active-path resolution helpers.

The helpers are deliberately library-only: callers choose a project-specific
environment variable and pass any registered external paths explicitly.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Mapping


ROOT_MARKERS = (Path(".chief-of-staff/project.json"), Path("AGENTS.md"), Path(".git"))
HISTORICAL_RECORD_CLASSES = frozenset(
    {
        "historical_audit",
        "frozen_candidate",
        "hash_manifest",
        "context_migration",
        "legacy_build",
        "provenance",
    }
)
ROOT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:")


class PortabilityError(ValueError):
    """Raised when a root or path would violate the portability boundary."""


@dataclass(frozen=True)
class RootResolution:
    path: Path
    source: str


@dataclass(frozen=True)
class PortablePath:
    root_id: str
    scope: str
    relative_path: str | None
    absolute_path: Path


def _anchor_directory(anchor: Path) -> Path:
    anchor = anchor.expanduser()
    if not anchor.is_absolute():
        anchor = Path.cwd() / anchor
    if anchor.exists() and anchor.is_file():
        anchor = anchor.parent
    return anchor.resolve()


def _git_root(anchor: Path) -> Path | None:
    result = subprocess.run(
        ["git", "-C", str(anchor), "rev-parse", "--show-toplevel"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    candidate = Path(result.stdout.strip())
    return candidate.resolve() if candidate.is_dir() else None


def discover_project_root(
    *,
    anchor: str | Path | None = None,
    cwd: str | Path | None = None,
    env_var: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> RootResolution:
    """Resolve a project root without requiring a machine-specific default.

    Order: caller-selected environment override, Git root, upward marker search,
    then the caller's current project directory as a compatibility fallback.
    """

    environment = os.environ if environ is None else environ
    if env_var:
        override = environment.get(env_var)
        if override:
            candidate = Path(override).expanduser()
            if not candidate.is_absolute() or not candidate.is_dir():
                raise PortabilityError("project root override must be an existing absolute directory")
            return RootResolution(candidate.resolve(), "environment_override")

    fallback = _anchor_directory(Path(cwd) if cwd is not None else Path.cwd())
    start = _anchor_directory(Path(anchor) if anchor is not None else fallback)

    git_root = _git_root(start)
    if git_root is not None:
        return RootResolution(git_root, "git_root")

    for candidate in (start, *start.parents):
        if any((candidate / marker).exists() for marker in ROOT_MARKERS):
            return RootResolution(candidate, "project_marker")
    return RootResolution(fallback, "cwd_fallback")


def _valid_root_id(value: object) -> str | None:
    if isinstance(value, str) and ROOT_ID_RE.fullmatch(value):
        return value
    return None


def _hashed_root_id(namespace: str, identity: str) -> str:
    digest = hashlib.sha256(f"{namespace}\0{identity}".encode("utf-8")).hexdigest()[:24]
    return f"project:{digest}"


def stable_root_id(root: str | Path, configured: str | None = None) -> str:
    """Return a move-stable identity without hashing the absolute root path."""

    if configured is not None:
        root_id = _valid_root_id(configured)
        if root_id is None:
            raise PortabilityError("configured root_id is invalid")
        return root_id

    root_path = Path(root).resolve()
    project_file = root_path / ".chief-of-staff" / "project.json"
    if project_file.is_file():
        try:
            project = json.loads(project_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise PortabilityError("project identity file is unreadable") from exc
        root_id = _valid_root_id(project.get("root_id"))
        if root_id is not None:
            return root_id
        project_name = project.get("project_name")
        if isinstance(project_name, str) and project_name.strip():
            return _hashed_root_id("project_name", project_name.strip())

    result = subprocess.run(
        ["git", "-C", str(root_path), "remote", "get-url", "origin"],
        text=True,
        capture_output=True,
        check=False,
    )
    remote = result.stdout.strip() if result.returncode == 0 else ""
    if remote:
        return _hashed_root_id("git_origin", remote)
    raise PortabilityError("stable root_id needs configured, project, or Git-origin identity")


def resolve_project_path(
    root: str | Path,
    raw_path: str,
    *,
    root_id: str,
    external_registry: Mapping[str, Mapping[str, object]] | None = None,
    record_class: str = "active",
) -> PortablePath:
    """Resolve an active project path or an explicitly registered external input."""

    valid_root_id = _valid_root_id(root_id)
    if valid_root_id is None:
        raise PortabilityError("root_id is invalid")
    if record_class in HISTORICAL_RECORD_CLASSES:
        raise PortabilityError("historical evidence cannot be used as an active runtime path")
    if record_class != "active":
        raise PortabilityError("unknown path record class")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise PortabilityError("path must be a non-empty string")
    if "\\" in raw_path or WINDOWS_DRIVE_RE.match(raw_path):
        raise PortabilityError("active project paths must use relative POSIX syntax")

    supplied = Path(raw_path)
    if supplied.is_absolute():
        entry = (external_registry or {}).get(raw_path)
        if not isinstance(entry, Mapping):
            raise PortabilityError("absolute paths require exact external intake registration")
        permissions = entry.get("permissions")
        if (
            entry.get("authorized") is not True
            or entry.get("project_root_dependency") is not False
            or not isinstance(entry.get("identity"), str)
            or not entry.get("identity")
            or not isinstance(permissions, list)
            or not permissions
            or not all(isinstance(item, str) and item for item in permissions)
        ):
            raise PortabilityError("external intake is incomplete or makes the path a project-root dependency")
        return PortablePath(valid_root_id, "external_registered", None, supplied.resolve())

    raw_segments = raw_path.split("/")
    posix = PurePosixPath(raw_path)
    if posix.is_absolute() or any(part in {"", ".", ".."} for part in raw_segments):
        raise PortabilityError("active project path must be normalized and cannot escape with '..'")

    root_path = Path(root).resolve()
    candidate = (root_path / Path(*posix.parts)).resolve(strict=False)
    try:
        candidate.relative_to(root_path)
    except ValueError as exc:
        raise PortabilityError("active project path escapes the project root or follows an escaping symlink") from exc
    return PortablePath(valid_root_id, "project", posix.as_posix(), candidate)
