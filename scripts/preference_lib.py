#!/usr/bin/env python3
"""Shared validation and atomic persistence for optional Chief preferences."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path
from typing import Any

try:
    from .legacy_terminology_migration import (
        LegacyTerminologyConflict,
        migrate_pin_snapshot_input,
        migrate_profile_input,
    )
except ImportError:  # Direct script execution keeps the scripts directory on sys.path.
    from legacy_terminology_migration import (
        LegacyTerminologyConflict,
        migrate_pin_snapshot_input,
        migrate_profile_input,
    )


SKILL_ROOT = Path(__file__).resolve().parent.parent
CORE_PROFILE = SKILL_ROOT / "assets" / "operator-preferences.example.json"
OPERATOR_PROFILE = (
    SKILL_ROOT / "assets" / "presets" / "operator-controlled-bilingual.json"
)
MANAGED_START = "<!-- chief-of-staff-preferences:start -->"
MANAGED_END = "<!-- chief-of-staff-preferences:end -->"
CLIP_KINDS = {"written", "spoken"}
TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")
PIN_CORE_ROLES = {
    "general_office", "todo", "creative_director", "context_migration_monitor",
}
CHIEF_TITLE_PREFIX = "Chief of "
CHIEF_TITLE_EXCEPTION_ROLES = {"general_office", "todo", "context_migration_monitor"}
PIN_CRITERIA = [
    "user_delivery_value", "imminent_material_decision", "delay_cost",
    "cross_project_dependency", "activity", "evidence_confidence", "sidebar_cost",
]
PIN_DEFAULT_EXCLUSIONS = [
    "paused", "completed", "superseded", "migration_cancelled", "routine_push",
    "meeting_summary", "report_only", "process_only",
]
AUTOMATION_BUNDLE_FIELDS = [
    "id", "name", "kind", "target_thread_id", "status", "schedule",
    "prompt_sha256", "notification_policy",
]
AUTOMATION_REBIND_BEFORE = ["takeover", "authority_switch", "predecessor_archive"]
AUTOMATION_PRESERVE = ["schedule", "prompt_semantics", "notification_policy", "scope"]
RECOMMENDED_ACTION_CLASSES = [
    "exact_task_owned_temp_cleanup",
    "metadata_only_allowlisted_read",
    "fixed_sha256_one_shot_nonproduction_execution",
    "disposable_local_test_stop_rollback",
    "bounded_repair_recheck_without_scope_expansion",
]
RECOMMENDED_ACTION_CONDITIONS = [
    "single_clear_recommendation",
    "evidence_complete",
    "exact_identity_and_surface",
    "independent_verification_when_applicable",
    "no_unresolved_safety_dissent",
    "nonproduction",
    "no_real_customer_or_personal_data",
    "no_credentials_or_secrets",
    "stop_and_rollback_defined",
]
RECOMMENDED_OPERATOR_ONLY_ACTIONS = [
    "final_goal_or_material_product_direction",
    "visual_selection",
    "final_acceptance_or_termination",
    "chief_appoint_pause_remove_pin_or_replace",
    "payment_or_purchase",
    "release_deploy_production_or_rollback",
    "external_communication_new_collaborator_or_public_visibility",
    "credentials_secrets_real_identity_or_sensitive_data",
    "legal_privacy_or_material_security_risk_acceptance",
    "real_user_or_production_data_deletion",
    "recursive_broad_or_irreversible_deletion",
    "write_ownership_conflict",
    "failed_or_unverifiable_after_allowed_repair_recheck",
    "override_prior_explicit_operator_denial",
]
APPROVED_DECISION_RELAY_EXACT = {
    "mode": "todo_direct_exact_words_once",
    "audit": "general_office_asynchronous_nonblocking",
    "source": "registered_current_source_chief_only",
    "visual_route": "creative_director_only",
    "delivery_is_execution": False,
}
AUTONOMY_POLICY_EXACT = {
    "schema": "CHIEF_AUTONOMY_POLICY_V1",
    "enabled": False,
    "approval_package_required": True,
    "operation_revalidation_required": True,
    "ordinary_repair_cycles": 3,
    "protected_actions": [
        "new_permission", "real_data", "credentials_or_secrets", "production",
        "release_or_deploy", "payment", "external_send", "security_rejection",
    ],
}
CAPABILITY_DISCOVERY_SURFACES = [
    "host_and_installed_capabilities", "codex_plugins", "codex_skills",
    "official_documentation", "open_source_projects",
    "external_configuration_patterns",
]
CAPABILITY_DISCOVERY_CRITERIA = [
    "project_fit", "productivity_gain", "maintenance_activity", "license",
    "supply_chain_risk", "permission_impact", "integration_impact", "overlap",
]
CAPABILITY_DISCOVERY_TRIGGERS = [
    "project_start", "phase_or_stack_change", "repeated_manual_work",
    "blocker_or_failure", "before_custom_build", "before_production_execution",
]
CAPABILITY_DISCOVERY_LIFECYCLE_SURFACES = CAPABILITY_DISCOVERY_SURFACES + [
    "apps_connectors_mcp",
    "official_api_sdk_cli_framework_library",
    "maintained_oss_templates_starters_reference_implementations_design_systems",
    "host_project_runtimes_emulators_browsers_scripts_caches_builds",
    "containers_devcontainers_disposable_vms",
    "compliant_datasets_model_assets_eval_sets_prompt_libraries",
    "testing_eval_security_performance_reliability_observability",
    "ci_configuration_runbooks_sops_architecture_patterns",
    "saas_managed_cloud_research_only",
    "experts_maintainers_service_providers_discover_only_no_contact",
]
CAPABILITY_DISCOVERY_EVIDENCE = [
    "source", "fixed_version_or_revision", "fit", "benefit", "maintenance",
    "license", "supply_chain", "permissions", "privacy", "secrets", "cost",
    "integration_lifecycle", "overlap", "exit_removal_path",
]
CAPABILITY_DISCOVERY_PROHIBITED_ACTIONS = [
    "install", "pull", "download", "enable", "connect_account",
    "add_dependency", "payment", "contact_external", "external_send",
    "production_execution", "production_use", "project_mutation",
]
CAPABILITY_DISCOVERY_LIFECYCLE_EXACT = {
    "scope": "all_registered_chiefs",
    "trigger_policy": "key_events",
    "triggers": CAPABILITY_DISCOVERY_TRIGGERS,
    "acquisition_policy": "discover_and_recommend_only",
    "reporting_policy": "material_recommendations_only",
    "rollout_policy": "active_unfinished_immediate",
    "max_parallel_scans": 2,
    "paused_project_policy": "defer_until_resume",
    "max_candidates_per_trigger": 3,
    "dedupe_policy": "one_pack_per_chief_trigger",
    "serious_candidate_evidence": CAPABILITY_DISCOVERY_EVIDENCE,
    "prohibited_actions": CAPABILITY_DISCOVERY_PROHIBITED_ACTIONS,
    "default_adoption_scope": "project_local",
    "no_result_policy": "internal_evidence_only",
    "completed_archived_policy": "exclude",
    "testing_candidate_route": "testing_director_first",
    "visual_direction_route": "creative_director",
    "material_recommendation_route": "general_office",
}
CAPABILITY_DISCOVERY_LIFECYCLE_ONLY_KEYS = set(
    CAPABILITY_DISCOVERY_LIFECYCLE_EXACT
) - {"acquisition_policy"}


class PreferenceError(ValueError):
    """Raised when a preference profile is unsafe or malformed."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreferenceError(f"cannot read preference profile {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PreferenceError("preference profile must be a JSON object")
    try:
        migrated, _ = migrate_profile_input(value)
    except LegacyTerminologyConflict as exc:
        raise PreferenceError(str(exc)) from exc
    return migrated


def preset_profile(name: str) -> dict[str, Any]:
    paths = {
        "core": CORE_PROFILE,
        "operator-controlled-bilingual": OPERATOR_PROFILE,
    }
    try:
        profile = read_json(paths[name])
    except KeyError as exc:
        raise PreferenceError(f"unknown preset: {name}") from exc
    return copy.deepcopy(profile)


def _require_object(profile: dict[str, Any], key: str, errors: list[str]) -> dict[str, Any]:
    value = profile.get(key)
    if not isinstance(value, dict):
        errors.append(f"{key} must be an object")
        return {}
    return value


def _require_bool(section: dict[str, Any], key: str, label: str, errors: list[str]) -> None:
    if not isinstance(section.get(key), bool):
        errors.append(f"{label}.{key} must be a boolean")


def _unique_string_list(value: object, label: str, errors: list[str]) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        errors.append(f"{label} must be an array of non-empty strings")
        return []
    if len(value) != len(set(value)):
        errors.append(f"{label} must not contain duplicates")
    return value


def _validate_pin_governance(profile: dict[str, Any], errors: list[str]) -> None:
    pin = _require_object(profile, "pin_governance", errors)
    _require_bool(pin, "enabled", "pin_governance", errors)

    roles = pin.get("mandatory_core_roles")
    if not isinstance(roles, list):
        errors.append("pin_governance.mandatory_core_roles must be an array")
        roles = []
    seen_roles: set[str] = set()
    core_thread_ids: list[str] = []
    for index, item in enumerate(roles):
        label = f"pin_governance.mandatory_core_roles[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        role = item.get("role")
        if role not in PIN_CORE_ROLES:
            errors.append(f"{label}.role is invalid")
        elif role in seen_roles:
            errors.append(f"{label}.role is duplicated")
        else:
            seen_roles.add(role)
        title = item.get("title")
        if not isinstance(title, str) or not title:
            errors.append(f"{label}.title must be a non-empty string")
        elif (
            role in PIN_CORE_ROLES - CHIEF_TITLE_EXCEPTION_ROLES
            and (
                not title.startswith(CHIEF_TITLE_PREFIX)
                or not title[len(CHIEF_TITLE_PREFIX):].strip()
            )
        ):
            errors.append(
                f"{label}.title must start with {CHIEF_TITLE_PREFIX!r}; "
                "only general_office, todo, and the non-Chief context monitor are exceptions"
            )
        thread_id = item.get("thread_id")
        if thread_id is not None and (not isinstance(thread_id, str) or not thread_id):
            errors.append(f"{label}.thread_id must be a non-empty string or null")
        if isinstance(thread_id, str) and thread_id:
            core_thread_ids.append(thread_id)
    if len(roles) != len(PIN_CORE_ROLES) or seen_roles != PIN_CORE_ROLES:
        errors.append("pin_governance.mandatory_core_roles requires each core role exactly once")
    if len(core_thread_ids) != len(set(core_thread_ids)):
        errors.append("pin_governance mandatory core thread IDs must be unique")
    if pin.get("enabled") is True:
        if profile.get("scope") != "global":
            errors.append("enabled pin_governance requires global scope")
        if len(core_thread_ids) != len(PIN_CORE_ROLES):
            errors.append("enabled pin_governance requires a thread_id for every core role")

    slots = pin.get("optional_chief_slots")
    if not isinstance(slots, dict):
        errors.append("pin_governance.optional_chief_slots must be an object")
        slots = {}
    limit = slots.get("limit")
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        errors.append("pin_governance.optional_chief_slots.limit must be positive")
    if slots.get("default_pin_primary_task") is not False:
        errors.append("pin_governance.optional_chief_slots.default_pin_primary_task must be false")
    if slots.get("change_mode") != "recommend_then_operator_approve":
        errors.append("pin_governance.optional_chief_slots.change_mode is invalid")
    if slots.get("protect_manual_non_chief_pins") is not True:
        errors.append("pin_governance.optional_chief_slots.protect_manual_non_chief_pins must be true")
    if slots.get("capacity_policy") != "observed_capacity_then_paired_replacement":
        errors.append("pin_governance.optional_chief_slots.capacity_policy is invalid")

    recommendation = pin.get("recommendation_policy")
    if not isinstance(recommendation, dict):
        errors.append("pin_governance.recommendation_policy must be an object")
        recommendation = {}
    if recommendation.get("owner") != "general_office":
        errors.append("pin_governance.recommendation_policy.owner must be general_office")
    if recommendation.get("verifier") != "todo_read_only":
        errors.append("pin_governance.recommendation_policy.verifier must be todo_read_only")
    if recommendation.get("max_candidates") != 3:
        errors.append("pin_governance.recommendation_policy.max_candidates must be 3")
    if recommendation.get("max_pending_packs") != 1:
        errors.append("pin_governance.recommendation_policy.max_pending_packs must be 1")
    if recommendation.get("criteria") != PIN_CRITERIA:
        errors.append("pin_governance.recommendation_policy.criteria is invalid")
    if recommendation.get("default_exclusions") != PIN_DEFAULT_EXCLUSIONS:
        errors.append("pin_governance.recommendation_policy.default_exclusions is invalid")

    successor = pin.get("successor_inheritance")
    if not isinstance(successor, dict):
        errors.append("pin_governance.successor_inheritance must be an object")
        successor = {}
    for key in (
        "enabled", "exact_list_verification_required", "pin_before_takeover",
        "receipt_is_not_proof",
    ):
        if successor.get(key) is not True:
            errors.append(f"pin_governance.successor_inheritance.{key} must be true")
    if successor.get("replacement_policy") != "single_same_lineage_after_safe_handoff":
        errors.append("pin_governance.successor_inheritance.replacement_policy is invalid")

    grandmothered = pin.get("grandmothered_optional_chiefs")
    if not isinstance(grandmothered, list):
        errors.append("pin_governance.grandmothered_optional_chiefs must be an array")
        grandmothered = []
    grandmothered_ids: list[str] = []
    grandmothered_titles: list[str] = []
    for index, item in enumerate(grandmothered):
        label = f"pin_governance.grandmothered_optional_chiefs[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        title = item.get("title")
        thread_id = item.get("thread_id")
        if not isinstance(title, str) or not title:
            errors.append(f"{label}.title must be a non-empty string")
        else:
            grandmothered_titles.append(title)
        if not isinstance(thread_id, str) or not thread_id:
            errors.append(f"{label}.thread_id must be a non-empty string")
        else:
            grandmothered_ids.append(thread_id)
    if len(grandmothered_ids) != len(set(grandmothered_ids)):
        errors.append("pin_governance grandmothered thread IDs must be unique")
    if len(grandmothered_titles) != len(set(grandmothered_titles)):
        errors.append("pin_governance grandmothered titles must be unique")

    protected = _unique_string_list(
        pin.get("protected_manual_thread_ids"),
        "pin_governance.protected_manual_thread_ids", errors,
    )
    invalid = _unique_string_list(
        pin.get("invalid_successor_thread_ids"),
        "pin_governance.invalid_successor_thread_ids", errors,
    )
    eligible_ids = set(core_thread_ids) | set(grandmothered_ids)
    if eligible_ids.intersection(protected):
        errors.append("protected manual pins cannot duplicate Chief lineage IDs")
    if eligible_ids.intersection(invalid):
        errors.append("invalid successor IDs cannot duplicate eligible Chief lineage IDs")
    if set(protected).intersection(invalid):
        errors.append("protected manual pins cannot also be invalid successors")


def _validate_automation_inheritance(profile: dict[str, Any], errors: list[str]) -> None:
    section = _require_object(profile, "automation_inheritance", errors)
    _require_bool(section, "enabled", "automation_inheritance", errors)
    exact = {
        "scope": "bound_task_automations",
        "bundle_fields": AUTOMATION_BUNDLE_FIELDS,
        "rebind_before": AUTOMATION_REBIND_BEFORE,
        "reuse_existing": True,
        "missing_policy": "create_one_minimal_equivalent_within_existing_authorization",
        "preserve": AUTOMATION_PRESERVE,
        "duplicate_active_same_duty": "forbidden",
        "historical_repair": "remediate_without_unarchive_delete_or_duplicate",
    }
    for key, value in exact.items():
        if section.get(key) != value:
            errors.append(f"automation_inheritance.{key} is invalid")
    verification = section.get("verification")
    if not isinstance(verification, dict):
        errors.append("automation_inheritance.verification must be an object")
        verification = {}
    for key in (
        "live_evidence_required", "exact_target_status_schedule_required",
        "reference_or_receipt_is_not_proof",
    ):
        if verification.get(key) is not True:
            errors.append(f"automation_inheritance.verification.{key} must be true")
    gate = section.get("migration_gate")
    if not isinstance(gate, dict):
        errors.append("automation_inheritance.migration_gate must be an object")
        gate = {}
    gate_exact = {
        "automation_parity_required": True,
        "pin_parity_when_applicable": True,
        "bundle_parity_required": True,
        "failure_status": "MIGRATION_BLOCKED",
        "failure_record": "automation_rebind_failed",
        "keep_predecessor_active_unarchived": True,
    }
    for key, value in gate_exact.items():
        if gate.get(key) != value:
            errors.append(f"automation_inheritance.migration_gate.{key} is invalid")


def _validate_capability_discovery(profile: dict[str, Any], errors: list[str]) -> None:
    section = profile.get("project_start_capability_discovery")
    if section is None:
        return
    if not isinstance(section, dict):
        errors.append("project_start_capability_discovery must be an object")
        return
    _require_bool(
        section, "enabled", "project_start_capability_discovery", errors
    )
    legacy_exact = {
        "mode": "coverage_first",
        "timing": "before_production_execution",
        "search_surfaces": CAPABILITY_DISCOVERY_SURFACES,
        "evaluation_criteria": CAPABILITY_DISCOVERY_CRITERIA,
        "require_evidence_pack": True,
        "require_reuse_before_build": True,
        "testing_director_review": "required_for_test_capabilities",
        "acquisition_policy": "selected_fit_only_after_review",
        "cost_policy": "coverage_over_token_or_time_savings",
        "protected_actions": "separate_explicit_approval",
    }
    lifecycle_mode = bool(
        CAPABILITY_DISCOVERY_LIFECYCLE_ONLY_KEYS.intersection(section)
    )
    exact = dict(legacy_exact)
    if lifecycle_mode:
        exact.update(CAPABILITY_DISCOVERY_LIFECYCLE_EXACT)
        exact["search_surfaces"] = CAPABILITY_DISCOVERY_LIFECYCLE_SURFACES
    for key, value in exact.items():
        if section.get(key) != value:
            errors.append(f"project_start_capability_discovery.{key} is invalid")


def lifecycle_capability_discovery(enabled: bool = True) -> dict[str, Any]:
    """Return the complete lifecycle contract without mutating a legacy preset."""
    return {
        "enabled": enabled,
        "mode": "coverage_first",
        "timing": "before_production_execution",
        "search_surfaces": copy.deepcopy(CAPABILITY_DISCOVERY_LIFECYCLE_SURFACES),
        "evaluation_criteria": copy.deepcopy(CAPABILITY_DISCOVERY_CRITERIA),
        "require_evidence_pack": True,
        "require_reuse_before_build": True,
        "testing_director_review": "required_for_test_capabilities",
        "cost_policy": "coverage_over_token_or_time_savings",
        "protected_actions": "separate_explicit_approval",
        **copy.deepcopy(CAPABILITY_DISCOVERY_LIFECYCLE_EXACT),
    }


def capability_recommendation_pack_id(
    chief_id: str, trigger: str, evidence_identity: str
) -> str:
    """Bind a packet identity to its Chief, trigger, and frozen evidence."""
    for label, value in (
        ("chief_id", chief_id),
        ("trigger", trigger),
        ("evidence_identity", evidence_identity),
    ):
        if not isinstance(value, str) or not value.strip():
            raise PreferenceError(f"{label} must be a non-empty string")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", evidence_identity.strip()):
        raise PreferenceError("evidence_identity must be a fixed sha256 identity")
    material = json.dumps(
        [chief_id.strip(), trigger.strip(), evidence_identity.strip()],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"capability:{hashlib.sha256(material).hexdigest()}"


def _meaningful_capability_evidence(key: str, value: Any) -> bool:
    if value is None or isinstance(value, bool):
        return False
    if isinstance(value, str):
        normalized = value.strip()
        meaningful = bool(normalized) and normalized.lower() not in {
            "unknown", "n/a", "na", "none", "null", "tbd", "todo", "false",
        }
        if key == "source":
            return meaningful and (
                "://" in normalized or normalized.startswith("git@")
            )
        return meaningful
    if key in {"source", "fixed_version_or_revision"}:
        return False
    if isinstance(value, int):
        return True
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, list):
        return bool(value) and all(
            _meaningful_capability_evidence(key, item) for item in value
        )
    if isinstance(value, dict):
        return bool(value) and all(
            isinstance(item_key, str)
            and bool(item_key.strip())
            and _meaningful_capability_evidence(key, item_value)
            for item_key, item_value in value.items()
        )
    return False


def evaluate_capability_discovery(
    profile: dict[str, Any], event: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate one discovery trigger without acquiring or mutating anything."""
    errors = validate_preferences(profile)
    if errors:
        return {
            "status": "invalid_profile", "errors": errors,
            "mutation_performed": False, "operator_actionable_now": False,
        }
    if event.get("prior_operator_denial") is True:
        return {
            "status": "blocked", "reason": "prior_operator_denial",
            "mutation_performed": False, "operator_actionable_now": False,
        }
    section = profile.get("project_start_capability_discovery")
    if not isinstance(section, dict) or section.get("enabled") is not True:
        return {
            "status": "disabled", "mutation_performed": False,
            "operator_actionable_now": False,
        }

    lifecycle_mode = bool(
        CAPABILITY_DISCOVERY_LIFECYCLE_ONLY_KEYS.intersection(section)
    )
    lifecycle_status = event.get("lifecycle_status")
    if lifecycle_mode and lifecycle_status is None:
        return {
            "status": "evidence_required", "missing": ["lifecycle_status"],
            "mutation_performed": False, "operator_actionable_now": False,
        }
    if not lifecycle_mode and lifecycle_status is None:
        lifecycle_status = "active"
    if lifecycle_status in {"completed", "archived"}:
        return {
            "status": "excluded", "reason": lifecycle_status,
            "mutation_performed": False, "operator_actionable_now": False,
        }
    if lifecycle_status == "paused":
        return {
            "status": "deferred", "reason": "paused_until_resume",
            "mutation_performed": False, "operator_actionable_now": False,
        }
    if lifecycle_mode and lifecycle_status not in {"active", "unfinished"}:
        return {
            "status": "not_applicable", "reason": "invalid_lifecycle_status",
            "mutation_performed": False, "operator_actionable_now": False,
        }
    if lifecycle_mode and event.get("chief_registered") is not True:
        return {
            "status": "not_applicable", "reason": "unregistered_chief",
            "mutation_performed": False, "operator_actionable_now": False,
        }

    trigger = event.get("trigger")
    due_triggers = (
        CAPABILITY_DISCOVERY_TRIGGERS
        if lifecycle_mode
        else ["project_start", "before_production_execution"]
    )
    if trigger not in due_triggers:
        return {
            "status": "not_due",
            "mode": "lifecycle" if lifecycle_mode else "legacy_startup",
            "mutation_performed": False,
            "operator_actionable_now": False,
        }
    requested_action = event.get("requested_action")
    if lifecycle_mode and requested_action in CAPABILITY_DISCOVERY_PROHIBITED_ACTIONS:
        return {
            "status": "blocked",
            "reason": f"discover_only_forbids_{requested_action}",
            "operator_approval_required": True,
            "mutation_performed": False,
            "operator_actionable_now": False,
        }
    return {
        "status": "discovery_due",
        "mode": "lifecycle" if lifecycle_mode else "legacy_startup",
        "trigger": trigger,
        "acquisition_policy": section["acquisition_policy"],
        "max_parallel_scans": section.get("max_parallel_scans", 1),
        "allowed_actions": ["discover", "evaluate", "recommend"],
        "mutation_performed": False,
        "operator_actionable_now": False,
    }


def route_capability_recommendations(
    profile: dict[str, Any], packet: dict[str, Any]
) -> dict[str, Any]:
    """Deduplicate and route a lifecycle recommendation packet without a TODO write."""
    event_result = evaluate_capability_discovery(profile, packet)
    if event_result.get("status") != "discovery_due":
        return {**event_result, "operator_actionable_now": False}
    if event_result.get("mode") != "lifecycle":
        return {
            **event_result,
            "status": "legacy_evidence_only",
            "operator_actionable_now": False,
        }
    try:
        expected_pack_id = capability_recommendation_pack_id(
            packet.get("chief_id"), packet.get("trigger"),
            packet.get("evidence_identity"),
        )
    except PreferenceError:
        return {
            "status": "evidence_required",
            "missing": ["chief_id", "trigger", "evidence_identity"],
            "mutation_performed": False, "operator_actionable_now": False,
        }
    pack_id = packet.get("pack_id")
    if pack_id != expected_pack_id:
        return {
            "status": "evidence_required", "missing": ["bound_pack_id"],
            "expected_pack_id": expected_pack_id,
            "mutation_performed": False, "operator_actionable_now": False,
        }
    if pack_id in packet.get("existing_pack_ids", []):
        return {"status": "duplicate_suppressed", "pack_id": pack_id, "mutation_performed": False, "operator_actionable_now": False}
    if packet.get("routine_scan") is True:
        return {"status": "internal_evidence_only", "reason": "routine_scan", "candidates": [], "mutation_performed": False, "operator_actionable_now": False}

    candidates = packet.get("candidates", [])
    if not isinstance(candidates, list):
        return {"status": "evidence_required", "missing": ["candidates"], "mutation_performed": False, "operator_actionable_now": False}
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            rejected.append({"index": index, "reason": "candidate_not_object"})
            continue
        if candidate.get("decision") != "recommend" or candidate.get("material") is not True:
            rejected.append({"index": index, "reason": "rejected_or_not_material"})
            continue
        missing = [
            key for key in CAPABILITY_DISCOVERY_EVIDENCE
            if key not in candidate
            or not _meaningful_capability_evidence(key, candidate[key])
        ]
        if missing:
            rejected.append({"index": index, "reason": "evidence_incomplete", "missing": missing})
            continue
        accepted.append(copy.deepcopy(candidate))
    accepted = accepted[:3]
    if not accepted:
        return {
            "status": "internal_evidence_only",
            "pack_id": pack_id,
            "candidates": [],
            "rejected": rejected,
            "operator_actionable_now": False,
            "mutation_performed": False,
        }
    routes = []
    for candidate in accepted:
        if candidate.get("testing_related") is True:
            routes.append("testing_director")
        elif candidate.get("visual_direction") is True:
            routes.append("creative_director")
        else:
            routes.append("general_office")
    return {
        "status": "material_recommendation_ready",
        "pack_id": pack_id,
        "candidates": accepted,
        "routes": routes,
        "operator_actionable_now": False,
        "mutation_performed": False,
    }


def _validate_recommended_action_delegation(
    continuation: dict[str, Any], errors: list[str]
) -> None:
    section = continuation.get("recommended_action_delegation")
    if section is None:
        return
    if not isinstance(section, dict):
        errors.append(
            "governance_model.continuation_policy.recommended_action_delegation "
            "must be an object"
        )
        return
    label = "governance_model.continuation_policy.recommended_action_delegation"
    _require_bool(section, "enabled", label, errors)
    exact = {
        "authority_owner": "general_office",
        "decision_mode": "auto_authorize_single_recommended_bounded_action",
        "eligible_action_classes": RECOMMENDED_ACTION_CLASSES,
        "required_conditions": RECOMMENDED_ACTION_CONDITIONS,
        "prior_operator_denial_policy": "requires_explicit_operator_override",
        "audit_marker": "DELEGATED_RECOMMENDATION_EXECUTED",
        "operator_only_actions": RECOMMENDED_OPERATOR_ONLY_ACTIONS,
    }
    for key, value in exact.items():
        if section.get(key) != value:
            errors.append(f"{label}.{key} is invalid")


def _validate_approved_decision_relay(governance: dict[str, Any], errors: list[str]) -> None:
    """Keep schema-v1 profiles compatible while defaulting this relay off."""
    section = governance.get("approved_decision_relay")
    if section is None:
        return
    label = "governance_model.approved_decision_relay"
    if not isinstance(section, dict):
        errors.append(f"{label} must be an object")
        return
    _require_bool(section, "enabled", label, errors)
    for key, expected in APPROVED_DECISION_RELAY_EXACT.items():
        if key == "delivery_is_execution":
            if type(section.get(key)) is not bool or section.get(key) is not False:
                errors.append(f"{label}.{key} is invalid")
        elif section.get(key) != expected:
            errors.append(f"{label}.{key} is invalid")
    if section.get("enabled") is True and governance.get("enabled") is not True:
        errors.append("enabled approved_decision_relay requires enabled governance_model")


def validate_preferences(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        profile, _ = migrate_profile_input(profile)
    except LegacyTerminologyConflict as exc:
        return [str(exc)]
    if profile.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if profile.get("preset") not in {"core", "operator-controlled-bilingual", "custom"}:
        errors.append("preset is invalid")
    if profile.get("scope") not in {"global", "project"}:
        errors.append("scope must be global or project")
    if profile.get("report_review_mode", "exception_only") not in {
        "all_reports", "exception_only"
    }:
        errors.append("report_review_mode must be all_reports or exception_only")

    _validate_pin_governance(profile, errors)
    _validate_automation_inheritance(profile, errors)
    _validate_capability_discovery(profile, errors)

    governance = _require_object(profile, "governance_model", errors)
    _require_bool(governance, "enabled", "governance_model", errors)
    if governance.get("mode") != "chair_led_cabinet":
        errors.append("governance_model.mode must be chair_led_cabinet")
    if governance.get("operator_role") != "chair":
        errors.append("governance_model.operator_role must be chair")
    for key in ("general_office_title", "todo_title"):
        if not isinstance(governance.get(key), str) or not governance.get(key):
            errors.append(f"governance_model.{key} must be a non-empty string")
    office_thread = governance.get("general_office_thread_id")
    if office_thread is not None and not isinstance(office_thread, str):
        errors.append("governance_model.general_office_thread_id must be a string or null")
    if governance.get("enabled") is True and not office_thread:
        errors.append("enabled governance_model requires general_office_thread_id")
    if governance.get("direct_report_policy") != "chain_of_command":
        errors.append("governance_model.direct_report_policy must be chain_of_command")
    if governance.get("auditor_authority") != "evidence_only":
        errors.append("governance_model.auditor_authority must be evidence_only")
    if governance.get("partial_pause_policy") != "affected_surface_only":
        errors.append("governance_model.partial_pause_policy must be affected_surface_only")
    _validate_approved_decision_relay(governance, errors)
    continuation = governance.get("continuation_policy")
    if not isinstance(continuation, dict):
        errors.append("governance_model.continuation_policy must be an object")
        continuation = {}
    _require_bool(
        continuation,
        "enabled",
        "governance_model.continuation_policy",
        errors,
    )
    if continuation.get("enabled") is True and governance.get("enabled") is not True:
        errors.append("enabled continuation_policy requires enabled governance_model")
    if continuation.get("default_action") != "advance_best_safe_in_scope_path":
        errors.append(
            "governance_model.continuation_policy.default_action must be "
            "advance_best_safe_in_scope_path"
        )
    if continuation.get("stop_or_defer_is_operator_initiated") is not True:
        errors.append(
            "governance_model.continuation_policy.stop_or_defer_is_operator_initiated "
            "must be true"
        )
    if continuation.get("escalate_only_for") != ["new_permission", "new_chief"]:
        errors.append(
            "governance_model.continuation_policy.escalate_only_for must be "
            "[new_permission, new_chief]"
        )
    if continuation.get("ordinary_failure_policy") != (
        "continue_bounded_diagnosis_repair_and_verification"
    ):
        errors.append(
            "governance_model.continuation_policy.ordinary_failure_policy must be "
            "continue_bounded_diagnosis_repair_and_verification"
        )
    _validate_recommended_action_delegation(continuation, errors)
    autonomy = continuation.get("autonomy_policy")
    if autonomy is not None:
        if not isinstance(autonomy, dict):
            errors.append("governance_model.continuation_policy.autonomy_policy must be an object")
        else:
            for key, expected in AUTONOMY_POLICY_EXACT.items():
                if key == "enabled":
                    _require_bool(autonomy, key, "governance_model.continuation_policy.autonomy_policy", errors)
                elif key == "ordinary_repair_cycles":
                    if type(autonomy.get(key)) is not int or autonomy.get(key) != expected:
                        errors.append(f"governance_model.continuation_policy.autonomy_policy.{key} is invalid")
                elif key in {"approval_package_required", "operation_revalidation_required"}:
                    if type(autonomy.get(key)) is not bool or autonomy.get(key) is not expected:
                        errors.append(f"governance_model.continuation_policy.autonomy_policy.{key} is invalid")
                elif autonomy.get(key) != expected:
                    errors.append(f"governance_model.continuation_policy.autonomy_policy.{key} is invalid")
            if autonomy.get("enabled") is True and continuation.get("enabled") is not True:
                errors.append("enabled autonomy_policy requires enabled continuation_policy")

    visual = _require_object(profile, "visual_selection_gate", errors)
    _require_bool(visual, "enabled", "visual_selection_gate", errors)
    if not isinstance(visual.get("review_hub_title"), str) or not visual.get("review_hub_title"):
        errors.append("visual_selection_gate.review_hub_title must be a non-empty string")

    coaching = _require_object(profile, "american_english_coaching", errors)
    for key in ("enabled", "include_casual_chat", "written", "spoken", "idiom_notes"):
        _require_bool(coaching, key, "american_english_coaching", errors)

    audio = _require_object(profile, "audio_playback", errors)
    _require_bool(audio, "enabled", "audio_playback", errors)
    clips = audio.get("clips")
    if (
        not isinstance(clips, list)
        or not clips
        or not all(isinstance(item, str) and item in CLIP_KINDS for item in clips)
        or len(set(clips)) != len(clips)
    ):
        errors.append("audio_playback.clips must be unique written/spoken values")
    provider = audio.get("provider")
    if provider not in {"host_builtin", "auto", "macos_say"}:
        errors.append("audio_playback.provider must be host_builtin, auto, or macos_say")
    if audio.get("voice") is not None and not isinstance(audio.get("voice"), str):
        errors.append("audio_playback.voice must be a string or null")
    if audio.get("locale") != "en-US":
        errors.append("audio_playback.locale must be en-US")
    rate = audio.get("rate")
    if not isinstance(rate, int) or isinstance(rate, bool) or not 80 <= rate <= 350:
        errors.append("audio_playback.rate must be an integer from 80 through 350")
    storage_root = audio.get("storage_root")
    if storage_root is not None:
        if not isinstance(storage_root, str) or not Path(storage_root).expanduser().is_absolute():
            errors.append("audio_playback.storage_root must be an absolute path or null")
    if audio.get("enabled") is True and provider in {"auto", "macos_say"} and storage_root is None:
        errors.append("enabled offline audio_playback requires storage_root")
    if provider == "host_builtin" and storage_root is not None:
        errors.append("host_builtin audio_playback requires storage_root to be null")
    if audio.get("unavailable_behavior") != "text_only":
        errors.append("audio_playback.unavailable_behavior must be text_only")

    salutation = _require_object(profile, "operator_salutation", errors)
    _require_bool(salutation, "enabled", "operator_salutation", errors)
    salutation_value = salutation.get("value")
    if salutation_value is not None and not isinstance(salutation_value, str):
        errors.append("operator_salutation.value must be a string or null")
    if salutation.get("enabled") is True and not salutation_value:
        errors.append("enabled operator_salutation requires a non-empty value")

    paused = _require_object(profile, "paused_title_prefix", errors)
    _require_bool(paused, "enabled", "paused_title_prefix", errors)
    if not isinstance(paused.get("value"), str) or not paused.get("value"):
        errors.append("paused_title_prefix.value must be a non-empty string")

    reminders = _require_object(profile, "reminders", errors)
    _require_bool(reminders, "enabled", "reminders", errors)
    if not isinstance(reminders.get("timezone"), str) or not reminders.get("timezone"):
        errors.append("reminders.timezone must be a non-empty string")
    window = reminders.get("daytime_window")
    if not isinstance(window, dict):
        errors.append("reminders.daytime_window must be an object")
        window = {}
    for key in ("start", "end"):
        if not isinstance(window.get(key), str) or not TIME_PATTERN.fullmatch(window.get(key, "")):
            errors.append(f"reminders.daytime_window.{key} must be HH:MM")
    interval = window.get("interval_minutes")
    if not isinstance(interval, int) or isinstance(interval, bool) or interval < 1:
        errors.append("reminders.daytime_window.interval_minutes must be positive")
    for key in ("include_start", "include_end"):
        _require_bool(window, key, "reminders.daytime_window", errors)
    additional = reminders.get("additional_times")
    if not isinstance(additional, list) or not all(
        isinstance(item, str) and TIME_PATTERN.fullmatch(item) for item in additional
    ):
        errors.append("reminders.additional_times must contain HH:MM values")
    return errors


def require_valid(profile: dict[str, Any]) -> None:
    errors = validate_preferences(profile)
    if errors:
        raise PreferenceError("; ".join(errors))


def _pin_signal_score(signals: object, label: str) -> float:
    if not isinstance(signals, dict) or set(signals) != set(PIN_CRITERIA):
        raise PreferenceError(f"{label}.signals must contain every recommendation criterion")
    for key, value in signals.items():
        if (
            not isinstance(value, (int, float))
            or isinstance(value, bool)
            or not 0 <= value <= 1
        ):
            raise PreferenceError(f"{label}.signals.{key} must be from 0 through 1")
    benefit = sum(float(signals[key]) for key in PIN_CRITERIA if key != "sidebar_cost")
    return benefit - float(signals["sidebar_cost"])


def recommend_optional_chief_pins(
    profile: dict[str, Any], snapshot: dict[str, Any]
) -> dict[str, Any]:
    """Return a read-only recommendation packet; never pin, unpin, or create a task."""
    try:
        profile, _ = migrate_profile_input(profile)
        snapshot, _ = migrate_pin_snapshot_input(snapshot)
    except LegacyTerminologyConflict as exc:
        raise PreferenceError(str(exc)) from exc
    require_valid(profile)
    pin = profile["pin_governance"]
    if pin["enabled"] is not True:
        return {
            "status": "disabled",
            "candidates": [],
            "paired_replacement": None,
            "operator_approval_required": True,
            "mutation_performed": False,
        }
    if not isinstance(snapshot, dict):
        raise PreferenceError("pin snapshot must be an object")
    observed_capacity = snapshot.get("observed_capacity")
    if (
        not isinstance(observed_capacity, int)
        or isinstance(observed_capacity, bool)
        or observed_capacity < 1
    ):
        raise PreferenceError("pin snapshot observed_capacity must be positive")
    pending_packs = snapshot.get("pending_packs")
    if (
        not isinstance(pending_packs, int)
        or isinstance(pending_packs, bool)
        or pending_packs < 0
        or pending_packs > 1
    ):
        raise PreferenceError("pin snapshot pending_packs must be 0 or 1")
    candidates = snapshot.get("candidates")
    pinned = snapshot.get("pinned_threads")
    if not isinstance(candidates, list) or not isinstance(pinned, list):
        raise PreferenceError("pin snapshot candidates and pinned_threads must be arrays")

    protected_ids = set(pin["protected_manual_thread_ids"])
    invalid_successor_ids = set(pin["invalid_successor_thread_ids"])
    core_ids = {
        item["thread_id"] for item in pin["mandatory_core_roles"] if item["thread_id"]
    }
    pinned_ids: set[str] = set()
    replaceable: list[dict[str, Any]] = []
    optional_pinned = 0
    for index, item in enumerate(pinned):
        label = f"pin snapshot pinned_threads[{index}]"
        if not isinstance(item, dict):
            raise PreferenceError(f"{label} must be an object")
        thread_id = item.get("thread_id")
        pin_class = item.get("pin_class")
        if not isinstance(thread_id, str) or not thread_id:
            raise PreferenceError(f"{label}.thread_id must be a non-empty string")
        if thread_id in pinned_ids:
            raise PreferenceError("pin snapshot pinned thread IDs must be unique")
        pinned_ids.add(thread_id)
        if pin_class not in {
            "mandatory_core", "approved_optional", "grandmothered_optional",
            "manual_non_chief",
        }:
            raise PreferenceError(f"{label}.pin_class is invalid")
        if pin_class in {"approved_optional", "grandmothered_optional"}:
            optional_pinned += 1
            score = _pin_signal_score(item.get("signals"), label)
            if thread_id not in protected_ids and thread_id not in core_ids:
                replaceable.append(
                    {"thread_id": thread_id, "title": item.get("title"), "score": score}
                )
        if pin_class == "manual_non_chief":
            protected_ids.add(thread_id)

    excluded: list[dict[str, str]] = []
    eligible: list[dict[str, Any]] = []
    candidate_id_counts: dict[str, int] = {}
    for item in candidates:
        if isinstance(item, dict) and isinstance(item.get("thread_id"), str):
            thread_id = item["thread_id"]
            candidate_id_counts[thread_id] = candidate_id_counts.get(thread_id, 0) + 1
    for index, item in enumerate(candidates):
        label = f"pin snapshot candidates[{index}]"
        if not isinstance(item, dict):
            raise PreferenceError(f"{label} must be an object")
        thread_id = item.get("thread_id")
        title = item.get("title")
        lifecycle_status = item.get("lifecycle_status")
        work_kind = item.get("work_kind")
        if not isinstance(thread_id, str) or not thread_id:
            raise PreferenceError(f"{label}.thread_id must be a non-empty string")
        if not isinstance(title, str) or not title:
            raise PreferenceError(f"{label}.title must be a non-empty string")
        reasons: list[str] = []
        if candidate_id_counts.get(thread_id, 0) > 1 or thread_id in pinned_ids:
            reasons.append("duplication")
        if thread_id in invalid_successor_ids:
            reasons.append("invalid_lineage")
        if lifecycle_status in {"paused", "completed", "superseded", "migration_cancelled"}:
            reasons.append(lifecycle_status)
        elif lifecycle_status != "active":
            raise PreferenceError(f"{label}.lifecycle_status is invalid")
        if work_kind in {"routine_push", "meeting_summary", "report_only", "process_only"}:
            reasons.append(work_kind)
        elif work_kind != "product_delivery":
            raise PreferenceError(f"{label}.work_kind is invalid")
        for key, reason in (
            ("current", "not_current"),
            ("evidence_fresh", "stale_evidence"),
            ("lineage_valid", "invalid_lineage"),
        ):
            if not isinstance(item.get(key), bool):
                raise PreferenceError(f"{label}.{key} must be a boolean")
            if item[key] is False:
                reasons.append(reason)
        score = _pin_signal_score(item.get("signals"), label)
        if reasons:
            excluded.append({"thread_id": thread_id, "reason": ",".join(reasons)})
        else:
            eligible.append({"thread_id": thread_id, "title": title, "score": score})

    eligible.sort(key=lambda item: (-item["score"], item["title"], item["thread_id"]))
    maximum = pin["recommendation_policy"]["max_candidates"]
    recommended = eligible[:maximum]
    base = {
        "candidates": recommended,
        "excluded": excluded,
        "paired_replacement": None,
        "protected_manual_thread_ids": sorted(protected_ids),
        "todo_checks": [
            "identity", "currentness", "duplication", "evidence_freshness",
            "capacity", "lineage",
        ],
        "operator_approval_required": True,
        "mutation_performed": False,
    }
    if pending_packs == 1:
        return {"status": "pending_pack_exists", **base, "candidates": []}
    if not recommended:
        return {"status": "no_eligible_candidate", **base}

    optional_limit = pin["optional_chief_slots"]["limit"]
    has_capacity = len(pinned_ids) < observed_capacity and optional_pinned < optional_limit
    if has_capacity:
        available = min(
            observed_capacity - len(pinned_ids),
            optional_limit - optional_pinned,
            maximum,
        )
        return {"status": "recommendation_ready", **base, "candidates": recommended[:available]}

    replaceable.sort(key=lambda item: (item["score"], item.get("title") or "", item["thread_id"]))
    if replaceable:
        return {
            "status": "paired_replacement_recommendation",
            **base,
            "candidates": recommended[:1],
            "paired_replacement": {
                "add_thread_id": recommended[0]["thread_id"],
                "remove_thread_id": replaceable[0]["thread_id"],
                "automatic_eviction": False,
            },
        }
    return {"status": "capacity_full_no_safe_replacement", **base, "candidates": []}


def evaluate_recommended_action(
    profile: dict[str, Any], action: dict[str, Any]
) -> dict[str, Any]:
    """Evaluate standing delegation without executing or retrying an action."""
    require_valid(profile)
    continuation = profile["governance_model"]["continuation_policy"]
    policy = continuation.get("recommended_action_delegation")
    base = {
        "delegated": False,
        "operator_actionable_now": False,
        "audit_marker": None,
        "automatic_rerun": False,
    }
    if not isinstance(policy, dict) or policy.get("enabled") is not True:
        return {"status": "disabled", **base}
    if not isinstance(action, dict):
        raise PreferenceError("recommended action must be an object")

    stable_id = action.get("stable_id")
    if not isinstance(stable_id, str) or not stable_id.strip():
        return {"status": "evidence_required", "missing": ["stable_id"], **base}
    state = action.get("execution_state", "ready")
    if state in {"failed", "drifted", "out_of_scope"}:
        return {"status": "stopped", "reason": state, **base}
    if state != "ready":
        raise PreferenceError("recommended action execution_state is invalid")

    operator_only = action.get("operator_only_action")
    if operator_only is not None and operator_only not in RECOMMENDED_OPERATOR_ONLY_ACTIONS:
        raise PreferenceError("recommended action operator_only_action is invalid")

    readiness_checks = {
        "single_clear_recommendation": action.get("recommendation_count") == 1,
        "evidence_complete": action.get("evidence_complete") is True,
        "exact_identity_and_surface": action.get("exact_identity_and_surface") is True,
        "independent_verification_when_applicable": (
            action.get("independent_verification_when_applicable") is True
        ),
        "no_unresolved_safety_dissent": (
            action.get("no_unresolved_safety_dissent") is True
        ),
        "stop_and_rollback_defined": action.get("stop_and_rollback_defined") is True,
    }
    readiness_missing = [key for key, passed in readiness_checks.items() if not passed]
    if readiness_missing:
        return {
            "status": "evidence_required",
            "missing": sorted(readiness_missing),
            "reserved_action": operator_only,
            **base,
        }

    reserved_reason = operator_only
    if action.get("prior_operator_denial") is True:
        reserved_reason = "override_prior_explicit_operator_denial"
    for key, reason in (
        ("nonproduction", "release_deploy_production_or_rollback"),
        ("no_real_customer_or_personal_data", "real_user_or_production_data_deletion"),
        ("no_credentials_or_secrets", "credentials_secrets_real_identity_or_sensitive_data"),
    ):
        if action.get(key) is False:
            reserved_reason = reason
    if action.get("external_send") is True:
        reserved_reason = "external_communication_new_collaborator_or_public_visibility"
    if action.get("recursive") is True or action.get("uses_glob") is True:
        reserved_reason = "recursive_broad_or_irreversible_deletion"
    if action.get("prior_operator_denial") is True:
        reserved_reason = "override_prior_explicit_operator_denial"
    if reserved_reason is not None:
        return {
            "status": "operator_only",
            "reason": reserved_reason,
            **base,
            "operator_actionable_now": True,
        }

    action_class = action.get("action_class")
    if action_class not in RECOMMENDED_ACTION_CLASSES:
        return {
            "status": "operator_only",
            "reason": "ineligible_action_class",
            **base,
            "operator_actionable_now": True,
        }

    missing: list[str] = []
    delegation_checks = {
        "nonproduction": action.get("nonproduction") is True,
        "no_real_customer_or_personal_data": (
            action.get("no_real_customer_or_personal_data") is True
        ),
        "no_credentials_or_secrets": action.get("no_credentials_or_secrets") is True,
        "no_external_send": action.get("external_send") is False,
    }
    missing.extend(key for key, passed in delegation_checks.items() if not passed)

    if action_class == "exact_task_owned_temp_cleanup":
        sha256 = action.get("sha256")
        path = action.get("path")
        checks = {
            "absolute_exact_path": isinstance(path, str)
            and bool(path)
            and Path(path).is_absolute(),
            "regular_file": action.get("file_type") == "regular_file",
            "fresh_size": isinstance(action.get("size_bytes"), int)
            and not isinstance(action.get("size_bytes"), bool)
            and action.get("size_bytes") >= 0,
            "fresh_sha256": isinstance(sha256, str)
            and re.fullmatch(r"[0-9a-f]{64}", sha256) is not None,
            "non_symlink": action.get("is_symlink") is False,
            "no_symlink_follow": action.get("follow_symlinks") is False,
            "no_glob": action.get("uses_glob") is False,
            "non_recursive": action.get("recursive") is False,
            "task_owned": action.get("task_owned") is True,
            "temporary": action.get("temporary") is True,
        }
        missing.extend(key for key, passed in checks.items() if not passed)
    elif action_class == "metadata_only_allowlisted_read":
        allowlist = action.get("read_allowlist")
        checks = {
            "exact_target": isinstance(action.get("target"), str)
            and bool(action.get("target")),
            "fixed_read_allowlist": isinstance(allowlist, list)
            and bool(allowlist)
            and all(isinstance(item, str) and item for item in allowlist),
            "positive_max_bytes": isinstance(action.get("max_bytes"), int)
            and not isinstance(action.get("max_bytes"), bool)
            and action.get("max_bytes") > 0,
            "positive_timeout_seconds": isinstance(action.get("timeout_seconds"), int)
            and not isinstance(action.get("timeout_seconds"), bool)
            and action.get("timeout_seconds") > 0,
            "read_only": action.get("read_only") is True,
            "no_write": action.get("write_allowed") is False,
            "empty_write_roots": action.get("write_roots") == [],
            "tokens_not_persisted": action.get("tokens_persisted") is False,
            "exact_stop_condition": isinstance(action.get("stop_condition"), str)
            and bool(action.get("stop_condition")),
            "class_independent_verification": (
                action.get("class_independent_verification") is True
            ),
        }
        missing.extend(key for key, passed in checks.items() if not passed)
    elif action_class == "fixed_sha256_one_shot_nonproduction_execution":
        sha256 = action.get("sha256")
        io_allowlist = action.get("io_allowlist")
        checks = {
            "fixed_sha256": isinstance(sha256, str)
            and re.fullmatch(r"[0-9a-f]{64}", sha256) is not None,
            "one_shot": action.get("one_shot") is True,
            "no_overwrite": action.get("overwrite") is False,
            "io_allowlist": isinstance(io_allowlist, list)
            and bool(io_allowlist)
            and all(isinstance(item, str) and item for item in io_allowlist),
            "not_previously_run": action.get("execution_count") == 0,
            "no_automatic_rerun": action.get("automatic_rerun_requested") is False,
        }
        missing.extend(key for key, passed in checks.items() if not passed)
    elif action_class == "disposable_local_test_stop_rollback":
        target = action.get("disposable_target")
        io_allowlist = action.get("io_allowlist")
        rollback_steps = action.get("rollback_steps")
        checks = {
            "absolute_disposable_target": isinstance(target, str)
            and bool(target)
            and Path(target).is_absolute(),
            "target_is_disposable": action.get("target_is_disposable") is True,
            "fixed_io_allowlist": isinstance(io_allowlist, list)
            and bool(io_allowlist)
            and all(isinstance(item, str) and item for item in io_allowlist),
            "positive_timeout_seconds": isinstance(action.get("timeout_seconds"), int)
            and not isinstance(action.get("timeout_seconds"), bool)
            and action.get("timeout_seconds") > 0,
            "exact_stop_condition": isinstance(action.get("stop_condition"), str)
            and bool(action.get("stop_condition")),
            "rollback_steps": isinstance(rollback_steps, list)
            and bool(rollback_steps)
            and all(isinstance(item, str) and item for item in rollback_steps),
            "single_run": action.get("max_runs") == 1,
            "not_previously_run": action.get("execution_count") == 0,
            "no_automatic_rerun": action.get("automatic_rerun_requested") is False,
        }
        missing.extend(key for key, passed in checks.items() if not passed)
    elif action_class == "bounded_repair_recheck_without_scope_expansion":
        write_surface = action.get("existing_write_surface")
        candidate_sha256 = action.get("candidate_sha256")
        checks = {
            "frozen_candidate_sha256": isinstance(candidate_sha256, str)
            and re.fullmatch(r"[0-9a-f]{64}", candidate_sha256) is not None,
            "exact_repair_target": isinstance(action.get("repair_target"), str)
            and bool(action.get("repair_target")),
            "existing_write_owner": isinstance(action.get("existing_write_owner"), str)
            and bool(action.get("existing_write_owner")),
            "existing_write_surface": isinstance(write_surface, list)
            and bool(write_surface)
            and all(isinstance(item, str) and item for item in write_surface)
            and len(write_surface) == len(set(write_surface)),
            "unique_repair_surface": action.get("repair_surface_unique") is True,
            "no_write_owner_conflict": action.get("write_owner_conflict") is False,
            "no_scope_expansion": action.get("no_scope_expansion") is True,
            "single_repair_attempt": action.get("max_repair_attempts") == 1,
            "single_recheck": action.get("max_rechecks") == 1,
            "repair_not_started": action.get("repair_attempts_completed") == 0,
            "recheck_not_started": action.get("rechecks_completed") == 0,
            "no_automatic_rerun": action.get("automatic_rerun_requested") is False,
            "failure_stops": action.get("failure_stop") is True,
        }
        missing.extend(key for key, passed in checks.items() if not passed)
    if missing:
        return {"status": "evidence_required", "missing": sorted(set(missing)), **base}

    marker = f"{policy['audit_marker']}: {stable_id}"
    return {
        "status": "delegated",
        **base,
        "delegated": True,
        "audit_marker": marker,
    }


def evaluate_approved_decision_relay(
    profile: dict[str, Any], decision: dict[str, Any], registry: dict[str, Any]
) -> dict[str, Any]:
    """Validate a single TODO relay without sending, approving, or retrying it."""
    require_valid(profile)
    policy = profile["governance_model"].get("approved_decision_relay")
    base = {"delivery_performed": False, "audit_required": False, "operator_actionable_now": False}
    if not isinstance(policy, dict) or policy.get("enabled") is not True:
        return {"status": "disabled", **base}
    if not isinstance(decision, dict) or not isinstance(registry, dict):
        raise PreferenceError("decision relay and registry must be objects")
    required = {"stable_id", "original_words", "approved", "kind", "source_chief_id", "current", "delivered", "delivery_failed"}
    if set(decision) != required:
        return {"status": "evidence_required", "missing": ["exact_relay_record"], **base}
    if type(decision["delivered"]) is not bool or type(decision["delivery_failed"]) is not bool:
        return {"status": "evidence_required", "missing": ["delivery_state_booleans"], **base}
    if decision["kind"] == "visual_selection":
        return {"status": "creative_director_only", **base}
    if decision["kind"] != "nonvisual" or decision["approved"] is not True or decision["current"] is not True:
        return {"status": "not_approved_current_nonvisual", **base}
    if not isinstance(decision["stable_id"], str) or not decision["stable_id"].strip() or not isinstance(decision["original_words"], str) or not decision["original_words"].strip() or not isinstance(decision["source_chief_id"], str) or not decision["source_chief_id"].strip():
        return {"status": "evidence_required", "missing": ["stable_id_original_words_source_chief"], **base}
    tasks = registry.get("tasks")
    if not isinstance(tasks, list):
        return {"status": "evidence_required", "missing": ["registry_tasks"], **base}
    matches = [task for task in tasks if isinstance(task, dict) and task.get("task_id") == decision["source_chief_id"] and task.get("status") in {"queued", "running", "needs_attention"}]
    if len(matches) != 1:
        return {"status": "source_chief_not_unique_current", **base}
    if decision["delivered"] is True:
        return {"status": "duplicate_suppressed", **base}
    if decision["delivery_failed"] is True:
        return {"status": "delivery_failed_recorded", **base, "audit_required": True}
    return {
        "status": "todo_direct_relay_intent",
        "relay": {"stable_id": decision["stable_id"], "original_words": decision["original_words"], "target_chief_id": decision["source_chief_id"]},
        **base,
        "audit_required": True,
    }


def filter_operator_todo_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return only currently actionable items from the two authoritative hubs."""
    if not isinstance(items, list):
        raise PreferenceError("TODO items must be an array")
    excluded_states = {"delegated", "resolved", "evidence_gathering"}
    excluded_kinds = {
        "routine_report", "ordinary_failure", "internal_retry", "ordinary_test_result",
        "non_authoritative_copy",
    }
    actionable: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise PreferenceError(f"TODO items[{index}] must be an object")
        if item.get("operator_actionable_now") is not True:
            continue
        if (
            item.get("evidence_complete") is not True
            or item.get("exact_identity_and_surface") is not True
            or item.get("no_unresolved_safety_dissent") is not True
        ):
            continue
        if item.get("authoritative_hub") not in {"general_office", "creative_director"}:
            continue
        if item.get("state") in excluded_states or item.get("kind") in excluded_kinds:
            continue
        if item.get("entry_available") is not True:
            continue
        if item.get("testing_required") is True and item.get("testing_gate") != "exact_pass":
            continue
        if item.get("kind") == "visual_selection" and (
            item.get("authoritative_hub") != "creative_director"
            or item.get("clickable_entry") is not True
            or item.get("candidate_hash_frozen") is not True
            or item.get("testing_gate") != "exact_pass"
        ):
            continue
        actionable.append(copy.deepcopy(item))
    return actionable


def atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink() or path.parent.is_symlink():
        raise PreferenceError(f"refusing to write through a symlink: {path}")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def atomic_write_json(path: Path, profile: dict[str, Any]) -> None:
    try:
        profile, _ = migrate_profile_input(profile)
    except LegacyTerminologyConflict as exc:
        raise PreferenceError(str(exc)) from exc
    require_valid(profile)
    atomic_write_text(path, json.dumps(profile, ensure_ascii=False, indent=2) + "\n")


def managed_agents_block(profile_path: Path, renderer_path: Path) -> str:
    return f"""{MANAGED_START}
## Optional Chief of Staff operator preferences

- Before a complete user-facing reply, read `{profile_path}` when it exists and apply only policies whose `enabled` value is true. Missing or invalid profiles disable optional behavior; they do not change core safety or approval rules.
- If `operator_salutation.enabled` is true, use its configured value unless the operator explicitly overrides it in the current conversation.
- Name every durable Chief task with the exact prefix `Chief of `. The configured general-office and TODO tasks plus the non-Chief context migration monitor are title-prefix exceptions. Other non-Chief durable roles keep the `Role｜Work outcome` convention. Treat a user-supplied title as content guidance, not permission to drop the Chief prefix unless it names one of those registered exceptions.
- Apply `report_review_mode`. In `exception_only`, the project Chief reviews routine child progress and final handoffs against their contracts without asking the operator. Escalate only goal confirmation, material product choices, visual choices through the Creative Director, protected actions, safety/security, ownership or scope conflicts, failed or unverifiable work, depth expansion, and final project completion.
- If `governance_model.enabled` is true, treat the operator as chair: project Chiefs own routine administration, auditors have evidence-only authority, roles follow the registered chain of command, and an unresolved decision freezes only its affected write surface. Route non-visual statutory exceptions only to the configured general-office task as `CHAIR_BRIEF_READY`; only that task may emit the operator-facing `USER_ACTION_REQUIRED`. TODO scans only the general office and Creative Director.
- For recurring Testing or Creative execution, each Director must first reuse registered durable subordinate roles by registry ID, owner, and handoff; split independent lanes only when workload materially benefits. The Testing Director keeps sole quality-gate authority and the Creative Director keeps sole visual intake/selection authority. Create a durable subordinate only within existing authorization after duplicate-role and runtime-availability checks; temporary subagents never substitute for those long-running execution roles. If the runtime cannot delegate, record the limitation without claiming delegation occurred.
- Apply `pin_governance` narrowly. Ordinary Chiefs default unpinned, and their unpinned state is not a failure. Mandatory pins are limited to the configured general office, TODO, Creative Director, context migration monitor, and their valid successors. The Testing Director is an ordinary, default-unpinned, coordination-only evidence role and occupies neither a mandatory pin nor an optional product slot. Reuse the registered Testing Director for applicable independent quality evidence and the registered Creative Director for visual review; the source Chief supplies the frozen candidate, owner, and handoff, while each hub retains its independent boundary. Do not create duplicate Chiefs or substitute temporary subagents for those durable hubs; keep small checks local unless independence is materially useful. An optional product Chief may be pinned, created for pinning, unpinned, or replaced only after a general-office recommendation and the operator's explicit approval; pin approval never confirms the project goal or authorizes engineering, design, production, or bypass of the Product Manager discovery gate.
- The general office recommends at most three candidates in one pending pack. TODO is read-only and checks identity, currentness, duplication, evidence freshness, observed capacity, and lineage. Preserve manual non-Chief pins. At full capacity, produce only a paired replacement recommendation; never evict automatically. Exclude paused, completed, superseded, migration-cancelled, routine-push, meeting-summary, report-only, and process-only Chiefs by default. A `pinned: true` receipt is not proof; fresh `list_threads` exact-ID presence is required. Only mandatory or operator-approved lineages may use the safe-handoff single-replacement successor path.
- If `automation_inheritance.enabled` is true, inventory every automation bound to a migrating task with exact ID, name, kind, target task ID, status, schedule, prompt SHA-256, and notification policy. Before takeover, authority switching, or predecessor archival, reuse and rebind each automation to the exact successor task ID. Only when live evidence proves the old automation is absent may one minimal equivalent be created within existing authorization. Preserve schedule, prompt semantics, notification policy, and scope; forbid duplicate active same-duty automations.
- Automation references and update receipts are not proof. Require a fresh live automation view proving exact target, status, and schedule. Missing or mismatched automation parity records `automation_rebind_failed`, returns `MIGRATION_BLOCKED`, and keeps the predecessor active and unarchived. Takeover requires bundle parity, automation parity, and pin parity when applicable. Historical repair never unarchives or deletes a predecessor and never creates duplicate tasks or automations.
- For context capture, automatically continue only exact source-session-change and non-overwriting migration-number collisions. Allow at most one atomic build+verify per source-task safe boundary, fresh-check the newest nonzero usage/threshold/write safety, use the next unused monotonic number, and never overwrite/delete an older bundle or create a successor before a valid bundle. Repeated transient failures enter Chief-owned read-only diagnosis/backoff without `USER_ACTION_REQUIRED`; permission, storage, worktree, validation, automation, pin, and parity failures keep their actual gates.
- If `project_start_capability_discovery.enabled` is true, treat the key as schema-version-1 compatible. A legacy section without lifecycle fields retains the project-start scan and pre-production stack confirmation. A complete lifecycle section applies to all registered Chiefs at project start, phase/stack changes, repeated manual work, blockers/failures, before custom build, and before production execution. It is discover/evaluate/recommend only: do not install, pull, download, enable, connect accounts, add dependencies, pay, contact outsiders, send externally, mutate a project, or use a candidate in production without separate explicit approval. Use at most two scans, one deduplicated material pack, and three fixed-version candidates per trigger; keep no-result/all-reject/routine scans internal. Defer paused work, exclude completed/archived work, prefer project-local future adoption, route testing candidates first to the Testing Director, and keep visual direction with the Creative Director.
- Keep project runtime paths portable. Resolve a caller-selected project-specific environment override when present, then the Git root, then project markers upward from the script/configuration location, then the current project directory. The override is optional. Active state uses a stable `root_id` and project-relative POSIX paths; reject absolute project input, parent traversal, drive syntax, and symlink escape. Register external tools/materials by exact identity, path, permissions, and authorization without making them the project root. Preserve historical absolute-path evidence unchanged but exclude it from active root resolution; portable derivatives use a new hash and `derived_from`. Never default to a fixed volume, user home, temporary directory, machine username, or prior-device path.
- If `governance_model.continuation_policy.enabled` is true, every project Chief must select and execute the strongest evidence-backed safe in-scope continuation without asking the operator. Do not present stopping, preserving a failed state, or delaying as peer options while a safe continuation exists; the operator will initiate those choices when wanted. Escalate only when continuing itself requires a new permission or creation of a new Chief. An ordinary failure remains Chief-owned while another bounded safe diagnostic, repair, or verification path exists. This policy does not authorize protected actions, bypass the Creative Director visual gate, or conceal safety/security evidence; those constraints determine whether a path is safe and already authorized.
- If `governance_model.continuation_policy.autonomy_policy.enabled` is true, start a goal with one conditional approval package covering goal, surfaces, action classes, external targets, data class, finite resources, action-time revalidation, stop/rollback, and deferred final decisions. Recheck each action. New permissions, real data, credentials/secrets, production, release/deploy, payment, external send, and platform safety refusals remain separate stops. Use native clickable questions for missing material choices when available; a recommendation or silence is not approval.
- A newly recorded `preparation` must be exactly one of `rename_or_move_only`, `packaging_path_correction`, or `material_evidence_completion`, with an immutable retained `semantic_invariance_evidence_ref` plus SHA-256 evidence bound to its event ID, scope, and class before journal mutation. It does not debit a candidate-defect cycle; a behavior or security correction remains an exact candidate defect. Legacy retained records may replay without being reclassified, and no preparation changes prior stops, permissions, or consumed budgets.
- Only if `governance_model.approved_decision_relay.enabled` is true, TODO may relay an already-approved nonvisual operator decision once by stable ID and exact original wording directly to its one registered current source Chief, with mandatory asynchronous nonblocking General Office audit. TODO has transport authority only: it cannot approve or change business approval state. Unknown/stale/duplicate/delivery-failed IDs retain evidence without blind resend or a tool fallback; delivery/ACK is not execution or Testing evidence. Initial permission requests remain General-Office-only; visual decisions remain Creative-Director-only.
- Legacy repair limits remain unchanged. Under enabled autonomy policy, a genuine phase covered by the original conditional package may renew only its phase-local defect allowance and supersede only recorded numerical local-preparation limits; permission, safety, denial, paused, real-data, production, and external stops remain. Native clickable questions collect missing material choices when supported; they never bypass platform permission or safety limits.
- A continuous execution exception is never implied by this preference: it needs one exact approved package bound to existing plan, registry, approval, retry, and delivery-ledger records. Preserve explicit one-shot, denial, paused/archive, finite resource, independent-review, and protected-action stops; a host must only return a bounded local intent and never send, wake, or grant access itself.
- If `governance_model.continuation_policy.recommended_action_delegation.enabled` is true, the general office directly standing-delegates one evidence-complete, fixed-surface, nonproduction action from the exact allowlist and records `DELEGATED_RECOMMENDATION_EXECUTED: <stable_id>` for the source Chief. Require explicit `external_send=false` plus the selected class's exact allowlist, bounds, ownership/read-only, stop/rollback, and one-shot or one-repair-cycle evidence before delegation. Do not emit `USER_ACTION_REQUIRED`, a suggested reply, or a TODO item for delegated work. Prior explicit operator denial and every configured operator-only action remain reserved; ambiguity, incomplete evidence, unresolved safety dissent, failure, drift, or scope expansion stops delegation and never auto-reruns.
- TODO includes only `operator_actionable_now=true` records from the authoritative general-office or Creative Director hub after evidence completeness, exact identity/surface, and absence of unresolved safety dissent are present. Exclude delegated/resolved work, evidence gathering, unavailable entries, routine reports, ordinary failures, internal retries, ordinary test results, and non-authoritative copies. A Creative Director visual item is actionable only when its clickable entry is available, its candidate hash is frozen, and Testing passed that exact candidate.
- If `visual_selection_gate.enabled` is true, require clickable non-final previews and the operator's explicit selection before final visual implementation. Route every visual packet only to the configured `Chief of Creative Direction｜创意总监` task; do not duplicate it to the general Chief task, project tasks, roles, or TODO. If unanswered, only that Creative Director task remains the authoritative waiting item for the TODO scanner.
- If `american_english_coaching.enabled` is true, append its configured written, spoken, and idiom sections. Include casual conversation only when `include_casual_chat` is true.
- If audio is enabled with `provider: host_builtin`, keep the English text available for the host's built-in voice/read-aloud control; generate no files and do not claim autoplay or per-sentence native controls. For `auto` or `macos_say`, render each enabled written/spoken sentence with `{renderer_path}` and attach the returned absolute `.m4a` path separately. If rendering returns `text_only`, keep the text and do not write to another directory.
- Apply the configured pause-title prefix and reminder policy only when their sections are enabled. Saving reminder preferences does not itself authorize creating or changing automations.
{MANAGED_END}"""


def update_managed_agents(path: Path, block: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    start = existing.find(MANAGED_START)
    end = existing.find(MANAGED_END)
    if (start == -1) != (end == -1) or (start != -1 and end < start):
        raise PreferenceError("existing AGENTS.md contains an incomplete managed block")
    if start != -1:
        end += len(MANAGED_END)
        updated = existing[:start].rstrip() + "\n\n" + block + existing[end:]
    else:
        updated = existing.rstrip() + ("\n\n" if existing.strip() else "") + block + "\n"
    atomic_write_text(path, updated)
