"""Validate approved continuous-execution packages and reconcile bounded local intents.

This is deliberately a local, pure policy consumer.  It returns intents for the
Chief/host to observe and act on; it never sends a message, wakes a task, grants
permission, or writes an independent state store.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

try:
    from . import private_authority
except ImportError:  # Script execution keeps the same fail-closed authority path.
    import private_authority


SCHEMA = "CHIEF_EXECUTION_PACKAGE_V1"
PROTECTED_PERMISSIONS = {
    "remote_push", "remote_fetch", "production", "deployment", "payment",
    "external_message", "permission_expansion", "account_use",
}
ACTIVE_STATUSES = {"running", "testing_queue", "awaiting_input", "awaiting_permission", "quota_limited", "technical_blocked"}
INACTIVE_STATUSES = {"paused", "archived"}
REAL_PROGRESS_KINDS = {"acceptance_gain", "blocker_removed", "new_reproducible_cause"}
RETURN_KINDS = {"approval", "test_pass", "recovery", "resource_recovered"}


class ContinuousExecutionError(ValueError):
    pass


def _testing_reviewer_task_id(*, submitting_project: Path | None, native_observation_root: Path | None) -> str:
    if submitting_project is None or native_observation_root is None:
        raise ContinuousExecutionError("private Testing authority requires authoritative project and native receipt roots")
    try:
        return private_authority.testing_reviewer_task_id(
            forbidden_paths=(Path(__file__).resolve().parent.parent, submitting_project, native_observation_root)
        )
    except private_authority.PrivateAuthorityError as exc:
        raise ContinuousExecutionError("private Testing authority is unavailable") from exc


def _string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ContinuousExecutionError(f"{label} must be a non-empty string")
    return value


def _sha256(value: object, label: str) -> str:
    value = _string(value, label)
    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ContinuousExecutionError(f"{label} must be a lowercase SHA-256")
    return value


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise ContinuousExecutionError(f"{label} must be a non-empty array of strings")
    if len(value) != len(set(value)):
        raise ContinuousExecutionError(f"{label} must not contain duplicates")
    return list(value)


def validate_execution_package(value: object) -> dict[str, Any]:
    """Accept only an explicit, finite, local approved execution package."""
    if not isinstance(value, dict):
        raise ContinuousExecutionError("execution package must be an object")
    required = {
        "schema", "package_id", "approval_id", "approval_status", "approval_receipt_sha256", "approval_evidence_ref", "work_id", "project",
        "writer_task_id", "write_surface", "candidate_sha256", "independent_reviewer_task_ids", "goal", "endpoint", "permissions", "resource_limits",
        "acceptance", "stop_conditions", "native_intake",
    }
    missing = sorted(required - set(value))
    if missing:
        raise ContinuousExecutionError("execution package is missing: " + ", ".join(missing))
    if value["schema"] != SCHEMA or value["approval_status"] != "approved":
        raise ContinuousExecutionError("execution package is not explicitly approved")
    _sha256(value.get("approval_receipt_sha256"), "approval_receipt_sha256")
    _string(value.get("approval_evidence_ref"), "approval_evidence_ref")
    for key in ("package_id", "approval_id", "work_id", "writer_task_id", "goal", "endpoint"):
        _string(value.get(key), key)
    _sha256(value.get("candidate_sha256"), "candidate_sha256")
    _string_list(value.get("write_surface"), "write_surface")
    reviewers = _string_list(value.get("independent_reviewer_task_ids"), "independent_reviewer_task_ids")
    if value["writer_task_id"] in reviewers:
        raise ContinuousExecutionError("independent reviewer cannot be the package writer")
    if value["endpoint"] != "local_delivered":
        raise ContinuousExecutionError("execution package endpoint must remain local_delivered")
    project = value["project"]
    if not isinstance(project, dict):
        raise ContinuousExecutionError("project must be an object")
    for key in ("project_id", "root_id", "branch"):
        _string(project.get(key), f"project.{key}")
    permissions = _string_list(value["permissions"], "permissions")
    if set(permissions) & PROTECTED_PERMISSIONS:
        raise ContinuousExecutionError("execution package cannot imply protected actions")
    if not set(permissions).issubset({"local_read", "local_write", "local_test", "local_commit"}):
        raise ContinuousExecutionError("execution package contains an unapproved local permission")
    limits = value["resource_limits"]
    if not isinstance(limits, dict):
        raise ContinuousExecutionError("resource_limits must be an object")
    cycles = limits.get("max_progress_cycles")
    units = limits.get("max_resource_units")
    if type(cycles) is not int or not 4 <= cycles <= 1000:
        raise ContinuousExecutionError("resource_limits.max_progress_cycles must be a finite integer from 4 through 1000")
    if type(units) is not int or not 1 <= units <= 1_000_000:
        raise ContinuousExecutionError("resource_limits.max_resource_units must be a finite positive integer")
    _string(limits.get("resource_unit"), "resource_limits.resource_unit")
    _string_list(value["acceptance"], "acceptance")
    _string_list(value["stop_conditions"], "stop_conditions")
    intake = value["native_intake"]
    if not isinstance(intake, dict):
        raise ContinuousExecutionError("native_intake must be an object")
    _string(intake.get("root_id"), "native_intake.root_id")
    _string(intake.get("coordinator_task_id"), "native_intake.coordinator_task_id")
    if intake["coordinator_task_id"] == value["writer_task_id"]:
        raise ContinuousExecutionError("native intake coordinator must be independent of writer")
    policy = value.get("testing_policy")
    if policy is not None:
        if not isinstance(policy, dict) or set(policy) != {"risk", "scope", "sensitive", "production", "global_upgrade", "disputed"}:
            raise ContinuousExecutionError("testing_policy fields are incomplete or ambiguous")
        if policy["risk"] not in {"low", "medium", "high"} or not isinstance(policy["scope"], str) or not policy["scope"]:
            raise ContinuousExecutionError("testing_policy risk and scope are invalid")
        if any(type(policy[key]) is not bool for key in ("sensitive", "production", "global_upgrade", "disputed")):
            raise ContinuousExecutionError("testing_policy flags must be explicit booleans")
    return value


def validate_native_testing_return(observed: object, *, package: Mapping[str, Any], native_loader: Any, submitting_project: Path | None, native_observation_root: Path | None) -> None:
    """Validate original native Testing authority evidence; forwarded labels carry no authority."""
    if not isinstance(observed, dict):
        raise ContinuousExecutionError("testing return must be an object")
    policy = package.get("testing_policy")
    if not isinstance(policy, dict):
        raise ContinuousExecutionError("test_pass requires an approved testing_policy")
    ref, digest = observed.get("native_receipt_ref"), observed.get("native_receipt_sha256")
    receipt = native_loader(ref, digest, "testing return")
    common = {"work_id": package["work_id"], "package_id": package["package_id"], "candidate_sha256": package["candidate_sha256"], "project": package["project"], "writer_task_id": package["writer_task_id"], "risk": policy["risk"], "scope": policy["scope"], "sensitive": policy["sensitive"], "production": policy["production"], "global_upgrade": policy["global_upgrade"], "disputed": policy["disputed"]}
    if (any(type(receipt.get(key)) is not bool or receipt.get(key) is not policy[key] for key in ("sensitive", "production", "global_upgrade", "disputed"))
        or any(receipt.get(key) != value for key, value in common.items()) or receipt.get("unresolved_findings") is not False):
        raise ContinuousExecutionError("native Testing receipt does not bind the approved policy")
    if (receipt.get("authority_kind") != "native_coordinator_observation"
        or receipt.get("native_root_id") != package["native_intake"]["root_id"]
        or receipt.get("coordinator_task_id") != package["native_intake"]["coordinator_task_id"]
        or receipt.get("package_digest") != package_digest(package)
        or receipt.get("target_task_id") != package["writer_task_id"]
        or receipt.get("source_task_id") != receipt.get("issuer_task_id")
        or not isinstance(receipt.get("observation_id"), str) or not receipt["observation_id"]
        or not isinstance(receipt.get("native_event_id"), str) or not receipt["native_event_id"]):
        raise ContinuousExecutionError("native Testing receipt lacks exact coordinator identity")
    testing_reviewer = _testing_reviewer_task_id(submitting_project=submitting_project, native_observation_root=native_observation_root)
    direct = policy["risk"] == "high" or any(policy[key] for key in ("sensitive", "production", "global_upgrade", "disputed"))
    if direct:
        if receipt.get("schema") != "CHIEF_TESTING_GATE_RECEIPT_V1" or receipt.get("issuer_task_id") != testing_reviewer or receipt.get("status") != "TESTING_GATE_PASS":
            raise ContinuousExecutionError("high-risk Testing return requires the unique Testing Chief direct PASS")
        return
    delegation = observed.get("testing_delegation")
    checked = validate_delegated_testing(delegation, native_observation_loader=native_loader, package=package, submitting_project=submitting_project, native_observation_root=native_observation_root)
    delegation_receipt = native_loader(checked["delegation_evidence_ref"], checked["delegation_receipt_sha256"], "testing delegation")
    if (delegation_receipt.get("authority_kind") != "native_coordinator_observation"
        or delegation_receipt.get("native_root_id") != package["native_intake"]["root_id"]
        or delegation_receipt.get("coordinator_task_id") != package["native_intake"]["coordinator_task_id"]
        or delegation_receipt.get("package_digest") != package_digest(package)
        or delegation_receipt.get("project") != package["project"]
        or delegation_receipt.get("issuer_task_id") != testing_reviewer
        or delegation_receipt.get("target_task_id") != checked["reviewer_task_id"]
        or not isinstance(delegation_receipt.get("observation_id"), str) or not delegation_receipt["observation_id"]
        or not isinstance(delegation_receipt.get("native_event_id"), str) or not delegation_receipt["native_event_id"]):
        raise ContinuousExecutionError("native Testing delegation lacks exact coordinator identity")
    if (checked["reviewer_task_id"] not in package["independent_reviewer_task_ids"]
        or checked.get("writer_task_id") != package["writer_task_id"]
        or checked.get("candidate_sha256") != package["candidate_sha256"]
        or checked.get("risk") != policy["risk"]
        or checked.get("scope") != policy["scope"]
        or receipt.get("delegation_id") != checked["delegation_id"]):
        raise ContinuousExecutionError("testing delegation does not match the approved reviewer and policy")
    if receipt.get("schema") != "CHIEF_TESTING_REVIEW_RECEIPT_V1" or receipt.get("status") != "PASS" or receipt.get("reviewer_task_id") != checked["reviewer_task_id"] or receipt.get("issuer_task_id") != checked["reviewer_task_id"]:
        raise ContinuousExecutionError("delegated Testing return requires the registered reviewer exact PASS")


def _round_is_real(round_value: object, seen_evidence: set[str], seen_hashes: set[str]) -> bool:
    if not isinstance(round_value, dict) or not isinstance(round_value.get("round_id"), str) or not round_value["round_id"]:
        return False
    evidence = round_value.get("evidence")
    if not isinstance(evidence, dict):
        return False
    evidence_id = evidence.get("evidence_id")
    evidence_sha256 = evidence.get("evidence_sha256")
    if not isinstance(evidence_id, str) or not evidence_id or evidence_id in seen_evidence:
        return False
    try:
        _sha256(evidence_sha256, "evidence.evidence_sha256")
    except ContinuousExecutionError:
        return False
    if evidence_sha256 in seen_hashes:
        return False
    seen_evidence.add(evidence_id)
    seen_hashes.add(evidence_sha256)
    observation = evidence.get("observation")
    return (
        evidence.get("kind") in REAL_PROGRESS_KINDS
        and isinstance(evidence.get("evidence_ref"), str) and bool(evidence["evidence_ref"])
        and isinstance(observation, dict)
        and isinstance(observation.get("before"), str) and observation["before"]
        and isinstance(observation.get("after"), str) and observation["after"]
        and observation["before"] != observation["after"]
    )


def _progress_identity(round_value: object) -> str | None:
    """Return the semantic transition identity, never a caller-selected log ID.

    A fresh receipt may be necessary to prove a transition, but cannot turn the
    same fixed-surface before/after criterion into another unit of progress.
    """
    if not isinstance(round_value, dict) or not isinstance(round_value.get("evidence"), dict):
        return None
    evidence = round_value["evidence"]
    observation = evidence.get("observation")
    if not isinstance(observation, dict):
        return None
    fields = ("kind", "criterion_id", "work_id", "package_id", "candidate_sha256")
    # Older lightweight state observations have no package binding.  They are
    # still deduplicated by the actual fixed before/after transition.
    identity = {key: evidence.get(key) for key in fields}
    identity["before"] = observation.get("before")
    identity["after"] = observation.get("after")
    if not isinstance(identity["before"], str) or not isinstance(identity["after"], str):
        return None
    return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _accepted_criterion_ids(package: Mapping[str, Any]) -> set[str]:
    """Map the package's preapproved acceptance clauses to stable IDs."""
    return {"-".join(part for part in item.lower().split() if part) for item in package["acceptance"]}


