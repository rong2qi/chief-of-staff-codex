#!/usr/bin/env python3
"""V2, fail-closed, recoverable Codex Agent OS activation.

This is deliberately a local-filesystem journal, not a distributed atomic
transaction. It never infers a home directory or trusts a receipt for paths.
"""
from __future__ import annotations

import argparse
import ctypes
import errno
import fcntl
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

try:
    from . import private_authority
except ImportError:  # Direct CLI execution uses the same host authority boundary.
    import private_authority

SCHEMA = "CODEX_AGENT_OS_ACTIVATION_V2"
CANDIDATE_SCHEMA = "CODEX_AGENT_OS_CANDIDATE_V1"
GATE_SCHEMA = "CODEX_AGENT_OS_TESTING_GATE_V1"
TESTING_LANES = {"FRONTEND_UI", "BACKEND_API", "DATABASE_STORAGE", "DATA_MIGRATION", "INTEGRATION_ASYNC", "SECURITY_PRIVACY", "PERFORMANCE_RELIABILITY", "INFRA_CONFIG", "MOBILE_DESKTOP", "CLI_SCRIPT", "AI_DATA", "OBSERVABILITY_RUNBOOK", "END_TO_END"}
START, END = "<!-- agent-os-global:start -->", "<!-- agent-os-global:end -->"
PAYLOAD = """# Agent OS global engineering floor (managed)
restore local facts before implementation.
Read the nearest README, implementation, tests, configuration, and ownership rules.
Copy the closest valid local pattern before introducing a new one.
Use evidence for the actual dependency and API versions in use.
Run real relevant commands and update documentation with observed behavior.
Separate verified facts, inference, and open items in reports.
Stop and ask when a semantic ambiguity changes scope, authority, or behavior.
Persist durable rules only through an approved RULE_CANDIDATE.
"""
BLOCK = f"{START}\n{PAYLOAD}{END}\n".encode()
FIXED = {"plan": "plan.json", "intent": "activation-intent.json", "rollback_intent": "rollback-intent.json",
         "activation_commit": "activation-commit.json", "rollback_commit": "rollback-commit.json", "receipt": "receipt.json", "rollback_receipt": "rollback-receipt.json",
         "rollback_plan": "rollback-plan.json", "package_stage": "package-stage", "global_stage": "global-stage",
         "package_backup": "package-backup", "global_backup": "global-backup", "package_quarantine": "package-quarantine",
         "global_quarantine": "global-quarantine"}


class ActivationError(RuntimeError): pass
def testing_reviewer_task_id(*boundaries: Path) -> str:
    try:
        return private_authority.testing_reviewer_task_id(
            forbidden_paths=(Path(__file__).resolve().parent.parent, *boundaries)
        )
    except private_authority.PrivateAuthorityError as exc:
        raise ActivationError("private Testing authority is unavailable") from exc
def digest(data: bytes) -> str: return hashlib.sha256(data).hexdigest()
def canonical(value: object) -> bytes: return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
def lstat(path: Path):
    try: return path.lstat()
    except FileNotFoundError: return None
def exists(path: Path) -> bool: return lstat(path) is not None


def absolute_clean(path: Path, label: str) -> Path:
    if not path.is_absolute() or ".." in path.parts: raise ActivationError(f"{label} must be a clean absolute path")
    return path


def safe_ancestors(path: Path, label: str) -> None:
    absolute_clean(path, label)
    current = path
    while current != current.parent:
        info = lstat(current)
        # macOS exposes /tmp and /var as OS-owned aliases for /private. They
        # are unavoidable for disposable test roots and not caller-selected.
        if info and stat.S_ISLNK(info.st_mode) and str(current) not in {"/var", "/tmp"}:
            raise ActivationError(f"{label} has a symlink ancestor: {current}")
        current = current.parent


def require_dir(path: Path, label: str) -> None:
    absolute_clean(path, label); safe_ancestors(path.parent, label)
    info = lstat(path)
    if info is None or not stat.S_ISDIR(info.st_mode): raise ActivationError(f"{label} must be an existing directory")


def require_regular(path: Path, label: str) -> None:
    absolute_clean(path, label); safe_ancestors(path.parent, label)
    info = lstat(path)
    if info is None or not stat.S_ISREG(info.st_mode): raise ActivationError(f"{label} must be a regular file")
    if info.st_nlink != 1: raise ActivationError(f"{label} must not be a hardlink")


def contained(child: Path, parent: Path) -> bool:
    try: child.relative_to(parent); return True
    except ValueError: return False


def disjoint(*paths: Path) -> None:
    for index, left in enumerate(paths):
        for right in paths[index + 1:]:
            if contained(left, right) or contained(right, left): raise ActivationError(f"activation surfaces overlap: {left} / {right}")


def reject_inode_aliases(*paths: Path) -> None:
    """Lexically different writable surfaces must not identify the same inode."""
    seen: dict[tuple[int, int], Path] = {}
    for path in paths:
        info = lstat(path)
        if info is None: continue
        identity = (info.st_dev, info.st_ino)
        if identity in seen and seen[identity] != path: raise ActivationError(f"inode alias between activation surfaces: {seen[identity]} / {path}")
        seen[identity] = path


def inventory(root: Path, *, absent_ok: bool = False) -> dict[str, object]:
    if not exists(root):
        if absent_ok: return {"present": False, "entries": []}
        raise ActivationError(f"missing package surface: {root}")
    require_dir(root, "package surface")
    entries = []
    for base, dirs, names in os.walk(root, followlinks=False):
        base_path = Path(base)
        for name in dirs:
            node, info = base_path / name, lstat(base_path / name)
            if info is None or not stat.S_ISDIR(info.st_mode): raise ActivationError(f"unsafe package topology: {base_path / name}")
            entries.append({"path": node.relative_to(root).as_posix(), "type": "dir", "mode": stat.S_IMODE(info.st_mode), "size": 0, "sha256": None})
        for name in names:
            node, info = base_path / name, lstat(base_path / name)
            if info is None or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1: raise ActivationError(f"unsafe package topology: {node}")
            entries.append({"path": node.relative_to(root).as_posix(), "type": "file", "mode": stat.S_IMODE(info.st_mode), "size": info.st_size, "sha256": digest(node.read_bytes())})
    return {"present": True, "entries": sorted(entries, key=lambda item: item["path"])}


def inventory_hash(root: Path, *, absent_ok: bool = False) -> str: return digest(canonical(inventory(root, absent_ok=absent_ok)))


def global_bytes(path: Path, *, absent_ok: bool = False) -> bytes | None:
    if not exists(path) and absent_ok: return None
    require_regular(path, "global AGENTS file")
    data = path.read_bytes()
    try: data.decode("utf-8")
    except UnicodeDecodeError as error: raise ActivationError("global AGENTS file must be UTF-8") from error
    return data


