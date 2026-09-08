"""Validate externally anchored custom legacy AGENTS migration evidence."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

try:
    from . import private_authority
except ImportError:  # The standalone migration CLI uses the same host authority.
    import private_authority


SCHEMA = "CHIEF_AGENT_OS_LEGACY_GATE_V1"
HEX = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
IMPLEMENTATION_FILES = (
    "scripts/init_project.py", "scripts/agent_os.py", "scripts/legacy_agents_gate.py",
    "assets/project-template/.chief-of-staff/project.json", "assets/project-template/AGENTS.md",
)


class LegacyGateError(ValueError):
    pass


def _testing_reviewer_task_id(*boundaries: Path) -> str:
    try:
        return private_authority.testing_reviewer_task_id(
            forbidden_paths=(Path(__file__).resolve().parent.parent, *boundaries)
        )
    except private_authority.PrivateAuthorityError as exc:
        raise LegacyGateError("private Testing authority is unavailable") from exc


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _lexical_safe(path: Path, label: str) -> None:
    """Reject user-created aliases before any path resolution/consumption.

    macOS exposes /tmp and /var as OS compatibility redirects; every other
    lexical symlink in the caller-provided chain is an unapproved alias.
    """
    cursor = path
    while cursor.parent != cursor:
        if cursor.is_symlink() and cursor not in {Path("/tmp"), Path("/var")}:
            raise LegacyGateError(f"{label} ancestors must not be symlinks")
        cursor = cursor.parent


def project_root_id(project: Path) -> str:
    project_json = project / ".chief-of-staff" / "project.json"
    try:
        value = json.loads(project_json.read_text(encoding="utf-8"))
        name = value["project_name"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise LegacyGateError("project.json must provide project_name") from exc
    if not isinstance(name, str) or not name:
        raise LegacyGateError("project_name must be non-empty")
    return "agent-os:" + hashlib.sha256(name.encode("utf-8")).hexdigest()[:24]


def _external_file(path: Path, trust_root: Path, project: Path) -> Path:
    _lexical_safe(path, "gate")
    _lexical_safe(trust_root, "trust root")
    if not path.is_absolute() or not trust_root.is_absolute() or not path.is_file() or not trust_root.is_dir() or path.stat().st_nlink != 1:
        raise LegacyGateError("gate and trust root must be absolute non-symlink paths; gate must be a one-link regular file")
    cursor = path
    while True:
        if cursor.is_symlink():
            raise LegacyGateError("gate and trust root ancestors must not be symlinks")
        if cursor == trust_root:
            break
        if trust_root not in cursor.parents:
            raise LegacyGateError("gate is outside its trust root")
        cursor = cursor.parent
    resolved, trust, boundary = path.resolve(strict=True), trust_root.resolve(strict=True), project.resolve(strict=True)
    try:
        resolved.relative_to(trust)
    except ValueError as exc:
        raise LegacyGateError("gate is outside its trust root") from exc
    try:
        resolved.relative_to(boundary)
    except ValueError:
        return resolved
    raise LegacyGateError("gate must be external to the project boundary")


def validate_gate(project: Path, gate_path: Path, trust_root: Path, expected_gate_sha256: str) -> dict[str, str]:
    project = project.resolve(strict=True)
    gate = _external_file(gate_path, trust_root, project)
    testing_reviewer = _testing_reviewer_task_id(project, Path(trust_root), gate)
    if not HEX.fullmatch(expected_gate_sha256) or _sha(gate) != expected_gate_sha256:
        raise LegacyGateError("legacy gate SHA-256 mismatch")
    try:
        value: dict[str, Any] = json.loads(gate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LegacyGateError("legacy gate is unreadable") from exc
    required = {"schema", "status", "testing_chief_task_id", "gate_id", "candidate_id", "candidate_manifest_sha256", "project_identity", "pre_migration", "approved_agent_os_mode", "tested_lanes", "operator_approval_id"}
    if not isinstance(value, dict) or set(value) != required:
        raise LegacyGateError("legacy gate fields are incomplete or ambiguous")
    if value["schema"] != SCHEMA or value["status"] != "TESTING_GATE_PASS" or value["testing_chief_task_id"] != testing_reviewer:
        raise LegacyGateError("legacy gate authority is invalid")
    if not all(isinstance(value[key], str) and SAFE_ID.fullmatch(value[key]) for key in ("gate_id", "candidate_id", "operator_approval_id")) or not value["operator_approval_id"]:
        raise LegacyGateError("legacy gate identifiers are unsafe")
    if not isinstance(value["candidate_manifest_sha256"], str) or not HEX.fullmatch(value["candidate_manifest_sha256"]):
        raise LegacyGateError("candidate manifest hash is invalid")
    if gate.name != value["gate_id"] + ".json":
        raise LegacyGateError("gate filename must bind its gate_id")
    identity, preimage = value["project_identity"], value["pre_migration"]
    if not isinstance(identity, dict) or not isinstance(preimage, dict):
        raise LegacyGateError("legacy gate identity or preimage is invalid")
    project_json, agents = project / ".chief-of-staff" / "project.json", project / "AGENTS.md"
    try:
        project_name = json.loads(project_json.read_text(encoding="utf-8"))["project_name"]
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise LegacyGateError("project JSON is invalid") from exc
    if identity != {"root_id": project_root_id(project), "project_name": project_name}:
        raise LegacyGateError("legacy gate project identity mismatch")
    if preimage != {"project_json_sha256": _sha(project_json), "agents_sha256": _sha(agents)}:
        raise LegacyGateError("legacy gate preimage mismatch")
    if value["approved_agent_os_mode"] != "required" or not isinstance(value["tested_lanes"], list) or not {"INFRA_CONFIG", "SECURITY_PRIVACY"}.issubset(value["tested_lanes"]):
        raise LegacyGateError("legacy gate mode or test lanes are invalid")
    return {"gate_id": value["gate_id"], "gate_sha256": expected_gate_sha256, "candidate_manifest_sha256": value["candidate_manifest_sha256"], "preserved_agents_sha256": _sha(agents)}


def validate_required_receipt(
    project: Path,
    receipt_path: Path,
    trust_root: Path,
    *,
    agent_os_schema: str,
    source_versions: dict[str, object],
    contract_fingerprint_sha256: str,
) -> dict[str, str]:
    """Recheck a migrated project's external authority without trusting local hashes."""
    project = project.resolve(strict=True)
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LegacyGateError("required legacy receipt is unreadable") from exc
    required = {"gate_id", "gate_sha256", "candidate_manifest_sha256", "preserved_agents_sha256"}
    if not isinstance(receipt, dict) or set(receipt) != required or not SAFE_ID.fullmatch(str(receipt.get("gate_id"))) or not all(_is_hex for _is_hex in [bool(HEX.fullmatch(str(receipt.get(key)))) for key in ("gate_sha256", "candidate_manifest_sha256", "preserved_agents_sha256")]):
        raise LegacyGateError("required legacy receipt is invalid")
    # Preserve the caller's lexical path through the symlink check; resolving
    # first would turn macOS /var into /private/var and falsely fail the
    # containment walk against the original approved trust root.
    gate = Path(trust_root) / (receipt["gate_id"] + ".json")
    gate = _external_file(gate, Path(trust_root), project)
    testing_reviewer = _testing_reviewer_task_id(project, Path(trust_root), gate)
    if _sha(gate) != receipt["gate_sha256"]:
        raise LegacyGateError("required legacy gate drifted")
    gate_value = json.loads(gate.read_text(encoding="utf-8"))
    identity = gate_value.get("project_identity") if isinstance(gate_value, dict) else None
    if not isinstance(identity, dict) or identity != {"root_id": project_root_id(project), "project_name": json.loads((project / ".chief-of-staff" / "project.json").read_text(encoding="utf-8"))["project_name"]}:
        raise LegacyGateError("required legacy gate identity mismatch")
    if gate_value.get("schema") != SCHEMA or gate_value.get("status") != "TESTING_GATE_PASS" or gate_value.get("testing_chief_task_id") != testing_reviewer or gate_value.get("candidate_manifest_sha256") != receipt["candidate_manifest_sha256"] or gate_value.get("approved_agent_os_mode") != "required" or not {"INFRA_CONFIG", "SECURITY_PRIVACY"}.issubset(set(gate_value.get("tested_lanes", []))):
        raise LegacyGateError("required legacy gate authority mismatch")
    # A later compatible installed release must not fail merely because the
    # historical implementation hashes changed.  It still must reload the
    # fixed, externally anchored candidate and validate the deterministic
    # Agent OS contract that the receipt claims.
    validate_candidate_manifest(
        gate, Path(trust_root), boundary=project,
        agent_os_schema=agent_os_schema,
        source_versions=source_versions,
        contract_fingerprint_sha256=contract_fingerprint_sha256,
    )
    text = (project / "AGENTS.md").read_text(encoding="utf-8")
    start = (
        "<!-- agent-os-preserved-instructions:start -->\n"
        "## Preserved legacy instructions\n\n"
    )
    end = "<!-- agent-os-preserved-instructions:end -->"
    if start not in text or end not in text:
        raise LegacyGateError("required project has no preserved legacy wrapper")
    preserved = text.split(start, 1)[1].split(end, 1)[0]
    if hashlib.sha256(preserved.encode("utf-8")).hexdigest() != receipt["preserved_agents_sha256"] or gate_value.get("pre_migration", {}).get("agents_sha256") != receipt["preserved_agents_sha256"]:
        raise LegacyGateError("preserved legacy instructions do not match external gate")
    return receipt


