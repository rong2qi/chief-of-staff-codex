"""Schema-v1 governance helpers for approved autonomy and phase-bound repair budgets."""
from __future__ import annotations

from typing import Any, Mapping


AUTONOMY_SCHEMA = "CHIEF_AUTONOMY_POLICY_V1"
PHASE_SCHEMA = "CHIEF_REPAIR_PHASE_TRANSITION_V1"
CONTINUATION_KINDS = {"preparation", "evidence_collection", "candidate_defect"}
PROTECTED_ACTIONS = {"new_permission", "real_data", "credentials_or_secrets", "production", "release_or_deploy", "payment", "external_send", "security_rejection"}


class AutonomyPolicyError(ValueError):
    pass


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AutonomyPolicyError(f"{label} must be a non-empty string")
    return value


def _text_list(value: object, label: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise AutonomyPolicyError(f"{label} must be an array of non-empty strings")
    if len(value) != len(set(value)):
        raise AutonomyPolicyError(f"{label} must not contain duplicates")
    return list(value)


def validate_approval_package(value: object) -> dict[str, Any]:
    """Validate the up-front approval envelope; it never treats delivery as execution."""
    if not isinstance(value, dict):
        raise AutonomyPolicyError("approval package must be an object")
    required = {"schema", "package_id", "goal", "write_surfaces", "action_classes", "external_targets", "data_classification", "resource_limits", "reverification", "stop_conditions", "rollback", "deferred_final_decisions"}
    if set(value) != required or value.get("schema") != AUTONOMY_SCHEMA:
        raise AutonomyPolicyError("approval package fields are incomplete or ambiguous")
    for key in ("package_id", "goal", "data_classification", "rollback"):
        _text(value.get(key), key)
    for key in ("write_surfaces", "action_classes", "external_targets", "reverification", "stop_conditions", "deferred_final_decisions"):
        _text_list(value.get(key), key, allow_empty=key in {"write_surfaces", "external_targets", "deferred_final_decisions"})
    limits = value.get("resource_limits")
    if not isinstance(limits, dict) or set(limits) != {"unit", "maximum"}:
        raise AutonomyPolicyError("resource_limits must contain only unit and maximum")
    _text(limits.get("unit"), "resource_limits.unit")
    if type(limits.get("maximum")) is not int or limits["maximum"] < 1:
        raise AutonomyPolicyError("resource_limits.maximum must be a positive integer")
    return value


def classify_continuation(value: object) -> str:
    """Keep local preparation, evidence work, and a candidate defect distinct."""
    if not isinstance(value, Mapping) or value.get("kind") not in CONTINUATION_KINDS:
        raise AutonomyPolicyError("continuation kind must be preparation, evidence_collection, or candidate_defect")
    _text(value.get("scope"), "continuation.scope")
    if value["kind"] == "candidate_defect":
        _text(value.get("candidate_id"), "continuation.candidate_id")
        legacy_failure = value.get("failure_evidence")
        retained_failure = value.get("failure_evidence_ref"), value.get("failure_evidence_sha256")
        if not (isinstance(legacy_failure, str) and legacy_failure.strip()) and not all(
            isinstance(item, str) and item.strip() for item in retained_failure
        ):
            raise AutonomyPolicyError("continuation.failure_evidence must be a retained reference")
    return value["kind"]


def evaluate_approved_local_action(package: object, action: object, approval_context: object = None) -> dict[str, Any]:
    """Return a local source-Chief intent only after package-to-action revalidation.

    The caller/host owns delivery and execution.  This result is neither an ACK,
    a permission grant, nor a Testing verdict.
    """
    package = validate_approval_package(package)
    if not isinstance(action, Mapping):
        raise AutonomyPolicyError("action must be an object")
    required = {"action_class", "write_surface", "external_target", "data_classification", "resource_cost", "reverification_passed", "protected_action"}
    if set(action) != required:
        raise AutonomyPolicyError("action fields are incomplete or ambiguous")
    action_class = _text(action.get("action_class"), "action_class")
    surface = action.get("write_surface")
    target = action.get("external_target")
    if surface is not None and (not isinstance(surface, str) or not surface.strip()):
        raise AutonomyPolicyError("write_surface must be a string or null")
    if target is not None and (not isinstance(target, str) or not target.strip()):
        raise AutonomyPolicyError("external_target must be a string or null")
    derived_protected = action_class in PROTECTED_ACTIONS or any(token in action_class for token in ("external", "production", "release", "deploy", "payment", "permission"))
    if derived_protected:
        return {"status": "protected_action", "operator_actionable_now": True}
    if action_class not in package["action_classes"] or (surface is not None and surface not in package["write_surfaces"]) or (target is not None and target not in package["external_targets"]):
        return {"status": "chief_scope_diagnosis_required", "operator_actionable_now": False, "todo_suppressed": True}
    if action.get("data_classification") != package["data_classification"] or type(action.get("resource_cost")) is not int or action["resource_cost"] < 0 or action["resource_cost"] > package["resource_limits"]["maximum"]:
        return {"status": "chief_evidence_required", "operator_actionable_now": False, "todo_suppressed": True}
    if action.get("reverification_passed") is not True or action.get("protected_action") not in PROTECTED_ACTIONS | {"none"}:
        return {"status": "chief_evidence_required", "operator_actionable_now": False, "todo_suppressed": True}
    if action.get("protected_action") != "none":
        return {"status": "protected_action", "operator_actionable_now": True}
    # Shape validation is never approval.  A host/native consumer must supply
    # an exact approved action record plus cumulative resource observation.
    if not isinstance(approval_context, Mapping):
        return {"status": "chief_approval_evidence_required", "operator_actionable_now": False, "todo_suppressed": True}
    expected = {"package_id", "action_class", "write_surface", "external_target", "data_classification", "approved", "current", "resource_used", "resource_max"}
    if set(approval_context) != expected or approval_context.get("approved") is not True or approval_context.get("current") is not True:
        return {"status": "chief_approval_evidence_required", "operator_actionable_now": False, "todo_suppressed": True}
    if any(approval_context.get(key) != value for key, value in (("package_id", package["package_id"]), ("action_class", action_class), ("write_surface", surface), ("external_target", target), ("data_classification", action["data_classification"]))) or type(approval_context.get("resource_used")) is not int or type(approval_context.get("resource_max")) is not int or approval_context["resource_used"] < 0 or approval_context["resource_max"] != package["resource_limits"]["maximum"] or approval_context["resource_used"] + action["resource_cost"] > approval_context["resource_max"]:
        return {"status": "chief_approval_evidence_required", "operator_actionable_now": False, "todo_suppressed": True}
    return {"status": "native_approval_consumer_required", "operator_actionable_now": False, "todo_suppressed": True, "package_id": package["package_id"]}


def validate_phase_transition(value: object, state: Mapping[str, object]) -> dict[str, Any]:
    """Require evidence-rich phase closure before a reset can start at zero."""
    if not isinstance(value, dict):
        raise AutonomyPolicyError("phase transition must be an object")
    required = {"schema", "prior_phase_id", "prior_candidate_id", "new_phase_id", "prior_failure_evidence", "new_plan", "new_candidate_id", "stop_conditions", "resource_limits", "approval_id", "writer_task_id"}
    if set(value) != required or value.get("schema") != PHASE_SCHEMA:
        raise AutonomyPolicyError("phase transition fields are incomplete or ambiguous")
    prior, new = _text(value.get("prior_phase_id"), "prior_phase_id"), _text(value.get("new_phase_id"), "new_phase_id")
    if prior == new:
        raise AutonomyPolicyError("new_phase_id must differ from prior_phase_id")
    _text(value.get("prior_candidate_id"), "prior_candidate_id")
    evidence = value.get("prior_failure_evidence")
    if not isinstance(evidence, list) or not evidence or any(not isinstance(item, dict) or set(item) != {"evidence_ref", "evidence_sha256"} for item in evidence):
        raise AutonomyPolicyError("prior_failure_evidence must be retained evidence references")
    _text(value.get("new_plan"), "new_plan")
    _text(value.get("new_candidate_id"), "new_candidate_id")
    _text(value.get("approval_id"), "approval_id")
    _text(value.get("writer_task_id"), "writer_task_id")
    _text_list(value.get("stop_conditions"), "stop_conditions")
    limits = value.get("resource_limits")
    if not isinstance(limits, dict) or set(limits) != {"unit", "maximum"}:
        raise AutonomyPolicyError("phase resource_limits must contain only unit and maximum")
    _text(limits.get("unit"), "phase resource_limits.unit")
    if type(limits.get("maximum")) is not int or limits["maximum"] < 1:
        raise AutonomyPolicyError("phase resource_limits.maximum must be a positive integer")
    phases = state.get("phases")
    if isinstance(phases, list):
        active = state.get("active_phase_id")
        if active != prior or not any(isinstance(p, dict) and p.get("phase_id") == prior and p.get("closed") is not True for p in phases):
            raise AutonomyPolicyError("phase transition must close the exact active prior phase")
        if any(isinstance(p, dict) and p.get("phase_id") == new for p in phases):
            raise AutonomyPolicyError("new_phase_id has already been used")
    elif prior != "legacy":
        raise AutonomyPolicyError("legacy repair state may transition only from the explicit legacy phase")
    return value


def active_phase_state(state: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return phase-local cycles and diagnosis journal without rewriting legacy logs."""
    phases = state.get("phases")
    if not isinstance(phases, list):
        cycles = state.get("cycles")
        if not isinstance(cycles, list):
            raise AutonomyPolicyError("repair budget log schema is invalid")
        journal = state.setdefault("diagnosis_requests", [])
        if not isinstance(journal, list):
            raise AutonomyPolicyError("diagnosis request journal is invalid")
        return cycles, journal
    active = state.get("active_phase_id")
    phase = next((p for p in phases if isinstance(p, dict) and p.get("phase_id") == active), None)
    if not isinstance(phase, dict) or phase.get("closed") is True:
        raise AutonomyPolicyError("repair budget has no active phase")
    cycles, journal = phase.get("cycles"), phase.get("diagnosis_requests")
    if not isinstance(cycles, list) or not isinstance(journal, list):
        raise AutonomyPolicyError("active phase repair journal is invalid")
    return cycles, journal


def begin_new_phase(state: dict[str, Any], transition: object) -> dict[str, Any]:
    """Append a closed historical phase and create a zero-cycle active phase."""
    validate_phase_transition(transition, state)
    transition = dict(transition)
    prior = transition["prior_phase_id"]
    phases = state.get("phases")
    if not isinstance(phases, list):
        legacy_cycles = state.get("cycles")
        legacy_journal = state.get("diagnosis_requests", [])
        if not isinstance(legacy_cycles, list) or not isinstance(legacy_journal, list):
            raise AutonomyPolicyError("repair budget log schema is invalid")
        phases = [{"phase_id": "legacy", "cycles": legacy_cycles, "diagnosis_requests": legacy_journal, "closed": False}]
        # Preserve unknown extension fields and the original legacy journal;
        # V2 readers use phases, while historical readers still see their data.
        state["schema"] = "CHIEF_REPAIR_BUDGET_V2"
        state["phases"] = phases
        state["active_phase_id"] = "legacy"
    old = next(p for p in phases if p["phase_id"] == prior)
    old["closed"] = True
    old["transition"] = transition
    phases.append({"phase_id": transition["new_phase_id"], "cycles": [], "diagnosis_requests": [], "closed": False, "started_from": transition})
    state["active_phase_id"] = transition["new_phase_id"]
    return state