def global_hash(path: Path, *, absent_ok: bool = False) -> str | None:
    data = global_bytes(path, absent_ok=absent_ok)
    if data is None: return None
    return digest(canonical({"sha256": digest(data), "mode": stat.S_IMODE(lstat(path).st_mode)}))


def prospective_global(current: bytes) -> bytes:
    text = current.decode("utf-8"); starts, ends = text.count(START), text.count(END)
    if starts == ends == 0: return current + (b"" if not current or current.endswith(b"\n") else b"\n") + b"\n" + BLOCK
    if starts != 1 or ends != 1: raise ActivationError("managed global block is malformed")
    first, last = text.index(START), text.index(END) + len(END)
    if text[first:last] != BLOCK.decode().rstrip("\n"): raise ActivationError("managed global block differs from frozen payload")
    return current


def fsync_dir(path: Path) -> None:
    fd = os.open(str(path), os.O_RDONLY)
    try: os.fsync(fd)
    finally: os.close(fd)


def write_new(path: Path, data: bytes) -> None:
    if exists(path): raise ActivationError(f"create-new target already exists: {path}")
    require_dir(path.parent, "evidence/transaction parent")
    fd, name = tempfile.mkstemp(prefix=".agent-os-new-", dir=path.parent); temporary = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream: stream.write(data); stream.flush(); os.fsync(stream.fileno())
        os.link(temporary, path); fsync_dir(path.parent)
    except FileExistsError as error: raise ActivationError(f"create-new target already exists: {path}") from error
    finally:
        try: temporary.unlink()
        except FileNotFoundError: pass


def write_json_new(path: Path, data: dict[str, object]) -> None: write_new(path, canonical(data) + b"\n")
def load_json(path: Path, label: str) -> dict[str, object]:
    require_regular(path, label)
    raw = path.read_bytes()
    try: value = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError) as error: raise ActivationError(f"invalid {label}") from error
    if not isinstance(value, dict): raise ActivationError(f"invalid {label}")
    if raw != canonical(value) + b"\n": raise ActivationError(f"{label} is not canonical exact bytes")
    return value


def valid_txid(value: str) -> str:
    if len(value) != 32 or any(char not in "0123456789abcdef" for char in value): raise ActivationError("txid must be exactly 32 lowercase hexadecimal characters")
    return value


def approval_id(value: object, action: str) -> str:
    """An approval is immutable audit evidence, never a normalized display value."""
    if not isinstance(value, str) or not value or value != value.strip():
        raise ActivationError(f"{action} requires a nonempty approval ID without leading/trailing whitespace")
    return value


def validate_authority(candidate_path: Path, gate_path: Path, expected_gate: str, source_hash: str, *, authority_boundaries: tuple[Path, ...] | None) -> dict[str, object]:
    require_regular(candidate_path, "candidate manifest"); require_regular(gate_path, "testing gate")
    candidate_bytes, gate_bytes = candidate_path.read_bytes(), gate_path.read_bytes()
    if digest(gate_bytes) != expected_gate: raise ActivationError("expected testing-gate SHA256 mismatch")
    try: candidate, gate = json.loads(candidate_bytes), json.loads(gate_bytes)
    except (json.JSONDecodeError, UnicodeDecodeError) as error: raise ActivationError("invalid authority JSON") from error
    if not authority_boundaries:
        raise ActivationError("private Testing authority requires authoritative candidate and mutable-surface boundaries")
    testing_reviewer = testing_reviewer_task_id(*authority_boundaries)
    valid = (candidate.get("schema") == CANDIDATE_SCHEMA and candidate.get("candidate_id") and candidate.get("activation_scope") == "codex_only" and candidate.get("claude_runtime") == "dormant_unvalidated" and candidate.get("package_inventory_hash") == source_hash and candidate.get("global_block_hash") == digest(BLOCK) and gate.get("schema") == GATE_SCHEMA and gate.get("status") == "TESTING_GATE_PASS" and gate.get("testing_chief_task_id") == testing_reviewer and gate.get("candidate_id") == candidate.get("candidate_id") and gate.get("candidate_manifest_sha256") == digest(candidate_bytes) and gate.get("package_inventory_hash") == source_hash and gate.get("global_block_hash") == digest(BLOCK) and gate.get("claude_runtime") == "dormant_unvalidated" and isinstance(gate.get("tested_lanes"), list) and gate["tested_lanes"] and all(isinstance(lane, str) and lane in TESTING_LANES for lane in gate["tested_lanes"]))
    if not valid: raise ActivationError("candidate/testing gate authority binding mismatch")
    return {"candidate_id": candidate["candidate_id"], "candidate_manifest_sha256": digest(candidate_bytes), "testing_gate_sha256": digest(gate_bytes), "package_inventory_hash": source_hash, "global_block_hash": digest(BLOCK), "tested_lanes": gate["tested_lanes"], "claude_runtime": "dormant_unvalidated"}


def validate_authority_placement(candidate: Path, gate: Path, source: Path | None, paths: dict[str, Path], global_agents: Path, evidence: Path) -> None:
    """Detached authority cannot be hidden inside a package or mutable journal."""
    absolute_clean(candidate, "candidate manifest"); absolute_clean(gate, "testing gate")
    if candidate == gate: raise ActivationError("candidate and testing gate must be distinct artifacts")
    for artifact in (candidate, gate):
        protected_paths = (paths["destination"], global_agents, evidence, paths["package_tx"], paths["global_tx"], paths["package_probe_parent"], paths["global_probe_parent"], paths["package_probe"], paths["global_probe"])
        if source is not None: protected_paths = (source, *protected_paths)
        for protected in protected_paths:
            if contained(artifact, protected) or contained(protected, artifact):
                raise ActivationError("authority artifact overlaps a mutable activation surface")