def validate_candidate_manifest(
    gate_path: Path,
    trust_root: Path,
    *,
    boundary: Path,
    agent_os_schema: str,
    source_versions: dict[str, object],
    contract_fingerprint_sha256: str,
) -> dict[str, str]:
    """Reload and validate the fixed detached candidate without trusting a path argument."""
    gate_value = json.loads(gate_path.read_text(encoding="utf-8"))
    candidate_id = gate_value.get("candidate_id") if isinstance(gate_value, dict) else None
    if not isinstance(candidate_id, str) or not SAFE_ID.fullmatch(candidate_id):
        raise LegacyGateError("gate candidate_id is unsafe")
    trust = Path(trust_root)
    candidate = trust / "candidates" / (candidate_id + ".json")
    candidate = _external_file(candidate, trust, boundary)
    if _sha(candidate) != gate_value.get("candidate_manifest_sha256"):
        raise LegacyGateError("candidate manifest hash does not match gate")
    try: value = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise LegacyGateError("candidate manifest is unreadable") from exc
    required = {"schema", "candidate_id", "source_release_id", "implementation_files", "implementation_fingerprint_sha256", "agent_os_schema", "source_versions", "contract_fingerprint_sha256"}
    if not isinstance(value, dict) or set(value) != required or value.get("schema") != "CHIEF_AGENT_OS_LEGACY_CANDIDATE_V1" or value.get("candidate_id") != candidate_id or value.get("agent_os_schema") != agent_os_schema or value.get("source_versions") != source_versions or value.get("contract_fingerprint_sha256") != contract_fingerprint_sha256:
        raise LegacyGateError("candidate manifest contract mismatch")
    files = value.get("implementation_files")
    if not isinstance(files, dict) or set(files) != set(IMPLEMENTATION_FILES):
        raise LegacyGateError("candidate implementation file allowlist mismatch")
    fingerprint = hashlib.sha256(
        json.dumps(files, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if value.get("implementation_fingerprint_sha256") != fingerprint:
        raise LegacyGateError("candidate implementation fingerprint mismatch")
    return files


def validate_candidate_binding(gate_path: Path, trust_root: Path, *, skill_root: Path, agent_os_schema: str, source_versions: dict[str, object], contract_fingerprint_sha256: str) -> None:
    """Bind a gate to one fixed candidate manifest and the running source bytes."""
    files = validate_candidate_manifest(
        gate_path, trust_root, boundary=skill_root,
        agent_os_schema=agent_os_schema,
        source_versions=source_versions,
        contract_fingerprint_sha256=contract_fingerprint_sha256,
    )
    actual: dict[str, str] = {}
    for relative in IMPLEMENTATION_FILES:
        path = skill_root / relative
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise LegacyGateError("candidate implementation path is unsafe")
        actual[relative] = _sha(path)
    if files != actual:
        raise LegacyGateError("candidate implementation bytes do not match running source")