def _retained_json(root: Path, reference: object, expected_sha256: object, label: str) -> dict[str, Any]:
    """Load one retained in-project observation and recompute its exact hash."""
    reference = _string(reference, f"{label}_ref")
    if not reference.startswith("repo://"):
        raise ContinuousExecutionError(f"{label}_ref must be a repo:// reference")
    relative = Path(reference.removeprefix("repo://"))
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        raise ContinuousExecutionError(f"{label}_ref escapes the project")
    root = Path(root).resolve(strict=True)
    path = root / relative
    try:
        resolved = path.resolve(strict=True)
        resolved.relative_to(root)
        cursor = root
        for part in relative.parts:
            cursor /= part
            if cursor.is_symlink():
                raise ContinuousExecutionError(f"{label}_ref has a symlinked component")
        if not resolved.is_file() or resolved.stat().st_nlink != 1:
            raise ContinuousExecutionError(f"{label}_ref must be a one-link regular file")
        raw = resolved.read_bytes()
    except (OSError, ValueError) as exc:
        raise ContinuousExecutionError(f"{label}_ref is not a retained project observation") from exc
    expected = _sha256(expected_sha256, f"{label}_sha256")
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ContinuousExecutionError(f"{label} hash does not match retained bytes")
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContinuousExecutionError(f"{label} must be readable JSON") from exc
    if not isinstance(value, dict):
        raise ContinuousExecutionError(f"{label} must be a JSON object")
    return value


