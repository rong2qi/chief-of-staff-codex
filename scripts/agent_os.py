#!/usr/bin/env python3
"""Create and verify the portable, deterministic Agent OS V1 contract.

This module deliberately has no dependency on the Chief initializer.  Task 2
can compose it for new Chief projects while this CLI keeps legacy projects in
their existing mode until an explicit ``migrate`` command is issued.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

try:
    from .legacy_agents_gate import LegacyGateError, validate_gate, validate_required_receipt, validate_candidate_binding
except ImportError:  # Direct script execution keeps scripts on sys.path.
    from legacy_agents_gate import LegacyGateError, validate_gate, validate_required_receipt, validate_candidate_binding


AGENT_OS_SCHEMA = "AGENT_OS_V1"
WORK_PACKET_SCHEMA = "WORK_PACKET_V1"
RESULT_PACKET_SCHEMA = "RESULT_PACKET_V1"
RULE_CANDIDATE_SCHEMA = "RULE_CANDIDATE_V1"
SCHEMA_VERSION = 1
CORE_VERSION = "CORE_V1"
PROJECT_VERSION = "PROJECT_V1"
COMMANDS_VERSION = "COMMANDS_V1"
CODEX_ADAPTER_VERSION = "ADAPTER_CODEX_V1"
CLAUDE_ADAPTER_VERSION = "ADAPTER_CLAUDE_V1"
SOURCE_VERSIONS = {
    "core": CORE_VERSION,
    "project": PROJECT_VERSION,
    "commands": COMMANDS_VERSION,
    "codex_adapter": CODEX_ADAPTER_VERSION,
    "claude_adapter": CLAUDE_ADAPTER_VERSION,
}
PROVENANCE_SOURCES = [
    {
        "accessed_on": "2026-09-03",
        "commit": "f10729445d12ca586ed31f7ec50c257a0b336664",
        "source_id": "nmnmcc-agent-os-gist",
        "url": "https://gist.github.com/nmnmcc/37c855a390166f8df441001b266ae2e1/f10729445d12ca586ed31f7ec50c257a0b336664",
    },
    {
        "accessed_on": "2026-09-03",
        "commit": "cfc89848f505ad5cc6538021debaf3d9e595819b",
        "source_id": "nmnmcc-ceno-agents",
        "url": "https://github.com/nmnmcc/ceno/blob/cfc89848f505ad5cc6538021debaf3d9e595819b/AGENTS.md",
    },
]
CONTRACT_FILES = (
    ".agent-os/CORE.md",
    ".agent-os/PROJECT.md",
    ".agent-os/COMMANDS.md",
    ".agent-os/references.json",
    "AGENTS.md",
    "CLAUDE.md",
)
ROOT_ID_RE = re.compile(r"^agent-os:[a-f0-9]{24}$")
METADATA_START = "<!-- agent-os-metadata:start -->"
METADATA_END = "<!-- agent-os-metadata:end -->"
PRESERVED_LEGACY_START = (
    "\n<!-- agent-os-preserved-instructions:start -->\n"
    "## Preserved legacy instructions\n\n"
)
PRESERVED_LEGACY_END = "<!-- agent-os-preserved-instructions:end -->\n"


class AgentOsError(ValueError):
    """Raised for a rejected Agent OS contract or command."""


class RecoveryIncompleteError(AgentOsError):
    """Raised when rollback evidence must remain available for manual recovery."""

    def __init__(self, staging_path: Path):
        self.staging_path = staging_path
        super().__init__(f"recovery incomplete; staged backup retained at {staging_path}")


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _root_id(project_name: str) -> str:
    return "agent-os:" + hashlib.sha256(project_name.encode("utf-8")).hexdigest()[:24]


def _relative_path(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise AgentOsError(f"{label} must be a non-empty project-relative POSIX path")
    if "\\" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        raise AgentOsError(f"{label} must be a project-relative POSIX path")
    path = PurePosixPath(value)
    if any(part in {"", ".", ".."} for part in value.split("/")) or path.is_absolute():
        raise AgentOsError(f"{label} must be normalized and cannot escape the project")
    return path.as_posix()


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AgentOsError(f"{label} must be a non-empty string")
    return value


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise AgentOsError(f"{label} must be a non-empty list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise AgentOsError(f"{label} must contain only non-empty strings")
    return value


def _require_mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise AgentOsError(f"{label} must be an object")
    return value


def validate_work_packet(value: object, *, root_id: str) -> dict[str, Any]:
    """Validate a WORK_PACKET_V1 and return its normalized mapping."""

    packet = dict(_require_mapping(value, "work packet"))
    if packet.get("schema") != WORK_PACKET_SCHEMA:
        raise AgentOsError("work packet schema must be WORK_PACKET_V1")
    _string(packet.get("packet_id"), "work packet packet_id")
    if packet.get("project_root_id") != root_id:
        raise AgentOsError("work packet project_root_id does not match the Agent OS manifest")
    _string(packet.get("task_id"), "work packet task_id")
    _string(packet.get("objective"), "work packet objective")
    surfaces = [_relative_path(item, label="work packet write_surface") for item in _string_list(packet.get("write_surfaces"), "work packet write_surfaces")]
    if len(surfaces) != len(set(surfaces)):
        raise AgentOsError("work packet assigns a write surface more than once")
    _string_list(packet.get("acceptance_checks"), "work packet acceptance_checks")
    if packet.get("approval_status") not in {"not_required", "approved"}:
        raise AgentOsError("work packet approval_status must be not_required or approved")
    packet["write_surfaces"] = surfaces
    return packet


def validate_result_packet(value: object, *, root_id: str) -> dict[str, Any]:
    """Validate a RESULT_PACKET_V1 without trusting it to promote state."""

    packet = dict(_require_mapping(value, "result packet"))
    if packet.get("schema") != RESULT_PACKET_SCHEMA:
        raise AgentOsError("result packet schema must be RESULT_PACKET_V1")
    _string(packet.get("packet_id"), "result packet packet_id")
    _string(packet.get("work_packet_id"), "result packet work_packet_id")
    if packet.get("project_root_id") != root_id:
        raise AgentOsError("result packet project_root_id does not match the Agent OS manifest")
    _string(packet.get("task_id"), "result packet task_id")
    if packet.get("status") not in {"progress", "completed", "blocked", "failed"}:
        raise AgentOsError("result packet status is invalid")
    _string_list(packet.get("verified_facts"), "result packet verified_facts")
    changes = packet.get("changed_surfaces")
    if not isinstance(changes, list):
        raise AgentOsError("result packet changed_surfaces must be a list")
    packet["changed_surfaces"] = [_relative_path(item, label="result packet changed_surface") for item in changes]
    _string_list(packet.get("evidence"), "result packet evidence")
    _string(packet.get("next_step"), "result packet next_step")
    return packet


def validate_rule_candidate(value: object) -> dict[str, Any]:
    """Require a stable, explicit operator approval for persistent rules."""

    candidate = dict(_require_mapping(value, "rule candidate"))
    if candidate.get("schema") != RULE_CANDIDATE_SCHEMA:
        raise AgentOsError("rule candidate schema must be RULE_CANDIDATE_V1")
    _string(candidate.get("candidate_id"), "rule candidate candidate_id")
    if candidate.get("scope") not in {"project", "global"}:
        raise AgentOsError("rule candidate scope must be project or global")
    _string(candidate.get("proposed_rule"), "rule candidate proposed_rule")
    approval = _require_mapping(candidate.get("operator_approval"), "rule candidate operator_approval")
    if approval.get("status") != "approved" or not isinstance(approval.get("approval_id"), str) or not approval["approval_id"].strip():
        raise AgentOsError("rule candidate needs explicit operator approval before promotion")
    return candidate


def _metadata(text: str) -> dict[str, str]:
    start = text.find(METADATA_START)
    end = text.find(METADATA_END, start + len(METADATA_START))
    if start < 0 or end < 0:
        return {}
    values: dict[str, str] = {}
    for line in text[start + len(METADATA_START):end].splitlines():
        if ": " in line:
            key, value = line.split(": ", 1)
            if re.fullmatch(r"[a-z0-9_]+", key):
                values[key] = value.strip()
    return values


def extract_preserved_legacy_agents(text: str) -> str | None:
    """Return exact sentinel-bounded legacy instructions from a generated adapter."""

    start = text.find(PRESERVED_LEGACY_START)
    if start < 0:
        return None
    end = text.rfind(PRESERVED_LEGACY_END)
    payload_start = start + len(PRESERVED_LEGACY_START)
    if end < payload_start:
        raise AgentOsError("preserved legacy instructions wrapper is malformed")
    return text[payload_start:end]


def _render_files(project_name: str, *, legacy_agents: str | None = None) -> dict[str, bytes]:
    root_id = _root_id(project_name)
    core = (
        "# Agent OS Core\n\n"
        f"{METADATA_START}\n"
        f"agent_os_schema: {AGENT_OS_SCHEMA}\n"
        f"source_version: {CORE_VERSION}\n"
        f"{METADATA_END}\n\n"
        "This shared contract is versioned, deterministic, and portable.\n\n"
        "## Packet schemas\n\n"
        f"- `{WORK_PACKET_SCHEMA}`: unique packet_id, project_root_id, task_id, objective, write_surfaces, acceptance_checks, approval_status.\n"
        f"- `{RESULT_PACKET_SCHEMA}`: work_packet_id referencing a supplied work packet with the same root/task and owned changed_surfaces, plus packet_id, status, verified_facts, evidence, next_step.\n"
        f"- `{RULE_CANDIDATE_SCHEMA}`: candidate_id, scope, proposed_rule, operator_approval.\n\n"
        "Persistent rules are candidates until a non-empty explicit operator approval ID is recorded. "
        "Distinct concurrent work packets may not claim the same or nested write surface.\n"
    ).encode("utf-8")
    project = (
        "# Agent OS Project\n\n"
        f"{METADATA_START}\n"
        f"agent_os_schema: {AGENT_OS_SCHEMA}\n"
        f"source_version: {PROJECT_VERSION}\n"
        f"project_name: {project_name}\n"
        f"project_root_id: {root_id}\n"
        f"{METADATA_END}\n\n"
        "All active paths are project-relative POSIX paths. The root ID is derived from the project name, not its machine location.\n"
    ).encode("utf-8")
    commands = (
        "# Agent OS Commands\n\n"
        f"{METADATA_START}\n"
        f"agent_os_schema: {AGENT_OS_SCHEMA}\n"
        f"source_version: {COMMANDS_VERSION}\n"
        f"{METADATA_END}\n\n"
        "Use `agent_os.py init` for a new project, `migrate` only with explicit intent, and `verify` before consuming the contract.\n"
    ).encode("utf-8")
    references = _json_bytes({
        "schema": "AGENT_OS_REFERENCES_V1",
        "schema_version": 1,
        "agent_os_schema": AGENT_OS_SCHEMA,
        "source_versions": SOURCE_VERSIONS,
        "sources": PROVENANCE_SOURCES,
    })
    core_hash = _sha256(core)
    preserved_legacy = (
        PRESERVED_LEGACY_START + legacy_agents + PRESERVED_LEGACY_END
        if legacy_agents is not None else ""
    )
    codex_adapter = (
        "# Codex / Chief adapter\n\n"
        f"{METADATA_START}\n"
        f"agent_os_schema: {AGENT_OS_SCHEMA}\n"
        "adapter: codex\n"
        f"source_version: {CODEX_ADAPTER_VERSION}\n"
        f"core_sha256: {core_hash}\n"
        f"{METADATA_END}\n\n"
        "Follow `.agent-os/CORE.md` for shared execution contracts. Codex and the Chief retain their existing task, pin, automation, and Chief authority.\n"
        + preserved_legacy
    ).encode("utf-8")
    claude_adapter = (
        "# Claude adapter\n\n"
        f"{METADATA_START}\n"
        f"agent_os_schema: {AGENT_OS_SCHEMA}\n"
        "adapter: claude\n"
        f"source_version: {CLAUDE_ADAPTER_VERSION}\n"
        f"core_sha256: {core_hash}\n"
        f"{METADATA_END}\n\n"
        "Follow `.agent-os/CORE.md` for shared execution contracts. This adapter does not grant Claude Codex task, pin, automation, or Chief authority.\n"
    ).encode("utf-8")
    return {
        ".agent-os/CORE.md": core,
        ".agent-os/PROJECT.md": project,
        ".agent-os/COMMANDS.md": commands,
        ".agent-os/references.json": references,
        "AGENTS.md": codex_adapter,
        "CLAUDE.md": claude_adapter,
    }


def _manifest(project_name: str, files: Mapping[str, bytes]) -> bytes:
    manifest = {
        "schema": AGENT_OS_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "project_name": project_name,
        "root_id": _root_id(project_name),
        "source_versions": SOURCE_VERSIONS,
        "file_hashes": {path: _sha256(files[path]) for path in sorted(files)},
    }
    return _json_bytes(manifest)


def contract_fingerprint() -> str:
    files = render_contract_files("CHIEF_AGENT_OS_BINDING")
    return _sha256(_json_bytes({"source_versions": SOURCE_VERSIONS, "file_hashes": {key: _sha256(value) for key, value in sorted(files.items())}}))


def render_contract_files(
    project_name: str, *, codex_instructions: str | None = None
) -> dict[str, bytes]:
    """Render the complete deterministic contract for a caller-owned target."""
    files = _render_files(project_name, legacy_agents=codex_instructions)
    files[".agent-os/manifest.json"] = _manifest(project_name, files)
    return files


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise AgentOsError(f"{label} is unreadable") from exc
    if not isinstance(value, dict):
        raise AgentOsError(f"{label} must contain an object")
    return value


def _required_contract_paths() -> set[str]:
    return set(CONTRACT_FILES)


def _verify_manifest(target: Path) -> dict[str, Any]:
    if not target.is_dir():
        raise AgentOsError("target must be an existing directory")
    root = target.resolve()
    agent_dir = target / ".agent-os"
    manifest_path = agent_dir / "manifest.json"
    if agent_dir.is_symlink() and not agent_dir.exists():
        raise AgentOsError("dangling Agent OS path: .agent-os")
    if not agent_dir.exists() and not manifest_path.exists():
        raise AgentOsError("legacy")
    if not manifest_path.is_file():
        raise AgentOsError("missing Agent OS manifest")
    for relative in (".agent-os", ".agent-os/manifest.json", *CONTRACT_FILES):
        path = target / relative
        if path.exists():
            try:
                path.resolve(strict=True).relative_to(root)
            except ValueError as exc:
                raise AgentOsError(f"unsafe contract path: {relative} escapes the project root") from exc
    manifest = _read_json(manifest_path, "Agent OS manifest")
    if manifest.get("schema") != AGENT_OS_SCHEMA or manifest.get("schema_version") != SCHEMA_VERSION:
        raise AgentOsError("Agent OS manifest schema mismatch")
    project_name = manifest.get("project_name")
    if not isinstance(project_name, str) or not project_name:
        raise AgentOsError("Agent OS manifest project_name is invalid")
    if manifest.get("root_id") != _root_id(project_name) or not ROOT_ID_RE.fullmatch(str(manifest.get("root_id"))):
        raise AgentOsError("Agent OS manifest root_id is invalid")
    if manifest.get("source_versions") != SOURCE_VERSIONS:
        raise AgentOsError("source-version mismatch in Agent OS manifest")
    hashes = manifest.get("file_hashes")
    if not isinstance(hashes, dict) or set(hashes) != _required_contract_paths():
        raise AgentOsError("Agent OS manifest file_hashes are incomplete")

    for adapter in ("AGENTS.md", "CLAUDE.md"):
        if not (target / adapter).is_file():
            raise AgentOsError(f"missing adapter: {adapter}")
    for relative in sorted(_required_contract_paths()):
        path = target / relative
        if not path.is_file():
            raise AgentOsError(f"missing contract file: {relative}")
        expected = hashes.get(relative)
        if not isinstance(expected, str) or _sha256(path.read_bytes()) != expected:
            raise AgentOsError(f"hash mismatch: {relative}")

    agents_text = (target / "AGENTS.md").read_text(encoding="utf-8")
    try:
        legacy_agents = extract_preserved_legacy_agents(agents_text)
    except AgentOsError as exc:
        raise AgentOsError("canonical contract mismatch: AGENTS.md") from exc
    canonical = render_contract_files(project_name, codex_instructions=legacy_agents)
    for relative, expected in canonical.items():
        if (target / relative).read_bytes() != expected:
            raise AgentOsError(f"canonical contract mismatch: {relative}")

    core = (target / ".agent-os" / "CORE.md").read_text(encoding="utf-8")
    project = (target / ".agent-os" / "PROJECT.md").read_text(encoding="utf-8")
    commands = (target / ".agent-os" / "COMMANDS.md").read_text(encoding="utf-8")
    if _metadata(core).get("source_version") != SOURCE_VERSIONS["core"]:
        raise AgentOsError("source-version mismatch in CORE.md")
    if _metadata(project).get("source_version") != SOURCE_VERSIONS["project"]:
        raise AgentOsError("source-version mismatch in PROJECT.md")
    if _metadata(commands).get("source_version") != SOURCE_VERSIONS["commands"]:
        raise AgentOsError("source-version mismatch in COMMANDS.md")
    if _metadata(project).get("project_root_id") != manifest["root_id"]:
        raise AgentOsError("project root_id does not match manifest")
    references = _read_json(target / ".agent-os" / "references.json", "Agent OS references")
    canonical_references = json.loads(canonical[".agent-os/references.json"])
    if references != canonical_references:
        raise AgentOsError("canonical contract mismatch: .agent-os/references.json")
    core_hash = _sha256((target / ".agent-os" / "CORE.md").read_bytes())
    for adapter, adapter_kind, version in (
        ("AGENTS.md", "codex", CODEX_ADAPTER_VERSION),
        ("CLAUDE.md", "claude", CLAUDE_ADAPTER_VERSION),
    ):
        data = _metadata((target / adapter).read_text(encoding="utf-8"))
        if data.get("agent_os_schema") != AGENT_OS_SCHEMA or data.get("adapter") != adapter_kind or data.get("source_version") != version:
            raise AgentOsError(f"stale adapter: {adapter}")
        if data.get("core_sha256") != core_hash:
            raise AgentOsError(f"stale adapter: {adapter}")
    return manifest


def verify_required_legacy_receipt(target: Path, trust_root: str | None) -> None:
    receipt = target / ".agent-os" / "legacy-gate-receipt.json"
    if not receipt.exists():
        return
    if trust_root is None:
        raise AgentOsError("required legacy receipt needs an explicit external trust root")
    try:
        validate_required_receipt(
            target, receipt, Path(trust_root),
            agent_os_schema=AGENT_OS_SCHEMA,
            source_versions=SOURCE_VERSIONS,
            contract_fingerprint_sha256=contract_fingerprint(),
        )
    except LegacyGateError as exc:
        raise AgentOsError(f"required legacy receipt rejected: {exc}") from exc


def _verify_packets(
    manifest: Mapping[str, Any],
    work_packet_paths: Iterable[str],
    rule_candidate_paths: Iterable[str],
    result_packet_paths: Iterable[str],
) -> None:
    work_packets: dict[str, dict[str, Any]] = {}
    writers: list[tuple[str, str]] = []
    root_id = str(manifest["root_id"])
    for raw_path in work_packet_paths:
        packet = validate_work_packet(_read_json(Path(raw_path), "work packet"), root_id=root_id)
        if packet["packet_id"] in work_packets:
            raise AgentOsError(f"duplicate work packet_id: {packet['packet_id']}")
        for surface in packet["write_surfaces"]:
            for existing_surface, owner in writers:
                if owner != packet["packet_id"] and (
                    surface == existing_surface
                    or surface.startswith(existing_surface + "/")
                    or existing_surface.startswith(surface + "/")
                ):
                    raise AgentOsError(
                        f"unique-writer conflict: {surface} overlaps {existing_surface} "
                        f"claimed by packets {owner} and {packet['packet_id']}"
                    )
            writers.append((surface, packet["packet_id"]))
        work_packets[packet["packet_id"]] = packet
    for raw_path in result_packet_paths:
        result = validate_result_packet(_read_json(Path(raw_path), "result packet"), root_id=root_id)
        work_packet = work_packets.get(result["work_packet_id"])
        if work_packet is None:
            raise AgentOsError(
                f"result packet work_packet_id does not resolve: {result['work_packet_id']}"
            )
        if result["project_root_id"] != work_packet["project_root_id"]:
            raise AgentOsError("result packet project_root_id does not match work packet")
        if result["task_id"] != work_packet["task_id"]:
            raise AgentOsError("result packet task_id does not match work packet")
        for changed_surface in result["changed_surfaces"]:
            if not any(
                changed_surface == owned_surface
                or changed_surface.startswith(owned_surface + "/")
                for owned_surface in work_packet["write_surfaces"]
            ):
                raise AgentOsError(
                    f"result packet changed_surface is outside work packet ownership: {changed_surface}"
                )
    for raw_path in rule_candidate_paths:
        validate_rule_candidate(_read_json(Path(raw_path), "rule candidate"))


def _write_contract(
    target: Path,
    project_name: str,
    *,
    migration: bool,
    fail_after_replacements: int | None = None,
    interrupt_after_backups: int | None = None,
    fail_restore: bool = False,
    extra_files: Mapping[str, bytes] | None = None,
) -> str:
    target = target.resolve()
    manifest_path = target / ".agent-os" / "manifest.json"
    if migration and manifest_path.exists():
        _verify_manifest(target)
        return "already migrated"
    legacy_agents: str | None = None
    existing_agents = target / "AGENTS.md"
    if migration and existing_agents.is_file():
        try:
            legacy_agents = existing_agents.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            raise AgentOsError("conflict: existing AGENTS.md is not readable UTF-8") from exc
    files = render_contract_files(project_name, codex_instructions=legacy_agents)
    if extra_files:
        for relative, data in extra_files.items():
            _relative_path(relative, label="extra migration receipt path")
            if not isinstance(data, bytes):
                raise AgentOsError("extra migration receipt must be bytes")
        files.update(extra_files)
    conflicts = []
    for relative in sorted(files):
        destination = target / relative
        if not destination.exists():
            continue
        if migration and relative == "AGENTS.md" and destination.is_file():
            continue
        conflicts.append(relative)
    if conflicts:
        raise AgentOsError("conflict: existing destination(s): " + ", ".join(conflicts))

    for relative in files:
        try:
            (target / relative).parent.resolve(strict=False).relative_to(target)
        except ValueError as exc:
            raise AgentOsError(f"unsafe destination: {relative} escapes the project root") from exc

    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".agent-os-stage-", dir=parent))
    created_directories: list[Path] = []
    created_destinations: list[Path] = []
    backups: dict[Path, Path] = {}
    replacement_count = 0
    backup_count = 0
    remove_staging = True
    try:
        for relative, data in files.items():
            staged = staging / relative
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_bytes(data)
        for relative in sorted(files):
            destination = target / relative
            missing_directories: list[Path] = []
            parent_directory = destination.parent
            while not parent_directory.exists():
                missing_directories.append(parent_directory)
                parent_directory = parent_directory.parent
            for directory in reversed(missing_directories):
                directory.mkdir()
                created_directories.append(directory)
            if destination.exists():
                backup = staging / ".rollback" / relative
                backup.parent.mkdir(parents=True, exist_ok=True)
                os.replace(destination, backup)
                backups[destination] = backup
                backup_count += 1
                if (
                    interrupt_after_backups is not None
                    and backup_count >= interrupt_after_backups
                ):
                    raise KeyboardInterrupt()
            else:
                created_destinations.append(destination)
            if (
                fail_after_replacements is not None
                and replacement_count >= fail_after_replacements
            ):
                raise OSError("injected replacement failure")
            os.replace(staging / relative, destination)
            replacement_count += 1
    except BaseException as exc:
        recovery_errors: list[OSError] = []
        for destination in reversed(created_destinations):
            try:
                if destination.exists() or destination.is_symlink():
                    destination.unlink()
            except OSError as recovery_error:
                recovery_errors.append(recovery_error)
        for destination, backup in backups.items():
            try:
                if destination.exists() or destination.is_symlink():
                    destination.unlink()
                if fail_restore:
                    raise OSError("injected recovery restore failure")
                if backup.exists():
                    os.replace(backup, destination)
            except OSError as recovery_error:
                recovery_errors.append(recovery_error)
        for directory in reversed(created_directories):
            try:
                directory.rmdir()
            except OSError as recovery_error:
                recovery_errors.append(recovery_error)
        if recovery_errors:
            remove_staging = False
            raise RecoveryIncompleteError(staging) from exc
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        if isinstance(exc, Exception):
            raise AgentOsError("atomic contract replace failed; staged writes were rolled back") from exc
        raise
    finally:
        if remove_staging:
            shutil.rmtree(staging, ignore_errors=True)
    return "migrated" if migration else "initialized"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create and verify the deterministic Agent OS V1 contract.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("init", "initialize Agent OS V1 only when every destination is new"),
        ("migrate", "explicitly add Agent OS V1 to a legacy project; reruns verify idempotently"),
    ):
        command = subcommands.add_parser(name, help=help_text)
        command.add_argument("--target", required=True, help="project root to receive the contract")
        command.add_argument("--project-name", help="portable project name; defaults to the target directory name")
        if name == "migrate":
            command.add_argument("--legacy-agents-gate", help="absolute external approved legacy gate; never created by this command")
            command.add_argument("--expected-legacy-agents-gate-sha256", help="caller-pinned SHA-256 of the external gate")
            command.add_argument("--legacy-trust-root", help="absolute external trust directory containing the gate")
    verify = subcommands.add_parser("verify", help="verify Agent OS V1, packets, and rule approval")
    verify.add_argument("--target", required=True, help="project root to verify")
    verify.add_argument("--work-packet", action="append", default=[], help="WORK_PACKET_V1 JSON file")
    verify.add_argument("--result-packet", action="append", default=[], help="RESULT_PACKET_V1 JSON file")
    verify.add_argument("--rule-candidate", action="append", default=[], help="RULE_CANDIDATE_V1 JSON file")
    verify.add_argument("--legacy-trust-root", help="external trust root required to validate a gated legacy receipt")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target = Path(args.target).expanduser().resolve()
    try:
        if args.command in {"init", "migrate"}:
            project_name = args.project_name or target.name
            _string(project_name, "project_name")
            extra_files = None
            if args.command == "migrate":
                gate_args = (args.legacy_agents_gate, args.expected_legacy_agents_gate_sha256, args.legacy_trust_root)
                if any(gate_args) and not all(gate_args):
                    raise AgentOsError("custom legacy migration requires gate path, expected gate SHA-256, and trust root together")
                if all(gate_args):
                    try:
                        # Validation is preflight-only: this initializer never creates, copies,
                        # or refreshes trust evidence.  Receipt persistence belongs to a later
                        # required-mode project adoption transaction.
                        receipt = validate_gate(target, Path(args.legacy_agents_gate), Path(args.legacy_trust_root), args.expected_legacy_agents_gate_sha256)
                        validate_candidate_binding(Path(args.legacy_agents_gate), Path(args.legacy_trust_root), skill_root=Path(__file__).resolve().parent.parent, agent_os_schema=AGENT_OS_SCHEMA, source_versions=SOURCE_VERSIONS, contract_fingerprint_sha256=contract_fingerprint())
                        extra_files = {".agent-os/legacy-gate-receipt.json": _json_bytes(receipt)}
                    except LegacyGateError as exc:
                        raise AgentOsError(f"legacy gate rejected before migration: {exc}") from exc
            state = _write_contract(target, project_name, migration=args.command == "migrate", extra_files=extra_files)
            print(f"AGENT_OS_V1 {state}: {target}")
            return 0
        if not target.is_dir():
            raise AgentOsError("target must be an existing directory")
        try:
            manifest = _verify_manifest(target)
        except AgentOsError as exc:
            if str(exc) == "legacy":
                print(f"legacy: no Agent OS contract at {target}")
                return 0
            raise
        verify_required_legacy_receipt(target, args.legacy_trust_root)
        _verify_packets(manifest, args.work_packet, args.rule_candidate, args.result_packet)
        print(f"AGENT_OS_V1 verified: {target}")
        return 0
    except AgentOsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2 if str(exc).startswith("conflict:") else 1


if __name__ == "__main__":
    raise SystemExit(main())
