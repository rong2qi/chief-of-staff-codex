#!/usr/bin/env python3
"""Safely initialize or validate a Chief of Staff project."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from preference_lib import PreferenceError, read_json, require_valid, validate_preferences

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 and earlier
    tomllib = None


SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "project-template"
MUTABLE_STATE = {
    Path(".chief-of-staff/project-plan.json"),
    Path(".chief-of-staff/task-registry.json"),
    Path(".chief-of-staff/approval-queue.json"),
    Path(".chief-of-staff/decisions.md"),
    Path(".chief-of-staff/status.md"),
    Path(".chief-of-staff/control-plane.json"),
    Path(".chief-of-staff/throughput.json"),
}


def render(source: Path, project_name: str, preferences: Optional[dict] = None) -> bytes:
    data = source.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    json_name = json.dumps(project_name, ensure_ascii=False)[1:-1]
    rendered = (
        text.replace("{{PROJECT_NAME_JSON}}", json_name)
        .replace("{{PROJECT_NAME}}", project_name)
    )
    if source.relative_to(TEMPLATE_ROOT) == Path(".chief-of-staff/project.json"):
        project = json.loads(rendered)
        if preferences is not None:
            review_mode = preferences.get("report_review_mode", "exception_only")
            project["report_review_mode"] = review_mode
            project["report_approval_required"] = review_mode == "all_reports"
            governance = preferences["governance_model"]
            if governance["enabled"]:
                project["governance_model"] = "chair_led_cabinet"
                project["operator_role"] = "chair"
                project["routine_administration_owner"] = "project_chief"
                project["auditor_authority"] = "evidence_only"
                project["direct_report_policy"] = "chain_of_command"
                project["partial_pause_policy"] = "affected_surface_only"
                project["operator_escalation_policy"] = "statutory_exceptions_via_hubs"
                continuation = governance["continuation_policy"]
                if continuation["enabled"]:
                    project["continuation_policy"] = (
                        "advance_best_safe_in_scope_path"
                    )
                    project["ordinary_failure_policy"] = (
                        "continue_bounded_diagnosis_repair_and_verification"
                    )
                    project["continuation_escalation_policy"] = (
                        "new_permission_or_new_chief"
                    )
            visual = preferences["visual_selection_gate"]
            project["visual_selection_gate"] = (
                "operator_after_clickable_preview" if visual["enabled"] else "disabled"
            )
            project["visual_review_hub_title"] = visual["review_hub_title"]
        return encoded_json(project)
    return rendered.encode("utf-8")


def template_files() -> list[tuple[Path, Path]]:
    return [
        (source, source.relative_to(TEMPLATE_ROOT))
        for source in sorted(TEMPLATE_ROOT.rglob("*"))
        if source.is_file()
    ]


def safe_target(raw_target: str) -> Path:
    target = Path(raw_target).expanduser().resolve()
    if target == Path(target.anchor) or target == Path.home().resolve():
        raise ValueError("refusing to initialize a filesystem root or home directory")
    return target


def validate_toml(path: Path) -> str | None:
    if tomllib is not None:
        try:
            with path.open("rb") as handle:
                tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            return str(exc)
        return None

    return "strict TOML parsing requires Python 3.11+"


def require_keys(value: dict, keys: set[str], relative: Path, errors: list[str]) -> None:
    missing = sorted(keys - set(value))
    if missing:
        errors.append(f"missing keys in {relative}: {', '.join(missing)}")


def migrate_mutable_state(relative: Path, value: object) -> tuple[object, bool]:
    """Add backward-compatible fields without changing existing state values."""
    if not isinstance(value, dict):
        return value, False

    changed = False
    if relative.name == "task-registry.json" and isinstance(value.get("tasks"), list):
        for task in value["tasks"]:
            if not isinstance(task, dict):
                continue
            defaults = {
                "parent_task_id": None,
                "phase_id": None,
                "management_depth": 2,
                "project_id": None,
                "coordination_with": [],
            }
            for key, default in defaults.items():
                if key not in task:
                    task[key] = default
                    changed = True

    if relative.name == "approval-queue.json" and isinstance(value.get("requests"), list):
        for request in value["requests"]:
            if not isinstance(request, dict):
                continue
            if "request_kind" not in request:
                request["request_kind"] = "report_review"
                changed = True

    if relative.name == "throughput.json":
        defaults = {
            "schema_version": 1,
            "execution_mode": "effective_throughput",
            "max_parallel_phase_lanes": 2,
            "no_evidence_checkpoint_limit": 2,
            "consecutive_no_evidence_checkpoints": 0,
            "active_phase_lanes": [],
            "last_evidence_checkpoint": None,
        }
        for key, default in defaults.items():
            if key not in value:
                value[key] = default
                changed = True

    return value, changed


def encoded_json(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def validate_state(relative: Path, value: object, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"top-level JSON value in {relative} must be an object")
        return
    if value.get("schema_version") != 1:
        errors.append(f"unsupported schema_version in {relative}")
        return

    if relative.name == "project.json":
        require_keys(
            value,
            {
                "schema_version", "project_name", "primary_task_title", "control_plane",
                "pin_primary_task", "report_review_mode", "report_approval_required",
                "governance_model", "operator_role", "routine_administration_owner",
                "auditor_authority", "direct_report_policy", "partial_pause_policy",
                "operator_escalation_policy", "continuation_policy",
                "ordinary_failure_policy", "continuation_escalation_policy",
                "task_title_pattern",
                "require_goal_confirmation", "max_management_depth",
                "durable_goal_enabled", "execution_mode", "max_parallel_phase_lanes",
                "no_evidence_checkpoint_limit", "visual_selection_gate",
                "visual_review_hub_title",
                "auto_advance_low_impact", "proactive_follow_up", "approval_required",
                "durable_child_scope", "archive_completed_child_tasks",
                "projectless_child_policy",
                "peer_coordination_enabled", "peer_contact_policy",
                "subagent_meetings_enabled", "max_meeting_participants",
            },
            relative,
            errors,
        )
        for key in (
            "project_name", "primary_task_title", "control_plane", "task_title_pattern",
            "report_review_mode", "governance_model", "operator_role",
            "routine_administration_owner", "auditor_authority", "direct_report_policy",
            "partial_pause_policy", "operator_escalation_policy", "continuation_policy",
            "ordinary_failure_policy", "continuation_escalation_policy",
            "visual_selection_gate", "visual_review_hub_title",
        ):
            if key in value and not isinstance(value[key], str):
                errors.append(f"{key} in {relative} must be a string")
        project_name = value.get("project_name")
        primary_task_title = value.get("primary_task_title")
        if isinstance(project_name, str) and isinstance(primary_task_title, str):
            expected_title = f"Chief of {project_name}"
            if primary_task_title != expected_title:
                errors.append(
                    f"primary_task_title in {relative} must be {expected_title!r}"
                )
        for key in (
            "pin_primary_task", "report_approval_required", "require_goal_confirmation",
            "durable_goal_enabled",
            "auto_advance_low_impact", "proactive_follow_up",
            "archive_completed_child_tasks",
            "peer_coordination_enabled", "subagent_meetings_enabled",
        ):
            if key in value and not isinstance(value[key], bool):
                errors.append(f"{key} in {relative} must be a boolean")
        max_depth = value.get("max_management_depth")
        if not isinstance(max_depth, int) or isinstance(max_depth, bool) or max_depth < 1:
            errors.append(f"max_management_depth in {relative} must be a positive integer")
        if value.get("execution_mode") != "effective_throughput":
            errors.append(f"execution_mode in {relative} must be 'effective_throughput'")
        report_review_mode = value.get("report_review_mode")
        if report_review_mode not in {"all_reports", "exception_only"}:
            errors.append(
                f"report_review_mode in {relative} must be 'all_reports' or 'exception_only'"
            )
        expected_legacy_flag = report_review_mode == "all_reports"
        if isinstance(value.get("report_approval_required"), bool) and value.get(
            "report_approval_required"
        ) != expected_legacy_flag:
            errors.append(
                f"report_approval_required in {relative} must match report_review_mode"
            )
        governance_model = value.get("governance_model")
        if governance_model not in {"standard", "chair_led_cabinet"}:
            errors.append(
                f"governance_model in {relative} must be 'standard' or 'chair_led_cabinet'"
            )
        if governance_model == "chair_led_cabinet":
            expected_governance = {
                "operator_role": "chair",
                "routine_administration_owner": "project_chief",
                "auditor_authority": "evidence_only",
                "direct_report_policy": "chain_of_command",
                "partial_pause_policy": "affected_surface_only",
                "operator_escalation_policy": "statutory_exceptions_via_hubs",
            }
            for key, expected_value in expected_governance.items():
                if value.get(key) != expected_value:
                    errors.append(
                        f"{key} in {relative} must be {expected_value!r} under chair_led_cabinet"
                    )
        continuation_policy = value.get("continuation_policy")
        if continuation_policy not in {"standard", "advance_best_safe_in_scope_path"}:
            errors.append(
                f"continuation_policy in {relative} must be 'standard' or "
                "'advance_best_safe_in_scope_path'"
            )
        if continuation_policy == "advance_best_safe_in_scope_path":
            if governance_model != "chair_led_cabinet":
                errors.append(
                    f"continuation_policy in {relative} requires chair_led_cabinet"
                )
            expected_continuation = {
                "ordinary_failure_policy": (
                    "continue_bounded_diagnosis_repair_and_verification"
                ),
                "continuation_escalation_policy": "new_permission_or_new_chief",
            }
            for key, expected_value in expected_continuation.items():
                if value.get(key) != expected_value:
                    errors.append(
                        f"{key} in {relative} must be {expected_value!r} under "
                        "advance_best_safe_in_scope_path"
                    )
        if value.get("visual_selection_gate") not in {
            "disabled", "operator_after_clickable_preview"
        }:
            errors.append(
                f"visual_selection_gate in {relative} must be "
                "'disabled' or 'operator_after_clickable_preview'"
            )
        if not isinstance(value.get("visual_review_hub_title"), str) or not value.get(
            "visual_review_hub_title"
        ):
            errors.append(
                f"visual_review_hub_title in {relative} must be a non-empty string"
            )
        for key in ("max_parallel_phase_lanes", "no_evidence_checkpoint_limit"):
            number = value.get(key)
            if not isinstance(number, int) or isinstance(number, bool) or number < 1:
                errors.append(f"{key} in {relative} must be a positive integer")
        if value.get("durable_child_scope") != "same_project":
            errors.append(f"durable_child_scope in {relative} must be 'same_project'")
        if value.get("projectless_child_policy") != "temporary_subagents":
            errors.append(
                f"projectless_child_policy in {relative} must be 'temporary_subagents'"
            )
        if value.get("peer_contact_policy") != "registered_same_project":
            errors.append(
                f"peer_contact_policy in {relative} must be 'registered_same_project'"
            )
        max_participants = value.get("max_meeting_participants")
        if (
            not isinstance(max_participants, int)
            or isinstance(max_participants, bool)
            or max_participants < 1
        ):
            errors.append(
                f"max_meeting_participants in {relative} must be a positive integer"
            )
        approvals = value.get("approval_required")
        if not isinstance(approvals, list) or not all(isinstance(item, str) for item in approvals):
            errors.append(f"approval_required in {relative} must be an array of strings")

    elif relative.name == "project-plan.json":
        require_keys(
            value,
            {
                "schema_version", "goal_status", "project_status", "final_goal",
                "deliverables", "acceptance_criteria", "non_goals", "constraints",
                "confirmed_at", "current_phase_id", "phases",
            },
            relative,
            errors,
        )
        if value.get("goal_status") not in {"unconfirmed", "confirmed"}:
            errors.append(f"goal_status in {relative} is invalid")
        project_statuses = {
            "awaiting_goal", "active", "awaiting_user", "blocked", "completed"
        }
        if value.get("project_status") not in project_statuses:
            errors.append(f"project_status in {relative} is invalid")
        if "final_goal" in value and not isinstance(value["final_goal"], str):
            errors.append(f"final_goal in {relative} must be a string")
        for key in ("deliverables", "non_goals", "constraints"):
            if key in value and (
                not isinstance(value[key], list)
                or not all(isinstance(item, str) for item in value[key])
            ):
                errors.append(f"{key} in {relative} must be an array of strings")
        for key in ("confirmed_at", "current_phase_id"):
            if key in value and value[key] is not None and not isinstance(value[key], str):
                errors.append(f"{key} in {relative} must be a string or null")

        criteria = value.get("acceptance_criteria")
        if not isinstance(criteria, list):
            errors.append(f"acceptance_criteria in {relative} must be an array")
        else:
            criterion_statuses = {"pending", "verified", "failed"}
            seen_criterion_ids: set[str] = set()
            for index, criterion in enumerate(criteria):
                label = f"{relative} acceptance_criteria[{index}]"
                if not isinstance(criterion, dict):
                    errors.append(f"{label} must be an object")
                    continue
                require_keys(
                    criterion,
                    {"criterion_id", "description", "status", "evidence"},
                    Path(label),
                    errors,
                )
                for key in ("criterion_id", "description"):
                    if key in criterion and not isinstance(criterion[key], str):
                        errors.append(f"{key} in {label} must be a string")
                criterion_id = criterion.get("criterion_id")
                if isinstance(criterion_id, str):
                    if criterion_id in seen_criterion_ids:
                        errors.append(
                            f"duplicate criterion_id in {relative}: {criterion_id}"
                        )
                    seen_criterion_ids.add(criterion_id)
                if criterion.get("status") not in criterion_statuses:
                    errors.append(f"status in {label} is invalid")
                evidence = criterion.get("evidence")
                if not isinstance(evidence, list) or not all(
                    isinstance(item, str) for item in evidence
                ):
                    errors.append(f"evidence in {label} must be an array of strings")

        phases = value.get("phases")
        if not isinstance(phases, list):
            errors.append(f"phases in {relative} must be an array")
        else:
            phase_statuses = {"planned", "active", "awaiting_user", "blocked", "completed"}
            seen_phase_ids: set[str] = set()
            for index, phase in enumerate(phases):
                label = f"{relative} phases[{index}]"
                if not isinstance(phase, dict):
                    errors.append(f"{label} must be an object")
                    continue
                require_keys(
                    phase,
                    {
                        "phase_id", "title", "objective", "status",
                        "acceptance_criteria", "task_ids", "result_summary",
                    },
                    Path(label),
                    errors,
                )
                for key in ("phase_id", "title", "objective"):
                    if key in phase and not isinstance(phase[key], str):
                        errors.append(f"{key} in {label} must be a string")
                phase_id = phase.get("phase_id")
                if isinstance(phase_id, str):
                    if phase_id in seen_phase_ids:
                        errors.append(f"duplicate phase_id in {relative}: {phase_id}")
                    seen_phase_ids.add(phase_id)
                if phase.get("status") not in phase_statuses:
                    errors.append(f"status in {label} is invalid")
                for key in ("acceptance_criteria", "task_ids"):
                    if key in phase and (
                        not isinstance(phase[key], list)
                        or not all(isinstance(item, str) for item in phase[key])
                    ):
                        errors.append(f"{key} in {label} must be an array of strings")
                result_summary = phase.get("result_summary")
                if result_summary is not None and not isinstance(result_summary, str):
                    errors.append(f"result_summary in {label} must be a string or null")

        if value.get("goal_status") == "unconfirmed":
            if value.get("project_status") != "awaiting_goal":
                errors.append(
                    f"unconfirmed goal in {relative} requires project_status awaiting_goal"
                )
        if value.get("goal_status") == "confirmed":
            if value.get("project_status") == "awaiting_goal":
                errors.append(
                    f"confirmed goal in {relative} cannot remain awaiting_goal"
                )
            if not value.get("final_goal"):
                errors.append(f"confirmed goal in {relative} requires final_goal")
            if not isinstance(value.get("deliverables"), list) or not value["deliverables"]:
                errors.append(f"confirmed goal in {relative} requires deliverables")
            if not isinstance(criteria, list) or not criteria:
                errors.append(f"confirmed goal in {relative} requires acceptance_criteria")
            if not isinstance(value.get("confirmed_at"), str) or not value["confirmed_at"]:
                errors.append(f"confirmed goal in {relative} requires confirmed_at")
        if value.get("project_status") == "active":
            current_phase_id = value.get("current_phase_id")
            if not isinstance(current_phase_id, str) or not current_phase_id:
                errors.append(f"active project in {relative} requires current_phase_id")
            elif not isinstance(phases, list) or not any(
                isinstance(phase, dict)
                and phase.get("phase_id") == current_phase_id
                and phase.get("status") == "active"
                for phase in phases
            ):
                errors.append(
                    f"active project in {relative} requires a matching active phase"
                )
        if value.get("project_status") == "completed":
            if value.get("goal_status") != "confirmed":
                errors.append(f"completed project in {relative} requires a confirmed goal")
            if not isinstance(criteria, list) or not criteria or any(
                not isinstance(item, dict) or item.get("status") != "verified"
                or not item.get("evidence")
                for item in criteria
            ):
                errors.append(
                    f"completed project in {relative} requires verified acceptance evidence"
                )

    elif relative.name == "task-registry.json":
        require_keys(value, {"schema_version", "tasks"}, relative, errors)
        tasks = value.get("tasks")
        if not isinstance(tasks, list):
            errors.append(f"tasks in {relative} must be an array")
            return
        required_task_keys = {
            "task_id", "host_id", "title", "role", "objective", "status",
            "write_surface", "depends_on", "last_cursor", "result_summary",
            "parent_task_id", "phase_id", "management_depth",
            "project_id",
            "coordination_with",
        }
        statuses = {"queued", "running", "needs_attention", "completed", "failed", "archived"}
        task_by_id: dict[str, dict] = {}
        for index, task in enumerate(tasks):
            label = f"{relative} task[{index}]"
            if not isinstance(task, dict):
                errors.append(f"{label} must be an object")
                continue
            require_keys(task, required_task_keys, Path(label), errors)
            for key in ("task_id", "title", "role", "objective"):
                if key in task and not isinstance(task[key], str):
                    errors.append(f"{key} in {label} must be a string")
            task_id = task.get("task_id")
            if isinstance(task_id, str):
                if task_id in task_by_id:
                    errors.append(f"duplicate task_id in {relative}: {task_id}")
                task_by_id[task_id] = task
            if task.get("status") not in statuses:
                errors.append(f"status in {label} is invalid")
            for key in ("write_surface", "depends_on", "coordination_with"):
                if key in task and (
                    not isinstance(task[key], list)
                    or not all(isinstance(item, str) for item in task[key])
                ):
                    errors.append(f"{key} in {label} must be an array of strings")
            for key in (
                "host_id", "last_cursor", "result_summary", "parent_task_id", "phase_id",
                "project_id",
            ):
                if key in task and task[key] is not None and not isinstance(task[key], str):
                    errors.append(f"{key} in {label} must be a string or null")
            management_depth = task.get("management_depth")
            if (
                not isinstance(management_depth, int)
                or isinstance(management_depth, bool)
                or management_depth < 1
            ):
                errors.append(f"management_depth in {label} must be a positive integer")

        for task_id, task in task_by_id.items():
            peers = task.get("coordination_with")
            if not isinstance(peers, list):
                continue
            for peer_id in peers:
                if not isinstance(peer_id, str):
                    continue
                peer = task_by_id.get(peer_id)
                if peer is None:
                    errors.append(
                        f"coordination peer {peer_id!r} for task {task_id!r} is not registered"
                    )
                    continue
                if peer_id == task_id:
                    errors.append(f"task {task_id!r} cannot coordinate with itself")
                if task_id not in peer.get("coordination_with", []):
                    errors.append(
                        f"coordination edge between {task_id!r} and {peer_id!r} must be symmetric"
                    )
                project_id = task.get("project_id")
                if not isinstance(project_id, str) or project_id != peer.get("project_id"):
                    errors.append(
                        f"coordination peers {task_id!r} and {peer_id!r} must share project_id"
                    )

    elif relative.name == "approval-queue.json":
        require_keys(value, {"schema_version", "requests"}, relative, errors)
        requests = value.get("requests")
        if not isinstance(requests, list):
            errors.append(f"requests in {relative} must be an array")
            return
        required_request_keys = {
            "request_id", "request_kind", "task_id", "host_id", "task_title", "report_type",
            "submitted_at", "summary", "requested_decision", "status",
            "decided_at", "decision_note",
        }
        request_kinds = {"goal_confirmation", "report_review", "depth_expansion"}
        report_types = {"progress", "final"}
        review_statuses = {"pending", "approved", "changes_requested", "superseded"}
        seen_request_ids: set[str] = set()
        for index, request in enumerate(requests):
            label = f"{relative} request[{index}]"
            if not isinstance(request, dict):
                errors.append(f"{label} must be an object")
                continue
            require_keys(request, required_request_keys, Path(label), errors)
            for key in (
                "request_id", "request_kind", "submitted_at", "summary", "requested_decision",
            ):
                if key in request and not isinstance(request[key], str):
                    errors.append(f"{key} in {label} must be a string")
            request_id = request.get("request_id")
            if isinstance(request_id, str):
                if request_id in seen_request_ids:
                    errors.append(f"duplicate request_id in {relative}: {request_id}")
                seen_request_ids.add(request_id)
            request_kind = request.get("request_kind")
            if request_kind not in request_kinds:
                errors.append(f"request_kind in {label} is invalid")
            report_type = request.get("report_type")
            if request_kind == "report_review" and report_type not in report_types:
                errors.append(f"report_type in {label} is invalid for report_review")
            if request_kind != "report_review" and report_type is not None:
                errors.append(f"report_type in {label} must be null for {request_kind}")
            if request.get("status") not in review_statuses:
                errors.append(f"status in {label} is invalid")
            for key in (
                "task_id", "host_id", "task_title", "report_type", "decided_at",
                "decision_note",
            ):
                if key in request and request[key] is not None and not isinstance(request[key], str):
                    errors.append(f"{key} in {label} must be a string or null")

    elif relative.name == "control-plane.json":
        require_keys(
            value,
            {"schema_version", "provider", "adapter", "adapter_config"},
            relative,
            errors,
        )
        if "provider" in value and not isinstance(value["provider"], str):
            errors.append(f"provider in {relative} must be a string")
        if value.get("adapter") is not None and not isinstance(value.get("adapter"), str):
            errors.append(f"adapter in {relative} must be a string or null")
        if "adapter_config" in value and not isinstance(value["adapter_config"], dict):
            errors.append(f"adapter_config in {relative} must be an object")

    elif relative.name == "throughput.json":
        require_keys(value, {
            "schema_version", "execution_mode", "max_parallel_phase_lanes",
            "no_evidence_checkpoint_limit", "consecutive_no_evidence_checkpoints",
            "active_phase_lanes", "last_evidence_checkpoint",
        }, relative, errors)
        if value.get("execution_mode") != "effective_throughput":
            errors.append(f"execution_mode in {relative} must be 'effective_throughput'")
        for key in ("max_parallel_phase_lanes", "no_evidence_checkpoint_limit"):
            number = value.get(key)
            if not isinstance(number, int) or isinstance(number, bool) or number < 1:
                errors.append(f"{key} in {relative} must be a positive integer")
        count = value.get("consecutive_no_evidence_checkpoints")
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            errors.append(f"consecutive_no_evidence_checkpoints in {relative} must be a non-negative integer")
        lanes = value.get("active_phase_lanes")
        if not isinstance(lanes, list) or not all(isinstance(item, str) for item in lanes):
            errors.append(f"active_phase_lanes in {relative} must be an array of strings")
        checkpoint = value.get("last_evidence_checkpoint")
        if checkpoint is not None and not isinstance(checkpoint, str):
            errors.append(f"last_evidence_checkpoint in {relative} must be a string or null")


def validate(target: Path) -> list[str]:
    errors: list[str] = []
    required = [relative for _, relative in template_files()]
    for relative in required:
        if not (target / relative).is_file():
            errors.append(f"missing {relative}")

    for relative in (
        Path(".chief-of-staff/project.json"),
        Path(".chief-of-staff/project-plan.json"),
        Path(".chief-of-staff/task-registry.json"),
        Path(".chief-of-staff/approval-queue.json"),
        Path(".chief-of-staff/control-plane.json"),
        Path(".chief-of-staff/throughput.json"),
    ):
        path = target / relative
        if path.is_file():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                validate_state(relative, value, errors)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append(f"invalid JSON in {relative}: {exc}")

    plan_path = target / ".chief-of-staff" / "project-plan.json"
    registry_path = target / ".chief-of-staff" / "task-registry.json"
    if plan_path.is_file() and registry_path.is_file():
        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            if isinstance(plan, dict) and plan.get("project_status") == "active":
                current_phase_id = plan.get("current_phase_id")
                tasks = registry.get("tasks") if isinstance(registry, dict) else None
                active_statuses = {"queued", "running", "needs_attention"}
                if not isinstance(tasks, list) or not any(
                    isinstance(task, dict)
                    and task.get("phase_id") == current_phase_id
                    and task.get("status") in active_statuses
                    for task in tasks
                ):
                    errors.append(
                        "active project requires a queued, running, or needs_attention "
                        "task in the current phase"
                    )
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass

    preferences_path = target / ".chief-of-staff" / "preferences.json"
    if preferences_path.is_file():
        try:
            preferences = read_json(preferences_path)
            errors.extend(
                f"invalid preferences.json: {error}"
                for error in validate_preferences(preferences)
            )
            if preferences.get("scope") != "project":
                errors.append("project preferences.json requires scope project")
        except PreferenceError as exc:
            errors.append(str(exc))

    toml_files = [target / ".codex" / "config.toml"]
    # FAT/exFAT volumes may expose macOS AppleDouble sidecars such as
    # `._scout.toml`; they are metadata, not Codex agent profiles.
    toml_files.extend(
        path for path in sorted((target / ".codex" / "agents").glob("*.toml"))
        if not path.name.startswith("._")
    )
    for path in toml_files:
        if path.is_file():
            if tomllib is None:
                relative = path.relative_to(target)
                template = TEMPLATE_ROOT / relative
                error = None if template.is_file() and path.read_bytes() == template.read_bytes() else (
                    "Python 3.10 fallback only accepts the validated v1 template"
                )
            else:
                error = validate_toml(path)
            if error:
                errors.append(f"invalid TOML in {path.relative_to(target)}: {error}")

    return errors


def initialize(
    target: Path,
    project_name: str,
    preferences: Optional[dict] = None,
    persist_preferences: bool = False,
) -> int:
    files = template_files()
    conflicts: list[Path] = []
    planned: list[tuple[Path, bytes]] = []

    for source, relative in files:
        destination = target / relative
        expected = render(source, project_name, preferences)
        cursor = target
        unsafe_parent = False
        for part in relative.parts[:-1]:
            cursor = cursor / part
            if cursor.is_symlink():
                unsafe_parent = True
                break
        if unsafe_parent or destination.is_symlink():
            conflicts.append(relative)
            continue
        if destination.exists():
            if relative in MUTABLE_STATE:
                if relative.suffix == ".json":
                    try:
                        value = json.loads(destination.read_text(encoding="utf-8"))
                        value, changed = migrate_mutable_state(relative, value)
                        state_errors: list[str] = []
                        validate_state(relative, value, state_errors)
                        if state_errors:
                            raise ValueError("; ".join(state_errors))
                        if changed:
                            planned.append((destination, encoded_json(value)))
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
                        conflicts.append(relative)
                        continue
                continue
            if relative == Path(".codex/config.toml"):
                try:
                    existing_config = destination.read_text(encoding="utf-8")
                    if tomllib is None:
                        if "[features]\ngoals = true" in existing_config:
                            continue
                        if "[features]" not in existing_config:
                            data = existing_config.rstrip() + "\n\n[features]\ngoals = true\n"
                            planned.append((destination, data.encode("utf-8")))
                            continue
                        raise ValueError("existing features policy conflicts")
                    parsed_config = tomllib.loads(existing_config) if tomllib is not None else {}
                    features = parsed_config.get("features") if isinstance(parsed_config, dict) else None
                    if features is None:
                        data = existing_config.rstrip() + "\n\n[features]\ngoals = true\n"
                        planned.append((destination, data.encode("utf-8")))
                        continue
                    if isinstance(features, dict) and features.get("goals") is True:
                        continue
                except (OSError, UnicodeDecodeError, AttributeError, ValueError):
                    pass
            if destination.read_bytes() == expected:
                continue
            if relative == Path(".chief-of-staff/project.json"):
                try:
                    existing_project = json.loads(destination.read_text(encoding="utf-8"))
                    expected_project = json.loads(expected.decode("utf-8"))
                    # Upgrade an older managed project by adding only missing defaults.
                    upgraded_project = dict(existing_project)
                    project_changed = False
                    if "report_review_mode" not in upgraded_project:
                        upgraded_project["report_review_mode"] = (
                            "all_reports"
                            if upgraded_project.get("report_approval_required") is True
                            else "exception_only"
                        )
                        project_changed = True
                    for key in (
                        "durable_goal_enabled", "execution_mode", "max_parallel_phase_lanes",
                        "no_evidence_checkpoint_limit", "visual_selection_gate",
                        "visual_review_hub_title", "governance_model", "operator_role",
                        "routine_administration_owner", "auditor_authority",
                        "direct_report_policy", "partial_pause_policy",
                        "operator_escalation_policy", "continuation_policy",
                        "ordinary_failure_policy", "continuation_escalation_policy",
                    ):
                        if key not in upgraded_project:
                            upgraded_project[key] = expected_project[key]
                            project_changed = True
                    if project_changed:
                        state_errors: list[str] = []
                        validate_state(relative, upgraded_project, state_errors)
                        if not state_errors:
                            planned.append((destination, encoded_json(upgraded_project)))
                            continue
                    previous_peer_coordination = dict(expected_project)
                    for key in (
                        "peer_coordination_enabled", "peer_contact_policy",
                        "subagent_meetings_enabled", "max_meeting_participants",
                    ):
                        previous_peer_coordination.pop(key, None)
                    previous_project_scoping = dict(previous_peer_coordination)
                    for key in (
                        "durable_child_scope", "archive_completed_child_tasks",
                        "projectless_child_policy",
                    ):
                        previous_project_scoping.pop(key, None)
                    previous_dynamic = dict(previous_project_scoping)
                    for key in (
                        "require_goal_confirmation", "max_management_depth",
                        "report_review_mode",
                        "governance_model", "operator_role", "routine_administration_owner",
                        "auditor_authority", "direct_report_policy", "partial_pause_policy",
                        "operator_escalation_policy",
                        "durable_goal_enabled", "execution_mode", "max_parallel_phase_lanes",
                        "no_evidence_checkpoint_limit", "visual_selection_gate",
                        "visual_review_hub_title",
                        "auto_advance_low_impact", "proactive_follow_up",
                    ):
                        previous_dynamic.pop(key, None)
                    previous_before_report_approval = dict(previous_dynamic)
                    previous_before_report_approval.pop("report_approval_required", None)
                    previous_before_pinning = dict(previous_before_report_approval)
                    previous_before_pinning.pop("pin_primary_task", None)
                    previous_legacy = dict(previous_before_pinning)
                    previous_legacy["primary_task_title"] = "Chief of Staff"
                    if existing_project in (
                        previous_peer_coordination, previous_project_scoping, previous_dynamic,
                        previous_before_report_approval,
                        previous_before_pinning, previous_legacy,
                    ):
                        planned.append((destination, expected))
                        continue
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    pass
            if relative == Path("AGENTS.md"):
                current_text = expected.decode("utf-8")
                peer_coordination = """\n## Peer coordination and subagent meetings\n\n- Durable roles may message only peers listed in their `coordination_with` registry field, and only when both tasks have the same verified `project_id`. The Chief grants or revokes these contact edges.\n- A peer message has a bounded purpose, relevant evidence, the interface or dependency at issue, and the response needed. Routine peer sync does not require user approval, but the sender reports the resulting decision or unresolved conflict to the Chief.\n- Peer dialogue cannot transfer write ownership, expand scope, approve a report, or authorize a protected action. Conflicting assumptions or requested ownership changes go to the Chief before either task implements them.\n- When `subagent_meetings_enabled` is true, any durable role may summon up to `max_meeting_participants` temporary subagents for independent research, discussion, testing, or review. Participants are read-only by default, cannot create durable tasks, and do not add a management layer.\n- Every meeting records one question, participant roles, inputs, stopping condition, and synthesis owner. The parent waits for all requested results, reconciles them by evidence rather than vote, and sends one concise meeting outcome to affected peers and the Chief.\n"""
                project_lifecycle = """\n## Project placement and task lifecycle\n\n- Every durable child task must be created in the same saved Codex project as its Chief. Record the returned `project_id` in `task-registry.json` and verify it matches before delegation continues.\n- If the Chief has no saved project context, use temporary subagents by default. Ask the user to choose or save a project before creating a durable child whose separate history is truly required. Never create a projectless durable child silently.\n- Active, queued, failed, or needs-attention child tasks remain visible for follow-up. Do not pin child tasks unless the user explicitly requests it.\n- Archive a durable child only after its final report is explicitly approved, its evidence and result are recorded, and no retry or dependent follow-up remains. Archiving is reversible and must not delete its registry entry, task ID, cursor, or summary.\n"""
                goal_closure = """\n## Goal closure and active progression\n\n- Before implementation, the Chief proposes and asks the user to confirm the final goal, deliverables, acceptance criteria, non-goals, and constraints. A new project permits only bounded read-only discovery before confirmation. In a migrated project, already-running non-high-impact tasks may finish, but no new task or phase starts before confirmation.\n- A phase completion is not project completion. The project is complete only when the goal is confirmed and every final acceptance criterion has non-empty verification evidence in `project-plan.json`.\n- Until completion, keep a phase task queued, running, or needing attention unless the project is explicitly waiting for the user or blocked with evidence and a release condition. If all phase tasks stop while final acceptance is unmet, immediately dispatch the next safe in-scope phase.\n- Follow all active tasks with bounded waits. After any completion, failure, or attention event, snapshot every active task before deciding what comes next.\n- A Chief report for an unfinished project always includes the final goal, current phase, verified progress, active roles, gap to delivery, and next checkpoint, even when no approval is pending.\n- Management depth 1 is the Chief, depth 2 is a phase lead, and depth 3 is an execution role. Phase leads may create depth-3 tasks only when explicitly authorized in their contract. Temporary subagents cannot create durable roles. Depth 4 or deeper requires an approved `depth_expansion` request.\n- The Chief is the sole writer of `project-plan.json`, `task-registry.json`, `approval-queue.json`, and consolidated status. Low-impact in-scope phases advance automatically; protected actions retain their separate approval requirements.\n"""
                report_gate = """\n## Report approval gate\n\nWhen `.chief-of-staff/project.json` sets `report_approval_required` to `true`, every milestone report and final handoff includes a stable `<task_id>:<report_sequence>` ID and requests `批准` or `退回修改`. The child opens a blocking review request so Codex marks it as needing attention; if the host cannot do that, it ends with `REVIEW_REQUIRED: <request_id>`. The Chief snapshots all active children after any wake-up, records every unseen request in `approval-queue.json`, and batches pending reports for the user in the Chief task. Only the user's explicit decision relayed by the Chief clears the gate.\n"""
                previous_peer_coordination = current_text.replace(peer_coordination, "")
                previous_project_scoping = previous_peer_coordination.replace(project_lifecycle, "")
                previous_current = previous_project_scoping.replace(goal_closure, "")
                previous_current = previous_current.replace(
                    "- `.chief-of-staff/project-plan.json`: confirmed final goal, acceptance evidence, project status, and phase plan.\n",
                    "",
                )
                previous_text = previous_current.replace(report_gate, "")
                previous_text = previous_text.replace(
                    "- `.chief-of-staff/approval-queue.json`: deduplicated human-review requests and decisions.\n",
                    "",
                )
                legacy_text = previous_text.replace(
                    f"This project is coordinated through one primary Codex task named `Chief of {project_name}`.",
                    "This project is coordinated through one primary Codex task titled `Chief of Staff`.",
                ).replace(
                    "- A task is the Chief of Staff only when its title matches the `primary_task_title` in `.chief-of-staff/project.json` or its initiating prompt explicitly assigns that role.",
                    "- A task is the Chief of Staff only when its title or initiating prompt explicitly assigns that role.",
                )
                if destination.read_bytes() in {
                    previous_peer_coordination.encode("utf-8"),
                    previous_project_scoping.encode("utf-8"),
                    previous_current.encode("utf-8"), previous_text.encode("utf-8"),
                    legacy_text.encode("utf-8"),
                }:
                    planned.append((destination, expected))
                    continue
            conflicts.append(relative)
        else:
            planned.append((destination, expected))

    if preferences is not None and persist_preferences:
        preference_destination = target / ".chief-of-staff" / "preferences.json"
        preference_expected = encoded_json(preferences)
        if preference_destination.is_symlink() or preference_destination.parent.is_symlink():
            conflicts.append(Path(".chief-of-staff/preferences.json"))
        elif preference_destination.exists():
            if preference_destination.read_bytes() != preference_expected:
                conflicts.append(Path(".chief-of-staff/preferences.json"))
        else:
            planned.append((preference_destination, preference_expected))

    if conflicts:
        print("Chief of Staff initialization stopped; existing files differ:", file=sys.stderr)
        for relative in conflicts:
            print(f"- {relative}", file=sys.stderr)
        print("No files were written. Reconcile or move the conflicts, then retry.", file=sys.stderr)
        return 2

    target.mkdir(parents=True, exist_ok=True)
    for destination, data in planned:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)

    errors = validate(target)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    action = "initialized" if planned else "already initialized"
    print(f"Chief of Staff {action}: {target}")
    print(f"Files written: {len(planned)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=".", help="Project root; defaults to the current directory")
    parser.add_argument("--project-name", help="Display name; defaults to the target directory name")
    profile_group = parser.add_mutually_exclusive_group()
    profile_group.add_argument(
        "--preferences",
        help="Validated project-scoped profile; projected and copied into the project",
    )
    profile_group.add_argument(
        "--policy-profile",
        help="Validated global profile; policies are projected without copying the profile",
    )
    parser.add_argument("--check", action="store_true", help="Validate an initialized project without writing")
    args = parser.parse_args()

    try:
        target = safe_target(args.target)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    project_name = (args.project_name or target.name).strip()
    if not project_name or any(ord(character) < 32 for character in project_name):
        print("ERROR: project name must be a non-empty single line", file=sys.stderr)
        return 2

    preferences = None
    selected_profile = args.preferences or args.policy_profile
    if selected_profile:
        try:
            preference_path = Path(selected_profile).expanduser()
            if not preference_path.is_absolute():
                raise PreferenceError("preference profile path must be absolute")
            preferences = read_json(preference_path.resolve())
            require_valid(preferences)
            if args.preferences and preferences.get("scope") != "project":
                raise PreferenceError("--preferences requires scope project")
            if args.policy_profile and preferences.get("scope") != "global":
                raise PreferenceError("--policy-profile requires scope global")
        except PreferenceError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

    if args.check:
        errors = validate(target)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"Chief of Staff project is valid: {target}")
        return 0
    return initialize(
        target,
        project_name,
        preferences,
        persist_preferences=bool(args.preferences),
    )


if __name__ == "__main__":
    raise SystemExit(main())
