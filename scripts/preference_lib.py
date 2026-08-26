#!/usr/bin/env python3
"""Shared validation and atomic persistence for optional Chief preferences."""

from __future__ import annotations

import copy
import json
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
PIN_CRITERIA = [
    "user_delivery_value", "imminent_material_decision", "delay_cost",
    "cross_project_dependency", "activity", "evidence_confidence", "sidebar_cost",
]
PIN_DEFAULT_EXCLUSIONS = [
    "paused", "completed", "superseded", "migration_cancelled", "routine_push",
    "meeting_summary", "report_only", "process_only",
]


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
        if not isinstance(item.get("title"), str) or not item.get("title"):
            errors.append(f"{label}.title must be a non-empty string")
        thread_id = item.get("thread_id")
        if thread_id is not None and (not isinstance(thread_id, str) or not thread_id):
            errors.append(f"{label}.thread_id must be a non-empty string or null")
        if isinstance(thread_id, str) and thread_id:
            core_thread_ids.append(thread_id)
    if len(roles) != 4 or seen_roles != PIN_CORE_ROLES:
        errors.append("pin_governance.mandatory_core_roles requires each core role exactly once")
    if len(core_thread_ids) != len(set(core_thread_ids)):
        errors.append("pin_governance mandatory core thread IDs must be unique")
    if pin.get("enabled") is True:
        if profile.get("scope") != "global":
            errors.append("enabled pin_governance requires global scope")
        if len(core_thread_ids) != 4:
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
- Apply `report_review_mode`. In `exception_only`, the project Chief reviews routine child progress and final handoffs against their contracts without asking the operator. Escalate only goal confirmation, material product choices, visual choices through the Creative Director, protected actions, safety/security, ownership or scope conflicts, failed or unverifiable work, depth expansion, and final project completion.
- If `governance_model.enabled` is true, treat the operator as chair: project Chiefs own routine administration, auditors have evidence-only authority, roles follow the registered chain of command, and an unresolved decision freezes only its affected write surface. Route non-visual statutory exceptions only to the configured general-office task as `CHAIR_BRIEF_READY`; only that task may emit the operator-facing `USER_ACTION_REQUIRED`. TODO scans only the general office and Creative Director.
- Apply `pin_governance` narrowly. Ordinary Chiefs default unpinned, and their unpinned state is not a failure. Mandatory pins are limited to the configured general office, TODO, Creative Director, context migration monitor, and their valid successors. An optional product Chief may be pinned, created for pinning, unpinned, or replaced only after a general-office recommendation and the operator's explicit approval; pin approval never confirms the project goal or authorizes engineering, design, production, or bypass of the Product Manager discovery gate.
- The general office recommends at most three candidates in one pending pack. TODO is read-only and checks identity, currentness, duplication, evidence freshness, observed capacity, and lineage. Preserve manual non-Chief pins. At full capacity, produce only a paired replacement recommendation; never evict automatically. Exclude paused, completed, superseded, migration-cancelled, routine-push, meeting-summary, report-only, and process-only Chiefs by default. A `pinned: true` receipt is not proof; fresh `list_threads` exact-ID presence is required. Only mandatory or operator-approved lineages may use the safe-handoff single-replacement successor path.
- If `governance_model.continuation_policy.enabled` is true, every project Chief must select and execute the strongest evidence-backed safe in-scope continuation without asking the operator. Do not present stopping, preserving a failed state, or delaying as peer options while a safe continuation exists; the operator will initiate those choices when wanted. Escalate only when continuing itself requires a new permission or creation of a new Chief. An ordinary failure remains Chief-owned while another bounded safe diagnostic, repair, or verification path exists. This policy does not authorize protected actions, bypass the Creative Director visual gate, or conceal safety/security evidence; those constraints determine whether a path is safe and already authorized.
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
