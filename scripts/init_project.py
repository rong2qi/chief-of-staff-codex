#!/usr/bin/env python3
"""Safely initialize or validate a Chief of Staff project."""

from __future__ import annotations

import argparse
import hashlib
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
    Path(".chief-of-staff/pin-state.json"),
    Path(".chief-of-staff/product-discovery.json"),
    Path(".chief-of-staff/task-registry.json"),
    Path(".chief-of-staff/approval-queue.json"),
    Path(".chief-of-staff/decisions.md"),
    Path(".chief-of-staff/status.md"),
    Path(".chief-of-staff/control-plane.json"),
    Path(".chief-of-staff/throughput.json"),
}

PRODUCT_DISCOVERY_LANES = {
    "project_initiation",
    "requirements_analysis",
    "market_research",
    "architecture_feasibility",
}
PRODUCT_DISCOVERY_DELIVERABLES = {
    "project_charter",
    "market_competitor_research",
    "user_research_and_personas",
    "business_policy_feasibility",
    "requirements_inventory_and_prioritization",
    "architecture_feasibility",
    "risk_gap_and_mvp_recommendation",
}
PRODUCT_DISCOVERY_COVERAGE = {
    "problem_definition",
    "goals_non_goals_acceptance_metrics",
    "market_competitors",
    "users_pain_points_personas",
    "policy_constraints_business_feasibility",
    "requirements_sources_and_tiering",
    "rejected_false_duplicate_high_difficulty",
    "advisory_architecture_feasibility",
    "risks_evidence_gaps_mvp",
    "traceable_evidence_index",
}
PROJECT_CLASSIFICATION_POLICIES = {
    "project_classification_policy": "classify_after_goal_confirmation",
    "deliverable_product_discovery_policy": "required_before_production",
    "production_start_policy": (
        "deny_until_product_discovery_passed_or_coordination_exempt"
    ),
    "product_discovery_state_file": ".chief-of-staff/product-discovery.json",
}
STATUS_HEADINGS = (
    "最终目标", "当前阶段", "产品分类与发现门", "已验证事实", "推断",
    "待确认项", "待批复汇报", "正在工作的岗位", "距最终交付的差距",
    "风险", "下一步", "下一检查点",
)


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


def migrate_mutable_state(
    relative: Path,
    value: object,
    *,
    legacy_upgrade: bool = False,
    legacy_task_ids: set[str] | None = None,
    legacy_phase_ids: set[str] | None = None,
) -> tuple[object, bool]:
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
            task_id = task.get("task_id")
            if (
                "work_class" not in task
                and legacy_upgrade
                and isinstance(task_id, str)
                and task_id in (legacy_task_ids or set())
            ):
                task["work_class"] = "legacy_existing"
                changed = True

    if relative.name == "project-plan.json" and isinstance(value.get("phases"), list):
        for phase in value["phases"]:
            if not isinstance(phase, dict):
                continue
            phase_id = phase.get("phase_id")
            if (
                "phase_class" not in phase
                and legacy_upgrade
                and isinstance(phase_id, str)
                and phase_id in (legacy_phase_ids or set())
            ):
                phase["phase_class"] = "legacy_existing"
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


def legacy_allowlist_digest(phase_ids: set[str], task_ids: set[str]) -> str:
    payload = {
        "phase_ids": sorted(phase_ids),
        "task_ids": sorted(task_ids),
    }
    return hashlib.sha256(encoded_json(payload)).hexdigest()


def traceable_ref_error(target: Path, ref: object, *, artifact: bool = False) -> str | None:
    if not isinstance(ref, str) or not ref:
        return "must be a non-empty reference"
    if ref.startswith("repo://"):
        relative_text = ref.removeprefix("repo://")
        relative_path = Path(relative_text)
        if (
            not relative_text
            or relative_path.is_absolute()
            or ".." in relative_path.parts
        ):
            return "contains an unsafe repository path"
        resolved = (target / relative_path).resolve()
        try:
            resolved.relative_to(target.resolve())
        except ValueError:
            return "escapes the project root"
        if not resolved.is_file():
            return "does not resolve to a project file"
        return None
    if ref.startswith(("https://", "user://", "record://")):
        return None
    return (
        "must use repo:// for a project file or a traceable https://, user://, or record:// reference"
        if not artifact
        else "must use repo://, https://, user://, or record://"
    )


def migrate_status_text(text: str) -> tuple[str, bool]:
    heading = "## 产品分类与发现门"
    if heading in text:
        return text, False
    marker = "## 已验证事实"
    if marker not in text:
        return text, False
    section = (
        "## 产品分类与发现门\n\n"
        "- Classification: legacy unclassified.\n"
        "- Product discovery gate: legacy pending.\n"
        "- Production execution: no new phase until classification and the applicable gate.\n\n"
    )
    return text.replace(marker, section + marker, 1), True


