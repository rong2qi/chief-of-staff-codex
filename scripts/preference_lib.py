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


SKILL_ROOT = Path(__file__).resolve().parent.parent
CORE_PROFILE = SKILL_ROOT / "assets" / "operator-preferences.example.json"
OPERATOR_PROFILE = (
    SKILL_ROOT / "assets" / "presets" / "operator-controlled-bilingual.json"
)
MANAGED_START = "<!-- chief-of-staff-preferences:start -->"
MANAGED_END = "<!-- chief-of-staff-preferences:end -->"
CLIP_KINDS = {"written", "spoken"}
TIME_PATTERN = re.compile(r"^(?:[01]\d|2[0-3]):[0-5]\d$")


class PreferenceError(ValueError):
    """Raised when a preference profile is unsafe or malformed."""


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreferenceError(f"cannot read preference profile {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise PreferenceError("preference profile must be a JSON object")
    return value


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


def validate_preferences(profile: dict[str, Any]) -> list[str]:
    errors: list[str] = []
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
    require_valid(profile)
    atomic_write_text(path, json.dumps(profile, ensure_ascii=False, indent=2) + "\n")


def managed_agents_block(profile_path: Path, renderer_path: Path) -> str:
    return f"""{MANAGED_START}
## Optional Chief of Staff operator preferences

- Before a complete user-facing reply, read `{profile_path}` when it exists and apply only policies whose `enabled` value is true. Missing or invalid profiles disable optional behavior; they do not change core safety or approval rules.
- If `operator_salutation.enabled` is true, use its configured value unless the operator explicitly overrides it in the current conversation.
- Apply `report_review_mode`. In `exception_only`, the project Chief reviews routine child progress and final handoffs against their contracts without asking the operator. Escalate only goal confirmation, material product choices, visual choices through the Creative Director, protected actions, safety/security, ownership or scope conflicts, failed or unverifiable work, depth expansion, and final project completion.
- If `governance_model.enabled` is true, treat the operator as chair: project Chiefs own routine administration, auditors have evidence-only authority, roles follow the registered chain of command, and an unresolved decision freezes only its affected write surface. Route non-visual statutory exceptions only to the configured general-office task as `CHAIR_BRIEF_READY`; only that task may emit the operator-facing `USER_ACTION_REQUIRED`. TODO scans only the general office and Creative Director.
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