def package_digest(package: Mapping[str, Any]) -> str:
    """Hash the immutable package payload without its observation hash field."""
    canonical = {key: value for key, value in package.items() if key != "approval_receipt_sha256"}
    return hashlib.sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def validate_progress_evidence(value: object, evidence_root: Path, package: Mapping[str, Any], *, retained_loader: Any = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContinuousExecutionError("progress evidence must be an object")
    observed = retained_loader(value.get("evidence_ref"), value.get("evidence_sha256"), "progress evidence") if retained_loader else _retained_json(evidence_root, value.get("evidence_ref"), value.get("evidence_sha256"), "progress evidence")
    if (
        observed.get("schema") != "CHIEF_EXECUTION_PROGRESS_EVIDENCE_V1"
        or observed.get("kind") != value.get("kind")
        or observed.get("evidence_id") != value.get("evidence_id")
        or observed.get("observation") != value.get("observation")
        or observed.get("work_id") != package["work_id"]
        or observed.get("package_id") != package["package_id"]
        or observed.get("candidate_sha256") != package["candidate_sha256"]
        or not isinstance(observed.get("criterion_id"), str)
        or not observed["criterion_id"]
        or observed["criterion_id"] not in _accepted_criterion_ids(package)
    ):
        raise ContinuousExecutionError("progress evidence does not match its retained observation")
    normalized = dict(value)
    for key in ("kind", "evidence_id", "observation", "work_id", "package_id", "candidate_sha256", "criterion_id"):
        normalized[key] = observed[key]
    return normalized


def progress_summary(rounds: object) -> dict[str, int]:
    """Measure only retained distinct evidence; IDs and logs never create progress."""
    if not isinstance(rounds, list):
        raise ContinuousExecutionError("rounds must be an array")
    seen_rounds: set[str] = set()
    seen_evidence: set[str] = set()
    seen_hashes: set[str] = set()
    seen_transitions: set[str] = set()
    real = 0
    trailing_stagnant = 0
    for item in rounds:
        round_id = item.get("round_id") if isinstance(item, dict) else None
        if not isinstance(round_id, str) or not round_id or round_id in seen_rounds:
            trailing_stagnant += 1
            continue
        seen_rounds.add(round_id)
        transition = _progress_identity(item)
        if _round_is_real(item, seen_evidence, seen_hashes) and transition is not None and transition not in seen_transitions:
            real += 1
            seen_transitions.add(transition)
            trailing_stagnant = 0
        else:
            trailing_stagnant += 1
    return {"real_progress_cycles": real, "trailing_stagnant_rounds": trailing_stagnant}


def validate_delegated_testing(value: object, *, native_observation_loader: Any = None, package: Mapping[str, Any] | None = None, submitting_project: Path | None = None, native_observation_root: Path | None = None) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContinuousExecutionError("testing delegation must be an object")
    for key in ("testing_chief_task_id", "delegation_id", "reviewer_task_id", "writer_task_id", "scope", "delegation_evidence_ref"):
        _string(value.get(key), key)
    testing_reviewer = _testing_reviewer_task_id(submitting_project=submitting_project, native_observation_root=native_observation_root)
    if value.get("testing_chief_task_id") != testing_reviewer:
        raise ContinuousExecutionError("testing delegation must be issued by the unique Testing Chief")
    if value.get("reviewer_registered") is not True:
        raise ContinuousExecutionError("testing reviewer must be pre-registered")
    if value.get("reviewer_task_id") == value.get("writer_task_id"):
        raise ContinuousExecutionError("testing reviewer must be independent of the writer")
    if value.get("risk") not in {"low", "medium"} or value.get("global_upgrade") is True or value.get("disputed") is True:
        raise ContinuousExecutionError("delegated testing is unavailable for high-risk, disputed, or global-upgrade work")
    _sha256(value.get("candidate_sha256"), "candidate_sha256")
    _sha256(value.get("delegation_receipt_sha256"), "delegation_receipt_sha256")
    if native_observation_loader is not None:
        observed = native_observation_loader(value["delegation_evidence_ref"], value["delegation_receipt_sha256"], "testing delegation")
        if (observed.get("schema") != "CHIEF_TESTING_DELEGATION_EVIDENCE_V1" or observed.get("issuer_task_id") != testing_reviewer
            or observed.get("delegation_id") != value["delegation_id"] or observed.get("reviewer_task_id") != value["reviewer_task_id"]
            or observed.get("writer_task_id") != value["writer_task_id"] or observed.get("candidate_sha256") != value["candidate_sha256"]
            or observed.get("risk") != value["risk"] or observed.get("scope") != value["scope"]
            or any(observed.get(key) is not False for key in ("sensitive", "production", "global_upgrade", "disputed"))):
            raise ContinuousExecutionError("testing delegation is not an exact retained Testing Chief receipt")
        if package is not None and (observed.get("work_id") != package["work_id"] or observed.get("package_id") != package["package_id"] or observed.get("candidate_sha256") != package["candidate_sha256"]):
            raise ContinuousExecutionError("testing delegation does not bind the active package")
    return value


def reconcile_execution(state: object, package: object | None) -> dict[str, Any]:
    """Return one bounded next intent for a single work ID without dispatching it."""
    if not isinstance(state, dict):
        raise ContinuousExecutionError("execution state must be an object")
    if package is None:
        return {"status": state.get("status", "unknown"), "next_action": "LEGACY_CONTRACT"}
    package = validate_execution_package(package)
    work_id = _string(state.get("work_id"), "state.work_id")
    status = _string(state.get("status"), "state.status")
    if work_id != package["work_id"] or state.get("package_id") != package["package_id"]:
        return {"status": status, "next_action": "HOLD_WORK_ID_MISMATCH"}
    if state.get("legacy_stop") in {"one_shot", "stopped", "denied"}:
        return {"status": status, "next_action": "HOLD_LEGACY_STOP"}
    if status in INACTIVE_STATUSES:
        return {"status": status, "next_action": "HOLD_INACTIVE_TARGET"}
    if status == "local_delivered":
        return {"status": status, "next_action": "NO_ACTION"}
    if status not in ACTIVE_STATUSES:
        raise ContinuousExecutionError("state.status is not an execution status")
    if state.get("owner_task_id") != package["writer_task_id"]:
        return {"status": status, "next_action": "HOLD_OWNER_MISMATCH"}
    if "resource_units_used" not in state:
        raise ContinuousExecutionError("resource_units_used must come from a retained measurement")
    used = state.get("resource_units_used")
    if type(used) is not int or used < 0:
        raise ContinuousExecutionError("resource_units_used must be a non-negative integer")
    if used >= package["resource_limits"]["max_resource_units"]:
        return {"status": status, "next_action": "STOP_RESOURCE_LIMIT"}
    returns = state.get("returns", [])
    if not isinstance(returns, list):
        raise ContinuousExecutionError("returns must be an array")
    dispatched = state.get("dispatched_return_ids", [])
    if not isinstance(dispatched, list) or not all(isinstance(item, str) for item in dispatched):
        raise ContinuousExecutionError("dispatched_return_ids must be an array of strings")
    matching = [item for item in returns if isinstance(item, dict) and item.get("work_id") == work_id]
    if returns and not matching:
        matching = []  # old work evidence is retained but can never close this work ID.
    for returned in matching:
        return_id = returned.get("return_id")
        if not isinstance(return_id, str) or not return_id or return_id in dispatched:
            continue
        if returned.get("package_id") != package["package_id"] or returned.get("kind") not in RETURN_KINDS:
            continue
        if returned.get("scope") != "local":
            continue
        if returned.get("kind") == "test_pass":
            _sha256(returned.get("candidate_sha256"), "return.candidate_sha256")
            expected_candidate = _sha256(state.get("expected_candidate_sha256"), "state.expected_candidate_sha256")
            if returned["candidate_sha256"] != expected_candidate:
                return {"status": status, "next_action": "HOLD_CANDIDATE_MISMATCH"}
        expected_status = {"approval": "awaiting_permission", "test_pass": "testing_queue", "recovery": "technical_blocked", "resource_recovered": "quota_limited"}.get(returned["kind"])
        if status not in {"running", expected_status}:
            return {"status": status, "next_action": "HOLD_RETURN_STATE_MISMATCH"}
        return {"status": status, "next_action": "CONTINUE_RETURNED_WORK", "return_id": return_id}
    summary = progress_summary(state.get("rounds", []))
    if matching:
        # The exact return was already dispatched.  Never infer a second send
        # merely because a later observation has no new receipt.
        return {"status": status, "next_action": "NO_ACTION", **summary}
    if not returns and not state.get("rounds"):
        return {"status": status, "next_action": "OBSERVATION_GAP", **summary}
    if returns and not matching and not state.get("rounds"):
        # An older work ID stays retained for audit but has no authority over
        # the current work item.
        return {"status": status, "next_action": "NO_ACTION", **summary}
    if summary["real_progress_cycles"] >= package["resource_limits"]["max_progress_cycles"]:
        return {"status": status, "next_action": "STOP_PROGRESS_CYCLE_LIMIT", **summary}
    if summary["trailing_stagnant_rounds"] >= 2:
        rounds = state.get("rounds", [])
        stagnant_ids = [item.get("round_id") for item in rounds[-2:] if isinstance(item, dict)]
        if len(stagnant_ids) != 2 or not all(isinstance(item, str) and item for item in stagnant_ids):
            return {"status": status, "next_action": "HOLD_DIAGNOSIS_EVIDENCE_INSUFFICIENT", **summary}
        diagnosis = state.get("independent_diagnosis")
        if isinstance(diagnosis, dict):
            if (
                all(isinstance(diagnosis.get(key), str) and diagnosis[key] for key in ("diagnosis_id", "reviewer_task_id", "new_path", "evidence_ref"))
                and diagnosis.get("round_ids") == stagnant_ids
                and diagnosis.get("work_id") == package["work_id"]
                and diagnosis.get("package_id") == package["package_id"]
                and diagnosis.get("candidate_sha256") == package["candidate_sha256"]
                and diagnosis.get("reviewer_task_id") in package["independent_reviewer_task_ids"]
            ):
                return {"status": status, "next_action": "HOLD_DIAGNOSIS_REQUIRES_RETRY_RECEIPT", **summary}
            return {"status": status, "next_action": "HOLD_DIAGNOSIS_EVIDENCE_INSUFFICIENT", **summary}
        request = state.get("independent_diagnosis_requested")
        if isinstance(request, dict) and request.get("round_ids") == stagnant_ids and isinstance(request.get("diagnosis_request_id"), str) and request["diagnosis_request_id"]:
            return {"status": status, "next_action": "AWAIT_DIAGNOSIS", **summary}
        return {"status": status, "next_action": "REQUEST_INDEPENDENT_DIAGNOSIS", "round_ids": stagnant_ids, **summary}
    return {"status": status, "next_action": "CONTINUE", **summary}


def permits_continuous_cycle(package: object, rounds: object) -> bool:
    """Retry-policy adapter: only distinct real evidence can exceed legacy three cycles."""
    checked = validate_execution_package(package)
    summary = progress_summary(rounds)
    return (
        summary["trailing_stagnant_rounds"] == 0
        and 0 < summary["real_progress_cycles"] <= checked["resource_limits"]["max_progress_cycles"]
    )


def validate_execution_records(plan: object, registry: object, approvals: object, *, evidence_root: Path | None = None, retained_loader: Any = None, native_observation_loader: Any = None, submitting_project: Path | None = None, native_observation_root: Path | None = None) -> None:
    """Bind opt-in packages to the existing plan, registry, and approval queue.

    Missing `execution_packages` deliberately means legacy operation.  This
    function validates the existing records in place; it neither creates a
    queue/database nor dispatches a task.
    """
    if not isinstance(plan, dict) or not isinstance(registry, dict) or not isinstance(approvals, dict):
        raise ContinuousExecutionError("continuous execution records must be objects")
    raw_packages = plan.get("execution_packages")
    if raw_packages is None:
        return
    if not isinstance(raw_packages, list) or not raw_packages:
        raise ContinuousExecutionError("execution_packages must be a non-empty array when present")
    packages = [validate_execution_package(item) for item in raw_packages]
    by_id = {item["package_id"]: item for item in packages}
    if len(by_id) != len(packages):
        raise ContinuousExecutionError("execution_packages must have unique package_id values")
    if len({item["work_id"] for item in packages}) != len(packages) or len({item["approval_id"] for item in packages}) != len(packages):
        raise ContinuousExecutionError("execution packages must not reuse work_id or approval_id")
    requests = approvals.get("requests")
    if not isinstance(requests, list):
        raise ContinuousExecutionError("approval queue requests must be an array")
    approvals_by_id = {item.get("request_id"): item for item in requests if isinstance(item, dict)}
    if len(approvals_by_id) != len(requests) or any(not isinstance(item.get("request_id"), str) or not item["request_id"] for item in requests if isinstance(item, dict)):
        raise ContinuousExecutionError("approval queue request IDs must be unique")
    tasks = registry.get("tasks")
    if not isinstance(tasks, list):
        raise ContinuousExecutionError("task registry tasks must be an array")
    tasks_by_work = {item.get("execution_work_id"): item for item in tasks if isinstance(item, dict) and isinstance(item.get("execution_work_id"), str)}
    if len(tasks_by_work) != len([item for item in tasks if isinstance(item, dict) and isinstance(item.get("execution_work_id"), str)]):
        raise ContinuousExecutionError("task registry execution_work_id values must be unique")
    for package in packages:
        approval = approvals_by_id.get(package["approval_id"])
        if (
            not isinstance(approval, dict)
            or approval.get("status") != "approved"
            or approval.get("decision_receipt_sha256") != package["approval_receipt_sha256"]
            or not isinstance(approval.get("decision_evidence_ref"), str)
            or not approval["decision_evidence_ref"]
        ):
            raise ContinuousExecutionError("execution package approval_id must bind an approved queue record")
        if approval["decision_evidence_ref"] != package["approval_evidence_ref"]:
            raise ContinuousExecutionError("execution package approval evidence reference must match its queue record")
        if evidence_root is not None or retained_loader is not None or native_observation_loader is not None:
            if native_observation_loader is None or not package["approval_evidence_ref"].startswith("native://"):
                raise ContinuousExecutionError("execution approval must be an external native observation")
            observed = native_observation_loader(
                package["approval_evidence_ref"], package["approval_receipt_sha256"], "approval evidence"
            )
            if (
                observed.get("schema") != "CHIEF_EXECUTION_APPROVAL_EVIDENCE_V1"
                or observed.get("kind") != "execution_approval"
                or observed.get("observation_id") != package["approval_id"]
                or observed.get("approval_id") != package["approval_id"]
                or observed.get("package_id") != package["package_id"]
                or observed.get("package_sha256") != package_digest(package)
                or observed.get("decision") != "approved"
                or not isinstance(observed.get("observed_by"), str)
                or not observed["observed_by"]
                or observed["observed_by"] == package["writer_task_id"]
                or observed.get("authority_kind") != "native_coordinator_observation"
                or observed.get("coordinator_task_id") != package["native_intake"]["coordinator_task_id"]
                or observed.get("native_root_id") != package["native_intake"]["root_id"]
                or observed.get("project") != package["project"]
                or observed.get("writer_task_id") != package["writer_task_id"]
                or observed.get("candidate_sha256") != package["candidate_sha256"]
            ):
                raise ContinuousExecutionError("approval evidence is not an independent approved observation")
        task = tasks_by_work.get(package["work_id"])
        if not isinstance(task, dict) or task.get("execution_package_id") != package["package_id"]:
            raise ContinuousExecutionError("execution package work_id must bind one registry task")
        if task.get("task_id") != package["writer_task_id"]:
            raise ContinuousExecutionError("execution package writer_task_id must match its registry task")
        task_project = task.get("project_id")
        if task_project != package["project"]["project_id"]:
            raise ContinuousExecutionError("execution package project_id must match its registry task")
        if task.get("status") not in {"running", "testing_queue", "awaiting_input", "awaiting_permission", "quota_limited", "technical_blocked"}:
            raise ContinuousExecutionError("execution package writer must be current and active")
        if task.get("execution_root_id") != package["project"]["root_id"] or task.get("execution_branch") != package["project"]["branch"]:
            raise ContinuousExecutionError("execution package root_id and branch must match its registry task")
        if task.get("write_surface") != package["write_surface"]:
            raise ContinuousExecutionError("execution package write_surface must match its registry task")
        registry_by_id = {item.get("task_id"): item for item in tasks if isinstance(item, dict)}
        for reviewer_id in package["independent_reviewer_task_ids"]:
            reviewer = registry_by_id.get(reviewer_id)
            if not isinstance(reviewer, dict) or reviewer.get("execution_reviewer_for") != package["work_id"]:
                raise ContinuousExecutionError("execution package reviewer must be pre-registered for this work")
            if reviewer.get("task_id") == package["writer_task_id"] or reviewer.get("project_id") != package["project"]["project_id"] or reviewer.get("status") in {"paused", "archived", "completed"}:
                raise ContinuousExecutionError("execution package reviewer must be current, independent, and project-bound")
            if reviewer.get("write_surface"):
                raise ContinuousExecutionError("execution package reviewer must not own the writer surface")
        delegation = package.get("testing_delegation")
        if delegation is not None:
            checked_delegation = validate_delegated_testing(delegation, native_observation_loader=native_observation_loader, package=package, submitting_project=submitting_project, native_observation_root=native_observation_root)
            if checked_delegation["writer_task_id"] != package["writer_task_id"]:
                raise ContinuousExecutionError("testing delegation writer must match the execution package writer")
