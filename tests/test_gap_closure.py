"""RED-first coverage for the five delivery-continuation closure gaps."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock
from pathlib import Path

from scripts import agent_os, delivery_ledger, feedback_coverage, legacy_agents_gate, profile_rebind, retry_policy
from tests.private_authority_fixture import TESTING_REVIEWER_ID


def observed(root, kind, identity, observation, hash_key):
    payload = {"schema": "CHIEF_DELIVERY_EVIDENCE_V1", "kind": kind, "identity": identity, "observation": observation}
    path = root / (kind + ".json")
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    path.write_bytes(raw)
    return {"evidence_path": str(path), "evidence_sha256": hashlib.sha256(raw).hexdigest(), hash_key: hashlib.sha256((json.dumps(observation, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()}


class GapClosureTests(unittest.TestCase):
    def test_ledger_consumes_recovery_once_after_restart(self):
        from tests.test_continuous_execution import PACKAGE, state
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); payload={"schema":"CHIEF_DELIVERY_PAYLOAD_V1","report_id":"report-recovery-1","work_id":"work-new","package_id":"package-1","candidate_sha256":"a"*64,"kind":"recovery","scope":"local","source_task_id":"writer-1","target_task_id":"chief-1","project_id":"project-1"}; raw=(json.dumps(payload,sort_keys=True)+"\n").encode(); (root/"payload.json").write_bytes(raw)
            report={"report_id":"report-recovery-1","source_task_id":"writer-1","target_task_id":"chief-1","project_id":"project-1","payload_sha256":hashlib.sha256(raw).hexdigest(),"artifact_refs":["repo://payload.json"],"continuous_payload_ref":"repo://payload.json"}; ledger=delivery_ledger.Ledger(root); ledger.ingest("ARTIFACT_FROZEN",report); ledger.ingest("SEND_ATTEMPTED",{**report,"attempt_id":"a1"}); identity={k:report[k] for k in ("report_id","source_task_id","target_task_id","project_id","payload_sha256")}; ledger.ingest("TRANSPORT_ACCEPTED",{**report,"attempt_id":"a1","tool_name":"send",**observed(root,"transport_accepted",{**identity,"attempt_id":"a1"},{"status":"accepted","attempt_id":"a1","tool_name":"send"},"raw_receipt_sha256")}); ack={"ack_task_id":"chief-1","observed_by_task_id":"writer-1","observation_kind":"receiver_stream","receiver_event_id":"e1"}; ledger.ingest("RECEIVER_ACK_OBSERVED",{**report,"attempt_id":"a1",**ack,**observed(root,"receiver_ack",{**identity,"attempt_id":"a1"},ack,"raw_observation_sha256")}); review={"decision":"accepted","reviewer_task_id":"chief-1"}; ledger.ingest("REVIEW_DECIDED",{**report,"attempt_id":"a1",**review,**observed(root,"review_decision",{**identity,"attempt_id":"a1"},review,"review_receipt_sha256")}); returned={**payload,"ledger_report_id":"report-recovery-1","return_id":"r1"}; first=ledger.reconcile_execution(state(returns=[returned],expected_candidate_sha256="a"*64),PACKAGE); self.assertEqual(first["next_action"],"CONTINUE_RETURNED_WORK"); restarted=delivery_ledger.Ledger(root); second=restarted.reconcile_execution(state(returns=[returned],expected_candidate_sha256="a"*64),PACKAGE); self.assertNotEqual(second["next_action"],"CONTINUE_RETURNED_WORK"); self.assertEqual(restarted.snapshot()["reports"]["report-recovery-1"]["state"],"execution_intent_pending")
            with self.assertRaises(delivery_ledger.LedgerError): restarted.reconcile_execution(state(returns=[{**returned,"kind":"test_pass"}],expected_candidate_sha256="a"*64),PACKAGE)
    def test_initializer_required_gate_binds_running_source_and_rechecks_external_receipt(self):
        """The Chief initializer, not only the standalone Agent OS CLI, owns required adoption."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            skill = root / "skill"
            source = Path(__file__).resolve().parents[1]
            shutil.copytree(source, skill, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            # A pinned Chief source is now a real Git checkout, including in this fixture.
            subprocess.run(["git", "init", str(skill)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(skill), "add", "."], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(skill), "-c", "user.name=rong2qi",
                            "-c", "user.email=249084307+rong2qi@users.noreply.github.com",
                            "commit", "-m", "fixture source"], check=True, capture_output=True)
            script = skill / "scripts" / "init_project.py"

            def inventory(path):
                return {
                    item.relative_to(path).as_posix(): item.read_bytes()
                    for item in sorted(path.rglob("*")) if item.is_file()
                }

            def legacy_project(name):
                project = root / name
                created = subprocess.run(
                    [sys.executable, str(script), "--target", str(project), "--project-name", "Example"],
                    text=True, capture_output=True,
                )
                self.assertEqual(created.returncode, 0, created.stderr)
                project_json = project / ".chief-of-staff" / "project.json"
                value = json.loads(project_json.read_text())
                value.pop("agent_os_mode")
                value.pop("agent_os_manifest")
                for key in ("work_execution_version", "work_execution_adoption", "chief_version",
                            "chief_schema_version", "chief_source_commit"):
                    value.pop(key, None)
                (project / ".chief-of-staff" / "chief-lock.json").unlink()
                project_json.write_text(json.dumps(value, indent=2) + "\n")
                (project / "AGENTS.md").write_text(
                    (skill / "assets" / "project-template" / "AGENTS.md").read_text()
                    .replace("{{PROJECT_NAME_JSON}}", "Example")
                    .replace("{{PROJECT_NAME}}", "Example")
                )
                shutil.rmtree(project / ".agent-os")
                (project / "CLAUDE.md").unlink()
                return project

            def gate_for(project, trust):
                (trust / "candidates").mkdir(parents=True)
                files = {
                    name: hashlib.sha256((skill / name).read_bytes()).hexdigest()
                    for name in legacy_agents_gate.IMPLEMENTATION_FILES
                }
                candidate = trust / "candidates" / "candidate-1.json"
                candidate.write_text(json.dumps({
                    "schema": "CHIEF_AGENT_OS_LEGACY_CANDIDATE_V1",
                    "candidate_id": "candidate-1", "source_release_id": "copy-test",
                    "implementation_files": files,
                    "implementation_fingerprint_sha256": hashlib.sha256(
                        json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
                    ).hexdigest(),
                    "agent_os_schema": agent_os.AGENT_OS_SCHEMA,
                    "source_versions": agent_os.SOURCE_VERSIONS,
                    "contract_fingerprint_sha256": agent_os.contract_fingerprint(),
                }) + "\n")
                project_json = project / ".chief-of-staff" / "project.json"
                gate = trust / "gate-1.json"
                gate.write_text(json.dumps({
                    "schema": "CHIEF_AGENT_OS_LEGACY_GATE_V1", "status": "TESTING_GATE_PASS",
                    "testing_chief_task_id": TESTING_REVIEWER_ID,
                    "gate_id": "gate-1", "candidate_id": "candidate-1",
                    "candidate_manifest_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                    "project_identity": {"root_id": legacy_agents_gate.project_root_id(project), "project_name": "Example"},
                    "pre_migration": {
                        "project_json_sha256": hashlib.sha256(project_json.read_bytes()).hexdigest(),
                        "agents_sha256": hashlib.sha256((project / "AGENTS.md").read_bytes()).hexdigest(),
                    },
                    "approved_agent_os_mode": "required",
                    "tested_lanes": ["INFRA_CONFIG", "SECURITY_PRIVACY"],
                    "operator_approval_id": "approval-1",
                }) + "\n")
                return gate

            rejected = legacy_project("rejected")
            rejected_trust = root / "rejected-trust"
            rejected_gate = gate_for(rejected, rejected_trust)
            before = inventory(rejected)
            with (skill / "scripts" / "legacy_agents_gate.py").open("a", encoding="utf-8") as handle:
                handle.write("# one-byte candidate drift\n")
            failed = subprocess.run([
                sys.executable, str(script), "--target", str(rejected), "--project-name", "Example",
                "--migrate-agent-os", "--legacy-agents-gate", str(rejected_gate),
                "--expected-legacy-agents-gate-sha256", hashlib.sha256(rejected_gate.read_bytes()).hexdigest(),
                "--legacy-trust-root", str(rejected_trust),
            ], text=True, capture_output=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("implementation", failed.stderr)
            self.assertEqual(inventory(rejected), before)

            # Recopy after the adversarial byte change so this gate binds a clean fixed source.
            shutil.rmtree(skill)
            shutil.copytree(source, skill, ignore=shutil.ignore_patterns(".git", "__pycache__"))
            # A pinned Chief source is now a real Git checkout, including in this fixture.
            subprocess.run(["git", "init", str(skill)], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(skill), "add", "."], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(skill), "-c", "user.name=rong2qi",
                            "-c", "user.email=249084307+rong2qi@users.noreply.github.com",
                            "commit", "-m", "fixture source"], check=True, capture_output=True)
            script = skill / "scripts" / "init_project.py"
            adopted = legacy_project("adopted")
            trust = root / "trust"
            gate = gate_for(adopted, trust)
            migrated = subprocess.run([
                sys.executable, str(script), "--target", str(adopted), "--project-name", "Example",
                "--migrate-agent-os", "--legacy-agents-gate", str(gate),
                "--expected-legacy-agents-gate-sha256", hashlib.sha256(gate.read_bytes()).hexdigest(),
                "--legacy-trust-root", str(trust),
            ], text=True, capture_output=True)
            self.assertEqual(migrated.returncode, 0, migrated.stderr)
            no_trust = subprocess.run(
                [sys.executable, str(script), "--target", str(adopted), "--project-name", "Example", "--check"],
                text=True, capture_output=True,
            )
            self.assertNotEqual(no_trust.returncode, 0)
            checked = subprocess.run([
                sys.executable, str(script), "--target", str(adopted), "--project-name", "Example",
                "--check", "--legacy-trust-root", str(trust),
            ], text=True, capture_output=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            # Receipt validation reloads the fixed candidate; a locally rehashed
            # replacement cannot inherit the old external gate approval.
            candidate = trust / "candidates" / "candidate-1.json"
            replacement = json.loads(candidate.read_text())
            replacement["source_release_id"] = "rehash-attempt"
            candidate.write_text(json.dumps(replacement) + "\n")
            drifted = subprocess.run([
                sys.executable, str(script), "--target", str(adopted), "--project-name", "Example",
                "--check", "--legacy-trust-root", str(trust),
            ], text=True, capture_output=True)
            self.assertNotEqual(drifted.returncode, 0)
            self.assertIn("required receipt", drifted.stderr)

    def test_ledger_requires_observed_receiver_ack_before_review_or_next_step(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); ledger = delivery_ledger.Ledger(root)
            report = {"report_id": "report-1", "source_task_id": "child-1", "target_task_id": "chief-1", "project_id": "project-1", "payload_sha256": "a" * 64, "artifact_refs": ["repo://report.md"]}
            ledger.ingest("ARTIFACT_FROZEN", report)
            ledger.ingest("SEND_ATTEMPTED", {**report, "attempt_id": "attempt-1"})
            identity = {key: report[key] for key in ("report_id", "source_task_id", "target_task_id", "project_id", "payload_sha256")}
            ledger.ingest("TRANSPORT_ACCEPTED", {**report, "attempt_id": "attempt-1", "tool_name": "send_message_to_thread", **observed(root, "transport_accepted", {**identity, "attempt_id": "attempt-1"}, {"status": "accepted", "attempt_id": "attempt-1", "tool_name": "send_message_to_thread"}, "raw_receipt_sha256")})
            with self.assertRaises(delivery_ledger.LedgerError):
                ledger.ingest("REVIEW_DECIDED", {**report, "decision": "accepted"})
            ack = {"ack_task_id": "chief-1", "observed_by_task_id": "child-1", "observation_kind": "receiver_stream", "receiver_event_id": "receiver-event-1"}
            ledger.ingest("RECEIVER_ACK_OBSERVED", {**report, "attempt_id": "attempt-1", **ack, **observed(root, "receiver_ack", {**identity, "attempt_id": "attempt-1"}, ack, "raw_observation_sha256")})
            review = {"decision": "accepted", "reviewer_task_id": "chief-1"}
            ledger.ingest("REVIEW_DECIDED", {**report, "attempt_id": "attempt-1", **review, **observed(root, "review_decision", {**identity, "attempt_id": "attempt-1"}, review, "review_receipt_sha256")})
            dispatch = {"next_action_id": "next-1", "next_target_task_id": "child-2", "next_target_status": "active", "next_target_scope": "source/next"}
            ledger.ingest("NEXT_STEP_DISPATCHED", {**report, "attempt_id": "attempt-1", **dispatch, **observed(root, "next_dispatch", {**identity, "attempt_id": "attempt-1"}, {"status": "accepted", **dispatch}, "dispatch_receipt_sha256")})
            self.assertEqual(ledger.snapshot()["reports"]["report-1"]["state"], "next_step_dispatched")

    def test_ledger_rejects_conflicting_duplicate_and_terminal_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = delivery_ledger.Ledger(Path(temporary))
            event = {"report_id": "report-1", "source_task_id": "child-1", "target_task_id": "chief-1", "project_id": "project-1", "payload_sha256": "a" * 64, "artifact_refs": ["repo://report.md"], "event_id": "event-1"}
            ledger.ingest("ARTIFACT_FROZEN", event)
            ledger.ingest("ARTIFACT_FROZEN", event)
            with self.assertRaises(delivery_ledger.LedgerError):
                ledger.ingest("ARTIFACT_FROZEN", {**event, "payload_sha256": "b" * 64})
            ledger.ingest("BLOCKED", {**event, "event_id": "event-2", "blocked_reason": "approval required"})
            with self.assertRaises(delivery_ledger.LedgerError):
                ledger.ingest("TRANSPORT_ACCEPTED", {**event, "event_id": "event-3", "attempt_id": "attempt-1", "tool_name": "send_message_to_thread", "raw_receipt_sha256": "c" * 64})

    def test_empty_native_summary_is_observation_gap_not_empty_completion_or_retry(self):
        with tempfile.TemporaryDirectory() as temporary:
            ledger = delivery_ledger.Ledger(Path(temporary))
            report = {"report_id": "report-1", "source_task_id": "child-1", "target_task_id": "chief-1", "project_id": "project-1", "payload_sha256": "a" * 64, "artifact_refs": ["repo://report.md"]}
            ledger.ingest("ARTIFACT_FROZEN", report)
            ledger.ingest("COMPLETION_OBSERVATION", {**report, "observer": "native_read", "items": [], "result_artifact_confirmed": False})
            result = ledger.reconcile()
            self.assertEqual(ledger.snapshot()["reports"]["report-1"]["state"], "completed_unobserved")
            self.assertEqual(result["intents"][0]["next_required_action"], "OBSERVATION_GAP")

    def test_ledger_replays_journal_over_forged_snapshot_and_keeps_per_report_intents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); ledger = delivery_ledger.Ledger(root)
            for report_id in ("report-1", "report-2"):
                report = {"report_id": report_id, "source_task_id": "child-1", "target_task_id": "chief-1", "project_id": "project-1", "payload_sha256": ("a" if report_id == "report-1" else "b") * 64, "artifact_refs": ["repo://report.md"]}
                ledger.ingest("ARTIFACT_FROZEN", report)
                ledger.ingest("COMPLETION_OBSERVATION", {**report, "items": [], "result_artifact_confirmed": False, "observation_cursor": report_id})
            (root / "snapshot.json").write_text('{"schema":"CHIEF_DELIVERY_LEDGER_V1","reports":{"forged":{"state":"continued"}},"event_ids":{"forged":"x"}}\n')
            replayed = ledger.snapshot()
            self.assertNotIn("forged", replayed["reports"])
            intents = ledger.reconcile()["intents"]
            self.assertEqual([item["report_id"] for item in intents], ["report-1", "report-2"])
            self.assertEqual([item["observation_cursor"] for item in intents], ["report-1", "report-2"])

    def test_r3_ledger_locks_ack_to_accepted_attempt_and_rejects_alias_before_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); outside = root / "outside"; outside.mkdir(); alias = root / "alias"; alias.symlink_to(outside, target_is_directory=True)
            with self.assertRaises(delivery_ledger.LedgerError): delivery_ledger.Ledger(alias / "ledger")
            self.assertFalse((outside / "ledger").exists())
            ledger = delivery_ledger.Ledger(root / "ledger")
            report = {"report_id":"r", "source_task_id":"child", "target_task_id":"chief", "project_id":"p", "payload_sha256":"a"*64, "artifact_refs":["repo://r"]}
            identity = {key: report[key] for key in ("report_id","source_task_id","target_task_id","project_id","payload_sha256")}
            ledger.ingest("ARTIFACT_FROZEN", report); ledger.ingest("SEND_ATTEMPTED", {**report,"attempt_id":"a1"})
            ledger.ingest("TRANSPORT_ACCEPTED", {**report,"attempt_id":"a1","tool_name":"send", **observed(root / "ledger", "transport_accepted", {**identity,"attempt_id":"a1"}, {"status":"accepted","attempt_id":"a1","tool_name":"send"}, "raw_receipt_sha256")})
            ledger.ingest("SEND_ATTEMPTED", {**report,"attempt_id":"a2"})
            ack={"ack_task_id":"chief","observed_by_task_id":"child","observation_kind":"receiver_stream","receiver_event_id":"e2"}
            with self.assertRaisesRegex(delivery_ledger.LedgerError, "exact accepted"):
                ledger.ingest("RECEIVER_ACK_OBSERVED", {**report,"attempt_id":"a2",**ack,**observed(root / "ledger", "receiver_ack", {**identity,"attempt_id":"a2"}, ack, "raw_observation_sha256")})
            ledger.ingest("COMPLETION_OBSERVATION", {**report,"items":[],"result_artifact_confirmed":False})
            with self.assertRaises(delivery_ledger.LedgerError): ledger.ingest("COMPLETED_EMPTY", {**report,"attempt_id":"a1","absence_verified":True,"absence_evidence_sha256":"b"*64})

    def test_r3_lexical_trust_alias_and_fresh_review_events_are_rejected_or_allowed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); outside=root/"outside"; outside.mkdir(); alias=root/"alias"; alias.symlink_to(outside,target_is_directory=True)
            project=root/"project"; project.mkdir()
            with self.assertRaisesRegex(legacy_agents_gate.LegacyGateError,"ancestors"):
                legacy_agents_gate.validate_gate(project,alias/"trust"/"gate.json",alias/"trust","a"*64)
            state=root/"budget"/".chief-of-staff"; state.mkdir(parents=True)
            (state/"project.json").write_text('{"max_repair_cycles":3,"repair_reviewer_id":"sol"}\n')
            project_root=state.parent
            retry_policy.consume_repair_cycle(project_root,"c1","review-event-1","repair-1",reviewer_id="sol")
            second=retry_policy.consume_repair_cycle(project_root,"c2","review-event-2","repair-2",reviewer_id="sol")
            self.assertEqual(len(second["cycles"]),2)
            (state/"project.json").write_text('{"max_repair_cycles":3,"repair_failure_stop":true}\n')
            with self.assertRaisesRegex(retry_policy.RetryPolicyError,"stopped"):
                retry_policy.consume_repair_cycle(project_root,"c3","review-event-3","repair-3",reviewer_id="sol")

    def test_feedback_coverage_does_not_infer_activation_from_source_or_tests(self):
        index = feedback_coverage.CoverageIndex()
        index.record("rule", "rule-1", "a" * 64)
        index.record("source", "source-1", "b" * 64)
        index.record("tests", "tests-1", "c" * 64)
        self.assertFalse(index.ready_for("project_adoption"))
        index.record("testing", "gate-1", "d" * 64)
        index.record("review", "review-1", "e" * 64)
        index.record("installed", "installed-1", "f" * 64)
        index.record("global", "global-1", "0" * 64)
        index.record("project", "project-1", "1" * 64)
        self.assertTrue(index.ready_for("project_adoption"))

    def test_profile_rebind_validates_preimages_without_writing_profile(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); profile = root / "profile.json"; agents = root / "AGENTS.md"
            profile.write_text(json.dumps(profile_rebind.default_profile()) + "\n")
            agents.write_text("before\n")
            renderer = root / "renderer.py"; renderer.write_text("# renderer\n")
            before_profile = profile.read_bytes(); before_agents = agents.read_bytes()
            receipt = profile_rebind.prepare(profile, agents, hashlib.sha256(before_profile).hexdigest(), hashlib.sha256(before_agents).hexdigest(), renderer_path=renderer)
            self.assertEqual(profile.read_bytes(), before_profile)
            self.assertEqual(agents.read_bytes(), before_agents)
            self.assertEqual(receipt["profile_sha256"], hashlib.sha256(before_profile).hexdigest())
            with self.assertRaises(profile_rebind.RebindError):
                profile_rebind.prepare(profile, agents, "0" * 64, "b" * 64, renderer_path=root / "renderer.py")

    def test_profile_prepare_rejects_ancestor_alias_and_live_output_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); outside = root / "outside"; outside.mkdir(); linked = root / "linked"; linked.symlink_to(outside, target_is_directory=True)
            profile = outside / "profile.json"; agents = outside / "AGENTS.md"; renderer = outside / "renderer.py"
            profile.write_text(json.dumps(profile_rebind.default_profile())); agents.write_text("before\n"); renderer.write_text("# renderer\n")
            with self.assertRaises(profile_rebind.RebindError):
                profile_rebind.prepare(linked / "profile.json", agents, hashlib.sha256(profile.read_bytes()).hexdigest(), hashlib.sha256(agents.read_bytes()).hexdigest(), renderer_path=renderer)
            script = Path(profile_rebind.__file__)
            before = (profile.read_bytes(), agents.read_bytes())
            result = subprocess.run([sys.executable, str(script), "prepare", "--profile", str(profile), "--global-agents", str(agents), "--expected-profile-sha256", hashlib.sha256(before[0]).hexdigest(), "--expected-global-agents-sha256", hashlib.sha256(before[1]).hexdigest(), "--renderer", str(renderer), "--receipt-out", str(profile), "--frozen-output", str(agents)], text=True, capture_output=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual((profile.read_bytes(), agents.read_bytes()), before)

    def test_retry_budget_consumer_is_idempotent_and_enforces_project_bound(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); state = root / ".chief-of-staff"; state.mkdir()
            (state / "project.json").write_text('{"max_repair_cycles": 1}\n')
            first = retry_policy.consume_repair_cycle(root, "candidate-1", "review-1", "repair-1")
            self.assertEqual(len(first["cycles"]), 1)
            self.assertEqual(retry_policy.consume_repair_cycle(root, "candidate-1", "review-1", "repair-1"), first)
            with self.assertRaisesRegex(retry_policy.RetryPolicyError, "exhausted"):
                retry_policy.consume_repair_cycle(root, "candidate-2", "review-1", "repair-2")

    def test_recovery_rejects_fixed_ledger_hardlink_before_external_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for fixed_name in ("events.jsonl", "snapshot.json", ".lock"):
                ledger_root = root / fixed_name; ledger_root.mkdir()
                outside = root / ("outside-" + fixed_name.replace(".", "_")); outside.write_bytes(b"outside bytes\n")
                os.link(outside, ledger_root / fixed_name)
                before = outside.read_bytes()
                with self.assertRaisesRegex(delivery_ledger.LedgerError, "hardlink"):
                    delivery_ledger.Ledger(ledger_root)
                self.assertEqual(outside.read_bytes(), before)

    def test_recovery_fixed_reviewer_and_duplicate_receipt_precede_stop(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); state = root / ".chief-of-staff"; state.mkdir()
            config = state / "project.json"; config.write_text('{"max_repair_cycles":3,"repair_reviewer_id":"sol"}\n')
            with self.assertRaisesRegex(retry_policy.RetryPolicyError, "configured"):
                retry_policy.consume_repair_cycle(root, "c1", "rv1", "repair-1", reviewer_id="other")
            self.assertFalse((state / "repair-budget.json").exists())
            first = retry_policy.consume_repair_cycle(root, "c1", "rv1", "repair-1", reviewer_id="sol")
            before = json.dumps(first, sort_keys=True)
            config.write_text('{"max_repair_cycles":3,"repair_reviewer_id":"sol","repair_failure_stop":true}\n')
            self.assertEqual(
                retry_policy.consume_repair_cycle(root, "c1", "rv1", "repair-1", reviewer_id="sol"),
                first,
            )
            self.assertEqual(json.dumps(json.loads((state / "repair-budget.json").read_text()), sort_keys=True), before)
            config.write_text('{"max_repair_cycles":3,"repair_reviewer_id":"sol","repair_budget_status":"exhausted"}\n')
            self.assertEqual(
                retry_policy.consume_repair_cycle(root, "c1", "rv1", "repair-1", reviewer_id="sol"),
                first,
            )
            rejected_before = (state / "repair-budget.json").read_bytes()
            with self.assertRaisesRegex(retry_policy.RetryPolicyError, "conflicts"):
                retry_policy.consume_repair_cycle(root, "changed", "rv1", "repair-1", reviewer_id="sol")
            self.assertEqual((state / "repair-budget.json").read_bytes(), rejected_before)
            with self.assertRaisesRegex(retry_policy.RetryPolicyError, "stopped"):
                retry_policy.consume_repair_cycle(root, "c2", "rv2", "repair-2", reviewer_id="sol")
            self.assertEqual((state / "repair-budget.json").read_bytes(), rejected_before)

    def test_retry_budget_fixed_paths_reject_escapes_before_external_state_changes(self):
        """The symlink case reproduces Testing's finding; other aliases are defensive."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            valid_state = b'{"cycles": [], "schema": "CHIEF_REPAIR_BUDGET_V1"}\n'

            def project_at(path):
                state = path / ".chief-of-staff"; state.mkdir(parents=True)
                (state / "project.json").write_text('{"max_repair_cycles": 3}\n')
                return state

            # Testing-reproduced case: a budget-file symlink previously made
            # consume_repair_cycle overwrite the external valid-state sentinel.
            symlink_project = root / "symlink-project"; symlink_state = project_at(symlink_project)
            symlink_outside = root / "outside-symlink.json"; symlink_outside.write_bytes(valid_state)
            (symlink_state / "repair-budget.json").symlink_to(symlink_outside)
            before = symlink_outside.read_bytes()
            with self.assertRaisesRegex(retry_policy.RetryPolicyError, "unsafe"):
                retry_policy.consume_repair_cycle(symlink_project, "c1", "review-1", "repair-1")
            self.assertEqual(symlink_outside.read_bytes(), before)

            # Defensive variants share the same owned fixed-state boundary.
            hardlink_project = root / "hardlink-project"; hardlink_state = project_at(hardlink_project)
            hardlink_outside = root / "outside-hardlink.json"; hardlink_outside.write_bytes(valid_state)
            os.link(hardlink_outside, hardlink_state / "repair-budget.json")
            before = hardlink_outside.read_bytes()
            with self.assertRaisesRegex(retry_policy.RetryPolicyError, "unsafe"):
                retry_policy.consume_repair_cycle(hardlink_project, "c1", "review-1", "repair-1")
            self.assertEqual(hardlink_outside.read_bytes(), before)

            linked_state_project = root / "linked-state-project"; linked_state_project.mkdir()
            linked_state_outside = root / "outside-state"; linked_state_outside.mkdir()
            (linked_state_outside / "project.json").write_text('{"max_repair_cycles": 3}\n')
            (linked_state_project / ".chief-of-staff").symlink_to(linked_state_outside, target_is_directory=True)
            before = {item.name: item.read_bytes() for item in linked_state_outside.iterdir()}
            with self.assertRaisesRegex(retry_policy.RetryPolicyError, "unsafe"):
                retry_policy.consume_repair_cycle(linked_state_project, "c1", "review-1", "repair-1")
            self.assertEqual({item.name: item.read_bytes() for item in linked_state_outside.iterdir()}, before)

            linked_parent_outside = root / "outside-parent"; linked_parent_project = linked_parent_outside / "project"
            project_at(linked_parent_project)
            linked_parent = root / "linked-parent"; linked_parent.symlink_to(linked_parent_outside, target_is_directory=True)
            before = {item.relative_to(linked_parent_outside).as_posix(): item.read_bytes() for item in linked_parent_outside.rglob("*") if item.is_file()}
            with self.assertRaisesRegex(retry_policy.RetryPolicyError, "unsafe"):
                retry_policy.consume_repair_cycle(linked_parent / "project", "c1", "review-1", "repair-1")
            self.assertEqual({item.relative_to(linked_parent_outside).as_posix(): item.read_bytes() for item in linked_parent_outside.rglob("*") if item.is_file()}, before)

    def test_retry_budget_holds_open_state_directory_after_parent_swap(self):
        """A post-config parent swap must not redirect the repair receipt outside."""
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"; state = project / ".chief-of-staff"
            state.mkdir(parents=True)
            config = {"max_repair_cycles": 3}
            (state / "project.json").write_text(json.dumps(config) + "\n")
            outside = root / "outside"; outside.mkdir()
            retained = project / ".chief-of-staff-retained"
            original_loads = json.loads
            swapped = False

            def swap_after_config(raw, *args, **kwargs):
                nonlocal swapped
                value = original_loads(raw, *args, **kwargs)
                if not swapped and value == config:
                    state.rename(retained)
                    state.symlink_to(outside, target_is_directory=True)
                    swapped = True
                return value

            with mock.patch.object(retry_policy.json, "loads", side_effect=swap_after_config):
                result = retry_policy.consume_repair_cycle(project, "c1", "review-1", "repair-1")

            self.assertTrue(swapped)
            self.assertEqual(len(result["cycles"]), 1)
            self.assertTrue((retained / "repair-budget.json").is_file())
            self.assertFalse((outside / "repair-budget.json").exists())

    def test_retry_budget_concurrent_ancestor_replacement_is_contained(self):
        """Real directory changes at a controlled open boundary never redirect writes."""
        for timing in ("before_open", "after_open"):
            for replacement in ("link", "directory"):
                with self.subTest(timing=timing, replacement=replacement), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary).resolve()
                    ancestor = root / "ancestor"
                    project = ancestor / "project"
                    outside = root / "replacement"
                    retained = root / "retained"
                    for location in (project, outside / "project"):
                        state = location / ".chief-of-staff"
                        state.mkdir(parents=True)
                        (state / "project.json").write_text('{"max_repair_cycles":3}\n')
                    started, completed = threading.Event(), threading.Event()
                    worker_errors = []

                    def substitute():
                        try:
                            if not started.wait(5):
                                raise RuntimeError("test open boundary was not reached")
                            ancestor.rename(retained)
                            if replacement == "link":
                                ancestor.symlink_to(outside, target_is_directory=True)
                            else:
                                outside.rename(ancestor)
                        except Exception as exc:
                            worker_errors.append(exc)
                        finally:
                            completed.set()

                    native_open = os.open
                    descriptors = []

                    def at_boundary(path, flags, *args, **kwargs):
                        target = os.fspath(path)
                        # Match both the old full-path open and a component walk.
                        selected = not started.is_set() and target in (str(project), "ancestor")
                        if selected and timing == "before_open":
                            started.set()
                            if not completed.wait(5):
                                raise RuntimeError("test substitution timed out")
                        fd = native_open(path, flags, *args, **kwargs)
                        descriptors.append(fd)
                        if selected and timing == "after_open":
                            started.set()
                            if not completed.wait(5):
                                os.close(fd)
                                raise RuntimeError("test substitution timed out")
                        return fd

                    worker = threading.Thread(target=substitute)
                    worker.start()
                    result = None
                    try:
                        with mock.patch.object(retry_policy.os, "open", side_effect=at_boundary) as intercepted:
                            with mock.patch.object(retry_policy.os, "supports_dir_fd", os.supports_dir_fd | {intercepted}):
                                try:
                                    result = retry_policy.consume_repair_cycle(project, "c1", "rv1", "r1")
                                except retry_policy.RetryPolicyError:
                                    pass
                    finally:
                        worker.join(6)
                    self.assertFalse(worker.is_alive())
                    self.assertEqual(worker_errors, [])
                    self.assertTrue(started.is_set())
                    replacement_root = outside if replacement == "link" else ancestor
                    self.assertFalse((replacement_root / "project/.chief-of-staff/repair-budget.json").exists())
                    self.assertEqual(sorted(p.relative_to(replacement_root).as_posix() for p in replacement_root.rglob("*") if p.is_file()), ["project/.chief-of-staff/project.json"])
                    receipt = retained / "project/.chief-of-staff/repair-budget.json"
                    if result is not None:
                        self.assertEqual(json.loads(receipt.read_text()), result)
                    else:
                        self.assertFalse(receipt.exists())
                    if timing == "before_open":
                        self.assertIsNone(result)
                    else:
                        self.assertIsNotNone(result)
                    for fd in set(descriptors):
                        with self.assertRaises(OSError):
                            os.fstat(fd)

    def test_retry_budget_relative_and_system_temp_alias_controls(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "project/.chief-of-staff"
            state.mkdir(parents=True)
            (state / "project.json").write_text('{"max_repair_cycles":3}\n')
            original_cwd = Path.cwd()
            try:
                os.chdir(root)
                result = retry_policy.consume_repair_cycle(Path("project"), "c1", "rv1", "r1")
                self.assertEqual(len(result["cycles"]), 1)
            finally:
                os.chdir(original_cwd)
            for unsafe in (root / "project/../project", Path("/" + str(root)) / "project"):
                with self.subTest(path=str(unsafe)):
                    with self.assertRaisesRegex(retry_policy.RetryPolicyError, "unsafe"):
                        retry_policy.consume_repair_cycle(unsafe, "c2", "rv2", "r2")
            self.assertEqual(len(json.loads((state / "repair-budget.json").read_text())["cycles"]), 1)
            if sys.platform == "darwin":
                with tempfile.TemporaryDirectory(dir="/tmp") as alias_temporary:
                    alias_state = Path(alias_temporary) / ".chief-of-staff"
                    alias_state.mkdir()
                    (alias_state / "project.json").write_text('{"max_repair_cycles":3}\n')
                    self.assertEqual(len(retry_policy.consume_repair_cycle(Path(alias_temporary), "c1", "rv1", "r1")["cycles"]), 1)

    def test_retry_budget_ancestor_capabilities_fail_closed(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / ".chief-of-staff"; state.mkdir()
            (state / "project.json").write_text('{"max_repair_cycles":3}\n')
            for capability in ("supports_dir_fd", "supports_follow_symlinks"):
                with self.subTest(capability=capability):
                    with mock.patch.object(retry_policy.os, capability, getattr(os, capability) - {os.stat}):
                        with self.assertRaisesRegex(retry_policy.RetryPolicyError, "unavailable"):
                            retry_policy.consume_repair_cycle(root, "c1", "rv1", "r1")
                    self.assertFalse((state / "repair-budget.json").exists())

    def test_retry_contract_boolean_fields_reject_numeric_lookalikes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for field in ("repair_failure_stop", "repair_one_shot"):
                for value in (1, 1.0, 0, 0.0):
                    project = root / (field + "-" + repr(value).replace(".", "_")); state = project / ".chief-of-staff"; state.mkdir(parents=True)
                    (state / "project.json").write_text(json.dumps({"max_repair_cycles": 3, field: value}) + "\n")
                    with self.assertRaisesRegex(retry_policy.RetryPolicyError, "boolean"):
                        retry_policy.consume_repair_cycle(project, "c1", "review-1", "repair-1")
                    self.assertFalse((state / "repair-budget.json").exists())

            for field in ("repair_failure_stop", "repair_one_shot"):
                for value in (None, False, True):
                    project = root / (field + "-legal-" + str(value)); state = project / ".chief-of-staff"; state.mkdir(parents=True)
                    (state / "project.json").write_text(json.dumps({"max_repair_cycles": 3, field: value}) + "\n")
                    if field == "repair_failure_stop" and value is True:
                        with self.assertRaisesRegex(retry_policy.RetryPolicyError, "stopped"):
                            retry_policy.consume_repair_cycle(project, "c1", "review-1", "repair-1")
                    else:
                        result = retry_policy.consume_repair_cycle(project, "c1", "review-1", "repair-1")
                        self.assertEqual(len(result["cycles"]), 1)

    def test_custom_legacy_gate_binds_exact_bytes_identity_and_external_trust_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); project = root / "project"; trust = root / "trust"; project.mkdir(); trust.mkdir()
            (project / "AGENTS.md").write_text("legacy rules\n")
            (project / ".chief-of-staff").mkdir(); project_json = project / ".chief-of-staff" / "project.json"; project_json.write_text('{"project_name":"Example"}\n')
            agents_hash = hashlib.sha256((project / "AGENTS.md").read_bytes()).hexdigest()
            project_hash = hashlib.sha256(project_json.read_bytes()).hexdigest()
            gate = trust / "gate-1.json"
            gate.write_text(json.dumps({"schema": "CHIEF_AGENT_OS_LEGACY_GATE_V1", "status": "TESTING_GATE_PASS", "testing_chief_task_id": TESTING_REVIEWER_ID, "gate_id": "gate-1", "candidate_id": "candidate-1", "candidate_manifest_sha256": "a" * 64, "project_identity": {"root_id": legacy_agents_gate.project_root_id(project), "project_name": "Example"}, "pre_migration": {"project_json_sha256": project_hash, "agents_sha256": agents_hash}, "approved_agent_os_mode": "required", "tested_lanes": ["INFRA_CONFIG", "SECURITY_PRIVACY"], "operator_approval_id": "approval-1"}) + "\n")
            receipt = legacy_agents_gate.validate_gate(project, gate, trust, hashlib.sha256(gate.read_bytes()).hexdigest())
            self.assertEqual(receipt["gate_id"], "gate-1")
            (project / "AGENTS.md").write_text("tampered\n")
            with self.assertRaises(legacy_agents_gate.LegacyGateError):
                legacy_agents_gate.validate_gate(project, gate, trust, hashlib.sha256(gate.read_bytes()).hexdigest())

    def test_candidate_manifest_rejects_a_symlinked_trust_ancestor(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); trust = root / "trust"; outside = root / "outside"
            trust.mkdir(); outside.mkdir()
            (outside / "candidate-1.json").write_text("{}\n")
            (trust / "candidates").symlink_to(outside, target_is_directory=True)
            gate = trust / "gate-1.json"
            gate.write_text(json.dumps({
                "candidate_id": "candidate-1", "candidate_manifest_sha256": "a" * 64,
            }) + "\n")
            with self.assertRaisesRegex(legacy_agents_gate.LegacyGateError, "symlinks"):
                legacy_agents_gate.validate_candidate_binding(
                    gate, trust, skill_root=Path(agent_os.__file__).resolve().parents[1],
                    agent_os_schema=agent_os.AGENT_OS_SCHEMA,
                    source_versions=agent_os.SOURCE_VERSIONS,
                    contract_fingerprint_sha256=agent_os.contract_fingerprint(),
                )

    def test_retry_policy_has_three_repair_cycles_after_initial_review(self):
        policy = retry_policy.RetryPolicy.from_mapping({"max_repair_cycles": 3})
        self.assertTrue(policy.permit(reviews=1, repairs=3))
        self.assertFalse(policy.permit(reviews=1, repairs=4))
        self.assertFalse(retry_policy.RetryPolicy.from_mapping({"max_repair_cycles": 1}).permit(reviews=1, repairs=2))

    def test_migration_parser_exposes_external_legacy_gate_inputs(self):
        args = agent_os.build_parser().parse_args(["migrate", "--target", "/tmp/project", "--legacy-agents-gate", "/tmp/trust/gate-1.json", "--expected-legacy-agents-gate-sha256", "a" * 64, "--legacy-trust-root", "/tmp/trust"])
        self.assertEqual(args.legacy_agents_gate, "/tmp/trust/gate-1.json")

    def test_release_map_excludes_versioned_companion_roots_from_chief_payload(self):
        root = Path(__file__).resolve().parents[1]
        release = json.loads((root / "release-map.json").read_text())
        self.assertEqual(release["chief_payload_excludes"], ["agent-orchestration", "agent-profiles"])

    def test_strict_delivery_policy_wires_coldstart_results_and_budget_to_reference(self):
        root = Path(__file__).resolve().parents[1]
        skill = (root / "SKILL.md").read_text(encoding="utf-8")
        protocol = (root / "references" / "coordination-protocol.md").read_text(encoding="utf-8")
        reference = (root / "references" / "delivery-ledger.md").read_text(encoding="utf-8")
        self.assertIn("coordination-protocol.md", skill)
        for phrase in ("cold start", "authorized heartbeat", "OBSERVATION_GAP"):
            self.assertIn(phrase, protocol)
        self.assertIn("delivery-ledger.md", protocol)
        self.assertIn("stable reviewer identity", reference)
        self.assertIn("temporary native transport", reference)

    def test_custom_gate_migration_records_only_hash_receipt_in_its_atomic_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); project = root / "project"; trust = root / "trust"; project.mkdir(); trust.mkdir(); (project / ".chief-of-staff").mkdir()
            (project / "AGENTS.md").write_text("legacy rules\n")
            project_json = project / ".chief-of-staff" / "project.json"; project_json.write_text('{"project_name":"Example"}\n')
            candidate_dir = trust / "candidates"; candidate_dir.mkdir()
            source_root = Path(agent_os.__file__).resolve().parents[1]
            files = {name: hashlib.sha256((source_root / name).read_bytes()).hexdigest() for name in legacy_agents_gate.IMPLEMENTATION_FILES}
            candidate = candidate_dir / "candidate-1.json"; candidate.write_text(json.dumps({"schema": "CHIEF_AGENT_OS_LEGACY_CANDIDATE_V1", "candidate_id": "candidate-1", "source_release_id": "source-test", "implementation_files": files, "implementation_fingerprint_sha256": hashlib.sha256(json.dumps(files, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), "agent_os_schema": agent_os.AGENT_OS_SCHEMA, "source_versions": agent_os.SOURCE_VERSIONS, "contract_fingerprint_sha256": agent_os.contract_fingerprint()}) + "\n")
            gate = trust / "gate-1.json"; gate.write_text(json.dumps({"schema": "CHIEF_AGENT_OS_LEGACY_GATE_V1", "status": "TESTING_GATE_PASS", "testing_chief_task_id": TESTING_REVIEWER_ID, "gate_id": "gate-1", "candidate_id": "candidate-1", "candidate_manifest_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(), "project_identity": {"root_id": legacy_agents_gate.project_root_id(project), "project_name": "Example"}, "pre_migration": {"project_json_sha256": hashlib.sha256(project_json.read_bytes()).hexdigest(), "agents_sha256": hashlib.sha256((project / "AGENTS.md").read_bytes()).hexdigest()}, "approved_agent_os_mode": "required", "tested_lanes": ["INFRA_CONFIG", "SECURITY_PRIVACY"], "operator_approval_id": "approval-1"}) + "\n")
            result = subprocess.run([sys.executable, str(Path(agent_os.__file__)), "migrate", "--target", str(project), "--project-name", "Example", "--legacy-agents-gate", str(gate), "--expected-legacy-agents-gate-sha256", hashlib.sha256(gate.read_bytes()).hexdigest(), "--legacy-trust-root", str(trust)], text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            receipt = json.loads((project / ".agent-os" / "legacy-gate-receipt.json").read_text())
            self.assertEqual(set(receipt), {"gate_id", "gate_sha256", "candidate_manifest_sha256", "preserved_agents_sha256"})

    def test_ledger_cli_ingest_check_and_reconcile_keep_transport_and_ack_separate(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); ledger = root / "ledger"; script = Path(delivery_ledger.__file__)
            base = {"report_id": "report-1", "source_task_id": "child-1", "target_task_id": "chief-1", "project_id": "project-1", "payload_sha256": "a" * 64, "artifact_refs": ["repo://report.md"]}
            def call(event, payload):
                path = root / (event + ".json"); path.write_text(json.dumps(payload))
                return subprocess.run([sys.executable, str(script), "--ledger", str(ledger), "ingest", "--event", event, "--payload", str(path)], text=True, capture_output=True)
            self.assertEqual(call("ARTIFACT_FROZEN", base).returncode, 0)
            self.assertEqual(call("SEND_ATTEMPTED", {**base, "attempt_id": "attempt-1"}).returncode, 0)
            identity = {key: base[key] for key in ("report_id", "source_task_id", "target_task_id", "project_id", "payload_sha256")}
            self.assertEqual(call("TRANSPORT_ACCEPTED", {**base, "attempt_id": "attempt-1", "tool_name": "send_message_to_thread", **observed(ledger, "transport_accepted", {**identity, "attempt_id": "attempt-1"}, {"status": "accepted", "attempt_id": "attempt-1", "tool_name": "send_message_to_thread"}, "raw_receipt_sha256")}).returncode, 0)
            reconciled = subprocess.run([sys.executable, str(script), "--ledger", str(ledger), "reconcile"], text=True, capture_output=True)
            self.assertEqual(reconciled.returncode, 0, reconciled.stderr)
            self.assertEqual(json.loads(reconciled.stdout)["intents"][0]["next_required_action"], "OBSERVE_RECEIVER_ACK")
            rejected = call("REVIEW_DECIDED", {**base, "decision": "accepted"})
            self.assertNotEqual(rejected.returncode, 0)
            ack = {"ack_task_id": "chief-1", "observed_by_task_id": "child-1", "observation_kind": "receiver_stream", "receiver_event_id": "receiver-event-1"}
            self.assertEqual(call("RECEIVER_ACK_OBSERVED", {**base, "attempt_id": "attempt-1", **ack, **observed(ledger, "receiver_ack", {**identity, "attempt_id": "attempt-1"}, ack, "raw_observation_sha256")}).returncode, 0)
            checked = subprocess.run([sys.executable, str(script), "--ledger", str(ledger), "check"], text=True, capture_output=True)
            self.assertEqual(json.loads(checked.stdout)["reports"]["report-1"]["state"], "received_unprocessed")

    def test_ledger_cli_restart_rejects_self_ack_and_preserves_append_only_journal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); ledger = root / "ledger"; script = Path(delivery_ledger.__file__)
            base = {"report_id": "report-1", "source_task_id": "child-1", "target_task_id": "chief-1", "project_id": "project-1", "payload_sha256": "a" * 64, "artifact_refs": ["repo://report.md"]}
            def call(event, payload):
                path = root / "payload.json"; path.write_text(json.dumps(payload))
                return subprocess.run([sys.executable, str(script), "--ledger", str(ledger), "ingest", "--event", event, "--payload", str(path)], text=True, capture_output=True)
            self.assertEqual(call("ARTIFACT_FROZEN", base).returncode, 0)
            self.assertEqual(call("SEND_ATTEMPTED", {**base, "attempt_id": "attempt-1"}).returncode, 0)
            identity = {key: base[key] for key in ("report_id", "source_task_id", "target_task_id", "project_id", "payload_sha256")}
            self.assertEqual(call("TRANSPORT_ACCEPTED", {**base, "attempt_id": "attempt-1", "tool_name": "send_message_to_thread", **observed(ledger, "transport_accepted", {**identity, "attempt_id": "attempt-1"}, {"status": "accepted", "attempt_id": "attempt-1", "tool_name": "send_message_to_thread"}, "raw_receipt_sha256")}).returncode, 0)
            before = (ledger / "events.jsonl").read_bytes()
            self.assertNotEqual(call("RECEIVER_ACK_OBSERVED", {**base, "ack_task_id": "child-1", "ack_receipt_sha256": "c" * 64}).returncode, 0)
            self.assertEqual((ledger / "events.jsonl").read_bytes(), before)
            self.assertEqual(call("COMPLETION_OBSERVATION", {**base, "observer": "native_read", "items": [], "result_artifact_confirmed": False}).returncode, 0)
            restarted = subprocess.run([sys.executable, str(script), "--ledger", str(ledger), "reconcile"], text=True, capture_output=True)
            self.assertEqual(json.loads(restarted.stdout)["intents"][0]["next_required_action"], "OBSERVATION_GAP")

    def test_explicit_strict_closure_adoption_creates_machine_checkable_mode_and_ledger(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            script = Path(__file__).resolve().parents[1] / "scripts" / "init_project.py"
            created = subprocess.run([sys.executable, str(script), "--target", str(target), "--project-name", "Example", "--delivery-ledger-mode", "strict"], text=True, capture_output=True)
            self.assertEqual(created.returncode, 0, created.stderr)
            project = json.loads((target / ".chief-of-staff" / "project.json").read_text())
            self.assertEqual(project["delivery_ledger_mode"], "strict")
            self.assertEqual(project["delivery_ledger_reconcile_triggers"], ["next_active_turn", "cold_start", "authorized_heartbeat"])
            self.assertTrue((target / ".chief-of-staff" / "delivery-ledger" / "snapshot.json").is_file())
            checked = subprocess.run([sys.executable, str(script), "--target", str(target), "--project-name", "Example", "--check"], text=True, capture_output=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            project["max_repair_cycles"] = 1; project["private_project_note"] = "preserve-me"
            (target / ".chief-of-staff" / "project.json").write_text(json.dumps(project) + "\n")
            # A stricter known bound survives a normal rerun; unknown bytes are
            # project-owned and must not be normalized away.
            rerun = subprocess.run([sys.executable, str(script), "--target", str(target), "--project-name", "Example"], text=True, capture_output=True)
            self.assertEqual(rerun.returncode, 0, rerun.stderr)
            after = json.loads((target / ".chief-of-staff" / "project.json").read_text())
            self.assertEqual(after["max_repair_cycles"], 1)
            self.assertEqual(after["private_project_note"], "preserve-me")
