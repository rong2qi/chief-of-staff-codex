import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "init_project.py"
TEMPLATE = ROOT / "assets" / "project-template"


def run(target, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--target", str(target), "--project-name", "Example", *args],
        text=True, capture_output=True,
    )


def read_state(target, name):
    return json.loads((target / ".chief-of-staff" / name).read_text())


def write_state(target, name, value):
    (target / ".chief-of-staff" / name).write_text(json.dumps(value) + "\n")


def confirm_goal(target):
    plan = read_state(target, "project-plan.json")
    plan.update(
        {
            "goal_status": "confirmed",
            "project_status": "blocked",
            "final_goal": "Deliver a validated example",
            "deliverables": ["validated example"],
            "acceptance_criteria": [
                {"criterion_id": "acceptance-1", "description": "Validated", "status": "pending", "evidence": []}
            ],
            "confirmed_at": "2026-08-26T00:00:00Z",
        }
    )
    write_state(target, "project-plan.json", plan)


def phase(phase_id, phase_class, task_ids=None, status="planned"):
    return {
        "phase_id": phase_id,
        "title": phase_id,
        "objective": "Complete the phase",
        "status": status,
        "phase_class": phase_class,
        "acceptance_criteria": ["phase accepted"],
        "task_ids": task_ids or [],
        "result_summary": None,
    }


def task(task_id, work_class, phase_id, depth=2, status="queued"):
    return {
        "task_id": task_id,
        "host_id": None,
        "title": task_id,
        "role": "Product Manager" if work_class == "product_discovery" else "Role",
        "objective": "Complete assigned work",
        "status": status,
        "work_class": work_class,
        "write_surface": [],
        "depends_on": [],
        "last_cursor": None,
        "result_summary": None,
        "parent_task_id": None,
        "phase_id": phase_id,
        "management_depth": depth,
        "project_id": None,
        "coordination_with": [],
    }


def classify_coordination(target, reason="Only synchronize an already-approved change"):
    discovery = read_state(target, "product-discovery.json")
    discovery.update(
        {
            "classification_status": "classified",
            "project_classification": "coordination_only",
            "classification_reason": reason,
            "classified_at": "2026-08-26T00:01:00Z",
            "classification_evidence_refs": ["goal-contract"],
            "product_manager_required": False,
            "exemption_reason": reason,
            "gate_status": "exempt",
        }
    )
    for lane in discovery["lanes"].values():
        lane["status"] = "not_applicable"
        lane["execution_mode"] = "not_applicable"
    for deliverable in discovery["required_deliverables"].values():
        deliverable["status"] = "not_applicable"
    discovery["gate_decision"].update(
        {
            "decision": "not_applicable",
            "material_direction_status": "not_applicable",
            "review_route": "not_applicable",
            "review_status": "not_applicable",
        }
    )
    write_state(target, "product-discovery.json", discovery)


def classify_deliverable(target, gate_status="awaiting_product_manager"):
    discovery = read_state(target, "product-discovery.json")
    discovery.update(
        {
            "classification_status": "classified",
            "project_classification": "deliverable_project",
            "classification_reason": "Creates a new accepted product artifact",
            "classified_at": "2026-08-26T00:01:00Z",
            "classification_evidence_refs": ["goal-contract"],
            "product_manager_required": True,
            "exemption_reason": None,
            "gate_status": gate_status,
        }
    )
    write_state(target, "product-discovery.json", discovery)