def topology(source: Path | None, skills: Path, global_agents: Path, evidence: Path, txid: str) -> dict[str, Path]:
    for path, label in ((skills, "skills root"), (global_agents.parent, "global parent"), (evidence, "evidence root")): require_dir(path, label)
    if source is not None: require_dir(source, "source")
    # Recovery legitimately begins after the global file was moved to its
    # transaction backup, so absence is classified later rather than rejected.
    if exists(global_agents): require_regular(global_agents, "global AGENTS file")
    destination = skills / "chief-of-staff"; package_tx = skills / ".agent-os-transactions" / txid; global_tx = global_agents.parent / ".agent-os-transactions" / txid; evidence_tx = evidence / txid
    package_probe_parent, global_probe_parent = skills / ".agent-os-probes", global_agents.parent / ".agent-os-probes"
    package_probe, global_probe = package_probe_parent / txid, global_probe_parent / txid
    # Two independently locked transaction parents must be distinct; equality
    # would both alias journals and deadlock/re-enter an advisory lock.
    # The real Codex layout is commonly <global-parent>/skills.  The inverse
    # would make the global journal nested in Skills and is rejected.
    if skills == global_agents.parent or contained(global_agents.parent, skills):
        raise ActivationError("skills root must be a strict child of, or disjoint from, global parent")
    disjoint(destination, package_tx, global_tx, evidence_tx, package_probe, global_probe)
    disjoint(evidence, package_probe_parent, global_probe_parent)
    if package_tx == global_tx or package_tx == evidence_tx or global_tx == evidence_tx: raise ActivationError("transaction leaves must be distinct")
    if source is not None:
        disjoint(source, destination, global_agents, evidence, package_tx, global_tx, package_probe, global_probe)
        if contained(package_tx, source) or contained(global_tx, source) or contained(evidence_tx, source) or contained(package_probe, source) or contained(global_probe, source): raise ActivationError("source cannot contain a derived transaction/evidence/probe leaf")
        if contained(source, skills) or contained(skills, source): raise ActivationError("source and skills root must be disjoint")
    if exists(destination) and stat.S_ISLNK(lstat(destination).st_mode): raise ActivationError("destination must not be symlink")
    for transaction_parent in (package_tx.parent, global_tx.parent):
        if exists(transaction_parent) and not stat.S_ISDIR(lstat(transaction_parent).st_mode): raise ActivationError("transaction parent must be a real directory")
    for probe_parent in (package_probe_parent, global_probe_parent):
        safe_ancestors(probe_parent, "probe parent")
        if exists(probe_parent) and (stat.S_ISLNK(lstat(probe_parent).st_mode) or not stat.S_ISDIR(lstat(probe_parent).st_mode)):
            raise ActivationError("probe parent must be a real non-symlink directory")
    reject_inode_aliases(*(path for path in (source, skills, global_agents.parent, global_agents, evidence, destination, package_tx, global_tx, evidence_tx, package_probe_parent, global_probe_parent, package_probe, global_probe) if path is not None))
    if source is not None and any(exists(source / name) for name in (".git", ".superpowers")): raise ActivationError("source must be extracted reviewed candidate")
    return {"destination": destination, "package_tx": package_tx, "global_tx": global_tx, "evidence_tx": evidence_tx, "package_probe_parent": package_probe_parent, "global_probe_parent": global_probe_parent, "package_probe": package_probe, "global_probe": global_probe}


def plan_data(source: Path, skills: Path, global_agents: Path, evidence: Path, txid: str, authority: dict[str, object]) -> dict[str, object]:
    paths = topology(source, skills, global_agents, evidence, txid); source_hash = inventory_hash(source); pre_package = inventory_hash(paths["destination"], absent_ok=True)
    if source_hash != authority["package_inventory_hash"]: raise ActivationError("source inventory no longer matches candidate")
    global_pre = global_bytes(global_agents); assert global_pre is not None
    global_mode = stat.S_IMODE(lstat(global_agents).st_mode); global_post = prospective_global(global_pre)
    global_pre_hash = global_hash(global_agents); assert global_pre_hash is not None
    global_post_hash = digest(canonical({"sha256": digest(global_post), "mode": global_mode}))
    return {"schema": SCHEMA, "txid": txid, "activation_scope": "codex_only", "claude_runtime": "dormant_unvalidated", "source": str(source), "skills_root": str(skills), "global_agents": str(global_agents), "evidence_root": str(evidence), "destination": str(paths["destination"]), "original_destination_present": inventory(paths["destination"], absent_ok=True)["present"], "source_inventory_hash": source_hash, "package_pre_hash": pre_package, "package_post_hash": source_hash, "package_change_required": pre_package != source_hash, "global_pre_hash": global_pre_hash, "global_post_hash": global_post_hash, "global_mode": global_mode, "global_change_required": global_pre_hash != global_post_hash, "global_block_hash": digest(BLOCK), "authority": authority, "fixed_names": FIXED}


@contextmanager
def locks(first: Path, second: Path):
    handles = []
    try:
        for parent in sorted((first, second), key=str):
            require_dir(parent, "transaction parent"); fd = os.open(str(parent), os.O_RDONLY); fcntl.flock(fd, fcntl.LOCK_EX); handles.append(fd)
        yield
    finally:
        for fd in reversed(handles):
            try: fcntl.flock(fd, fcntl.LOCK_UN)
            finally: os.close(fd)


def _rename_noreplace(source: Path, target: Path) -> None:
    label, fault = os.environ.get("AGENT_OS_RENAME_LABEL", ""), os.environ.get("AGENT_OS_RENAME_FAULT", "")
    if fault == f"before:{label}": raise ActivationError(f"injected before rename {label}")
    if sys.platform == "darwin":
        function = ctypes.CDLL(None, use_errno=True).renamex_np; result = function(ctypes.c_char_p(os.fsencode(source)), ctypes.c_char_p(os.fsencode(target)), ctypes.c_uint(4))
    elif sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True); syscall = 316 if ctypes.sizeof(ctypes.c_void_p) == 8 else 353; result = libc.syscall(syscall, -100, ctypes.c_char_p(os.fsencode(source)), -100, ctypes.c_char_p(os.fsencode(target)), 1)
    else: raise ActivationError("kernel no-replace rename is unavailable on this platform")
    if result != 0:
        code = ctypes.get_errno(); raise OSError(code, os.strerror(code), str(target))
    fsync_dir(source.parent)
    if target.parent != source.parent: fsync_dir(target.parent)
    if os.environ.get("AGENT_OS_RENAME_EXIT") == f"after:{label}": os._exit(92)
    if fault == f"after:{label}": raise ActivationError(f"injected after rename {label}")
    if fault == f"keyboard-after:{label}": raise KeyboardInterrupt(f"injected after rename {label}")
    if fault == f"systemexit-after:{label}": raise SystemExit(93)


def _probe_stat(fd: int, name: str):
    return os.stat(name, dir_fd=fd, follow_symlinks=False)


