"""Load the operator-provisioned private reviewer identity, fail closed.

The authority selection is deliberately outside this public skill.  A trusted
host operator supplies both the absolute configuration path and its SHA-256 in
the process environment; callers, candidates, receipts, and projects never
select it.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Iterable


CONFIG_PATH_ENV = "CHIEF_PRIVATE_AUTHORITY_CONFIG_PATH"
CONFIG_SHA256_ENV = "CHIEF_PRIVATE_AUTHORITY_CONFIG_SHA256"
SCHEMA = "CHIEF_PRIVATE_AUTHORITY_CONFIG_V1"
HEX = re.compile(r"^[0-9a-f]{64}$")
SAFE_TASK_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
MAX_CONFIG_BYTES = 16 * 1024


class PrivateAuthorityError(ValueError):
    pass


def _no_duplicate_object(pairs: list[tuple[object, object]]) -> dict[str, object]:
    value: dict[str, object] = {}
    for key, item in pairs:
        if not isinstance(key, str) or key in value:
            raise PrivateAuthorityError("private authority configuration has duplicate keys")
        value[key] = item
    return value


def _safe_absolute(value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise PrivateAuthorityError(f"{label} is not configured by the host operator")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise PrivateAuthorityError(f"{label} must be a clean absolute path")
    return path


def _reject_aliases(path: Path) -> None:
    current = path
    while current.parent != current:
        try:
            info = current.lstat()
        except FileNotFoundError:
            current = current.parent
            continue
        if stat.S_ISLNK(info.st_mode) and current not in {Path("/tmp"), Path("/var")}:
            raise PrivateAuthorityError("private authority configuration has an unsafe symlink alias")
        current = current.parent


def _outside_forbidden(path: Path, forbidden_paths: Iterable[Path]) -> None:
    for item in forbidden_paths:
        try:
            # Planned activation destinations and transaction roots may not yet
            # exist.  Their authoritative parents have already been checked by
            # the caller; lexical resolution still makes containment fail closed.
            boundary = Path(item).resolve(strict=False)
        except OSError as exc:
            raise PrivateAuthorityError("private authority forbidden boundary is unreadable") from exc
        try:
            path.relative_to(boundary)
        except ValueError:
            continue
        raise PrivateAuthorityError("private authority configuration must remain outside public/project/receipt/candidate boundaries")


def testing_reviewer_task_id(*, forbidden_paths: Iterable[Path]) -> str:
    """Return one operator-pinned reviewer identity, or raise without fallback."""
    path = _safe_absolute(os.environ.get(CONFIG_PATH_ENV), CONFIG_PATH_ENV)
    expected = os.environ.get(CONFIG_SHA256_ENV)
    if not isinstance(expected, str) or not HEX.fullmatch(expected):
        raise PrivateAuthorityError(f"{CONFIG_SHA256_ENV} must be a lowercase SHA-256")
    _reject_aliases(path)
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise PrivateAuthorityError("private authority configuration is unavailable") from exc
    _outside_forbidden(resolved, forbidden_paths)
    # O_NONBLOCK prevents a hostile FIFO/device path from turning an authority
    # check into an unbounded wait; fstat below still accepts regular files only.
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise PrivateAuthorityError("private authority configuration cannot be opened safely") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise PrivateAuthorityError("private authority configuration must be a one-link regular file")
        raw = os.read(descriptor, MAX_CONFIG_BYTES + 1)
        if len(raw) > MAX_CONFIG_BYTES:
            raise PrivateAuthorityError("private authority configuration exceeds the bounded size")
        if os.read(descriptor, 1):
            raise PrivateAuthorityError("private authority configuration exceeds the bounded size")
    except OSError as exc:
        raise PrivateAuthorityError("private authority configuration is unreadable") from exc
    finally:
        os.close(descriptor)
    if hashlib.sha256(raw).hexdigest() != expected:
        raise PrivateAuthorityError("private authority configuration SHA-256 drifted")
    try:
        value = json.loads(raw, object_pairs_hook=_no_duplicate_object)
    except (UnicodeDecodeError, json.JSONDecodeError, PrivateAuthorityError) as exc:
        raise PrivateAuthorityError("private authority configuration is invalid JSON") from exc
    if not isinstance(value, dict) or set(value) != {"schema", "testing_reviewer_task_id"}:
        raise PrivateAuthorityError("private authority configuration fields are incomplete or ambiguous")
    reviewer = value.get("testing_reviewer_task_id")
    if value.get("schema") != SCHEMA or not isinstance(reviewer, str) or not SAFE_TASK_ID.fullmatch(reviewer):
        raise PrivateAuthorityError("private authority reviewer identity is invalid")
    return reviewer