def pass_product_gate(target, runtime_mode="pm_single_task_fallback"):
    discovery = read_state(target, "product-discovery.json")
    artifact_path = target / ".chief-of-staff" / "discovery-report.md"
    artifact_path.write_text("# Product discovery report\n\nVerified repository evidence.\n")
    discovery["gate_status"] = "passed"
    discovery["product_manager"].update(
        {
            "owner_id": "pm-1",
            "owner_kind": "durable_task",
            "runtime_mode": runtime_mode,
            "runtime_limitation": (
                "Runtime has no subagent slots" if runtime_mode == "pm_single_task_fallback" else None
            ),
        }
    )
    for index, lane in enumerate(discovery["lanes"].values(), start=1):
        lane.update(
            {
                "status": "verified",
                "execution_mode": (
                    "product_manager_fallback"
                    if runtime_mode == "pm_single_task_fallback"
                    else "temporary_helper"
                ),
                "owner_id": "pm-1" if runtime_mode == "pm_single_task_fallback" else f"helper-{index}",
                "management_depth": 2 if runtime_mode == "pm_single_task_fallback" else 3,
                "artifact_refs": ["repo://.chief-of-staff/discovery-report.md"],
                "evidence_refs": ["evidence-1"],
            }
        )
    for deliverable in discovery["required_deliverables"].values():
        deliverable.update(
            {
                "status": "verified",
                "artifact_refs": ["repo://.chief-of-staff/discovery-report.md"],
                "evidence_refs": ["evidence-1"],
            }
        )
    discovery["synthesis_coverage"] = {
        key: True for key in discovery["synthesis_coverage"]
    }
    discovery["evidence_index"] = [
        {
            "evidence_id": "evidence-1",
            "kind": "verified_fact",
            "summary": "Repository evidence supports the recommendation",
            "source_ref": "repo://AGENTS.md",
            "verification_method": "direct_file_inspection",
            "verified_at": "2026-08-26T00:02:00Z",
        }
    ]
    discovery["gate_decision"].update(
        {
            "decision": "proceed",
            "material_direction_status": "no_conflict",
            "review_route": "chief",
            "review_status": "approved",
            "decision_ref": "decision://product-gate-1",
        }
    )
    write_state(target, "product-discovery.json", discovery)


