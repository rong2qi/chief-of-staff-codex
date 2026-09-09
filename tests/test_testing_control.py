"""Behavior regressions for Chief v2.0.2 non-blocking Testing control."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import unittest

from scripts import testing_control as policy


FIXTURE = Path(__file__).parent / "fixtures/testing-control-v2.0.2.json"
SHA = "a" * 40
OLD_SHA = "b" * 40


def delta(*rows, tests=None):
    tests = tests if tests is not None else [
        {"test_id": row["test_id"], "scope": row.get("scope", row["test_id"] + " scope")}
        for row in rows if row.get("classification") != "INHERITED_PASS"
    ]
    return {
        "current_candidate_sha": SHA,
        "impact_map": list(rows),
        "testing_payload": {"candidate_sha": SHA, "tests": tests},
    }


def impacted(test_id="changed"):
    return {"test_id": test_id, "classification": "RETEST_REQUIRED",
            "source_candidate_sha": OLD_SHA, "evidence_hash": "e" * 64,
            "changed_paths": [f"src/{test_id}.py"],
            "reasons": ["Git diff intersects tested inputs or dependencies"]}


class TestingControlTests(unittest.TestCase):
    def test_ack_records_state_without_reasoning_or_wait(self):
        result = policy.process_events([{"type": "TESTING_INTAKE_ACK"}])
        self.assertEqual(result["status"], "TELEMETRY_RECORDED")
        self.assertEqual(result["reasoning_turns"], 0)
        self.assertFalse(result["wait"])

    def test_scope_update_ack_cannot_preempt_implementer_completed(self):
        result = policy.process_events([
            {"type": "TESTING_SCOPE_UPDATE_ACK"},
            {"type": "IMPLEMENTER_COMPLETED", "candidate": SHA},
        ])
        self.assertEqual(result["next_event"]["type"], "IMPLEMENTER_COMPLETED")
        self.assertEqual(result["actionable_events"], [
            {"type": "IMPLEMENTER_COMPLETED", "candidate": SHA}])

    def test_dependency_ready_cannot_preempt_build_critical_path(self):
        result = policy.process_events([
            {"type": "TESTING_DEPENDENCY_READY"},
            {"type": "BUILD_SUCCEEDED", "artifact": "release.apk"},
        ], build_critical_path=True)
        self.assertEqual(result["next_event"]["type"], "BUILD_SUCCEEDED")
        self.assertTrue(result["build_critical_path"])
        self.assertEqual(result["reasoning_turns"], 1)

    def test_unchanged_tested_scope_is_inherited_without_request(self):
        inherited = {"test_id": "stable", "classification": "INHERITED_PASS",
                     "source_candidate_sha": OLD_SHA, "evidence_hash": "e" * 64,
                     "changed_paths": [], "reasons": ["unchanged"]}
        result = policy.decide_testing(delta(inherited, tests=[]), risk_level="L2")
        self.assertEqual(result["status"], "INHERITED_PASS")
        self.assertIsNone(result["testing_request"])

    def test_single_file_change_generates_only_targeted_justification(self):
        changed, stable = impacted("one"), {
            "test_id": "stable", "classification": "INHERITED_PASS",
            "source_candidate_sha": OLD_SHA, "evidence_hash": "f" * 64,
            "changed_paths": ["src/one.py"], "reasons": ["unchanged scope"]}
        result = policy.decide_testing(delta(changed, stable), risk_level="L2",
            new_risks=["changed command behavior"],
            why_local_insufficient="business contract needs independent observation")
        request = result["testing_request"]
        self.assertEqual([x["test_id"] for x in request["testing_payload"]["tests"]], ["one"])
        self.assertEqual(request["justification"]["changed_paths_assets"], ["src/one.py"])

    def test_integration_only_never_expands_to_full_retest(self):
        stable = {"test_id": "m1", "classification": "INHERITED_PASS",
                  "source_candidate_sha": OLD_SHA, "evidence_hash": "e" * 64,
                  "changed_paths": [], "reasons": ["unchanged"]}
        smoke = {"test_id": "integration-smoke", "classification": "INTEGRATION_ONLY",
                 "source_candidate_sha": None, "changed_paths": [],
                 "reasons": ["combination-only wiring/shared-state risk"]}
        result = policy.decide_testing(delta(stable, smoke), risk_level="L2",
            why_local_insufficient="first combined runtime interaction needs independent smoke")
        tests = result["testing_request"]["testing_payload"]["tests"]
        self.assertEqual([test["test_id"] for test in tests], ["integration-smoke"])
        self.assertEqual(result["testing_request"]["justification"]["previous_tested_sha_evidence"],
                         [{"candidate_sha": OLD_SHA, "evidence_id": "e" * 64}])

    def test_l0_skill_install_uses_deterministic_local_evidence(self):
        result = policy.decide_testing(delta(impacted("skill-manifest")), risk_level="L0",
            local_evidence_sufficient=True, new_risks=["new installed files"])
        self.assertEqual(result["status"], "LOCAL_CHECK_PASS")
        self.assertIsNone(result["testing_request"])
        self.assertFalse(result["blocking"])

    def test_empty_items_becomes_infra_error_not_product_failure(self):
        first = policy.consume_delivery({"attempts": 1}, {"items": []})
        final = policy.consume_delivery({"attempts": first["attempts"]}, {"items": []})
        self.assertEqual(final["status"], "TESTING_INFRA_ERROR")
        self.assertFalse(final["product_failed"])
        self.assertEqual(final["candidate_state"], "LOCAL_CANDIDATE_READY / TESTING_INFRA_ERROR")
        contradictory = policy.consume_delivery(
            {"attempts": 2}, {"status": "TESTING_GATE_PASS", "items": []})
        self.assertEqual(contradictory["status"], "TESTING_INFRA_ERROR")

    def test_delivery_retry_budget_is_exactly_one_automatic_retry(self):
        first = policy.consume_delivery({"attempts": 1}, {"status": "timeout"})
        self.assertEqual(first, {"schema": policy.SCHEMA, "status": "RETRY_TESTING_DELIVERY",
            "attempts": 2, "product_failed": False, "retry": True, "wait": False})
        second = policy.consume_delivery({"attempts": 2}, {"status": "transport_failure"})
        self.assertFalse(second["retry"])
        with self.assertRaises(ValueError):
            policy.consume_delivery({"attempts": 3}, {"status": "timeout"})

    def test_testing_pending_does_not_stop_other_runnable_module(self):
        result = policy.schedule_modules([
            {"module_id": "ali", "testing_status": "TESTING_PENDING", "risk_level": "L2"},
            {"module_id": "next", "runnable": True, "risk_level": "L1"},
        ])
        self.assertEqual(result["status"], "CONTINUE_RUNNABLE_MODULE")
        self.assertEqual(result["next_module"], "next")
        self.assertFalse(result["wait"])

    def test_creative_visual_revisions_batch_without_one_to_one_testing(self):
        revisions = [{"new_risks": []} for _ in range(5)]
        result = policy.creative_iteration(revisions)
        self.assertEqual(result["testing_round_trips"], 0)
        risky = revisions + [{"asset_provenance_changed": True, "meaningful_boundary": True}]
        result = policy.creative_iteration(risky, risk_level="L2")
        self.assertEqual(result["testing_round_trips"], 1)
        self.assertLess(result["testing_round_trips"], result["revision_count"])

    def test_l3_sync_gate_blocks_only_the_dangerous_action(self):
        result = policy.decide_testing(delta(impacted("signing")), risk_level="L3",
            new_risks=["production signing identity changed"],
            why_local_insufficient="production certificate must be independently verified")
        self.assertTrue(result["blocking"])
        self.assertEqual(result["blocked_action"], "dangerous promotion")
        schedule = policy.schedule_modules([
            {"module_id": "sign", "testing_status": "TESTING_PENDING", "risk_level": "L3"},
            {"module_id": "docs", "runnable": True, "risk_level": "L0"},
        ])
        self.assertEqual(schedule["next_module"], "docs")

    def test_pending_never_claims_testing_pass(self):
        result = policy.decide_testing(delta(impacted()), risk_level="L2",
            new_risks=["business output changed"],
            why_local_insufficient="target behavior needs independent observation")
        rendered = json.dumps(result, sort_keys=True)
        self.assertNotIn("TESTING_GATE_PASS", rendered)
        self.assertEqual(result["candidate_state"], "LOCAL_CANDIDATE_READY / TESTING_PENDING")

    def test_local_candidate_can_be_ready_without_testing_verdict(self):
        result = policy.schedule_modules([
            {"module_id": "candidate", "testing_status": "TESTING_PENDING", "risk_level": "L2"},
        ])
        self.assertEqual(result["status"], "LOCAL_CANDIDATE_READY / TESTING_PENDING")
        self.assertFalse(result["wait"])

    def test_telemetry_storm_cannot_starve_real_events(self):
        storm = [{"type": name} for name in (
            ["TESTING_INTAKE_ACK"] * 40 + ["TESTING_DEPENDENCY_READY"] * 40
            + ["TESTING_STARTED"] * 40 + ["TESTING_SCOPE_UPDATE_ACK"] * 40)]
        storm.insert(97, {"type": "IMPLEMENTER_COMPLETED", "candidate": SHA})
        result = policy.process_events(storm)
        self.assertEqual(result["next_event"]["type"], "IMPLEMENTER_COMPLETED")
        self.assertEqual(len(result["telemetry"]), 160)
        self.assertEqual(result["reasoning_turns"], 1)

    def test_scope_changed_requires_actual_new_risk_to_be_decision(self):
        self.assertEqual(policy.classify_event({"type": "TESTING_SCOPE_CHANGED"}), "telemetry")
        self.assertEqual(policy.classify_event({"type": "TESTING_SCOPE_CHANGED",
                                                "new_risk": ["new payment path"]}), "decision")

    def test_no_new_risk_does_not_default_to_full_retest(self):
        row = {"test_id": "unknown", "classification": "RETEST_REQUIRED",
               "source_candidate_sha": None, "changed_paths": [],
               "reasons": ["missing or unverifiable frozen evidence"]}
        result = policy.decide_testing(delta(row), risk_level="L2")
        self.assertIsNone(result["testing_request"])
        self.assertEqual(result["reason"], "no changed input, dependency impact, or new risk")

    def test_dogfood_replays_all_five_incidents_and_cli(self):
        body = json.loads(FIXTURE.read_text())
        result = policy.replay_dogfood(body)
        self.assertEqual(len(result["results"]), 5)
        by_name = {item["name"]: item["after"] for item in result["results"]}
        self.assertIsNone(by_name["skill install + empty Testing"]["testing_request"])
        self.assertFalse(by_name["Ali candidate + Testing pending"]["wait"])
        self.assertEqual(by_name["Creative multi-round adjustment"]["testing_round_trips"], 0)
        self.assertEqual(by_name["APK fast path + dependency ready"]["next_event"]["type"], "BUILD_SUCCEEDED")
        tests = by_name["integration of tested components"]["testing_request"]["testing_payload"]["tests"]
        self.assertEqual([item["test_id"] for item in tests], ["integration-smoke"])
        run = subprocess.run([sys.executable, str(Path(policy.__file__)), "dogfood", "--request", str(FIXTURE)],
                             text=True, capture_output=True)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout)["schema"], "CHIEF_TESTING_DOGFOOD_RESULT_V1")


if __name__ == "__main__":
    unittest.main()