def _probe_read(fd: int, name: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    handle = os.open(name, flags, dir_fd=fd)
    try:
        info = os.fstat(handle)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1: raise ActivationError("unsafe probe file")
        return os.read(handle, info.st_size + 1)
    finally: os.close(handle)


def _probe_write_new(fd: int, name: str, data: bytes) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    handle = os.open(name, flags, 0o600, dir_fd=fd)
    try: os.write(handle, data); os.fsync(handle)
    finally: os.close(handle)


def _renameat_noreplace(fd: int, source: str, target: str) -> None:
    if sys.platform == "darwin":
        function = ctypes.CDLL(None, use_errno=True).renameatx_np
        result = function(ctypes.c_int(fd), ctypes.c_char_p(os.fsencode(source)), ctypes.c_int(fd), ctypes.c_char_p(os.fsencode(target)), ctypes.c_uint(4))
    elif sys.platform.startswith("linux"):
        libc = ctypes.CDLL(None, use_errno=True); syscall = 316 if ctypes.sizeof(ctypes.c_void_p) == 8 else 353
        result = libc.syscall(syscall, ctypes.c_int(fd), ctypes.c_char_p(os.fsencode(source)), ctypes.c_int(fd), ctypes.c_char_p(os.fsencode(target)), ctypes.c_uint(1))
    else: raise ActivationError("kernel no-replace rename is unavailable on this platform")
    if result != 0:
        code = ctypes.get_errno(); raise OSError(code, os.strerror(code), target)
    os.fsync(fd)


def probe_noreplace(fd: int, *, directory: bool, label: str) -> None:
    """Descriptor-relative disposable capability test; retained evidence only."""
    if os.environ.get("AGENT_OS_PROBE_FAIL") == label: raise ActivationError(f"injected no-replace probe failure: {label}")
    token = ".agent-os-probe-" + os.urandom(8).hex(); source, target = token + "-source", token + "-target"
    success_source, success_target = token + "-success-source", token + "-success-target"
    if directory:
        os.mkdir(source, dir_fd=fd); os.mkdir(target, dir_fd=fd); os.mkdir(success_source, dir_fd=fd)
    else:
        _probe_write_new(fd, source, b"probe-source\n"); _probe_write_new(fd, target, b"probe-target\n"); _probe_write_new(fd, success_source, b"probe-success\n")
    source_id, target_id = _probe_stat(fd, source), _probe_stat(fd, target)
    try: _renameat_noreplace(fd, source, target)
    except OSError as error:
        if error.errno != errno.EEXIST: raise ActivationError("no-replace rename capability unavailable") from error
    else: raise ActivationError("no-replace capability probe overwrote an existing target")
    if _probe_stat(fd, source) != source_id or _probe_stat(fd, target) != target_id:
        raise ActivationError("probe object changed concurrently; preserving replacement")
    if directory:
        if not stat.S_ISDIR(_probe_stat(fd, source).st_mode) or not stat.S_ISDIR(_probe_stat(fd, target).st_mode): raise ActivationError("no-replace directory EEXIST probe did not preserve both entries")
        _renameat_noreplace(fd, success_source, success_target)
        try: _probe_stat(fd, success_source); raise ActivationError("no-replace directory probe source remained")
        except FileNotFoundError: pass
        if not stat.S_ISDIR(_probe_stat(fd, success_target).st_mode): raise ActivationError("no-replace directory probe move failed")
    else:
        if _probe_read(fd, target) != b"probe-target\n" or _probe_read(fd, source) != b"probe-source\n": raise ActivationError("no-replace file EEXIST probe did not preserve bytes")
        _renameat_noreplace(fd, success_source, success_target)
        try: _probe_stat(fd, success_source); raise ActivationError("no-replace file probe source remained")
        except FileNotFoundError: pass
        if _probe_read(fd, success_target) != b"probe-success\n": raise ActivationError("no-replace file probe move failed")
    os.fsync(fd)


def _open_directory_nofollow(path: Path, label: str, *, dir_fd: int | None = None) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(str(path) if dir_fd is None else path.name, flags, dir_fd=dir_fd)
    except OSError as error:
        raise ActivationError(f"{label} must be a real non-symlink directory") from error
    if not stat.S_ISDIR(os.fstat(fd).st_mode):
        os.close(fd); raise ActivationError(f"{label} must be a real directory")
    return fd


def create_probe_root(parent: Path, probe_parent: Path, probe_root: Path, txid: str) -> int:
    """Create retained probe evidence through no-follow dirfds, never path traversal."""
    if probe_parent.parent != parent or probe_root.parent != probe_parent or probe_root.name != txid:
        raise ActivationError("invalid derived probe topology")
    safe_ancestors(probe_parent, "probe parent")
    parent_fd = _open_directory_nofollow(parent, "probe filesystem parent")
    probes_fd = root_fd = None
    try:
        try: os.mkdir(probe_parent.name, dir_fd=parent_fd)
        except FileExistsError: pass
        probes_fd = _open_directory_nofollow(probe_parent, "probe parent", dir_fd=parent_fd)
        try: os.mkdir(txid, dir_fd=probes_fd)
        except FileExistsError as error: raise ActivationError("probe evidence transaction ID already used") from error
        root_fd = _open_directory_nofollow(probe_root, "probe evidence transaction", dir_fd=probes_fd)
        os.fsync(root_fd); os.fsync(probes_fd); os.fsync(parent_fd)
        return root_fd
    except BaseException:
        if root_fd is not None: os.close(root_fd)
        raise
    finally:
        if probes_fd is not None: os.close(probes_fd)
        os.close(parent_fd)


def probe_root_matches_fd(probe_root: Path, fd: int) -> None:
    safe_ancestors(probe_root, "probe evidence transaction")
    path_info, fd_info = lstat(probe_root), os.fstat(fd)
    if path_info is None or stat.S_ISLNK(path_info.st_mode) or not stat.S_ISDIR(path_info.st_mode) or (path_info.st_dev, path_info.st_ino) != (fd_info.st_dev, fd_info.st_ino):
        raise ActivationError("CONFLICT: probe root pathname no longer identifies held probe evidence")


def inject_probe_substitution(probe_root: Path, prefix: str) -> None:
    """Test-only post-validation race hook; production never sets this variable."""
    if os.environ.get("AGENT_OS_PROBE_SUBSTITUTE") != prefix: return
    outside = Path(os.environ.get("AGENT_OS_PROBE_SUBSTITUTE_OUTSIDE", ""))
    require_dir(outside, "probe substitution outside")
    retained = probe_root.parent / (probe_root.name + ".retained-" + prefix)
    os.rename(probe_root, retained); os.symlink(outside, probe_root)


def move(source: Path, target: Path, label: str) -> None:
    if not exists(source): raise ActivationError(f"expected move source missing: {source}")
    if exists(target): raise ActivationError(f"expected move target already exists: {target}")
    old = os.environ.get("AGENT_OS_RENAME_LABEL"); os.environ["AGENT_OS_RENAME_LABEL"] = label
    try: _rename_noreplace(source, target)
    finally:
        if old is None: os.environ.pop("AGENT_OS_RENAME_LABEL", None)
        else: os.environ["AGENT_OS_RENAME_LABEL"] = old


def checked_move(paths: dict[str, Path], plan: dict[str, object], source: Path, target: Path, label: str) -> None:
    """Classify the entire fixed tuple on both sides of every rollback move."""
    reject_unrecognized(states(paths, plan)); move(source, target, label); reject_unrecognized(states(paths, plan))


def classify_package(path: Path, pre: str, post: str) -> str:
    if not exists(path): return "absent"
    actual = inventory_hash(path, absent_ok=True)
    return "PRE" if actual == pre else "POST" if actual == post else "UNRECOGNIZED"
def classify_global(path: Path, pre: str, post: str) -> str:
    if not exists(path): return "absent"
    try: actual = global_hash(path)
    except ActivationError: return "UNRECOGNIZED"
    return "PRE" if actual == pre else "POST" if actual == post else "UNRECOGNIZED"


def intent_paths(paths: dict[str, Path]) -> tuple[Path, Path]: return paths["package_tx"] / FIXED["intent"], paths["global_tx"] / FIXED["intent"]
def intent_from_tx(paths: dict[str, Path]) -> dict[str, object] | None:
    one, two = intent_paths(paths)
    if not exists(one) and not exists(two): return None
    if not exists(one) or not exists(two): raise ActivationError("CONFLICT: incomplete immutable activation intent")
    left, right = load_json(one, "activation intent"), load_json(two, "activation intent")
    if canonical(left) != canonical(right): raise ActivationError("CONFLICT: activation intent replicas differ")
    return left


def verify_plan(plan: dict[str, object], source: Path, skills: Path, global_agents: Path, evidence: Path, txid: str, authority: dict[str, object]) -> None:
    fresh = plan_data(source, skills, global_agents, evidence, txid, authority)
    if canonical(plan) != canonical(fresh): raise ActivationError("frozen plan no longer matches canonical roots or identities")


def verify_intent(plan: dict[str, object], source: Path | None, skills: Path, global_agents: Path, evidence: Path, txid: str, authority: dict[str, object], *, allow_missing_plan: bool = False) -> None:
    """Validate immutable topology and authority without treating recovery state as PRE."""
    paths = topology(source, skills, global_agents, evidence, txid)
    expected = {"schema": SCHEMA, "txid": txid, "activation_scope": "codex_only", "claude_runtime": "dormant_unvalidated",
                "skills_root": str(skills), "global_agents": str(global_agents), "evidence_root": str(evidence),
                "destination": str(paths["destination"]), "global_block_hash": digest(BLOCK), "authority": authority, "fixed_names": FIXED}
    if any(plan.get(key) != value for key, value in expected.items()): raise ActivationError("immutable intent does not match canonical roots or authority")
    approval_id(plan.get("operator_approval_id"), "activation intent")
    if source is not None and plan.get("source") != str(source): raise ActivationError("immutable intent source differs from apply source")
    plan_file = paths["evidence_tx"] / FIXED["plan"]
    if exists(plan_file):
        require_regular(plan_file, "frozen plan")
        if plan.get("plan_sha256") != digest(plan_file.read_bytes()): raise ActivationError("frozen plan bytes no longer match immutable intent")
    elif not allow_missing_plan: raise ActivationError("frozen plan evidence is missing")
    if source is not None and inventory_hash(source) != plan.get("source_inventory_hash"): raise ActivationError("source mutated since immutable intent")


def stage(source: Path, global_agents: Path, paths: dict[str, Path], plan: dict[str, object]) -> None:
    package_stage, global_stage = paths["package_tx"] / FIXED["package_stage"], paths["global_tx"] / FIXED["global_stage"]
    if exists(package_stage) or exists(global_stage): raise ActivationError("transaction stage already exists")
    if plan["package_change_required"]:
        shutil.copytree(source, package_stage, symlinks=False); fsync_dir(package_stage.parent)
        if inventory_hash(package_stage) != plan["package_post_hash"]: raise ActivationError("staged package identity does not match frozen post-state")
    if plan["global_change_required"]:
        write_new(global_stage, prospective_global(global_bytes(global_agents) or b"")); os.chmod(global_stage, int(plan["global_mode"])); fsync_dir(global_stage.parent)
        if global_hash(global_stage) != plan["global_post_hash"]: raise ActivationError("staged global identity does not match frozen post-state")


def states(paths: dict[str, Path], plan: dict[str, object]) -> dict[str, str]:
    return {"live_package": classify_package(paths["destination"], str(plan["package_pre_hash"]), str(plan["package_post_hash"])), "stage_package": classify_package(paths["package_tx"] / FIXED["package_stage"], str(plan["package_pre_hash"]), str(plan["package_post_hash"])), "backup_package": classify_package(paths["package_tx"] / FIXED["package_backup"], str(plan["package_pre_hash"]), str(plan["package_post_hash"])), "quarantine_package": classify_package(paths["package_tx"] / FIXED["package_quarantine"], str(plan["package_pre_hash"]), str(plan["package_post_hash"])), "live_global": classify_global(Path(str(plan["global_agents"])), str(plan["global_pre_hash"]), str(plan["global_post_hash"])), "stage_global": classify_global(paths["global_tx"] / FIXED["global_stage"], str(plan["global_pre_hash"]), str(plan["global_post_hash"])), "backup_global": classify_global(paths["global_tx"] / FIXED["global_backup"], str(plan["global_pre_hash"]), str(plan["global_post_hash"])), "quarantine_global": classify_global(paths["global_tx"] / FIXED["global_quarantine"], str(plan["global_pre_hash"]), str(plan["global_post_hash"]))}
def reject_unrecognized(state: dict[str, str]) -> None:
    bad = [key for key, value in state.items() if value == "UNRECOGNIZED"]
    if bad: raise ActivationError("CONFLICT: unrecognized surface(s): " + ", ".join(bad))


def live_post_package(plan: dict[str, object]) -> str:
    return "POST" if plan["package_change_required"] else "PRE"


def live_post_global(plan: dict[str, object]) -> str:
    return "POST" if plan["global_change_required"] else "PRE"


ROLLBACK_SLOTS = ("live_package", "stage_package", "backup_package", "quarantine_package", "live_global", "stage_global", "backup_global", "quarantine_global")


def rollback_sequence(plan: dict[str, object]) -> list[dict[str, str]]:
    """Generated R0..Rn complete slot tuples for this exact activation."""
    state = {slot: "absent" for slot in ROLLBACK_SLOTS}
    state["live_package"] = live_post_package(plan)
    state["live_global"] = live_post_global(plan)
    if plan["package_change_required"] and plan["original_destination_present"]: state["backup_package"] = "PRE"
    if plan["global_change_required"]: state["backup_global"] = "PRE"
    result = [dict(state)]
    if plan["package_change_required"]:
        state["live_package"], state["quarantine_package"] = "absent", "POST"; result.append(dict(state))
    if plan["global_change_required"]:
        state["live_global"], state["quarantine_global"] = "absent", "POST"; result.append(dict(state))
    if plan["package_change_required"] and plan["original_destination_present"]:
        state["backup_package"], state["live_package"] = "absent", "PRE"; result.append(dict(state))
    if plan["global_change_required"]:
        state["backup_global"], state["live_global"] = "absent", "PRE"; result.append(dict(state))
    return result


def rollback_state_index(paths: dict[str, Path], plan: dict[str, object]) -> int:
    actual = states(paths, plan); reject_unrecognized(actual)
    sequence = rollback_sequence(plan)
    for index, expected in enumerate(sequence):
        if actual == expected: return index
    raise ActivationError("CONFLICT: rollback tuple is not an exact reachable state")


def rollback_moves(paths: dict[str, Path], plan: dict[str, object]) -> list[tuple[Path, Path, str]]:
    """The one-slot-pair moves which generate R1..Rn from R0."""
    moves: list[tuple[Path, Path, str]] = []
    if plan["package_change_required"]:
        moves.append((paths["destination"], paths["package_tx"] / FIXED["package_quarantine"], "rollback-package-post-to-quarantine"))
    if plan["global_change_required"]:
        moves.append((Path(str(plan["global_agents"])), paths["global_tx"] / FIXED["global_quarantine"], "rollback-global-post-to-quarantine"))
    if plan["package_change_required"] and plan["original_destination_present"]:
        moves.append((paths["package_tx"] / FIXED["package_backup"], paths["destination"], "rollback-package-pre-to-live"))
    if plan["global_change_required"]:
        moves.append((paths["global_tx"] / FIXED["global_backup"], Path(str(plan["global_agents"])), "rollback-global-pre-to-live"))
    if len(moves) + 1 != len(rollback_sequence(plan)):
        raise ActivationError("internal rollback transition generation mismatch")
    return moves


def advance_rollback(paths: dict[str, Path], plan: dict[str, object], index: int) -> None:
    sequence = rollback_sequence(plan)
    if index >= len(sequence) - 1: return
    if rollback_state_index(paths, plan) != index: raise ActivationError("CONFLICT: rollback tuple changed before transition")
    source, target, label = rollback_moves(paths, plan)[index]
    move(source, target, label)
    if rollback_state_index(paths, plan) != index + 1: raise ActivationError("CONFLICT: rollback tuple changed after transition")


def commit_data(plan: dict[str, object], kind: str) -> dict[str, object]: return {"schema": SCHEMA, "kind": kind, "txid": plan["txid"], "intent_sha256": digest(canonical(plan)), "package_post_hash": plan["package_post_hash"], "global_post_hash": plan["global_post_hash"]}
def valid_commit(paths: dict[str, Path], plan: dict[str, object], kind: str) -> int:
    name, expected = (FIXED["activation_commit"] if kind == "activation" else FIXED["rollback_commit"]), canonical(commit_data(plan, kind)); count = 0
    for path in (paths["package_tx"] / name, paths["global_tx"] / name):
        if exists(path):
            if canonical(load_json(path, f"{kind} commit")) != expected: raise ActivationError("CONFLICT: invalid commit replica")
            count += 1
    return count
def publish_commit(paths: dict[str, Path], plan: dict[str, object], kind: str) -> None:
    name, data = (FIXED["activation_commit"] if kind == "activation" else FIXED["rollback_commit"]), commit_data(plan, kind)
    for root in (paths["package_tx"], paths["global_tx"]):
        replica = root / name
        if exists(replica):
            if canonical(load_json(replica, f"{kind} commit")) != canonical(data): raise ActivationError("CONFLICT: existing commit replica differs")
        else: write_json_new(replica, data)
def publish_receipt(paths: dict[str, Path], plan: dict[str, object], state: str) -> None:
    receipt = paths["evidence_tx"] / (FIXED["receipt"] if state == "activated" else FIXED["rollback_receipt"])
    data = {"schema": SCHEMA, "txid": plan["txid"], "state": state, "intent_sha256": digest(canonical(plan)), "authority": plan["authority"]}
    if exists(receipt):
        if canonical(load_json(receipt, f"{state} receipt")) != canonical(data): raise ActivationError("CONFLICT: existing receipt differs")
    else: write_json_new(receipt, data)


def rollback_plan_value(plan: dict[str, object]) -> dict[str, object]:
    return {"schema": SCHEMA, "txid": plan["txid"], "intent_sha256": digest(canonical(plan)), "target": "baseline"}


def rollback_plan_bytes(plan: dict[str, object]) -> bytes:
    return canonical(rollback_plan_value(plan)) + b"\n"


def rollback_plan_data(paths: dict[str, Path], plan: dict[str, object]) -> tuple[dict[str, object], str]:
    path = paths["evidence_tx"] / FIXED["rollback_plan"]
    value = load_json(path, "rollback plan")
    expected = rollback_plan_value(plan)
    if value != expected or path.read_bytes() != rollback_plan_bytes(plan): raise ActivationError("rollback plan does not bind the immutable activation intent")
    return value, digest(rollback_plan_bytes(plan))


def rollback_intent_value(plan: dict[str, object], approval: str) -> dict[str, object]:
    approval = approval_id(approval, "rollback")
    return {"schema": SCHEMA, "kind": "rollback", "txid": plan["txid"], "activation_intent_sha256": digest(canonical(plan)), "rollback_plan_sha256": digest(rollback_plan_bytes(plan)), "operator_approval_id": approval}


def validate_rollback_intent(paths: dict[str, Path], plan: dict[str, object]) -> dict[str, object]:
    left_path, right_path = paths["package_tx"] / FIXED["rollback_intent"], paths["global_tx"] / FIXED["rollback_intent"]
    if not exists(left_path) or not exists(right_path): raise ActivationError("CONFLICT: incomplete immutable rollback intent")
    left, right = load_json(left_path, "rollback intent"), load_json(right_path, "rollback intent")
    if left != right: raise ActivationError("CONFLICT: rollback intent replicas differ")
    required = {"schema", "kind", "txid", "activation_intent_sha256", "rollback_plan_sha256", "operator_approval_id"}
    if set(left) != required: raise ActivationError("CONFLICT: rollback intent schema is invalid")
    try: stored_approval = approval_id(left.get("operator_approval_id"), "rollback intent")
    except ActivationError as error: raise ActivationError("CONFLICT: rollback intent schema is invalid") from error
    expected = rollback_intent_value(plan, stored_approval)
    if left != expected: raise ActivationError("CONFLICT: rollback intent binding is invalid")
    return left


def restore_baseline(paths: dict[str, Path], plan: dict[str, object]) -> None:
    state = states(paths, plan); reject_unrecognized(state); original = bool(plan["original_destination_present"])
    if plan["package_change_required"] and state["live_package"] == "POST": move(paths["destination"], paths["package_tx"] / FIXED["package_quarantine"], "recover-package-post"); state = states(paths, plan)
    if plan["global_change_required"] and state["live_global"] == "POST": move(Path(str(plan["global_agents"])), paths["global_tx"] / FIXED["global_quarantine"], "recover-global-post"); state = states(paths, plan)
    if plan["package_change_required"] and original and state["live_package"] == "absent":
        if state["backup_package"] != "PRE": raise ActivationError("CONFLICT: original package backup unavailable")
        move(paths["package_tx"] / FIXED["package_backup"], paths["destination"], "recover-package-pre"); state = states(paths, plan)
    if not original and state["live_package"] != "absent": raise ActivationError("CONFLICT: package cannot return to absent baseline")
    if plan["global_change_required"] and state["live_global"] == "absent":
        if state["backup_global"] != "PRE": raise ActivationError("CONFLICT: original global backup unavailable")
        move(paths["global_tx"] / FIXED["global_backup"], Path(str(plan["global_agents"])), "recover-global-pre"); state = states(paths, plan)
    final = states(paths, plan); reject_unrecognized(final)
    if final["live_global"] != "PRE" or (original and final["live_package"] != "PRE") or (not original and final["live_package"] != "absent"): raise ActivationError("CONFLICT: baseline recovery incomplete")


def apply(source: Path, skills: Path, global_agents: Path, evidence: Path, txid: str, authority: dict[str, object], approval: str) -> None:
    approval = approval_id(approval, "apply")
    paths = topology(source, skills, global_agents, evidence, txid); plan = load_json(paths["evidence_tx"] / FIXED["plan"], "frozen plan"); verify_plan(plan, source, skills, global_agents, evidence, txid, authority)
    if exists(paths["package_tx"]) or exists(paths["global_tx"]): raise ActivationError("transaction ID already used")
    for output in (paths["evidence_tx"] / FIXED["receipt"], paths["evidence_tx"] / FIXED["rollback_receipt"], paths["evidence_tx"] / FIXED["rollback_plan"]):
        if exists(output): raise ActivationError("preflight output conflict before mutation")
    with locks(skills, global_agents.parent):
        paths["package_tx"].parent.mkdir(exist_ok=True); paths["global_tx"].parent.mkdir(exist_ok=True); require_dir(paths["package_tx"].parent, "package transaction root"); require_dir(paths["global_tx"].parent, "global transaction root")
        held_probes: list[tuple[Path, int, str]] = []
        try:
            for parent, prefix, probe_parent, probe_root in ((skills, "skills", paths["package_probe_parent"], paths["package_probe"]), (global_agents.parent, "global", paths["global_probe_parent"], paths["global_probe"])):
                held_fd = create_probe_root(parent, probe_parent, probe_root, txid)
                held_probes.append((probe_root, held_fd, prefix))
                probe_noreplace(held_fd, directory=True, label=f"{prefix}-directory")
                probe_noreplace(held_fd, directory=False, label=f"{prefix}-file")
            for probe_root, held_fd, prefix in held_probes:
                inject_probe_substitution(probe_root, prefix)
                probe_root_matches_fd(probe_root, held_fd)
        finally:
            for _, held_fd, _ in reversed(held_probes): os.close(held_fd)
        paths["package_tx"].mkdir(); paths["global_tx"].mkdir(); fsync_dir(paths["package_tx"].parent); fsync_dir(paths["global_tx"].parent)
        # The plan is evidence, not a path authority. Its byte digest is
        # carried into both immutable intents before the first live rename.
        intent = dict(plan); intent["plan_sha256"] = digest((paths["evidence_tx"] / FIXED["plan"]).read_bytes()); intent["operator_approval_id"] = approval
        for path in intent_paths(paths): write_json_new(path, intent)
        plan = intent
        if inventory_hash(source) != plan["source_inventory_hash"]: raise ActivationError("source mutated before staging")
        stage(source, global_agents, paths, plan); fresh = states(paths, plan); reject_unrecognized(fresh)
        if fresh["live_package"] not in ({"PRE"} if plan["original_destination_present"] else {"absent"}) or fresh["live_global"] != "PRE": raise ActivationError("pre-state drift before first live move")
        if plan["package_change_required"] and plan["original_destination_present"]:
            move(paths["destination"], paths["package_tx"] / FIXED["package_backup"], "package-pre-to-backup")
            if states(paths, plan)["backup_package"] != "PRE": raise ActivationError("backup package identity mismatch")
        if inventory_hash(source) != plan["source_inventory_hash"] or states(paths, plan)["live_global"] != "PRE": raise ActivationError("source/global drift before global move")
        if plan["global_change_required"]:
            move(global_agents, paths["global_tx"] / FIXED["global_backup"], "global-pre-to-backup")
            if states(paths, plan)["backup_global"] != "PRE": raise ActivationError("backup global identity mismatch")
        if inventory_hash(source) != plan["source_inventory_hash"]: raise ActivationError("source mutated before package install")
        if plan["package_change_required"]:
            move(paths["package_tx"] / FIXED["package_stage"], paths["destination"], "package-stage-to-live")
            if states(paths, plan)["live_package"] != "POST": raise ActivationError("package post identity mismatch")
        if plan["global_change_required"]:
            move(paths["global_tx"] / FIXED["global_stage"], global_agents, "global-stage-to-live")
            if states(paths, plan)["live_global"] != "POST": raise ActivationError("global post identity mismatch")
        publish_commit(paths, plan, "activation"); publish_receipt(paths, plan, "activated")


def recover(source: Path, skills: Path, global_agents: Path, evidence: Path, txid: str, authority: dict[str, object]) -> str:
    paths = topology(source, skills, global_agents, evidence, txid)
    if not exists(paths["package_tx"]) and not exists(paths["global_tx"]): return "baseline"
    plan = intent_from_tx(paths)
    if plan is None: raise ActivationError("CONFLICT: transaction roots lack immutable intent")
    verify_intent(plan, source, skills, global_agents, evidence, txid, authority, allow_missing_plan=True)
    with locks(skills, global_agents.parent):
        rollback_intent = paths["package_tx"] / FIXED["rollback_intent"]
        if exists(rollback_intent) or exists(paths["global_tx"] / FIXED["rollback_intent"]):
            plan_path = paths["evidence_tx"] / FIXED["rollback_plan"]
            rollback_value = validate_rollback_intent(paths, plan)
            evidence_gap = not exists(plan_path)
            if exists(plan_path):
                _, rollback_sha = rollback_plan_data(paths, plan)
                if rollback_value.get("rollback_plan_sha256") != rollback_sha: raise ActivationError("CONFLICT: rollback intent does not bind fixed rollback plan")
            index = rollback_state_index(paths, plan)
            while index < len(rollback_sequence(plan)) - 1:
                advance_rollback(paths, plan, index); index += 1
            publish_commit(paths, plan, "rollback"); publish_receipt(paths, plan, "baseline")
            return "baseline-evidence-gap" if evidence_gap else "baseline"
        state = states(paths, plan); reject_unrecognized(state); commits = valid_commit(paths, plan, "activation")
        if state["live_package"] == live_post_package(plan) and state["live_global"] == live_post_global(plan) and commits: publish_commit(paths, plan, "activation"); publish_receipt(paths, plan, "activated"); return "activated"
        if commits: raise ActivationError("CONFLICT: activation commit exists but live state is incomplete")
        restore_baseline(paths, plan); return "baseline"


def rollback_plan(source: Path, skills: Path, global_agents: Path, evidence: Path, txid: str, authority: dict[str, object]) -> None:
    paths = topology(source, skills, global_agents, evidence, txid); plan = intent_from_tx(paths)
    if plan is None: raise ActivationError("activation intent is required")
    verify_intent(plan, source, skills, global_agents, evidence, txid, authority)
    if valid_commit(paths, plan, "activation") != 2: raise ActivationError("activation commit is required")
    write_new(paths["evidence_tx"] / FIXED["rollback_plan"], rollback_plan_bytes(plan))


def rollback(source: Path, skills: Path, global_agents: Path, evidence: Path, txid: str, authority: dict[str, object], approval: str) -> None:
    approval = approval_id(approval, "rollback")
    paths = topology(source, skills, global_agents, evidence, txid); plan = intent_from_tx(paths)
    if plan is None: raise ActivationError("activation intent is required")
    verify_intent(plan, source, skills, global_agents, evidence, txid, authority)
    _, rollback_sha = rollback_plan_data(paths, plan)
    with locks(skills, global_agents.parent):
        # Re-read exact bytes under lock; an external writer cannot race a
        # reviewed rollback plan into the intent after the earlier check.
        _, locked_rollback_sha = rollback_plan_data(paths, plan)
        if locked_rollback_sha != rollback_sha: raise ActivationError("rollback plan changed before locked transition")
        if valid_commit(paths, plan, "activation") != 2: raise ActivationError("rollback requires two exact activation commits")
        artifacts = (paths["package_tx"] / FIXED["rollback_intent"], paths["global_tx"] / FIXED["rollback_intent"], paths["package_tx"] / FIXED["rollback_commit"], paths["global_tx"] / FIXED["rollback_commit"], paths["evidence_tx"] / FIXED["rollback_receipt"])
        if any(exists(path) for path in artifacts): raise ActivationError("rollback artifacts already exist")
        if rollback_state_index(paths, plan) != 0: raise ActivationError("rollback requires the exact R0 activated tuple")
        rollback_intent = rollback_intent_value(plan, approval)
        if rollback_intent["rollback_plan_sha256"] != rollback_sha: raise ActivationError("rollback plan deterministic binding mismatch")
        for root in (paths["package_tx"], paths["global_tx"]): write_json_new(root / FIXED["rollback_intent"], rollback_intent)
        for index in range(len(rollback_sequence(plan)) - 1): advance_rollback(paths, plan, index)
        if rollback_state_index(paths, plan) != len(rollback_sequence(plan)) - 1: raise ActivationError("CONFLICT: rollback did not reach final exact tuple")
        publish_commit(paths, plan, "rollback"); publish_receipt(paths, plan, "baseline")


def verify(source: Path, skills: Path, global_agents: Path, evidence: Path, txid: str, authority: dict[str, object], wanted: str) -> None:
    paths = topology(source, skills, global_agents, evidence, txid); plan = intent_from_tx(paths)
    if plan is None: raise ActivationError("activation intent is required")
    verify_intent(plan, source, skills, global_agents, evidence, txid, authority)
    state = states(paths, plan); reject_unrecognized(state)
    if wanted == "activated":
        if valid_commit(paths, plan, "activation") < 1 or state["live_package"] != live_post_package(plan) or state["live_global"] != live_post_global(plan): raise ActivationError("activation state is not verified")
    else:
        package_ok = state["live_package"] == ("PRE" if plan["original_destination_present"] else "absent")
        if not package_ok or state["live_global"] != "PRE": raise ActivationError("baseline state is not verified")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__); commands = result.add_subparsers(dest="command", required=True)
    def common(command, approval: bool = False, source: bool = False):
        if source: command.add_argument("--source", required=True)
        command.add_argument("--skills-root", required=True); command.add_argument("--global-agents", required=True); command.add_argument("--evidence-root", required=True); command.add_argument("--txid", required=True); command.add_argument("--candidate", required=True); command.add_argument("--testing-gate", required=True); command.add_argument("--expected-testing-gate-sha256", required=True)
        if approval: command.add_argument("--operator-approval-id", required=True)
    common(commands.add_parser("plan"), source=True); common(commands.add_parser("apply"), True, True)
    for name in ("rollback-plan", "recover"): common(commands.add_parser(name))
    common(commands.add_parser("rollback"), True); verify_cmd = commands.add_parser("verify"); common(verify_cmd); verify_cmd.add_argument("--state", choices=("activated", "baseline"), required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        source = Path(args.source) if hasattr(args, "source") else None
        skills, global_agents, evidence, txid = Path(args.skills_root), Path(args.global_agents), Path(args.evidence_root), valid_txid(args.txid)
        paths = topology(source, skills, global_agents, evidence, txid)
        if source is not None:
            source_hash = inventory_hash(source)
        else:
            frozen = intent_from_tx(paths)
            if frozen is None:
                # Validate caller-pinned authority against its own declared
                # inventory before refusing to infer a baseline without intent.
                require_regular(Path(args.candidate), "candidate manifest")
                candidate_probe = json.loads(Path(args.candidate).read_bytes())
                source_hash = str(candidate_probe.get("package_inventory_hash", ""))
            else: source_hash = str(frozen.get("source_inventory_hash", ""))
        authority_boundaries = (
            Path(args.candidate).parent,
            Path(args.testing_gate).parent,
            skills,
            global_agents.parent,
            evidence,
            paths["destination"],
            paths["package_tx"],
            paths["global_tx"],
            paths["package_probe_parent"],
            paths["global_probe_parent"],
        )
        if source is not None:
            authority_boundaries = (source, *authority_boundaries)
        authority = validate_authority(Path(args.candidate), Path(args.testing_gate), args.expected_testing_gate_sha256, source_hash, authority_boundaries=authority_boundaries)
        validate_authority_placement(Path(args.candidate), Path(args.testing_gate), source, paths, global_agents, evidence)
        if source is None and intent_from_tx(paths) is None: raise ActivationError("no immutable intent: baseline cannot be verified without frozen identity")
        if args.command == "plan":
            if exists(paths["evidence_tx"]): raise ActivationError("evidence transaction ID already used")
            paths["evidence_tx"].mkdir(); fsync_dir(paths["evidence_tx"].parent); write_json_new(paths["evidence_tx"] / FIXED["plan"], plan_data(source, skills, global_agents, evidence, txid, authority))
        elif args.command == "apply": apply(source, skills, global_agents, evidence, txid, authority, args.operator_approval_id)
        elif args.command == "recover": result = recover(source, skills, global_agents, evidence, txid, authority)
        elif args.command == "rollback-plan": rollback_plan(source, skills, global_agents, evidence, txid, authority)
        elif args.command == "rollback": rollback(source, skills, global_agents, evidence, txid, authority, args.operator_approval_id)
        else: verify(source, skills, global_agents, evidence, txid, authority, args.state)
        output = {"ok": True, "command": args.command, "txid": txid}
        if args.command == "recover" and result == "baseline-evidence-gap": output["evidence_gap"] = "rollback-plan-missing; immutable rollback intents restored baseline"
        print(json.dumps(output, sort_keys=True)); return 0
    except (ActivationError, OSError, shutil.Error) as error: print(f"ERROR: {error}", file=sys.stderr); return 1


if __name__ == "__main__": raise SystemExit(main())