class InitProjectTests(unittest.TestCase):
    def test_fresh_init_creates_throughput_and_goals_feature(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            result = run(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            project = json.loads((target / ".chief-of-staff/project.json").read_text())
            throughput = json.loads((target / ".chief-of-staff/throughput.json").read_text())
            self.assertTrue(project["durable_goal_enabled"])
            self.assertEqual(project["execution_mode"], "effective_throughput")
            self.assertEqual(project["report_review_mode"], "exception_only")
            self.assertFalse(project["report_approval_required"])
            self.assertEqual(project["governance_model"], "standard")
            self.assertEqual(project["operator_role"], "operator")
            self.assertEqual(project["continuation_policy"], "standard")
            self.assertEqual(project["ordinary_failure_policy"], "bounded_repair_cycle")
            self.assertEqual(project["visual_selection_gate"], "disabled")
            self.assertEqual(project["visual_review_hub_title"], "Chief of Creative Direction｜创意总监")
            self.assertEqual(throughput["max_parallel_phase_lanes"], 2)
            self.assertIn("[features]\ngoals = true", (target / ".codex/config.toml").read_text())
            agents = (target / "AGENTS.md").read_text()
            self.assertIn("Optional salutation, coaching, audio, and pause title", agents)
            self.assertNotIn("End every complete user-facing reply", agents)
            self.assertFalse((target / ".chief-of-staff/deployment-registry.json").exists())

    def test_appledouble_agent_sidecars_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            (target / ".codex/agents/._scout.toml").write_bytes(b"not toml metadata")
            result = run(target, "--check")
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_older_project_gets_missing_policy_fields_without_overwriting_custom_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            project_path = target / ".chief-of-staff/project.json"
            project = json.loads(project_path.read_text())
            for key in (
                "report_review_mode",
                "governance_model", "operator_role", "routine_administration_owner",
                "auditor_authority", "direct_report_policy", "partial_pause_policy",
                "operator_escalation_policy",
                "continuation_policy", "ordinary_failure_policy",
                "continuation_escalation_policy",
                "durable_goal_enabled", "execution_mode", "max_parallel_phase_lanes",
                "no_evidence_checkpoint_limit", "visual_selection_gate",
                "visual_review_hub_title", "legacy_allowlist_digest",
            ):
                project.pop(key)
            project["max_management_depth"] = 5
            project_path.write_text(json.dumps(project) + "\n")
            (target / ".chief-of-staff/throughput.json").unlink()
            old_config = (target / ".codex/config.toml").read_text().replace("\n[features]\ngoals = true\n", "\n")
            (target / ".codex/config.toml").write_text(old_config)
            result = run(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            upgraded = json.loads(project_path.read_text())
            self.assertEqual(upgraded["max_management_depth"], 5)
            self.assertEqual(upgraded["report_review_mode"], "exception_only")
            self.assertFalse(upgraded["report_approval_required"])
            self.assertEqual(upgraded["governance_model"], "standard")
            self.assertEqual(upgraded["continuation_policy"], "standard")
            self.assertEqual(upgraded["max_parallel_phase_lanes"], 2)
            self.assertEqual(upgraded["visual_selection_gate"], "disabled")
            self.assertEqual(upgraded["visual_review_hub_title"], "Chief of Creative Direction｜创意总监")
            self.assertTrue(json.loads((target / ".chief-of-staff/throughput.json").read_text())["execution_mode"] == "effective_throughput")
            self.assertIn("goals = true", (target / ".codex/config.toml").read_text())

    def test_existing_throughput_values_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            path = target / ".chief-of-staff/throughput.json"
            state = json.loads(path.read_text())
            state["max_parallel_phase_lanes"] = 4
            state["active_phase_lanes"] = ["delivery"]
            path.write_text(json.dumps(state) + "\n")
            result = run(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            preserved = json.loads(path.read_text())
            self.assertEqual(preserved["max_parallel_phase_lanes"], 4)
            self.assertEqual(preserved["active_phase_lanes"], ["delivery"])

    def test_project_preferences_enable_visual_gate_without_public_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            configure = ROOT / "scripts" / "configure_preferences.py"
            configured = subprocess.run(
                [
                    sys.executable, str(configure),
                    "--preset", "operator-controlled-bilingual",
                    "--scope", "project",
                    "--project-root", str(project),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(configured.returncode, 0, configured.stderr)
            profile = project / ".chief-of-staff/preferences.json"
            result = run(project, "--preferences", str(profile))
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((project / ".chief-of-staff/project.json").read_text())
            self.assertEqual(
                state["visual_selection_gate"],
                "operator_after_clickable_preview",
            )
            self.assertEqual(
                json.loads(profile.read_text())["scope"],
                "project",
            )

    def test_project_preferences_enable_chair_led_governance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            profile = json.loads(
                (ROOT / "assets/operator-preferences.example.json").read_text()
            )
            profile["scope"] = "project"
            profile["preset"] = "custom"
            profile["governance_model"]["enabled"] = True
            profile["governance_model"]["general_office_thread_id"] = "office-thread"
            profile["governance_model"]["continuation_policy"]["enabled"] = True
            profile_path = root / "profile.json"
            profile_path.write_text(json.dumps(profile), encoding="utf-8")
            result = run(project, "--preferences", str(profile_path))
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((project / ".chief-of-staff/project.json").read_text())
            self.assertEqual(state["governance_model"], "chair_led_cabinet")
            self.assertEqual(state["operator_role"], "chair")
            self.assertEqual(state["auditor_authority"], "evidence_only")
            self.assertEqual(state["direct_report_policy"], "chain_of_command")
            self.assertEqual(state["partial_pause_policy"], "affected_surface_only")
            self.assertEqual(
                state["continuation_policy"], "advance_best_safe_in_scope_path"
            )
            self.assertEqual(
                state["continuation_escalation_policy"],
                "new_permission_or_new_chief",
            )

    def test_global_policy_profile_projects_rules_without_copying_private_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            profile = json.loads(
                (ROOT / "assets/operator-preferences.example.json").read_text()
            )
            profile["scope"] = "global"
            profile["preset"] = "custom"
            profile["governance_model"]["enabled"] = True
            profile["governance_model"]["general_office_thread_id"] = "office-thread"
            profile["governance_model"]["continuation_policy"]["enabled"] = True
            profile_path = root / "global-profile.json"
            profile_path.write_text(json.dumps(profile), encoding="utf-8")
            result = run(project, "--policy-profile", str(profile_path))
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((project / ".chief-of-staff/project.json").read_text())
            self.assertEqual(state["governance_model"], "chair_led_cabinet")
            self.assertEqual(
                state["ordinary_failure_policy"],
                "continue_bounded_diagnosis_repair_and_verification",
            )
            self.assertFalse((project / ".chief-of-staff/preferences.json").exists())

    def test_invalid_or_conflicting_existing_values_stop_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            project_path = target / ".chief-of-staff/project.json"
            project = json.loads(project_path.read_text())
            valid_project = project_path.read_bytes()
            project["execution_mode"] = "unsafe_parallel"
            project_path.write_text(json.dumps(project) + "\n")
            before = project_path.read_bytes()
            result = run(target)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(project_path.read_bytes(), before)
            self.assertIn("project.json", result.stderr)

            project_path.write_bytes(valid_project)
            config_path = target / ".codex/config.toml"
            config_path.write_text(config_path.read_text().replace("goals = true", "goals = false"))
            result = run(target)
            self.assertEqual(result.returncode, 2)
            self.assertIn(".codex/config.toml", result.stderr)

    def test_fresh_project_records_pending_product_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            project = read_state(target, "project.json")
            discovery = read_state(target, "product-discovery.json")
            self.assertEqual(project["project_classification_policy"], "classify_after_goal_confirmation")
            self.assertEqual(project["production_start_policy"], "deny_until_product_discovery_passed_or_coordination_exempt")
            self.assertIsNone(project["legacy_allowlist_digest"])
            self.assertEqual(discovery["classification_status"], "pending")
            self.assertEqual(discovery["project_classification"], "unclassified")
            self.assertEqual(set(discovery["lanes"]), {
                "project_initiation", "requirements_analysis", "market_research", "architecture_feasibility"
            })
            self.assertIn("Product classification and discovery gate", (target / "AGENTS.md").read_text())
            self.assertEqual(run(target, "--check").returncode, 0)

    def test_generated_contract_enforces_narrow_pin_inheritance_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            agents = (target / "AGENTS.md").read_text()
            self.assertIn("Ordinary project Chiefs default to unpinned", agents)
            self.assertIn("`general_office`, `todo`, `creative_director`, and `context_migration_monitor`", agents)
            self.assertIn("operator explicitly approves that exact change", agents)
            self.assertIn("Protect every manual non-Chief pin", agents)
            self.assertIn("paired replacement recommendation", agents)
            self.assertIn("does not confirm the project goal", agents)
            self.assertIn("call `list_threads`", agents)
            self.assertIn("exact task ID in `pinnedThreads`", agents)
            self.assertIn("After `MIGRATION_READY`", agents)
            self.assertIn("before takeover or authoritative-entry switching", agents)
            self.assertIn("`pin_verification_failed`", agents)
            self.assertIn("create at most one replacement", agents)
            self.assertIn("Never delete a predecessor, duplicate a Chief, change scope or pause state", agents)

            skill = (ROOT / "SKILL.md").read_text()
            readme = (ROOT / "README.md").read_text()
            governance = (ROOT / "references/pin-inheritance-governance.md").read_text()
            for text in (skill, readme, governance):
                self.assertIn("MIGRATION_READY", text)
                self.assertIn("list_threads", text)
                self.assertIn("pinnedThreads", text)
                self.assertIn("pin_verification_failed", text)

    def test_fresh_ordinary_chief_is_unpinned_and_cannot_enter_successor_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            project = read_state(target, "project.json")
            pin_state = read_state(target, "pin-state.json")
            self.assertFalse(project["pin_primary_task"])
            self.assertEqual(pin_state["role_class"], "ordinary_chief")
            self.assertEqual(pin_state["pin_status"], "unpinned")
            pin_state["pin_status"] = "verification_failed"
            pin_state["successor"]["migration_ready"] = True
            write_state(target, "pin-state.json", pin_state)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("ordinary_chief", result.stderr)
            self.assertIn("successor flow", result.stderr)

    def test_approved_optional_pin_does_not_confirm_goal_or_pass_product_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            project = read_state(target, "project.json")
            project["pin_primary_task"] = True
            write_state(target, "project.json", project)
            pin_state = read_state(target, "pin-state.json")
            pin_state.update({
                "role_class": "approved_optional_chief",
                "authorization_status": "approved",
                "operator_approval_ref": "approval:anonymous",
                "recommendation_ref": "recommendation:anonymous",
                "pin_status": "pending_verification",
                "successor_inheritance_eligible": True,
            })
            write_state(target, "pin-state.json", pin_state)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 0, result.stderr)
            plan = read_state(target, "project-plan.json")
            discovery = read_state(target, "product-discovery.json")
            self.assertEqual(plan["goal_status"], "unconfirmed")
            self.assertEqual(discovery["gate_status"], "awaiting_classification")

    def test_successor_requires_migration_exact_id_and_pin_before_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            project = read_state(target, "project.json")
            project["pin_primary_task"] = True
            write_state(target, "project.json", project)
            pin_state = read_state(target, "pin-state.json")
            pin_state.update({
                "role_class": "mandatory_core",
                "authorization_status": "not_required",
                "pin_status": "verified",
                "verified_thread_id": "thread:successor",
                "verified_at": "2026-08-26T00:00:00Z",
                "successor_inheritance_eligible": True,
            })
            pin_state["successor"].update({
                "candidate_thread_id": "thread:successor",
                "migration_ready": True,
                "exact_list_verified": True,
                "takeover_accepted": True,
                "predecessor_archived": True,
                "replacement_count": 1,
                "same_lineage": True,
                "safe_handoff": True,
            })
            write_state(target, "pin-state.json", pin_state)
            self.assertEqual(run(target, "--check").returncode, 0)
            pin_state["successor"]["exact_list_verified"] = False
            write_state(target, "pin-state.json", pin_state)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("exact-ID pin verification", result.stderr)

    def test_legacy_pinned_project_is_preserved_as_grandfathered(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            (target / ".chief-of-staff" / "pin-state.json").unlink()
            project = read_state(target, "project.json")
            project["pin_primary_task"] = True
            write_state(target, "project.json", project)
            self.assertEqual(run(target).returncode, 0)
            migrated = read_state(target, "pin-state.json")
            self.assertEqual(migrated["role_class"], "grandfathered_optional_chief")
            self.assertEqual(migrated["authorization_status"], "grandfathered_pending_review")
            self.assertEqual(migrated["pin_status"], "grandfathered_preserved")
            self.assertIsNone(migrated["verified_thread_id"])
            self.assertEqual(run(target, "--check").returncode, 0)

    def test_status_requires_all_governance_headings(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            status_path = target / ".chief-of-staff/status.md"
            status_path.write_text(status_path.read_text().replace("## 风险", "## Removed"))
            result = run(target, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("status.md is missing required heading: 风险", result.stderr)

    def test_confirmed_goal_requires_classification(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            confirm_goal(target)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("confirmed goal requires project classification", result.stderr)

    def test_classification_cannot_precede_goal_or_remain_abstract(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            classify_coordination(target)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("classification requires a confirmed goal", result.stderr)

            confirm_goal(target)
            discovery = read_state(target, "product-discovery.json")
            discovery["project_classification"] = "unclassified"
            discovery["product_manager_required"] = None
            discovery["gate_status"] = "awaiting_classification"
            write_state(target, "product-discovery.json", discovery)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("requires a concrete project classification", result.stderr)

    def test_coordination_exemption_requires_reason_and_blocks_production(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            confirm_goal(target)
            classify_coordination(target)
            self.assertEqual(run(target, "--check").returncode, 0)

            discovery = read_state(target, "product-discovery.json")
            discovery["exemption_reason"] = ""
            write_state(target, "product-discovery.json", discovery)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("requires exemption_reason", result.stderr)

            classify_coordination(target)
            plan = read_state(target, "project-plan.json")
            plan["phases"] = [phase("build", "production", ["builder"])]
            registry = read_state(target, "task-registry.json")
            registry["tasks"] = [task("builder", "production_execution", "build")]
            write_state(target, "project-plan.json", plan)
            write_state(target, "task-registry.json", registry)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("coordination_only project cannot create", result.stderr)

    def test_reclassification_to_deliverable_reinstates_product_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            confirm_goal(target)
            classify_coordination(target)
            self.assertEqual(run(target, "--check").returncode, 0)
            classify_deliverable(target)
            plan = read_state(target, "project-plan.json")
            plan["phases"] = [phase("build", "production", ["builder"])]
            registry = read_state(target, "task-registry.json")
            registry["tasks"] = [task("builder", "production_execution", "build")]
            write_state(target, "project-plan.json", plan)
            write_state(target, "task-registry.json", registry)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("production execution is denied", result.stderr)

    def test_product_manager_fallback_gate_passes_and_allows_production(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            confirm_goal(target)
            classify_deliverable(target, "in_progress")
            discovery = read_state(target, "product-discovery.json")
            discovery["product_manager"].update(
                {
                    "owner_id": "pm-1", "owner_kind": "durable_task",
                    "runtime_mode": "pm_single_task_fallback", "runtime_limitation": None,
                }
            )
            for lane in discovery["lanes"].values():
                lane.update({"execution_mode": "product_manager_fallback", "owner_id": "pm-1", "management_depth": 2})
            write_state(target, "product-discovery.json", discovery)
            plan = read_state(target, "project-plan.json")
            plan["phases"] = [phase("discovery", "product_discovery", ["pm-1"])]
            registry = read_state(target, "task-registry.json")
            registry["tasks"] = [task("pm-1", "product_discovery", "discovery", status="running")]
            write_state(target, "project-plan.json", plan)
            write_state(target, "task-registry.json", registry)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("requires runtime_limitation", result.stderr)

            pass_product_gate(target)
            registry["tasks"][0]["status"] = "completed"
            registry["tasks"].append(task("builder", "production_execution", "build"))
            plan["phases"].append(phase("build", "production", ["builder"]))
            write_state(target, "project-plan.json", plan)
            write_state(target, "task-registry.json", registry)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_four_helpers_and_fixed_product_boundaries_are_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            confirm_goal(target)
            classify_deliverable(target)
            pass_product_gate(target, runtime_mode="four_temporary_helpers")
            plan = read_state(target, "project-plan.json")
            plan["phases"] = [phase("discovery", "product_discovery", ["pm-1"], status="completed")]
            registry = read_state(target, "task-registry.json")
            registry["tasks"] = [task("pm-1", "product_discovery", "discovery", status="completed")]
            write_state(target, "project-plan.json", plan)
            write_state(target, "task-registry.json", registry)
            self.assertEqual(run(target, "--check").returncode, 0)

            discovery = read_state(target, "product-discovery.json")
            discovery["lanes"]["market_research"]["owner_id"] = "helper-1"
            discovery["guardrails"]["visual_direction"] = "product_manager"
            write_state(target, "product-discovery.json", discovery)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("distinct helper owners", result.stderr)
            self.assertIn("preserve architecture, visual, and approval boundaries", result.stderr)

    def test_passed_gate_rejects_incomplete_evidence_and_unresolved_direction(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            confirm_goal(target)
            classify_deliverable(target)
            pass_product_gate(target)
            discovery = read_state(target, "product-discovery.json")
            discovery["required_deliverables"]["project_charter"]["evidence_refs"] = []
            discovery["gate_decision"]["decision"] = "conditional_proceed"
            discovery["gate_decision"]["conditions"] = []
            discovery["gate_decision"]["material_direction_status"] = "operator_required"
            write_state(target, "product-discovery.json", discovery)
            registry = read_state(target, "task-registry.json")
            registry["tasks"] = [task("pm-1", "product_discovery", "discovery", status="completed")]
            plan = read_state(target, "project-plan.json")
            plan["phases"] = [phase("discovery", "product_discovery", ["pm-1"], status="completed")]
            write_state(target, "task-registry.json", registry)
            write_state(target, "project-plan.json", plan)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("requires every verified deliverable", result.stderr)
            self.assertIn("requires conditions", result.stderr)
            self.assertIn("cannot retain operator_required", result.stderr)

    def test_passed_gate_rejects_dangling_or_untraceable_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            confirm_goal(target)
            classify_deliverable(target)
            pass_product_gate(target)
            discovery = read_state(target, "product-discovery.json")
            discovery["lanes"]["market_research"]["evidence_refs"] = ["invented-evidence"]
            discovery["required_deliverables"]["market_competitor_research"]["artifact_refs"] = ["missing-report"]
            discovery["evidence_index"][0]["source_ref"] = "repo://does-not-exist.md"
            write_state(target, "product-discovery.json", discovery)
            registry = read_state(target, "task-registry.json")
            registry["tasks"] = [task("pm-1", "product_discovery", "discovery", status="completed")]
            plan = read_state(target, "project-plan.json")
            plan["phases"] = [phase("discovery", "product_discovery", ["pm-1"], status="completed")]
            write_state(target, "task-registry.json", registry)
            write_state(target, "project-plan.json", plan)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("unknown evidence ID", result.stderr)
            self.assertIn("must use repo://", result.stderr)
            self.assertIn("does not resolve to a project file", result.stderr)

            pass_product_gate(target)
            discovery = read_state(target, "product-discovery.json")
            discovery["evidence_index"].append(
                {
                    "evidence_id": "assumption-1",
                    "kind": "assumption",
                    "summary": "Demand may exist but has not been verified",
                    "source_ref": None,
                    "verification_method": None,
                    "verified_at": None,
                }
            )
            discovery["lanes"]["market_research"]["evidence_refs"] = ["assumption-1"]
            discovery["required_deliverables"]["market_competitor_research"]["evidence_refs"] = ["assumption-1"]
            write_state(target, "product-discovery.json", discovery)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("verified-fact evidence for every lane", result.stderr)
            self.assertIn("verified-fact evidence for every deliverable", result.stderr)

    def test_legacy_migration_allowlists_existing_work_without_faking_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            project = read_state(target, "project.json")
            for key in (
                "project_classification_policy", "deliverable_product_discovery_policy",
                "production_start_policy", "product_discovery_state_file",
                "legacy_allowlist_digest",
            ):
                project.pop(key)
            write_state(target, "project.json", project)
            (target / ".chief-of-staff/product-discovery.json").unlink()
            confirm_goal(target)
            plan = read_state(target, "project-plan.json")
            old_phase = phase("old-phase", "production", ["old-task"])
            old_phase.pop("phase_class")
            plan["phases"] = [old_phase]
            registry = read_state(target, "task-registry.json")
            old_task = task("old-task", "production_execution", "old-phase")
            old_task.pop("work_class")
            registry["tasks"] = [old_task]
            write_state(target, "project-plan.json", plan)
            write_state(target, "task-registry.json", registry)
            status_path = target / ".chief-of-staff/status.md"
            status_text = status_path.read_text()
            status_start = status_text.index("## 产品分类与发现门")
            status_end = status_text.index("## 已验证事实")
            status_path.write_text(status_text[:status_start] + status_text[status_end:])
            result = run(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            discovery = read_state(target, "product-discovery.json")
            self.assertEqual(discovery["classification_status"], "legacy_unclassified")
            self.assertEqual(discovery["gate_status"], "legacy_pending")
            self.assertEqual(discovery["legacy_allowlist"]["phase_ids"], ["old-phase"])
            self.assertEqual(discovery["legacy_allowlist"]["task_ids"], ["old-task"])
            self.assertIsNotNone(read_state(target, "project.json")["legacy_allowlist_digest"])
            self.assertEqual(read_state(target, "project-plan.json")["phases"][0]["phase_class"], "legacy_existing")
            self.assertEqual(read_state(target, "task-registry.json")["tasks"][0]["work_class"], "legacy_existing")
            self.assertEqual(run(target, "--check").returncode, 0)

            registry = read_state(target, "task-registry.json")
            registry["tasks"].append(task("new-task", "legacy_existing", "old-phase"))
            write_state(target, "task-registry.json", registry)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("not in the migration allowlist", result.stderr)

    def test_legacy_migration_when_policy_fields_exist_but_discovery_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            (target / ".chief-of-staff/product-discovery.json").unlink()
            confirm_goal(target)
            plan = read_state(target, "project-plan.json")
            old_phase = phase("existing-phase", "production", ["existing-task"])
            old_phase.pop("phase_class")
            plan["phases"] = [old_phase]
            registry = read_state(target, "task-registry.json")
            old_task = task("existing-task", "production_execution", "existing-phase")
            old_task.pop("work_class")
            registry["tasks"] = [old_task]
            write_state(target, "project-plan.json", plan)
            write_state(target, "task-registry.json", registry)
            status_path = target / ".chief-of-staff/status.md"
            status_text = status_path.read_text()
            status_start = status_text.index("## 产品分类与发现门")
            status_end = status_text.index("## 已验证事实")
            status_path.write_text(status_text[:status_start] + status_text[status_end:])
            result = run(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            discovery = read_state(target, "product-discovery.json")
            self.assertEqual(discovery["classification_status"], "legacy_unclassified")
            self.assertEqual(discovery["legacy_allowlist"]["task_ids"], ["existing-task"])
            self.assertIn("## 产品分类与发现门", status_path.read_text())
            self.assertIn("legacy pending", status_path.read_text())
            self.assertEqual(run(target, "--check").returncode, 0)

    def test_legacy_allowlist_mutation_breaks_immutable_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            project = read_state(target, "project.json")
            for key in (
                "project_classification_policy", "deliverable_product_discovery_policy",
                "production_start_policy", "product_discovery_state_file",
                "legacy_allowlist_digest",
            ):
                project.pop(key)
            write_state(target, "project.json", project)
            (target / ".chief-of-staff/product-discovery.json").unlink()
            self.assertEqual(run(target).returncode, 0)
            discovery = read_state(target, "product-discovery.json")
            discovery["legacy_allowlist"]["task_ids"].append("forged-task")
            write_state(target, "product-discovery.json", discovery)
            registry = read_state(target, "task-registry.json")
            registry["tasks"].append(task("forged-task", "legacy_existing", None))
            write_state(target, "task-registry.json", registry)
            result = run(target, "--check")
            self.assertEqual(result.returncode, 1)
            self.assertIn("immutable project digest", result.stderr)


if __name__ == "__main__":
    unittest.main()
