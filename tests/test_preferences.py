import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.preference_lib import (
    CAPABILITY_DISCOVERY_EVIDENCE,
    CAPABILITY_DISCOVERY_LIFECYCLE_EXACT,
    CAPABILITY_DISCOVERY_PROHIBITED_ACTIONS,
    CAPABILITY_DISCOVERY_TRIGGERS,
    CHIEF_TITLE_EXCEPTION_ROLES,
    CHIEF_TITLE_PREFIX,
    PIN_CRITERIA,
    PreferenceError,
    atomic_write_json,
    capability_recommendation_pack_id,
    evaluate_capability_discovery,
    evaluate_approved_decision_relay,
    evaluate_recommended_action,
    filter_operator_todo_items,
    lifecycle_capability_discovery,
    read_json,
    recommend_optional_chief_pins,
    route_capability_recommendations,
    validate_preferences,
)
from scripts.legacy_terminology_migration import (
    CURRENT_PROFILE_KEY,
    LEGACY_PROFILE_KEY,
    LEGACY_SNAPSHOT_PIN_CLASS,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIGURE = ROOT / "scripts" / "configure_preferences.py"
RENDER = ROOT / "scripts" / "render_english_audio.py"


def run_config(*args, env=None):
    return subprocess.run(
        [sys.executable, str(CONFIGURE), *map(str, args)],
        text=True,
        capture_output=True,
        env=env,
    )


class PreferenceTests(unittest.TestCase):
    def test_autonomy_boolean_contract_rejects_integer_truthy_values(self):
        profile = json.loads((ROOT / "assets/operator-preferences.example.json").read_text())
        autonomy = profile["governance_model"]["continuation_policy"]["autonomy_policy"]
        for key in ("approval_package_required", "operation_revalidation_required"):
            altered = json.loads(json.dumps(profile))
            altered["governance_model"]["continuation_policy"]["autonomy_policy"][key] = 1
            self.assertTrue(any(key in error for error in validate_preferences(altered)))

    def test_managed_rules_keep_first_request_and_direct_approved_relay_distinct(self):
        profile = self.delegated_profile()
        from scripts.preference_lib import managed_agents_block
        block = managed_agents_block(Path("/tmp/profile.json"), Path("/tmp/render.py"))
        self.assertIn("Initial permission requests remain General-Office-only", block)
        self.assertIn("mandatory asynchronous nonblocking General Office audit", block)
        self.assertIn("approved_decision_relay.enabled", block)
        self.assertIn("Reuse the registered Testing Director", block)
        self.assertIn("each Director must first reuse registered durable subordinate roles", block)
        self.assertIn("runtime cannot delegate, record the limitation", block)
        self.assertIn("packaging_path_correction", block)
        self.assertIn("semantic_invariance_evidence_ref", block)
        self.assertIn("native clickable questions", block)
        self.assertIn("numerical local-preparation limits", block)
        self.assertIn("never bypass platform permission or safety limits", block)

    def test_approved_decision_relay_is_opt_in_and_preserves_transport_boundary(self):
        profile = self.delegated_profile()
        decision = {
            "stable_id": "DEC-1", "original_words": "Proceed with the local change.",
            "approved": True, "kind": "nonvisual", "source_chief_id": "chief-1",
            "current": True, "delivered": False, "delivery_failed": False,
        }
        registry = {"tasks": [{"task_id": "chief-1", "status": "running"}]}
        self.assertEqual(evaluate_approved_decision_relay(profile, decision, registry)["status"], "disabled")
        profile["governance_model"]["approved_decision_relay"] = {
            "enabled": True,
            "mode": "todo_direct_exact_words_once",
            "audit": "general_office_asynchronous_nonblocking",
            "source": "registered_current_source_chief_only",
            "visual_route": "creative_director_only",
            "delivery_is_execution": False,
        }
        result = evaluate_approved_decision_relay(profile, decision, registry)
        self.assertEqual(result["status"], "todo_direct_relay_intent")
        self.assertEqual(result["relay"]["original_words"], decision["original_words"])
        self.assertTrue(result["audit_required"])
        self.assertFalse(result["delivery_performed"])
        self.assertEqual(evaluate_approved_decision_relay(profile, {**decision, "delivered": True}, registry)["status"], "duplicate_suppressed")
        failed = evaluate_approved_decision_relay(profile, {**decision, "delivery_failed": True}, registry)
        self.assertEqual(failed["status"], "delivery_failed_recorded")
        self.assertTrue(failed["audit_required"])
        for invalid in (0, "false"):
            self.assertEqual(evaluate_approved_decision_relay(profile, {**decision, "delivered": invalid}, registry)["status"], "evidence_required")
            self.assertEqual(evaluate_approved_decision_relay(profile, {**decision, "delivery_failed": invalid}, registry)["status"], "evidence_required")
        self.assertEqual(evaluate_approved_decision_relay(profile, {**decision, "kind": "visual_selection"}, registry)["status"], "creative_director_only")
        for invalid in (0, "false", None):
            altered = json.loads(json.dumps(profile))
            altered["governance_model"]["approved_decision_relay"]["delivery_is_execution"] = invalid
            self.assertTrue(any("delivery_is_execution" in error for error in validate_preferences(altered)))

    def test_missing_decision_relay_section_stays_schema1_compatible(self):
        profile = self.delegated_profile()
        self.assertEqual(validate_preferences(profile), [])
    def enabled_pin_profile(self):
        profile = json.loads(
            (ROOT / "assets/operator-preferences.example.json").read_text()
        )
        profile["pin_governance"]["enabled"] = True
        for index, role in enumerate(profile["pin_governance"]["mandatory_core_roles"]):
            role["thread_id"] = f"core-{index}"
        return profile

    def pin_candidate(self, thread_id, *, status="active", work_kind="product_delivery", score=0.8):
        return {
            "thread_id": thread_id,
            "title": f"Chief {thread_id}",
            "lifecycle_status": status,
            "work_kind": work_kind,
            "current": True,
            "evidence_fresh": True,
            "lineage_valid": True,
            "signals": {key: score for key in PIN_CRITERIA},
        }

    def delegated_profile(self):
        profile = json.loads(
            (ROOT / "assets/operator-preferences.example.json").read_text()
        )
        profile["governance_model"]["enabled"] = True
        profile["governance_model"]["general_office_thread_id"] = "general-office"
        profile["governance_model"]["continuation_policy"]["enabled"] = True
        policy = profile["governance_model"]["continuation_policy"][
            "recommended_action_delegation"
        ]
        policy["enabled"] = True
        return profile

    def lifecycle_discovery_profile(self):
        profile = json.loads(
            (ROOT / "assets/operator-preferences.example.json").read_text()
        )
        profile["project_start_capability_discovery"] = (
            lifecycle_capability_discovery(enabled=True)
        )
        return profile

    def capability_candidate(self, **overrides):
        candidate = {
            key: f"evidence-{key}" for key in CAPABILITY_DISCOVERY_EVIDENCE
        }
        candidate["source"] = "https://example.invalid/capability"
        candidate["fixed_version_or_revision"] = "v1.2.3"
        candidate.update({"material": True, "decision": "recommend"})
        candidate.update(overrides)
        return candidate

    def capability_packet(self, **overrides):
        chief_id = overrides.pop("chief_id", "chief-a")
        trigger = overrides.pop("trigger", "blocker_or_failure")
        evidence_identity = overrides.pop(
            "evidence_identity", f"sha256:{'e' * 64}"
        )
        packet = {
            "chief_id": chief_id,
            "trigger": trigger,
            "evidence_identity": evidence_identity,
            "pack_id": capability_recommendation_pack_id(
                chief_id, trigger, evidence_identity
            ),
            "chief_registered": True,
            "lifecycle_status": "active",
        }
        packet.update(overrides)
        return packet

    def eligible_action(self, action_class="metadata_only_allowlisted_read"):
        return {
            "stable_id": "REC-001",
            "action_class": action_class,
            "recommendation_count": 1,
            "evidence_complete": True,
            "exact_identity_and_surface": True,
            "independent_verification_when_applicable": True,
            "no_unresolved_safety_dissent": True,
            "nonproduction": True,
            "no_real_customer_or_personal_data": True,
            "no_credentials_or_secrets": True,
            "stop_and_rollback_defined": True,
            "prior_operator_denial": False,
            "external_send": False,
            "execution_state": "ready",
        }

    def test_recommended_action_missing_section_is_compatible_disabled(self):
        profile = self.delegated_profile()
        del profile["governance_model"]["continuation_policy"][
            "recommended_action_delegation"
        ]
        self.assertEqual(validate_preferences(profile), [])
        self.assertEqual(
            evaluate_recommended_action(profile, self.eligible_action())["status"],
            "disabled",
        )

    def test_exact_temp_cleanup_is_delegated_with_stable_audit_marker(self):
        action = self.eligible_action("exact_task_owned_temp_cleanup")
        action.update({
            "path": "/tmp/task-artifact.bin",
            "file_type": "regular_file",
            "size_bytes": 12,
            "sha256": "a" * 64,
            "is_symlink": False,
            "follow_symlinks": False,
            "uses_glob": False,
            "recursive": False,
            "task_owned": True,
            "temporary": True,
        })
        result = evaluate_recommended_action(self.delegated_profile(), action)
        self.assertEqual(result["status"], "delegated")
        self.assertEqual(
            result["audit_marker"], "DELEGATED_RECOMMENDATION_EXECUTED: REC-001"
        )
        self.assertFalse(result["operator_actionable_now"])

        action["file_type"] = "directory"
        rejected = evaluate_recommended_action(self.delegated_profile(), action)
        self.assertEqual(rejected["status"], "evidence_required")
        self.assertIn("regular_file", rejected["missing"])
        action["file_type"] = "regular_file"
        action["path"] = "relative.tmp"
        rejected = evaluate_recommended_action(self.delegated_profile(), action)
        self.assertIn("absolute_exact_path", rejected["missing"])

    def test_fixed_hash_one_shot_delegates_but_prior_denial_stays_operator_only(self):
        action = self.eligible_action(
            "fixed_sha256_one_shot_nonproduction_execution"
        )
        action.update({
            "sha256": "b" * 64,
            "one_shot": True,
            "overwrite": False,
            "external_send": False,
            "io_allowlist": ["/tmp/input", "/tmp/output"],
            "execution_count": 0,
            "automatic_rerun_requested": False,
        })
        self.assertEqual(
            evaluate_recommended_action(self.delegated_profile(), action)["status"],
            "delegated",
        )
        action["prior_operator_denial"] = True
        action["stable_id"] = "VIDEO-C"
        denied = evaluate_recommended_action(self.delegated_profile(), action)
        self.assertEqual(denied["status"], "operator_only")
        self.assertEqual(denied["reason"], "override_prior_explicit_operator_denial")

    def test_prior_denial_reason_precedes_external_send_reason(self):
        action = self.eligible_action(
            "fixed_sha256_one_shot_nonproduction_execution"
        )
        action.update({
            "prior_operator_denial": True,
            "external_send": True,
        })
        result = evaluate_recommended_action(self.delegated_profile(), action)
        self.assertEqual(result["status"], "operator_only")
        self.assertEqual(result["reason"], "override_prior_explicit_operator_denial")

    def test_reserved_actions_always_stay_operator_only(self):
        for reserved in (
            "payment_or_purchase",
            "release_deploy_production_or_rollback",
            "real_user_or_production_data_deletion",
            "external_communication_new_collaborator_or_public_visibility",
            "credentials_secrets_real_identity_or_sensitive_data",
        ):
            action = self.eligible_action()
            action["operator_only_action"] = reserved
            result = evaluate_recommended_action(self.delegated_profile(), action)
            self.assertEqual(result["status"], "operator_only", reserved)
            self.assertTrue(result["operator_actionable_now"], reserved)

    def test_incomplete_reserved_action_is_not_yet_operator_actionable(self):
        action = self.eligible_action()
        action["operator_only_action"] = "payment_or_purchase"
        action["evidence_complete"] = False
        action["exact_identity_and_surface"] = False
        result = evaluate_recommended_action(self.delegated_profile(), action)
        self.assertEqual(result["status"], "evidence_required")
        self.assertFalse(result["operator_actionable_now"])
        self.assertEqual(result["reserved_action"], "payment_or_purchase")

    def test_production_real_data_credentials_and_external_send_are_operator_only(self):
        for key, value in (
            ("nonproduction", False),
            ("no_real_customer_or_personal_data", False),
            ("no_credentials_or_secrets", False),
            ("external_send", True),
        ):
            action = self.eligible_action()
            action[key] = value
            result = evaluate_recommended_action(self.delegated_profile(), action)
            self.assertEqual(result["status"], "operator_only", key)
            self.assertTrue(result["operator_actionable_now"], key)

    def test_ambiguous_incomplete_or_dissenting_action_is_not_delegated(self):
        for key, value in (
            ("recommendation_count", 2),
            ("evidence_complete", False),
            ("no_unresolved_safety_dissent", False),
        ):
            action = self.eligible_action()
            action[key] = value
            result = evaluate_recommended_action(self.delegated_profile(), action)
            self.assertEqual(result["status"], "evidence_required", key)
            self.assertFalse(result["operator_actionable_now"], key)

    def test_metadata_read_requires_allowlist_limits_and_read_only_contract(self):
        action = self.eligible_action("metadata_only_allowlisted_read")
        rejected = evaluate_recommended_action(self.delegated_profile(), action)
        self.assertEqual(rejected["status"], "evidence_required")
        self.assertIn("fixed_read_allowlist", rejected["missing"])
        self.assertIn("positive_max_bytes", rejected["missing"])
        self.assertIn("read_only", rejected["missing"])
        self.assertIn("tokens_not_persisted", rejected["missing"])
        action.update({
            "target": "repo-metadata",
            "read_allowlist": ["git-status", "git-rev-parse"],
            "max_bytes": 65536,
            "timeout_seconds": 10,
            "read_only": True,
            "write_allowed": False,
            "write_roots": [],
            "tokens_persisted": False,
            "stop_condition": "first non-allowlisted response or size/time bound",
            "class_independent_verification": True,
        })
        self.assertEqual(
            evaluate_recommended_action(self.delegated_profile(), action)["status"],
            "delegated",
        )
        del action["external_send"]
        rejected = evaluate_recommended_action(self.delegated_profile(), action)
        self.assertIn("no_external_send", rejected["missing"])

    def test_disposable_test_requires_exact_target_stop_rollback_and_one_run(self):
        action = self.eligible_action("disposable_local_test_stop_rollback")
        rejected = evaluate_recommended_action(self.delegated_profile(), action)
        self.assertEqual(rejected["status"], "evidence_required")
        self.assertIn("absolute_disposable_target", rejected["missing"])
        action.update({
            "disposable_target": "/tmp/disposable-test-target",
            "target_is_disposable": True,
            "io_allowlist": ["/tmp/disposable-test-target"],
            "timeout_seconds": 30,
            "stop_condition": "first failure or 30 seconds",
            "rollback_steps": ["discard disposable target"],
            "max_runs": 1,
            "execution_count": 0,
            "automatic_rerun_requested": False,
        })
        self.assertEqual(
            evaluate_recommended_action(self.delegated_profile(), action)["status"],
            "delegated",
        )

    def test_bounded_repair_requires_existing_owner_surface_and_one_cycle(self):
        action = self.eligible_action(
            "bounded_repair_recheck_without_scope_expansion"
        )
        rejected = evaluate_recommended_action(self.delegated_profile(), action)
        self.assertEqual(rejected["status"], "evidence_required")
        self.assertIn("existing_write_owner", rejected["missing"])
        self.assertIn("no_scope_expansion", rejected["missing"])
        self.assertIn("frozen_candidate_sha256", rejected["missing"])
        action.update({
            "repair_target": "candidate-commit",
            "candidate_sha256": "c" * 64,
            "existing_write_owner": "source-chief",
            "existing_write_surface": ["scripts/preference_lib.py"],
            "repair_surface_unique": True,
            "write_owner_conflict": False,
            "no_scope_expansion": True,
            "max_repair_attempts": 1,
            "max_rechecks": 1,
            "repair_attempts_completed": 0,
            "rechecks_completed": 0,
            "automatic_rerun_requested": False,
            "failure_stop": True,
        })
        self.assertEqual(
            evaluate_recommended_action(self.delegated_profile(), action)["status"],
            "delegated",
        )

    def test_failure_or_drift_stops_without_rerun(self):
        for state in ("failed", "drifted", "out_of_scope"):
            action = self.eligible_action()
            action["execution_state"] = state
            result = evaluate_recommended_action(self.delegated_profile(), action)
            self.assertEqual(result["status"], "stopped")
            self.assertFalse(result["automatic_rerun"])

    def test_todo_filters_delegated_unready_and_unverified_visual_items(self):
        base = {
            "operator_actionable_now": True,
            "evidence_complete": True,
            "exact_identity_and_surface": True,
            "no_unresolved_safety_dissent": True,
            "authoritative_hub": "general_office",
            "state": "pending",
            "kind": "protected_action",
            "entry_available": True,
        }
        delegated = {**base, "id": "delegated", "state": "delegated"}
        unavailable = {**base, "id": "unavailable", "entry_available": False}
        incomplete = {**base, "id": "incomplete", "evidence_complete": False}
        visual_unverified = {
            **base,
            "id": "visual-unverified",
            "authoritative_hub": "creative_director",
            "kind": "visual_selection",
            "clickable_entry": True,
            "candidate_hash_frozen": True,
            "testing_gate": "pending",
        }
        visual_ready = {
            **visual_unverified,
            "id": "visual-ready",
            "testing_gate": "exact_pass",
        }
        result = filter_operator_todo_items(
            [delegated, unavailable, incomplete, visual_unverified, visual_ready]
        )
        self.assertEqual([item["id"] for item in result], ["visual-ready"])

    def test_resolved_or_delegated_heartbeat_item_does_not_repeat(self):
        items = [
            {
                "id": state,
                "operator_actionable_now": True,
                "evidence_complete": True,
                "exact_identity_and_surface": True,
                "no_unresolved_safety_dissent": True,
                "authoritative_hub": "general_office",
                "state": state,
                "kind": "protected_action",
                "entry_available": True,
            }
            for state in ("resolved", "delegated")
        ]
        self.assertEqual(filter_operator_todo_items(items), [])

    def test_configure_enables_delegation_on_legacy_profile_without_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            profile = self.delegated_profile()
            del profile["governance_model"]["continuation_policy"][
                "recommended_action_delegation"
            ]
            source = root / "legacy.json"
            source.write_text(json.dumps(profile), encoding="utf-8")
            result = run_config(
                "--input", source,
                "--scope", "global",
                "--data-root", data,
                "--profile-out", data / "chief-preferences.json",
                "--agents-file", root / "AGENTS.md",
                "--enable-recommended-action-delegation",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            configured = json.loads((data / "chief-preferences.json").read_text())
            self.assertTrue(
                configured["governance_model"]["continuation_policy"][
                    "recommended_action_delegation"
                ]["enabled"]
            )
            self.assertIn("DELEGATED_RECOMMENDATION_EXECUTED", (root / "AGENTS.md").read_text())

    def test_public_pin_presets_are_safe_and_id_free(self):
        for relative in (
            "assets/operator-preferences.example.json",
            "assets/presets/operator-controlled-bilingual.json",
        ):
            profile = json.loads((ROOT / relative).read_text())
            self.assertEqual(validate_preferences(profile), [])
            pin = profile["pin_governance"]
            self.assertFalse(pin["enabled"])
            self.assertEqual({item["role"] for item in pin["mandatory_core_roles"]}, {
                "general_office", "todo", "creative_director",
                "context_migration_monitor",
            })
            self.assertTrue(all(item["thread_id"] is None for item in pin["mandatory_core_roles"]))
            self.assertTrue(all(
                item["role"] in CHIEF_TITLE_EXCEPTION_ROLES
                or item["title"].startswith(CHIEF_TITLE_PREFIX)
                for item in pin["mandatory_core_roles"]
            ))
            self.assertEqual(pin["optional_chief_slots"]["limit"], 6)
            self.assertFalse(pin["optional_chief_slots"]["default_pin_primary_task"])
            self.assertEqual(pin["grandmothered_optional_chiefs"], [])
            self.assertEqual(pin["protected_manual_thread_ids"], [])
            self.assertEqual(pin["invalid_successor_thread_ids"], [])
            inheritance = profile["automation_inheritance"]
            self.assertFalse(inheritance["enabled"])
            self.assertEqual(inheritance["scope"], "bound_task_automations")
            self.assertEqual(inheritance["migration_gate"]["failure_status"], "MIGRATION_BLOCKED")
            self.assertTrue(inheritance["verification"]["live_evidence_required"])
            discovery = profile["project_start_capability_discovery"]
            self.assertTrue(discovery["enabled"])
            self.assertEqual(discovery["mode"], "coverage_first")
            self.assertTrue(discovery["require_reuse_before_build"])
            self.assertEqual(
                discovery["testing_director_review"],
                "required_for_test_capabilities",
            )

    def test_automation_inheritance_contract_fails_closed_when_weakened(self):
        profile = json.loads(
            (ROOT / "assets/operator-preferences.example.json").read_text()
        )
        profile["automation_inheritance"]["verification"]["reference_or_receipt_is_not_proof"] = False
        self.assertTrue(any(
            "reference_or_receipt_is_not_proof" in item
            for item in validate_preferences(profile)
        ))

    def test_legacy_profile_alias_migrates_one_way_and_dual_equal_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = self.enabled_pin_profile()
            current_value = [{"title": "Historical product Chief", "thread_id": "optional-1"}]
            profile["pin_governance"][CURRENT_PROFILE_KEY] = current_value
            profile["pin_governance"][LEGACY_PROFILE_KEY] = json.loads(json.dumps(current_value))
            source = root / "legacy-profile.json"
            source.write_text(json.dumps(profile), encoding="utf-8")
            checked = run_config("--check", source)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            migrated = read_json(source)
            self.assertEqual(migrated["pin_governance"][CURRENT_PROFILE_KEY], current_value)
            self.assertNotIn(LEGACY_PROFILE_KEY, migrated["pin_governance"])
            output = root / "normalized-profile.json"
            atomic_write_json(output, profile)
            persisted = json.loads(output.read_text())
            self.assertIn(CURRENT_PROFILE_KEY, persisted["pin_governance"])
            self.assertNotIn(LEGACY_PROFILE_KEY, persisted["pin_governance"])

    def test_conflicting_legacy_profile_alias_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = self.enabled_pin_profile()
            profile["pin_governance"][CURRENT_PROFILE_KEY] = []
            profile["pin_governance"][LEGACY_PROFILE_KEY] = [
                {"title": "Conflicting Chief", "thread_id": "different"}
            ]
            errors = validate_preferences(profile)
            self.assertEqual(errors, ["legacy and current pin-governance aliases disagree"])
            path = Path(tmp) / "conflict.json"
            path.write_text(json.dumps(profile), encoding="utf-8")
            checked = run_config("--check", path)
            self.assertEqual(checked.returncode, 2)
            self.assertIn("aliases disagree", checked.stderr)
            with self.assertRaises(PreferenceError):
                read_json(path)

    def test_enabled_pin_governance_requires_four_unique_exact_ids(self):
        profile = self.enabled_pin_profile()
        self.assertEqual(validate_preferences(profile), [])
        profile["pin_governance"]["mandatory_core_roles"][0]["thread_id"] = None
        self.assertTrue(any("thread_id for every core role" in item for item in validate_preferences(profile)))
        profile = self.enabled_pin_profile()
        profile["pin_governance"]["mandatory_core_roles"][1]["thread_id"] = "core-0"
        self.assertTrue(any("must be unique" in item for item in validate_preferences(profile)))

    def test_core_chief_titles_require_prefix_except_registered_non_chiefs(self):
        profile = self.enabled_pin_profile()
        creative = next(
            item for item in profile["pin_governance"]["mandatory_core_roles"]
            if item["role"] == "creative_director"
        )
        creative["title"] = "Creative Director"
        self.assertTrue(any(
            "must start with 'Chief of '" in item
            for item in validate_preferences(profile)
        ))

        profile = self.enabled_pin_profile()
        office = next(
            item for item in profile["pin_governance"]["mandatory_core_roles"]
            if item["role"] == "general_office"
        )
        office["title"] = "冯宝宝"
        self.assertEqual(validate_preferences(profile), [])

    def test_context_monitor_system_title_is_valid_and_testing_is_not_pin_core(self):
        profile = self.enabled_pin_profile()
        monitor = next(
            item for item in profile["pin_governance"]["mandatory_core_roles"]
            if item["role"] == "context_migration_monitor"
        )
        monitor["title"] = "系统｜上下文迁移监视器"
        self.assertEqual(validate_preferences(profile), [])
        self.assertNotIn(
            "testing_director",
            {item["role"] for item in profile["pin_governance"]["mandatory_core_roles"]},
        )

    def test_capability_discovery_contract_fails_closed_when_weakened(self):
        profile = json.loads(
            (ROOT / "assets/operator-preferences.example.json").read_text()
        )
        profile["project_start_capability_discovery"]["require_reuse_before_build"] = False
        self.assertTrue(any(
            "project_start_capability_discovery.require_reuse_before_build" in item
            for item in validate_preferences(profile)
        ))

    def test_capability_discovery_missing_and_legacy_profiles_are_compatible(self):
        missing = json.loads(
            (ROOT / "assets/operator-preferences.example.json").read_text()
        )
        del missing["project_start_capability_discovery"]
        self.assertEqual(validate_preferences(missing), [])
        self.assertEqual(
            evaluate_capability_discovery(missing, {"trigger": "project_start"})[
                "status"
            ],
            "disabled",
        )

        legacy = json.loads(
            (ROOT / "assets/operator-preferences.example.json").read_text()
        )
        section = legacy["project_start_capability_discovery"]
        self.assertNotIn("trigger_policy", section)
        self.assertEqual(section["acquisition_policy"], "selected_fit_only_after_review")
        self.assertEqual(validate_preferences(legacy), [])
        self.assertEqual(
            evaluate_capability_discovery(
                legacy, {"trigger": "phase_or_stack_change"}
            )["status"],
            "not_due",
        )
        self.assertEqual(
            evaluate_capability_discovery(
                legacy, {"trigger": "before_production_execution"}
            )["mode"],
            "legacy_startup",
        )

    def test_lifecycle_discovery_exact_contract_and_partial_fields_fail_closed(self):
        profile = self.lifecycle_discovery_profile()
        self.assertEqual(profile["schema_version"], 1)
        section = profile["project_start_capability_discovery"]
        self.assertEqual(validate_preferences(profile), [])
        self.assertEqual(section["triggers"], CAPABILITY_DISCOVERY_TRIGGERS)
        self.assertEqual(section["max_parallel_scans"], 2)
        self.assertEqual(section["max_candidates_per_trigger"], 3)
        self.assertEqual(section["acquisition_policy"], "discover_and_recommend_only")
        self.assertEqual(section["serious_candidate_evidence"], CAPABILITY_DISCOVERY_EVIDENCE)

        partial = json.loads(
            (ROOT / "assets/operator-preferences.example.json").read_text()
        )
        partial["project_start_capability_discovery"]["scope"] = "all_registered_chiefs"
        errors = validate_preferences(partial)
        self.assertTrue(any("trigger_policy" in error for error in errors))
        self.assertTrue(any("acquisition_policy" in error for error in errors))

        weakened = self.lifecycle_discovery_profile()
        weakened["project_start_capability_discovery"]["max_parallel_scans"] = 3
        self.assertTrue(any(
            "max_parallel_scans" in error for error in validate_preferences(weakened)
        ))
        for key in CAPABILITY_DISCOVERY_LIFECYCLE_EXACT:
            invalid = self.lifecycle_discovery_profile()
            invalid["project_start_capability_discovery"][key] = None
            self.assertTrue(
                any(f".{key} is invalid" in error for error in validate_preferences(invalid)),
                key,
            )

    def test_lifecycle_discovery_runs_all_six_triggers_and_excludes_stale_work(self):
        profile = self.lifecycle_discovery_profile()
        for trigger in CAPABILITY_DISCOVERY_TRIGGERS:
            result = evaluate_capability_discovery(profile, {
                "trigger": trigger,
                "chief_registered": True,
                "lifecycle_status": "active",
            })
            self.assertEqual(result["status"], "discovery_due")
            self.assertEqual(result["max_parallel_scans"], 2)
            self.assertEqual(result["allowed_actions"], ["discover", "evaluate", "recommend"])
            self.assertFalse(result["mutation_performed"])
        for lifecycle_status, expected in (
            ("paused", "deferred"),
            ("completed", "excluded"),
            ("archived", "excluded"),
        ):
            result = evaluate_capability_discovery(profile, {
                "trigger": "project_start",
                "chief_registered": True,
                "lifecycle_status": lifecycle_status,
            })
            self.assertEqual(result["status"], expected)
        self.assertEqual(
            evaluate_capability_discovery(profile, {
                "trigger": "project_start", "chief_registered": False,
                "lifecycle_status": "active",
            })["status"],
            "not_applicable",
        )

    def test_lifecycle_discover_only_blocks_every_acquisition_or_mutation(self):
        profile = self.lifecycle_discovery_profile()
        for action in CAPABILITY_DISCOVERY_PROHIBITED_ACTIONS:
            result = evaluate_capability_discovery(profile, {
                "trigger": "project_start",
                "chief_registered": True,
                "lifecycle_status": "active",
                "requested_action": action,
            })
            self.assertEqual(result["status"], "blocked", action)
            self.assertTrue(result["operator_approval_required"])
            self.assertFalse(result["mutation_performed"])

    def test_lifecycle_recommendations_dedupe_bound_route_and_stay_out_of_todo(self):
        profile = self.lifecycle_discovery_profile()
        base = self.capability_packet()
        duplicate = route_capability_recommendations(profile, {
            **base,
            "existing_pack_ids": [base["pack_id"]],
            "candidates": [self.capability_candidate()],
        })
        self.assertEqual(duplicate["status"], "duplicate_suppressed")
        self.assertFalse(duplicate["operator_actionable_now"])

        internal = route_capability_recommendations(profile, {
            **base,
            "candidates": [self.capability_candidate(material=False)],
        })
        self.assertEqual(internal["status"], "internal_evidence_only")
        self.assertFalse(internal["operator_actionable_now"])
        install_recommendation = route_capability_recommendations(profile, {
            **base,
            "candidates": [self.capability_candidate(decision="install")],
        })
        self.assertEqual(
            install_recommendation["status"], "internal_evidence_only"
        )
        routine = route_capability_recommendations(profile, {
            **base,
            "routine_scan": True,
            "candidates": [self.capability_candidate()],
        })
        self.assertEqual(routine["status"], "internal_evidence_only")
        self.assertEqual(routine["reason"], "routine_scan")

        candidates = [self.capability_candidate() for _ in range(5)]
        candidates[0]["testing_related"] = True
        candidates[1]["visual_direction"] = True
        routed = route_capability_recommendations(profile, {
            **base, "candidates": candidates,
        })
        self.assertEqual(routed["status"], "material_recommendation_ready")
        self.assertEqual(len(routed["candidates"]), 3)
        self.assertEqual(
            routed["routes"],
            ["testing_director", "creative_director", "general_office"],
        )
        self.assertFalse(routed["operator_actionable_now"])
        self.assertFalse(routed["mutation_performed"])

    def test_lifecycle_candidate_evidence_and_prior_denial_fail_closed(self):
        profile = self.lifecycle_discovery_profile()
        packet = {
            **self.capability_packet(trigger="before_custom_build"),
            "candidates": [self.capability_candidate()],
        }
        incomplete = json.loads(json.dumps(packet))
        del incomplete["candidates"][0]["exit_removal_path"]
        result = route_capability_recommendations(profile, incomplete)
        self.assertEqual(result["status"], "internal_evidence_only")
        self.assertIn("exit_removal_path", result["rejected"][0]["missing"])
        denied = route_capability_recommendations(
            profile, {**packet, "prior_operator_denial": True}
        )
        self.assertEqual(denied["status"], "blocked")
        self.assertEqual(denied["reason"], "prior_operator_denial")

    def test_lifecycle_evidence_rejects_booleans_and_sentinels(self):
        profile = self.lifecycle_discovery_profile()
        false_evidence = {
            key: False for key in CAPABILITY_DISCOVERY_EVIDENCE
        }
        false_evidence.update({"material": True, "decision": "recommend"})
        result = route_capability_recommendations(
            profile,
            self.capability_packet(candidates=[false_evidence]),
        )
        self.assertEqual(result["status"], "internal_evidence_only")
        self.assertEqual(
            set(result["rejected"][0]["missing"]),
            set(CAPABILITY_DISCOVERY_EVIDENCE),
        )
        sentinel = self.capability_candidate(
            source="unknown", fixed_version_or_revision="TBD"
        )
        result = route_capability_recommendations(
            profile,
            self.capability_packet(candidates=[sentinel]),
        )
        self.assertIn("source", result["rejected"][0]["missing"])
        self.assertIn(
            "fixed_version_or_revision", result["rejected"][0]["missing"]
        )
        untraceable = self.capability_candidate(source="project homepage")
        result = route_capability_recommendations(
            profile,
            self.capability_packet(candidates=[untraceable]),
        )
        self.assertIn("source", result["rejected"][0]["missing"])

    def test_lifecycle_numeric_evidence_requires_finite_values(self):
        profile = self.lifecycle_discovery_profile()
        numeric_evidence = [
            key for key in CAPABILITY_DISCOVERY_EVIDENCE
            if key not in {"source", "fixed_version_or_revision"}
        ]
        for nonfinite in (float("nan"), float("inf"), float("-inf")):
            candidate = self.capability_candidate()
            for key in numeric_evidence:
                candidate[key] = nonfinite
            if nonfinite != nonfinite:
                candidate = json.loads(json.dumps(candidate))
            result = route_capability_recommendations(
                profile,
                self.capability_packet(candidates=[candidate]),
            )
            self.assertEqual(result["status"], "internal_evidence_only")
            self.assertNotEqual(result["status"], "material_recommendation_ready")
            self.assertEqual(result["candidates"], [])
            self.assertEqual(
                set(result["rejected"][0]["missing"]), set(numeric_evidence)
            )
            self.assertFalse(result["operator_actionable_now"])
            self.assertFalse(result["mutation_performed"])
            self.assertNotIn("acquisition", result)
            self.assertNotIn("external_send", result)

        for finite in (0, -7, 1.5, -2.75):
            candidate = self.capability_candidate()
            for key in numeric_evidence:
                candidate[key] = finite
            result = route_capability_recommendations(
                profile,
                self.capability_packet(candidates=[candidate]),
            )
            self.assertEqual(result["status"], "material_recommendation_ready")

    def test_lifecycle_pack_id_is_bound_to_chief_trigger_and_evidence(self):
        profile = self.lifecycle_discovery_profile()
        packet = self.capability_packet(candidates=[self.capability_candidate()])
        self.assertEqual(
            route_capability_recommendations(profile, packet)["status"],
            "material_recommendation_ready",
        )
        forged = {
            **packet,
            "pack_id": "pack-b",
            "existing_pack_ids": [packet["pack_id"]],
        }
        result = route_capability_recommendations(profile, forged)
        self.assertEqual(result["status"], "evidence_required")
        self.assertIn("bound_pack_id", result["missing"])
        duplicate = {**packet, "existing_pack_ids": [packet["pack_id"]]}
        self.assertEqual(
            route_capability_recommendations(profile, duplicate)["status"],
            "duplicate_suppressed",
        )

    def test_lifecycle_prior_denial_precedes_duplicate_and_action_branches(self):
        profile = self.lifecycle_discovery_profile()
        packet = self.capability_packet(
            candidates=[self.capability_candidate()],
            prior_operator_denial=True,
            requested_action="install",
        )
        packet["existing_pack_ids"] = [packet["pack_id"]]
        result = route_capability_recommendations(profile, packet)
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["reason"], "prior_operator_denial")

    def test_direct_evaluator_requires_lifecycle_state_and_never_marks_todo(self):
        profile = self.lifecycle_discovery_profile()
        missing = evaluate_capability_discovery(profile, {
            "trigger": "project_start", "chief_registered": True,
        })
        self.assertEqual(missing["status"], "evidence_required")
        self.assertIn("lifecycle_status", missing["missing"])
        results = [
            missing,
            evaluate_capability_discovery(profile, {
                "trigger": "project_start", "chief_registered": True,
                "lifecycle_status": "active",
            }),
            evaluate_capability_discovery(profile, {
                "trigger": "project_start", "chief_registered": True,
                "lifecycle_status": "paused",
            }),
            evaluate_capability_discovery(profile, {
                "trigger": "project_start", "chief_registered": True,
                "lifecycle_status": "completed",
            }),
        ]
        self.assertTrue(all(
            result.get("operator_actionable_now") is False
            for result in results
        ))

    def test_configurator_enables_complete_lifecycle_discovery_without_touching_preset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            agents = root / "AGENTS.md"
            result = run_config(
                "--preset", "core",
                "--scope", "global",
                "--enable-lifecycle-capability-discovery",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            profile = json.loads((data / "chief-preferences.json").read_text())
            section = profile["project_start_capability_discovery"]
            self.assertEqual(section["scope"], "all_registered_chiefs")
            self.assertEqual(section["triggers"], CAPABILITY_DISCOVERY_TRIGGERS)
            self.assertEqual(section["acquisition_policy"], "discover_and_recommend_only")
            self.assertEqual(validate_preferences(profile), [])
            managed = agents.read_text()
            self.assertIn("all registered Chiefs", managed)
            self.assertIn("discover/evaluate/recommend only", managed)
            public = json.loads(
                (ROOT / "assets/operator-preferences.example.json").read_text()
            )
            self.assertNotIn("trigger_policy", public["project_start_capability_discovery"])

    def test_pin_recommendation_is_bounded_and_excludes_stale_or_process_work(self):
        profile = self.enabled_pin_profile()
        candidates = [self.pin_candidate(f"candidate-{index}", score=0.9 - index / 20) for index in range(5)]
        candidates.extend([
            self.pin_candidate("paused", status="paused"),
            self.pin_candidate("process", work_kind="routine_push"),
        ])
        candidates[1]["evidence_fresh"] = False
        result = recommend_optional_chief_pins(profile, {
            "observed_capacity": 20,
            "pending_packs": 0,
            "pinned_threads": [],
            "candidates": candidates,
        })
        self.assertEqual(result["status"], "recommendation_ready")
        self.assertLessEqual(len(result["candidates"]), 3)
        reasons = {item["thread_id"]: item["reason"] for item in result["excluded"]}
        self.assertIn("paused", reasons["paused"])
        self.assertIn("routine_push", reasons["process"])
        self.assertIn("stale_evidence", reasons["candidate-1"])
        self.assertTrue(result["operator_approval_required"])
        self.assertFalse(result["mutation_performed"])

    def test_full_capacity_protects_manual_pin_and_only_pairs_optional_replacement(self):
        profile = self.enabled_pin_profile()
        profile["pin_governance"]["protected_manual_thread_ids"] = ["manual"]
        low = {key: 0.1 for key in PIN_CRITERIA}
        pinned = [
            {"thread_id": "manual", "title": "Manual", "pin_class": "manual_non_chief"},
            {"thread_id": "old-optional", "title": "Old", "pin_class": LEGACY_SNAPSHOT_PIN_CLASS, "signals": low},
        ]
        result = recommend_optional_chief_pins(profile, {
            "observed_capacity": 2,
            "pending_packs": 0,
            "pinned_threads": pinned,
            "candidates": [self.pin_candidate("new")],
        })
        self.assertEqual(result["status"], "paired_replacement_recommendation")
        self.assertEqual(result["paired_replacement"]["remove_thread_id"], "old-optional")
        self.assertFalse(result["paired_replacement"]["automatic_eviction"])
        self.assertIn("manual", result["protected_manual_thread_ids"])
        pending = recommend_optional_chief_pins(profile, {
            "observed_capacity": 3,
            "pending_packs": 1,
            "pinned_threads": pinned,
            "candidates": [self.pin_candidate("new")],
        })
        self.assertEqual(pending["status"], "pending_pack_exists")
        self.assertEqual(pending["candidates"], [])

    def test_core_global_profile_preserves_existing_agents_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            agents = root / "AGENTS.md"
            agents.write_text("# Existing rule\n", encoding="utf-8")
            result = run_config(
                "--preset", "core",
                "--scope", "global",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            profile_path = data / "chief-preferences.json"
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(profile["report_review_mode"], "exception_only")
            self.assertFalse(profile["governance_model"]["enabled"])
            self.assertFalse(
                profile["governance_model"]["continuation_policy"]["enabled"]
            )
            self.assertFalse(profile["visual_selection_gate"]["enabled"])
            self.assertFalse(profile["american_english_coaching"]["enabled"])
            self.assertFalse(profile["audio_playback"]["enabled"])
            content = agents.read_text(encoding="utf-8")
            self.assertIn("# Existing rule", content)
            self.assertEqual(content.count("chief-of-staff-preferences:start"), 1)
            self.assertIn("automation_inheritance.enabled", content)
            self.assertIn("automation_rebind_failed", content)
            self.assertIn("project_start_capability_discovery.enabled", content)
            self.assertIn("Keep project runtime paths portable", content)
            self.assertIn("stable `root_id` and project-relative POSIX paths", content)
            self.assertIn("reject absolute project input, parent traversal", content)
            self.assertIn("Preserve historical absolute-path evidence unchanged", content)
            self.assertIn("portable derivatives use a new hash and `derived_from`", content)
            self.assertEqual(profile["schema_version"], 1)
            self.assertIn("Testing Director is an ordinary, default-unpinned", content)
            self.assertIn("Name every durable Chief task", content)

    def test_operator_preset_reconfigures_managed_block_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            agents = root / "AGENTS.md"
            agents.write_text("# Keep me\n", encoding="utf-8")
            command = (
                "--preset", "operator-controlled-bilingual",
                "--scope", "global",
                "--salutation", "妈妈",
                "--audio-provider", "macos_say",
                "--voice", "Samantha",
                "--audio-rate", "170",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(run_config(*command).returncode, 0)
            self.assertEqual(run_config(*command).returncode, 0)
            profile = json.loads((data / "chief-preferences.json").read_text())
            self.assertTrue(profile["visual_selection_gate"]["enabled"])
            self.assertEqual(profile["report_review_mode"], "exception_only")
            self.assertFalse(profile["governance_model"]["enabled"])
            self.assertEqual(
                profile["visual_selection_gate"]["review_hub_title"],
                "Chief of Creative Direction｜创意总监",
            )
            self.assertTrue(profile["american_english_coaching"]["include_casual_chat"])
            self.assertEqual(profile["audio_playback"]["clips"], ["written", "spoken"])
            self.assertEqual(
                profile["audio_playback"]["storage_root"],
                str((data / "english-audio").resolve()),
            )
            self.assertEqual(profile["operator_salutation"]["value"], "妈妈")
            self.assertEqual(profile["audio_playback"]["voice"], "Samantha")
            self.assertEqual(profile["audio_playback"]["rate"], 170)
            content = agents.read_text()
            self.assertEqual(content.count("chief-of-staff-preferences:start"), 1)
            self.assertIn("# Keep me", content)

    def test_reconfigure_preserves_unknown_top_level_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            agents = root / "AGENTS.md"
            first = run_config(
                "--preset", "core",
                "--scope", "global",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            profile_path = data / "chief-preferences.json"
            profile = json.loads(profile_path.read_text())
            profile["future_extension"] = {"keep": True}
            profile_path.write_text(json.dumps(profile), encoding="utf-8")
            second = run_config(
                "--preset", "operator-controlled-bilingual",
                "--scope", "global",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            updated = json.loads(profile_path.read_text())
            self.assertEqual(updated["future_extension"], {"keep": True})

    def test_custom_input_applies_independent_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            custom = json.loads(
                (ROOT / "assets/operator-preferences.example.json").read_text()
            )
            custom["american_english_coaching"]["enabled"] = True
            custom["american_english_coaching"]["include_casual_chat"] = True
            custom_path = root / "custom.json"
            custom_path.write_text(json.dumps(custom), encoding="utf-8")
            result = run_config(
                "--input", custom_path,
                "--scope", "global",
                "--data-root", data,
                "--agents-file", root / "AGENTS.md",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            profile = json.loads((data / "chief-preferences.json").read_text())
            self.assertEqual(profile["preset"], "custom")
            self.assertTrue(profile["american_english_coaching"]["enabled"])
            self.assertFalse(profile["visual_selection_gate"]["enabled"])
            self.assertFalse(profile["audio_playback"]["enabled"])

    def test_core_reconfigure_explicitly_disables_personal_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            agents = root / "AGENTS.md"
            enabled = run_config(
                "--preset", "operator-controlled-bilingual",
                "--scope", "global",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(enabled.returncode, 0, enabled.stderr)
            disabled = run_config(
                "--preset", "core",
                "--scope", "global",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(disabled.returncode, 0, disabled.stderr)
            profile = json.loads((data / "chief-preferences.json").read_text())
            for key in (
                "governance_model",
                "visual_selection_gate",
                "american_english_coaching",
                "audio_playback",
                "operator_salutation",
                "paused_title_prefix",
                "reminders",
            ):
                self.assertFalse(profile[key]["enabled"], key)

    def test_custom_chair_governance_requires_general_office_and_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            custom = json.loads(
                (ROOT / "assets/operator-preferences.example.json").read_text()
            )
            custom["governance_model"]["enabled"] = True
            custom["governance_model"]["general_office_thread_id"] = "thread-general-office"
            custom["governance_model"]["continuation_policy"]["enabled"] = True
            custom_path = root / "custom.json"
            custom_path.write_text(json.dumps(custom), encoding="utf-8")
            result = run_config(
                "--input", custom_path,
                "--scope", "global",
                "--data-root", data,
                "--agents-file", root / "AGENTS.md",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            profile = json.loads((data / "chief-preferences.json").read_text())
            self.assertTrue(profile["governance_model"]["enabled"])
            self.assertEqual(
                profile["governance_model"]["general_office_thread_id"],
                "thread-general-office",
            )
            self.assertIn("CHAIR_BRIEF_READY", (root / "AGENTS.md").read_text())
            self.assertIn(
                "strongest evidence-backed safe in-scope continuation",
                (root / "AGENTS.md").read_text(),
            )
            generated_agents = (root / "AGENTS.md").read_text()
            self.assertIn("at most one atomic build+verify per source-task safe boundary", generated_agents)
            self.assertIn("without `USER_ACTION_REQUIRED`", generated_agents)

    def test_continuation_policy_requires_enabled_governance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            custom = json.loads(
                (ROOT / "assets/operator-preferences.example.json").read_text()
            )
            custom["governance_model"]["continuation_policy"]["enabled"] = True
            custom_path = root / "custom.json"
            custom_path.write_text(json.dumps(custom), encoding="utf-8")
            result = run_config(
                "--input", custom_path,
                "--scope", "global",
                "--data-root", data,
                "--agents-file", root / "AGENTS.md",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn(
                "enabled continuation_policy requires enabled governance_model",
                result.stderr,
            )

    def test_missing_custom_data_root_fails_without_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "missing-volume" / "data"
            result = run_config(
                "--preset", "operator-controlled-bilingual",
                "--scope", "global",
                "--data-root", missing,
                "--agents-file", root / "AGENTS.md",
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(missing.exists())
            self.assertFalse((root / "AGENTS.md").exists())

    def test_project_scope_writes_only_project_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            result = run_config(
                "--preset", "core",
                "--scope", "project",
                "--project-root", project,
                "--agents-file", Path(tmp) / "global-agents.md",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            profile = json.loads(
                (project / ".chief-of-staff/preferences.json").read_text()
            )
            self.assertEqual(profile["scope"], "project")
            self.assertFalse((Path(tmp) / "global-agents.md").exists())

    def test_audio_renderer_creates_separate_cached_clip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            agents = root / "AGENTS.md"
            configured = run_config(
                "--preset", "operator-controlled-bilingual",
                "--scope", "global",
                "--salutation", "妈妈",
                "--audio-provider", "macos_say",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(configured.returncode, 0, configured.stderr)

            fake_say = root / "say"
            fake_say.write_text(
                "#!/bin/sh\nout=''\nwhile [ $# -gt 0 ]; do\n"
                "  if [ \"$1\" = '-o' ]; then shift; out=$1; fi\n"
                "  shift\ndone\nprintf 'M4A-DATA' > \"$out\"\n",
                encoding="utf-8",
            )
            fake_say.chmod(fake_say.stat().st_mode | stat.S_IXUSR)
            env = dict(
                os.environ,
                CHIEF_AUDIO_PLATFORM="Darwin",
                CHIEF_SAY_BIN=str(fake_say),
            )
            command = [
                sys.executable, str(RENDER),
                "--profile", str(data / "chief-preferences.json"),
                "--kind", "written",
                "--text", "Please resume the interrupted work.",
            ]
            first = subprocess.run(command, text=True, capture_output=True, env=env)
            second = subprocess.run(command, text=True, capture_output=True, env=env)
            self.assertEqual(first.returncode, 0, first.stderr)
            first_result = json.loads(first.stdout)
            second_result = json.loads(second.stdout)
            self.assertEqual(first_result["status"], "ready")
            self.assertFalse(first_result["cached"])
            self.assertTrue(second_result["cached"])
            self.assertEqual(first_result["path"], second_result["path"])
            self.assertEqual(Path(first_result["path"]).read_bytes(), b"M4A-DATA")
            self.assertFalse(list((data / "english-audio").glob(".chief-audio-*")))

    def test_audio_missing_root_returns_text_only_without_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = json.loads(
                (ROOT / "assets/presets/operator-controlled-bilingual.json").read_text()
            )
            profile["audio_playback"]["provider"] = "macos_say"
            profile["audio_playback"]["storage_root"] = str(root / "missing")
            profile_path = root / "profile.json"
            profile_path.write_text(json.dumps(profile), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable, str(RENDER),
                    "--profile", str(profile_path),
                    "--kind", "spoken",
                    "--text", "Pick up where you left off.",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["status"], "text_only")
            self.assertFalse((root / "missing").exists())

    def test_host_builtin_voice_generates_no_audio_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            agents = root / "AGENTS.md"
            configured = run_config(
                "--preset", "operator-controlled-bilingual",
                "--scope", "global",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(configured.returncode, 0, configured.stderr)
            profile_path = data / "chief-preferences.json"
            profile = json.loads(profile_path.read_text())
            self.assertEqual(profile["audio_playback"]["provider"], "host_builtin")
            self.assertIsNone(profile["audio_playback"]["storage_root"])
            self.assertFalse((data / "english-audio").exists())

            rendered = subprocess.run(
                [
                    sys.executable, str(RENDER),
                    "--profile", str(profile_path),
                    "--kind", "spoken",
                    "--text", "Use the built-in voice.",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            result = json.loads(rendered.stdout)
            self.assertEqual(result["status"], "text_only")
            self.assertIn("host built-in voice", result["reason"])


if __name__ == "__main__":
    unittest.main()