def read_json_object(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def legacy_product_discovery(
    rendered_template: bytes,
    *,
    phase_ids: set[str],
    task_ids: set[str],
) -> bytes:
    state = json.loads(rendered_template.decode("utf-8"))
    state["classification_status"] = "legacy_unclassified"
    state["gate_status"] = "legacy_pending"
    state["legacy_allowlist"] = {
        "phase_ids": sorted(phase_ids),
        "task_ids": sorted(task_ids),
    }
    state["migration_note"] = (
        "Existing work was preserved as legacy state; classify the project and pass "
        "the required product gate before adding production execution."
    )
    return encoded_json(state)


def grandfathered_pin_state(rendered_template: bytes) -> bytes:
    state = json.loads(rendered_template.decode("utf-8"))
    state.update(
        {
            "role_class": "grandfathered_optional_chief",
            "authorization_status": "grandfathered_pending_review",
            "pin_status": "grandfathered_preserved",
            "successor_inheritance_eligible": False,
        }
    )
    return encoded_json(state)


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
                "project_classification_policy",
                "deliverable_product_discovery_policy", "production_start_policy",
                "product_discovery_state_file", "legacy_allowlist_digest",
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
            "project_classification_policy",
            "deliverable_product_discovery_policy", "production_start_policy",
            "product_discovery_state_file",
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
        allowlist_digest = value.get("legacy_allowlist_digest")
        if allowlist_digest is not None and (
            not isinstance(allowlist_digest, str)
            or len(allowlist_digest) != 64
            or any(character not in "0123456789abcdef" for character in allowlist_digest)
        ):
            errors.append(f"legacy_allowlist_digest in {relative} must be a SHA-256 hex string or null")
        max_depth = value.get("max_management_depth")
        if not isinstance(max_depth, int) or isinstance(max_depth, bool) or max_depth < 1:
            errors.append(f"max_management_depth in {relative} must be a positive integer")
        if value.get("execution_mode") != "effective_throughput":
            errors.append(f"execution_mode in {relative} must be 'effective_throughput'")
        for key, expected_value in PROJECT_CLASSIFICATION_POLICIES.items():
            if value.get(key) != expected_value:
                errors.append(f"{key} in {relative} must be {expected_value!r}")
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
                        "phase_id", "title", "objective", "status", "phase_class",
                        "acceptance_criteria", "task_ids", "result_summary",
                    },
                    Path(label),
                    errors,
                )
                for key in ("phase_id", "title", "objective", "phase_class"):
                    if key in phase and not isinstance(phase[key], str):
                        errors.append(f"{key} in {label} must be a string")
                phase_id = phase.get("phase_id")
                if isinstance(phase_id, str):
                    if phase_id in seen_phase_ids:
                        errors.append(f"duplicate phase_id in {relative}: {phase_id}")
                    seen_phase_ids.add(phase_id)
                if phase.get("status") not in phase_statuses:
                    errors.append(f"status in {label} is invalid")
                if phase.get("phase_class") not in {
                    "goal_discovery", "product_discovery", "production",
                    "coordination", "legacy_existing",
                }:
                    errors.append(f"phase_class in {label} is invalid")
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

    elif relative.name == "pin-state.json":
        require_keys(
            value,
            {
                "schema_version", "role_class", "authorization_status",
                "operator_approval_ref", "recommendation_ref", "pin_status",
                "verified_thread_id", "verified_at",
                "successor_inheritance_eligible", "capacity_status",
                "exclusion_reasons", "successor",
            },
            relative,
            errors,
        )
        role_class = value.get("role_class")
        authorization_status = value.get("authorization_status")
        pin_status = value.get("pin_status")
        if role_class not in {
            "ordinary_chief", "mandatory_core", "approved_optional_chief",
            "grandfathered_optional_chief",
        }:
            errors.append(f"role_class in {relative} is invalid")
        if authorization_status not in {
            "not_required", "not_requested", "pending", "approved",
            "grandfathered_pending_review", "revoked",
        }:
            errors.append(f"authorization_status in {relative} is invalid")
        if pin_status not in {
            "unpinned", "pending_verification", "verified", "verification_failed",
            "capacity_waiting", "grandfathered_preserved", "superseded",
        }:
            errors.append(f"pin_status in {relative} is invalid")
        for key in (
            "operator_approval_ref", "recommendation_ref", "verified_thread_id",
            "verified_at",
        ):
            if value.get(key) is not None and not isinstance(value.get(key), str):
                errors.append(f"{key} in {relative} must be a string or null")
        if not isinstance(value.get("successor_inheritance_eligible"), bool):
            errors.append(f"successor_inheritance_eligible in {relative} must be boolean")
        if value.get("capacity_status") not in {"not_checked", "available", "full"}:
            errors.append(f"capacity_status in {relative} is invalid")
        exclusions = value.get("exclusion_reasons")
        if not isinstance(exclusions, list) or not all(
            isinstance(item, str) and item for item in exclusions
        ):
            errors.append(f"exclusion_reasons in {relative} must be non-empty strings")
        elif len(exclusions) != len(set(exclusions)):
            errors.append(f"exclusion_reasons in {relative} must not contain duplicates")

        successor = value.get("successor")
        if not isinstance(successor, dict):
            errors.append(f"successor in {relative} must be an object")
            successor = {}
        require_keys(
            successor,
            {
                "candidate_thread_id", "migration_ready", "exact_list_verified",
                "takeover_accepted", "predecessor_archived", "replacement_count",
                "same_lineage", "safe_handoff",
            },
            Path(f"{relative} successor"),
            errors,
        )
        if successor.get("candidate_thread_id") is not None and not isinstance(
            successor.get("candidate_thread_id"), str
        ):
            errors.append(f"successor.candidate_thread_id in {relative} must be string or null")
        for key in (
            "migration_ready", "exact_list_verified", "takeover_accepted",
            "predecessor_archived", "same_lineage", "safe_handoff",
        ):
            if not isinstance(successor.get(key), bool):
                errors.append(f"successor.{key} in {relative} must be boolean")
        replacement_count = successor.get("replacement_count")
        if (
            not isinstance(replacement_count, int)
            or isinstance(replacement_count, bool)
            or replacement_count not in {0, 1}
        ):
            errors.append(f"successor.replacement_count in {relative} must be 0 or 1")

        eligible = value.get("successor_inheritance_eligible") is True
        if role_class == "ordinary_chief":
            if authorization_status not in {"not_requested", "pending", "revoked"}:
                errors.append(f"ordinary_chief in {relative} cannot be pin-approved")
            if pin_status not in {"unpinned", "capacity_waiting", "superseded"}:
                errors.append(f"ordinary_chief in {relative} must remain unpinned")
            if eligible:
                errors.append(f"ordinary_chief in {relative} cannot inherit a pin")
        if role_class == "mandatory_core":
            if authorization_status != "not_required" or not eligible:
                errors.append(f"mandatory_core in {relative} requires inherited pin eligibility")
            if pin_status not in {
                "pending_verification", "verified", "verification_failed", "capacity_waiting",
            }:
                errors.append(f"mandatory_core in {relative} requires an active pin workflow")
        if role_class == "approved_optional_chief":
            if (
                authorization_status != "approved"
                or not value.get("operator_approval_ref")
                or not value.get("recommendation_ref")
                or not eligible
            ):
                errors.append(f"approved_optional_chief in {relative} requires recommendation and operator approval")
            if pin_status not in {
                "pending_verification", "verified", "verification_failed", "capacity_waiting",
            }:
                errors.append(f"approved_optional_chief in {relative} requires an approved pin workflow")
        if role_class == "grandfathered_optional_chief":
            if authorization_status != "grandfathered_pending_review":
                errors.append(f"grandfathered_optional_chief in {relative} requires pending value review")
            if pin_status not in {"grandfathered_preserved", "verified", "superseded"}:
                errors.append(f"grandfathered_optional_chief in {relative} has invalid pin state")
            if eligible:
                errors.append(f"grandfathered_optional_chief in {relative} cannot create a replacement before approval")
        if authorization_status == "pending" and not value.get("recommendation_ref"):
            errors.append(f"pending pin authorization in {relative} requires recommendation_ref")
        if pin_status == "verified":
            if not value.get("verified_thread_id") or not value.get("verified_at"):
                errors.append(f"verified pin in {relative} requires exact thread ID and verification time")
        elif value.get("verified_thread_id") is not None or value.get("verified_at") is not None:
            errors.append(f"unverified pin in {relative} cannot retain verified thread evidence")
        if pin_status == "verification_failed" and not eligible:
            errors.append(f"pin verification failure in {relative} is valid only for mandatory or approved lineage")

        progressed = any(
            successor.get(key) is True
            for key in (
                "migration_ready", "exact_list_verified", "takeover_accepted",
                "predecessor_archived", "same_lineage", "safe_handoff",
            )
        ) or replacement_count == 1 or successor.get("candidate_thread_id") is not None
        if progressed and not eligible:
            errors.append(f"successor flow in {relative} requires mandatory or approved lineage")
        if successor.get("exact_list_verified") is True and not successor.get("migration_ready"):
            errors.append(f"successor exact-list verification in {relative} requires MIGRATION_READY")
        if successor.get("takeover_accepted") is True and not (
            successor.get("migration_ready") is True
            and successor.get("exact_list_verified") is True
            and successor.get("same_lineage") is True
            and pin_status == "verified"
            and successor.get("candidate_thread_id") == value.get("verified_thread_id")
        ):
            errors.append(f"successor takeover in {relative} requires same-lineage exact-ID pin verification")
        if successor.get("predecessor_archived") is True and not successor.get("takeover_accepted"):
            errors.append(f"predecessor archival in {relative} requires verified successor takeover")
        if replacement_count == 1 and not (
            eligible
            and successor.get("migration_ready") is True
            and successor.get("same_lineage") is True
            and successor.get("safe_handoff") is True
        ):
            errors.append(f"replacement in {relative} requires one safe same-lineage handoff")

    elif relative.name == "product-discovery.json":
        require_keys(
            value,
            {
                "schema_version", "classification_status", "project_classification",
                "classification_reason", "classified_at",
                "classification_evidence_refs", "product_manager_required",
                "exemption_reason", "gate_status", "product_manager", "lanes",
                "required_deliverables", "synthesis_coverage", "evidence_index", "gate_decision",
                "guardrails", "legacy_allowlist", "migration_note",
            },
            relative,
            errors,
        )
        classification_status = value.get("classification_status")
        project_classification = value.get("project_classification")
        gate_status = value.get("gate_status")
        if classification_status not in {"pending", "classified", "legacy_unclassified"}:
            errors.append(f"classification_status in {relative} is invalid")
        if project_classification not in {
            "unclassified", "deliverable_project", "coordination_only"
        }:
            errors.append(f"project_classification in {relative} is invalid")
        if gate_status not in {
            "awaiting_classification", "legacy_pending", "awaiting_product_manager",
            "in_progress", "blocked", "passed", "exempt",
        }:
            errors.append(f"gate_status in {relative} is invalid")
        if not isinstance(value.get("classification_reason"), str):
            errors.append(f"classification_reason in {relative} must be a string")
        for key in ("classified_at", "exemption_reason", "migration_note"):
            if value.get(key) is not None and not isinstance(value.get(key), str):
                errors.append(f"{key} in {relative} must be a string or null")
        classification_refs = value.get("classification_evidence_refs")
        if not isinstance(classification_refs, list) or not all(
            isinstance(item, str) for item in classification_refs
        ):
            errors.append(
                f"classification_evidence_refs in {relative} must be an array of strings"
            )
        product_manager_required = value.get("product_manager_required")
        if product_manager_required is not None and not isinstance(
            product_manager_required, bool
        ):
            errors.append(f"product_manager_required in {relative} must be boolean or null")

        product_manager = value.get("product_manager")
        if not isinstance(product_manager, dict):
            errors.append(f"product_manager in {relative} must be an object")
            product_manager = {}
        require_keys(
            product_manager,
            {
                "owner_id", "owner_kind", "management_depth", "runtime_mode",
                "runtime_limitation",
            },
            Path(f"{relative} product_manager"),
            errors,
        )
        for key in ("owner_id", "runtime_limitation"):
            if product_manager.get(key) is not None and not isinstance(
                product_manager.get(key), str
            ):
                errors.append(f"product_manager.{key} in {relative} must be string or null")
        if product_manager.get("owner_kind") not in {None, "durable_task", "temporary_subagent"}:
            errors.append(f"product_manager.owner_kind in {relative} is invalid")
        if product_manager.get("management_depth") != 2:
            errors.append(f"product_manager.management_depth in {relative} must be 2")
        runtime_mode = product_manager.get("runtime_mode")
        if runtime_mode not in {
            "unassigned", "four_temporary_helpers", "pm_single_task_fallback",
        }:
            errors.append(f"product_manager.runtime_mode in {relative} is invalid")

        lanes = value.get("lanes")
        if not isinstance(lanes, dict) or set(lanes) != PRODUCT_DISCOVERY_LANES:
            errors.append(f"lanes in {relative} must contain the four required lanes")
            lanes = {}
        lane_statuses = {"pending", "active", "blocked", "verified", "not_applicable"}
        lane_modes = {"unassigned", "temporary_helper", "product_manager_fallback", "not_applicable"}
        for lane_id in PRODUCT_DISCOVERY_LANES:
            lane = lanes.get(lane_id)
            label = Path(f"{relative} lanes.{lane_id}")
            if not isinstance(lane, dict):
                errors.append(f"{label} must be an object")
                continue
            require_keys(
                lane,
                {
                    "status", "execution_mode", "owner_id", "management_depth",
                    "delegation_allowed", "artifact_refs", "evidence_refs",
                },
                label,
                errors,
            )
            if lane.get("status") not in lane_statuses:
                errors.append(f"status in {label} is invalid")
            if lane.get("execution_mode") not in lane_modes:
                errors.append(f"execution_mode in {label} is invalid")
            if lane.get("owner_id") is not None and not isinstance(lane.get("owner_id"), str):
                errors.append(f"owner_id in {label} must be a string or null")
            if lane.get("management_depth") not in {2, 3}:
                errors.append(f"management_depth in {label} must be 2 or 3")
            if lane.get("delegation_allowed") is not False:
                errors.append(f"delegation_allowed in {label} must be false")
            for key in ("artifact_refs", "evidence_refs"):
                refs = lane.get(key)
                if not isinstance(refs, list) or not all(isinstance(item, str) for item in refs):
                    errors.append(f"{key} in {label} must be an array of strings")

        deliverables = value.get("required_deliverables")
        if not isinstance(deliverables, dict) or set(deliverables) != PRODUCT_DISCOVERY_DELIVERABLES:
            errors.append(
                f"required_deliverables in {relative} must contain every required deliverable"
            )
            deliverables = {}
        for deliverable_id in PRODUCT_DISCOVERY_DELIVERABLES:
            deliverable = deliverables.get(deliverable_id)
            label = Path(f"{relative} required_deliverables.{deliverable_id}")
            if not isinstance(deliverable, dict):
                errors.append(f"{label} must be an object")
                continue
            require_keys(
                deliverable, {"status", "artifact_refs", "evidence_refs"}, label, errors
            )
            if deliverable.get("status") not in lane_statuses:
                errors.append(f"status in {label} is invalid")
            for key in ("artifact_refs", "evidence_refs"):
                refs = deliverable.get(key)
                if not isinstance(refs, list) or not all(isinstance(item, str) for item in refs):
                    errors.append(f"{key} in {label} must be an array of strings")

        synthesis_coverage = value.get("synthesis_coverage")
        if (
            not isinstance(synthesis_coverage, dict)
            or set(synthesis_coverage) != PRODUCT_DISCOVERY_COVERAGE
        ):
            errors.append(
                f"synthesis_coverage in {relative} must contain every required topic"
            )
            synthesis_coverage = {}
        elif not all(isinstance(item, bool) for item in synthesis_coverage.values()):
            errors.append(f"synthesis_coverage in {relative} must contain booleans")

        evidence_index = value.get("evidence_index")
        if not isinstance(evidence_index, list):
            errors.append(f"evidence_index in {relative} must be an array")
            evidence_index = []
        seen_evidence_ids: set[str] = set()
        verified_evidence_ids: set[str] = set()
        for index, evidence in enumerate(evidence_index):
            label = Path(f"{relative} evidence_index[{index}]")
            if not isinstance(evidence, dict):
                errors.append(f"{label} must be an object")
                continue
            require_keys(
                evidence,
                {
                    "evidence_id", "kind", "summary", "source_ref",
                    "verification_method", "verified_at",
                },
                label,
                errors,
            )
            for key in ("evidence_id", "summary"):
                if not isinstance(evidence.get(key), str) or not evidence.get(key):
                    errors.append(f"{key} in {label} must be a non-empty string")
            evidence_id = evidence.get("evidence_id")
            if isinstance(evidence_id, str):
                if evidence_id in seen_evidence_ids:
                    errors.append(f"duplicate evidence_id in {relative}: {evidence_id}")
                seen_evidence_ids.add(evidence_id)
            if evidence.get("kind") not in {"verified_fact", "assumption", "open_question"}:
                errors.append(f"kind in {label} is invalid")
            source_ref = evidence.get("source_ref")
            if source_ref is not None and not isinstance(source_ref, str):
                errors.append(f"source_ref in {label} must be a string or null")
            for key in ("verification_method", "verified_at"):
                if evidence.get(key) is not None and not isinstance(evidence.get(key), str):
                    errors.append(f"{key} in {label} must be a string or null")
            if evidence.get("kind") == "verified_fact" and (
                not source_ref
                or not evidence.get("verification_method")
                or not evidence.get("verified_at")
            ):
                errors.append(
                    f"verified_fact in {label} requires source, verification method, and time"
                )
            elif evidence.get("kind") == "verified_fact" and isinstance(evidence_id, str):
                verified_evidence_ids.add(evidence_id)

        gate_decision = value.get("gate_decision")
        if not isinstance(gate_decision, dict):
            errors.append(f"gate_decision in {relative} must be an object")
            gate_decision = {}
        require_keys(
            gate_decision,
            {
                "decision", "conditions", "material_direction_status", "review_route",
                "review_status", "decision_ref",
            },
            Path(f"{relative} gate_decision"),
            errors,
        )
        if gate_decision.get("decision") not in {
            "undecided", "proceed", "conditional_proceed", "do_not_proceed",
            "not_applicable",
        }:
            errors.append(f"gate_decision.decision in {relative} is invalid")
        conditions = gate_decision.get("conditions")
        if not isinstance(conditions, list) or not all(isinstance(item, str) for item in conditions):
            errors.append(f"gate_decision.conditions in {relative} must be an array of strings")
        if gate_decision.get("material_direction_status") not in {
            "no_conflict", "resolved_by_evidence", "operator_required",
            "operator_confirmed", "not_applicable",
        }:
            errors.append(f"gate_decision.material_direction_status in {relative} is invalid")
        if gate_decision.get("review_route") not in {"chief", "operator", "not_applicable"}:
            errors.append(f"gate_decision.review_route in {relative} is invalid")
        if gate_decision.get("review_status") not in {
            "pending", "approved", "changes_requested", "not_applicable"
        }:
            errors.append(f"gate_decision.review_status in {relative} is invalid")
        if gate_decision.get("decision_ref") is not None and not isinstance(
            gate_decision.get("decision_ref"), str
        ):
            errors.append(f"gate_decision.decision_ref in {relative} must be string or null")

        expected_guardrails = {
            "architecture_output": "advisory_non_binding",
            "visual_direction": "creative_director_only",
            "protected_actions": "separate_explicit_approval",
        }
        if value.get("guardrails") != expected_guardrails:
            errors.append(f"guardrails in {relative} must preserve architecture, visual, and approval boundaries")
        legacy_allowlist = value.get("legacy_allowlist")
        if not isinstance(legacy_allowlist, dict):
            errors.append(f"legacy_allowlist in {relative} must be an object")
            legacy_allowlist = {}
        require_keys(
            legacy_allowlist, {"phase_ids", "task_ids"},
            Path(f"{relative} legacy_allowlist"), errors,
        )
        for key in ("phase_ids", "task_ids"):
            ids = legacy_allowlist.get(key)
            if not isinstance(ids, list) or not all(isinstance(item, str) for item in ids):
                errors.append(f"legacy_allowlist.{key} in {relative} must be an array of strings")
            elif len(ids) != len(set(ids)):
                errors.append(f"legacy_allowlist.{key} in {relative} must not contain duplicates")

        if classification_status == "pending":
            if project_classification != "unclassified" or gate_status != "awaiting_classification":
                errors.append(f"pending classification in {relative} must await classification")
            if value.get("product_manager_required") is not None:
                errors.append(f"pending classification in {relative} requires null product_manager_required")
        if classification_status == "legacy_unclassified":
            if project_classification != "unclassified" or gate_status != "legacy_pending":
                errors.append(f"legacy_unclassified in {relative} requires legacy_pending gate")
            if value.get("product_manager_required") is not None:
                errors.append(f"legacy_unclassified in {relative} requires null product_manager_required")
        if classification_status in {"pending", "legacy_unclassified"}:
            if product_manager.get("owner_id") is not None or runtime_mode != "unassigned":
                errors.append(f"unclassified state in {relative} cannot assign a product manager")
        if classification_status == "classified":
            if project_classification not in {"deliverable_project", "coordination_only"}:
                errors.append(f"classified state in {relative} requires a concrete project classification")
            if (
                not value.get("classification_reason")
                or not value.get("classified_at")
                or not classification_refs
            ):
                errors.append(f"classified state in {relative} requires reason, time, and evidence")
        if project_classification == "coordination_only":
            if classification_status != "classified" or value.get("product_manager_required") is not False:
                errors.append(f"coordination_only in {relative} must be classified with no product manager")
            if not value.get("exemption_reason") or gate_status != "exempt":
                errors.append(f"coordination_only in {relative} requires exemption_reason and exempt gate")
            if product_manager.get("owner_id") is not None or runtime_mode != "unassigned":
                errors.append(f"coordination_only in {relative} cannot assign a product manager")
            if any(lane.get("status") != "not_applicable" for lane in lanes.values() if isinstance(lane, dict)):
                errors.append(f"coordination_only in {relative} requires not_applicable lanes")
            if any(
                lane.get("execution_mode") != "not_applicable"
                or lane.get("owner_id") is not None
                for lane in lanes.values() if isinstance(lane, dict)
            ):
                errors.append(f"coordination_only in {relative} cannot retain discovery lane owners")
            if any(item.get("status") != "not_applicable" for item in deliverables.values() if isinstance(item, dict)):
                errors.append(f"coordination_only in {relative} requires not_applicable deliverables")
            if gate_decision.get("decision") != "not_applicable" or gate_decision.get("review_status") != "not_applicable":
                errors.append(f"coordination_only in {relative} requires not_applicable gate decision")
            if any(synthesis_coverage.values()):
                errors.append(f"coordination_only in {relative} cannot claim product synthesis coverage")
        if project_classification == "deliverable_project":
            if classification_status != "classified" or value.get("product_manager_required") is not True:
                errors.append(f"deliverable_project in {relative} must be classified and require a product manager")
            if gate_status not in {"awaiting_product_manager", "in_progress", "blocked", "passed"}:
                errors.append(f"deliverable_project gate_status in {relative} is invalid")
            if value.get("exemption_reason") is not None:
                errors.append(f"deliverable_project in {relative} cannot have exemption_reason")
            if any(
                lane.get("status") == "not_applicable"
                for lane in lanes.values() if isinstance(lane, dict)
            ) or any(
                item.get("status") == "not_applicable"
                for item in deliverables.values() if isinstance(item, dict)
            ):
                errors.append(f"deliverable_project in {relative} must restore every discovery requirement")
            if gate_status in {"in_progress", "blocked", "passed"}:
                if not product_manager.get("owner_id") or product_manager.get("owner_kind") not in {
                    "durable_task", "temporary_subagent"
                }:
                    errors.append(f"active product discovery in {relative} requires a product manager owner")
                if runtime_mode == "unassigned":
                    errors.append(f"active product discovery in {relative} requires an assigned runtime mode")
            if runtime_mode == "four_temporary_helpers":
                if not product_manager.get("owner_id"):
                    errors.append(f"four_temporary_helpers in {relative} requires product manager owner")
                helper_ids: list[str] = []
                for lane in lanes.values():
                    if not isinstance(lane, dict):
                        continue
                    if lane.get("execution_mode") != "temporary_helper" or lane.get("management_depth") != 3:
                        errors.append(f"four_temporary_helpers in {relative} requires depth-3 temporary_helper lanes")
                    if not lane.get("owner_id"):
                        errors.append(f"four_temporary_helpers in {relative} requires lane owner IDs")
                    elif lane.get("owner_id") == product_manager.get("owner_id"):
                        errors.append(f"four_temporary_helpers in {relative} cannot use PM as helper owner")
                    else:
                        helper_ids.append(lane["owner_id"])
                if len(helper_ids) != len(set(helper_ids)):
                    errors.append(f"four_temporary_helpers in {relative} requires distinct helper owners")
            if runtime_mode == "pm_single_task_fallback":
                if not product_manager.get("runtime_limitation"):
                    errors.append(f"pm_single_task_fallback in {relative} requires runtime_limitation")
                for lane in lanes.values():
                    if not isinstance(lane, dict):
                        continue
                    if (
                        lane.get("execution_mode") != "product_manager_fallback"
                        or lane.get("management_depth") != 2
                        or lane.get("owner_id") != product_manager.get("owner_id")
                    ):
                        errors.append(f"pm_single_task_fallback in {relative} requires every lane owned by the PM at depth 2")
            if gate_status == "passed":
                if runtime_mode not in {"four_temporary_helpers", "pm_single_task_fallback"}:
                    errors.append(f"passed gate in {relative} requires a completed runtime mode")
                if any(
                    lane.get("status") != "verified"
                    or not lane.get("artifact_refs")
                    or not lane.get("evidence_refs")
                    for lane in lanes.values() if isinstance(lane, dict)
                ):
                    errors.append(f"passed gate in {relative} requires verified lane artifacts and evidence")
                if any(
                    item.get("status") != "verified"
                    or not item.get("artifact_refs")
                    or not item.get("evidence_refs")
                    for item in deliverables.values() if isinstance(item, dict)
                ):
                    errors.append(f"passed gate in {relative} requires every verified deliverable")
                if not evidence_index:
                    errors.append(f"passed gate in {relative} requires evidence_index")
                if any(
                    not verified_evidence_ids.intersection(lane.get("evidence_refs", []))
                    for lane in lanes.values() if isinstance(lane, dict)
                ):
                    errors.append(f"passed gate in {relative} requires verified-fact evidence for every lane")
                if any(
                    not verified_evidence_ids.intersection(item.get("evidence_refs", []))
                    for item in deliverables.values() if isinstance(item, dict)
                ):
                    errors.append(f"passed gate in {relative} requires verified-fact evidence for every deliverable")
                if not synthesis_coverage or not all(synthesis_coverage.values()):
                    errors.append(f"passed gate in {relative} requires complete synthesis coverage")
                if gate_decision.get("decision") not in {"proceed", "conditional_proceed"}:
                    errors.append(f"passed gate in {relative} requires proceed decision")
                if gate_decision.get("decision") == "conditional_proceed" and not conditions:
                    errors.append(f"conditional_proceed in {relative} requires conditions")
                if gate_decision.get("material_direction_status") == "operator_required":
                    errors.append(f"passed gate in {relative} cannot retain operator_required direction")
                if gate_decision.get("review_status") != "approved" or not gate_decision.get("decision_ref"):
                    errors.append(f"passed gate in {relative} requires approved review with decision_ref")

    elif relative.name == "task-registry.json":
        require_keys(value, {"schema_version", "tasks"}, relative, errors)
        tasks = value.get("tasks")
        if not isinstance(tasks, list):
            errors.append(f"tasks in {relative} must be an array")
            return
        required_task_keys = {
            "task_id", "host_id", "title", "role", "objective", "status",
            "work_class",
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
            if task.get("work_class") not in {
                "goal_discovery", "product_discovery", "production_execution",
                "coordination_only", "legacy_existing",
            }:
                errors.append(f"work_class in {label} is invalid")
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

    status_path = target / ".chief-of-staff" / "status.md"
    if status_path.is_file():
        try:
            status_text = status_path.read_text(encoding="utf-8")
            for heading in STATUS_HEADINGS:
                if f"## {heading}" not in status_text:
                    errors.append(f"status.md is missing required heading: {heading}")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"invalid status.md: {exc}")

    for relative in (
        Path(".chief-of-staff/project.json"),
        Path(".chief-of-staff/pin-state.json"),
        Path(".chief-of-staff/product-discovery.json"),
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

    project_path = target / ".chief-of-staff" / "project.json"
    discovery_path = target / ".chief-of-staff" / "product-discovery.json"
    plan_path = target / ".chief-of-staff" / "project-plan.json"
    registry_path = target / ".chief-of-staff" / "task-registry.json"
    pin_state_path = target / ".chief-of-staff" / "pin-state.json"
    if project_path.is_file() and pin_state_path.is_file():
        try:
            project = json.loads(project_path.read_text(encoding="utf-8"))
            pin_state = json.loads(pin_state_path.read_text(encoding="utf-8"))
            pin_primary = project.get("pin_primary_task")
            role_class = pin_state.get("role_class")
            if role_class == "ordinary_chief" and pin_primary is not False:
                errors.append("ordinary Chief requires pin_primary_task=false")
            if role_class in {"mandatory_core", "approved_optional_chief"} and pin_primary is not True:
                errors.append("mandatory or approved optional Chief requires pin_primary_task=true")
            if role_class == "grandfathered_optional_chief" and pin_primary is not True:
                errors.append("grandfathered optional Chief preserves pin_primary_task=true pending review")
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            pass
    if all(path.is_file() for path in (project_path, discovery_path, plan_path, registry_path)):
        try:
            project = json.loads(project_path.read_text(encoding="utf-8"))
            discovery = json.loads(discovery_path.read_text(encoding="utf-8"))
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            tasks = registry.get("tasks") if isinstance(registry, dict) else None
            phases = plan.get("phases") if isinstance(plan, dict) else None
            task_list = tasks if isinstance(tasks, list) else []
            phase_list = phases if isinstance(phases, list) else []
            if isinstance(plan, dict) and plan.get("project_status") == "active":
                current_phase_id = plan.get("current_phase_id")
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

            if isinstance(project, dict):
                for key, expected_value in PROJECT_CLASSIFICATION_POLICIES.items():
                    if project.get(key) != expected_value:
                        errors.append(f"project policy {key} does not match product-discovery governance")

            if isinstance(discovery, dict) and isinstance(plan, dict):
                classification_status = discovery.get("classification_status")
                classification = discovery.get("project_classification")
                gate_status = discovery.get("gate_status")
                goal_status = plan.get("goal_status")
                allowlist = discovery.get("legacy_allowlist")
                allowed_legacy_tasks = set(
                    allowlist.get("task_ids", []) if isinstance(allowlist, dict) else []
                )
                allowed_legacy_phases = set(
                    allowlist.get("phase_ids", []) if isinstance(allowlist, dict) else []
                )
                expected_allowlist_digest = legacy_allowlist_digest(
                    allowed_legacy_phases, allowed_legacy_tasks
                )
                stored_allowlist_digest = project.get("legacy_allowlist_digest")
                if classification_status == "legacy_unclassified" or (
                    allowed_legacy_tasks or allowed_legacy_phases
                ):
                    if stored_allowlist_digest != expected_allowlist_digest:
                        errors.append(
                            "legacy allowlist does not match the immutable project digest"
                        )
                elif stored_allowlist_digest is not None:
                    errors.append(
                        "non-legacy project cannot retain a legacy allowlist digest"
                    )

                evidence_index = discovery.get("evidence_index")
                evidence_ids = {
                    item.get("evidence_id")
                    for item in evidence_index if isinstance(item, dict)
                } if isinstance(evidence_index, list) else set()
                for item in (evidence_index if isinstance(evidence_index, list) else []):
                    if not isinstance(item, dict) or item.get("kind") != "verified_fact":
                        continue
                    source_error = traceable_ref_error(target, item.get("source_ref"))
                    if source_error:
                        errors.append(
                            f"evidence {item.get('evidence_id')!r} source_ref {source_error}"
                        )

                evidence_holders: list[tuple[str, dict]] = []
                for group_name in ("lanes", "required_deliverables"):
                    group = discovery.get(group_name)
                    if not isinstance(group, dict):
                        continue
                    evidence_holders.extend(
                        (f"{group_name}.{item_id}", item)
                        for item_id, item in group.items() if isinstance(item, dict)
                    )
                for label, item in evidence_holders:
                    for evidence_ref in item.get("evidence_refs", []):
                        if evidence_ref not in evidence_ids:
                            errors.append(
                                f"{label} references unknown evidence ID {evidence_ref!r}"
                            )
                    for artifact_ref in item.get("artifact_refs", []):
                        artifact_error = traceable_ref_error(
                            target, artifact_ref, artifact=True
                        )
                        if artifact_error:
                            errors.append(
                                f"{label} artifact {artifact_ref!r} {artifact_error}"
                            )

                for task in task_list:
                    if not isinstance(task, dict):
                        continue
                    task_id = task.get("task_id")
                    if task.get("work_class") == "legacy_existing" and task_id not in allowed_legacy_tasks:
                        errors.append(
                            f"task {task_id!r} claims legacy_existing but is not in the migration allowlist"
                        )
                for phase in phase_list:
                    if not isinstance(phase, dict):
                        continue
                    phase_id = phase.get("phase_id")
                    if phase.get("phase_class") == "legacy_existing" and phase_id not in allowed_legacy_phases:
                        errors.append(
                            f"phase {phase_id!r} claims legacy_existing but is not in the migration allowlist"
                        )

                nonlegacy_tasks = [
                    task for task in task_list
                    if isinstance(task, dict) and task.get("work_class") != "legacy_existing"
                ]
                nonlegacy_phases = [
                    phase for phase in phase_list
                    if isinstance(phase, dict) and phase.get("phase_class") != "legacy_existing"
                ]
                if goal_status == "unconfirmed":
                    if classification_status == "classified":
                        errors.append("project classification requires a confirmed goal")
                    if any(task.get("work_class") != "goal_discovery" for task in nonlegacy_tasks):
                        errors.append("unconfirmed goal permits only goal_discovery tasks")
                    if any(phase.get("phase_class") != "goal_discovery" for phase in nonlegacy_phases):
                        errors.append("unconfirmed goal permits only goal_discovery phases")
                elif goal_status == "confirmed" and classification_status == "pending":
                    errors.append("confirmed goal requires project classification")
                elif goal_status == "confirmed" and classification_status == "legacy_unclassified":
                    if nonlegacy_tasks or nonlegacy_phases:
                        errors.append(
                            "legacy project requires classification before new tasks or phases"
                        )

                if classification == "coordination_only":
                    if any(
                        task.get("work_class") in {"product_discovery", "production_execution"}
                        for task in nonlegacy_tasks
                    ) or any(
                        phase.get("phase_class") in {"product_discovery", "production"}
                        for phase in nonlegacy_phases
                    ):
                        errors.append(
                            "coordination_only project cannot create product-discovery or production work; reclassify first"
                        )

                if classification == "deliverable_project" and gate_status != "passed":
                    if any(
                        task.get("work_class") == "production_execution"
                        for task in nonlegacy_tasks
                    ) or any(
                        phase.get("phase_class") == "production"
                        for phase in nonlegacy_phases
                    ):
                        errors.append(
                            "production execution is denied until the product-discovery gate passes"
                        )

                product_manager = discovery.get("product_manager")
                if isinstance(product_manager, dict) and product_manager.get("owner_kind") == "durable_task":
                    owner_id = product_manager.get("owner_id")
                    owner = next(
                        (
                            task for task in task_list
                            if isinstance(task, dict) and task.get("task_id") == owner_id
                        ),
                        None,
                    )
                    if not isinstance(owner, dict):
                        errors.append("durable product manager owner must exist in task-registry.json")
                    else:
                        if owner.get("management_depth") != 2:
                            errors.append("durable product manager must have management_depth 2")
                        if owner.get("work_class") != "product_discovery":
                            errors.append("durable product manager must use work_class product_discovery")
                        if gate_status == "passed" and owner.get("status") not in {
                            "completed", "archived"
                        }:
                            errors.append("passed product-discovery gate requires completed product manager task")
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

    existing_project = read_json_object(target / ".chief-of-staff" / "project.json")
    discovery_path = target / ".chief-of-staff" / "product-discovery.json"
    pin_state_path = target / ".chief-of-staff" / "pin-state.json"
    legacy_upgrade = bool(
        existing_project is not None
        and (
            not discovery_path.is_file()
            or any(key not in existing_project for key in PROJECT_CLASSIFICATION_POLICIES)
        )
    )
    legacy_pin_upgrade = bool(
        existing_project is not None
        and existing_project.get("pin_primary_task") is True
        and not pin_state_path.is_file()
    )
    existing_plan = read_json_object(target / ".chief-of-staff" / "project-plan.json")
    existing_registry = read_json_object(target / ".chief-of-staff" / "task-registry.json")
    legacy_phase_ids = {
        phase["phase_id"]
        for phase in (existing_plan or {}).get("phases", [])
        if isinstance(phase, dict) and isinstance(phase.get("phase_id"), str)
    }
    legacy_task_ids = {
        task["task_id"]
        for task in (existing_registry or {}).get("tasks", [])
        if isinstance(task, dict) and isinstance(task.get("task_id"), str)
    }

    for source, relative in files:
        destination = target / relative
        expected = render(source, project_name, preferences)
        if (
            relative == Path(".chief-of-staff/product-discovery.json")
            and legacy_upgrade
            and not destination.exists()
        ):
            expected = legacy_product_discovery(
                expected,
                phase_ids=legacy_phase_ids,
                task_ids=legacy_task_ids,
            )
        if relative == Path(".chief-of-staff/pin-state.json") and legacy_pin_upgrade:
            expected = grandfathered_pin_state(expected)
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
                        value, changed = migrate_mutable_state(
                            relative,
                            value,
                            legacy_upgrade=legacy_upgrade,
                            legacy_task_ids=legacy_task_ids,
                            legacy_phase_ids=legacy_phase_ids,
                        )
                        state_errors: list[str] = []
                        validate_state(relative, value, state_errors)
                        if state_errors:
                            raise ValueError("; ".join(state_errors))
                        if changed:
                            planned.append((destination, encoded_json(value)))
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
                        conflicts.append(relative)
                        continue
                elif relative.name == "status.md":
                    try:
                        status_text = destination.read_text(encoding="utf-8")
                        migrated_status, changed = migrate_status_text(status_text)
                        if changed:
                            planned.append((destination, migrated_status.encode("utf-8")))
                    except (OSError, UnicodeDecodeError):
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
            if destination.read_bytes() == expected and not (
                relative == Path(".chief-of-staff/project.json") and legacy_upgrade
            ):
                continue
            if relative == Path(".chief-of-staff/project.json"):
                try:
                    existing_project = json.loads(destination.read_text(encoding="utf-8"))
                    expected_project = json.loads(expected.decode("utf-8"))
                    grandfathered_project = dict(expected_project)
                    grandfathered_project["pin_primary_task"] = True
                    if legacy_pin_upgrade and existing_project == grandfathered_project:
                        continue
                    # Upgrade an older managed project by adding only missing defaults.
                    upgraded_project = dict(existing_project)
                    project_changed = False
                    if legacy_upgrade and not upgraded_project.get("legacy_allowlist_digest"):
                        upgraded_project["legacy_allowlist_digest"] = legacy_allowlist_digest(
                            legacy_phase_ids, legacy_task_ids
                        )
                        project_changed = True
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
                        "project_classification_policy",
                        "deliverable_product_discovery_policy", "production_start_policy",
                        "product_discovery_state_file", "legacy_allowlist_digest",
                    ):
                        if key not in upgraded_project:
                            upgraded_project[key] = (
                                legacy_allowlist_digest(legacy_phase_ids, legacy_task_ids)
                                if key == "legacy_allowlist_digest" and legacy_upgrade
                                else expected_project[key]
                            )
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
                product_discovery_gate = """\n## Product classification and discovery gate\n\n- After the initial mission and goal boundary are confirmed, classify the project in `.chief-of-staff/product-discovery.json` before creating another phase or role. `deliverable_project` creates or materially changes a product, service, code, design, content asset, or other acceptance-tested deliverable. `coordination_only` is limited to synchronization, pushing an already-decided change, meeting summaries, filing/process follow-up, or read-only audit/aggregation and requires a concrete exemption reason.\n- A scope expansion from coordination into product creation immediately invalidates the exemption. Reclassify as `deliverable_project`, appoint one Product Manager phase lead at management depth 2, and complete the gate before production execution.\n- The Product Manager is not a Chief and does not create a second control plane. It owns four bounded evidence lanes: project initiation, requirements analysis, market research, and advisory architecture feasibility. Each temporary helper is depth 3, read-only by default, cannot delegate again, and cannot create a durable role. If the runtime lacks subagents, the Product Manager completes all four lanes in one task, records the runtime limitation, and preserves separate artifacts and evidence for every lane.\n- Before the gate passes, permit only goal clarification, product-discovery research, and reversible planning. Do not create or start engineering, design, content production, or another production-execution role or phase. Run `python3 scripts/init_project.py --target <project-root> --check` immediately before any production task is created or started; a nonzero result is a hard stop.\n- Gate evidence never invents interviews, surveys, market data, or policy findings. Human outreach, survey delivery, paid data, restricted access, and every protected action retain their separate approval gates. Architecture discovery is advisory and cannot bind the later Technical Lead. Experience goals may be recorded, but clickable NON-FINAL visual options still go only to the Creative Director.\n- Under `exception_only`, the project Chief reviews routine Product Manager and helper evidence. Escalate only a material unresolved product direction, safety/permission/ownership conflict, protected action, or final project acceptance. Continuation policy advances safe discovery work but never treats a pending gate as production authorization.\n"""
                report_gate = """\n## Report approval gate\n\nWhen `.chief-of-staff/project.json` sets `report_approval_required` to `true`, every milestone report and final handoff includes a stable `<task_id>:<report_sequence>` ID and requests `批准` or `退回修改`. The child opens a blocking review request so Codex marks it as needing attention; if the host cannot do that, it ends with `REVIEW_REQUIRED: <request_id>`. The Chief snapshots all active children after any wake-up, records every unseen request in `approval-queue.json`, and batches pending reports for the user in the Chief task. Only the user's explicit decision relayed by the Chief clears the gate.\n"""
                previous_product_discovery = current_text.replace(product_discovery_gate, "")
                previous_product_discovery = previous_product_discovery.replace(
                    "- `.chief-of-staff/product-discovery.json`: project classification, Product Manager ownership, four evidence lanes, required discovery deliverables, evidence index, legacy allowlist, and gate decision.\n",
                    "",
                )
                previous_peer_coordination = previous_product_discovery.replace(peer_coordination, "")
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
                compatibility_variants = {
                    previous_peer_coordination.encode("utf-8"),
                    previous_project_scoping.encode("utf-8"),
                    previous_current.encode("utf-8"), previous_text.encode("utf-8"),
                    legacy_text.encode("utf-8"),
                }
                narrow_pin_lines = """- Ordinary project Chiefs default to unpinned (`pin_primary_task=false`). That state is not a defect and never authorizes creating a successor, asking the operator to pin it, or archiving its predecessor.
- Only the central `general_office`, `todo`, `creative_director`, and `context_migration_monitor` roles require a pin. An optional product Chief may be created, pinned, unpinned, replaced, or inherit a pin only after the general office recommends it and the operator explicitly approves that exact change. Approval to appoint or pin does not confirm the project goal or authorize engineering, design, content, or production; the Product Manager discovery gate still applies.
- Optional slots default to six and remain bounded by observed capacity. Protect every manual non-Chief pin. If capacity is full, produce only a paired replacement recommendation; never evict automatically. The general office may present at most three candidates in one pending pack, and TODO only verifies identity, currentness, duplication, evidence freshness, capacity, and lineage. Exclude paused, completed, superseded, migration-cancelled, routine-push, meeting-summary, report-only, and process-only Chiefs by default; the central context migration monitor remains a mandatory exception.
- A successful pin API receipt is not proof. For a mandatory core role or operator-approved optional lineage, call `list_threads` and require the exact task ID in `pinnedThreads`; record a failed independent check as `pin_verification_failed`. A capacity-full result is not a task defect.
- Only an eligible mandatory or approved lineage may use successor pin inheritance. After `MIGRATION_READY` and a safe same-lineage handoff, create at most one replacement, verify its exact ID in a fresh `pinnedThreads` result before takeover or authoritative-entry switching, and archive the predecessor only after verified takeover. Never delete a predecessor, duplicate a Chief, change scope or pause state, or bypass an approval.
"""
                broad_pin_lines = """- The active Chief must remain pinned. A pin operation receipt is not success evidence: call `list_threads` and require the Chief's exact task ID in `pinnedThreads`. Record an independent-check failure as `pin_verification_failed`.
- A `MIGRATION_READY` successor may take control only after parity and an independent `list_threads` check shows its exact task ID in `pinnedThreads`, and that check must occur before takeover, authoritative-entry switching, or predecessor archival. On failure, do not accept takeover; at a safe boundary archive the old Chief with reason `unable_to_pin`, keep predecessors recoverable, create exactly one replacement in the same saved project and work state, transfer the goal, phase, pending approvals/TODOs, write ownership, evidence, and pause state, then repeat exact-ID verification. Never delete a predecessor, run duplicate Chiefs, change scope or pause state, or bypass an approval through pin inheritance.
"""
                old_pin_contract = current_text.replace(narrow_pin_lines, broad_pin_lines).replace(
                    "- `.chief-of-staff/pin-state.json`: pin role classification, recommendation/approval status, capacity result, exact-ID verification evidence, and bounded successor state.\n",
                    "",
                )
                compatibility_variants.add(old_pin_contract.encode("utf-8"))
                old_audio = b"- Generate separate written and spoken audio only when `audio_playback.enabled` is true. Use only its configured storage root; unavailable audio falls back to text without writing elsewhere."
                new_audio = b"- With `provider: host_builtin`, keep written/spoken text available to the host voice or read-aloud control and generate no files. Only opt-in `auto` or `macos_say` renders separate written/spoken attachments in the configured storage root; unavailable audio falls back to text without writing elsewhere."
                compatibility_variants.update(
                    item.replace(new_audio, old_audio)
                    for item in tuple(compatibility_variants)
                )
                if destination.read_bytes() in compatibility_variants:
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
