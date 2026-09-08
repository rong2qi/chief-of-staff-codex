import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from scripts import autonomy_policy, retry_policy
from scripts import continuous_execution

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "scripts"))
import init_project


def transition(**changes):
    value = {
        "schema": "CHIEF_REPAIR_PHASE_TRANSITION_V1", "prior_phase_id": "legacy",
        "prior_candidate_id": "old-candidate", "new_phase_id": "phase-2", "prior_failure_evidence": [{"evidence_ref":"repo://evidence/failure-1.json","evidence_sha256":"b" * 64}],
        "new_plan": "package-2", "new_candidate_id": "a" * 64,
        "approval_id": "approval-2", "writer_task_id": "writer-2",
        "stop_conditions": ["new_permission", "resource_limit"],
        "resource_limits": {"unit": "minutes", "maximum": 5},
    }
    value.update(changes)
    return value


class AutonomyPolicyTests(unittest.TestCase):
    def native_package(self, project, native, *, max_units=3):
        package = {
            "schema":"CHIEF_EXECUTION_PACKAGE_V1", "package_id":"p1", "approval_id":"ap1", "approval_status":"approved", "approval_receipt_sha256":"0" * 64, "approval_evidence_ref":"native://approval.json", "work_id":"w1", "project":{"project_id":"project-1","root_id":"root-1","branch":"branch"}, "writer_task_id":"writer-1", "write_surface":["repo://source"], "candidate_sha256":"a" * 64, "independent_reviewer_task_ids":["reviewer-1"], "goal":"local action", "endpoint":"local_delivered", "permissions":["local_read","local_write"], "resource_limits":{"max_progress_cycles":4,"max_resource_units":max_units,"resource_unit":"units"}, "acceptance":["done"], "stop_conditions":["new_permission"], "native_intake":{"root_id":"native-root","coordinator_task_id":"coordinator-1"}, "approved_local_actions":[{"action_id":"a1","action_class":"local_read","write_surface":None,"external_target":None,"data_classification":"synthetic","max_cost":2},{"action_id":"a2","action_class":"local_read","write_surface":None,"external_target":None,"data_classification":"synthetic","max_cost":2}]}
        digest = continuous_execution.package_digest(package)
        receipt={"schema":"CHIEF_EXECUTION_APPROVAL_EVIDENCE_V1","kind":"execution_approval","observation_id":"ap1","approval_id":"ap1","package_id":"p1","package_sha256":digest,"decision":"approved","observed_by":"operator","authority_kind":"native_coordinator_observation","coordinator_task_id":"coordinator-1","native_root_id":"native-root","project":package["project"],"writer_task_id":"writer-1","candidate_sha256":"a"*64}
        raw=(json.dumps(receipt,sort_keys=True)+"\n").encode(); package["approval_receipt_sha256"]=hashlib.sha256(raw).hexdigest(); native.mkdir(); (native/"approval.json").write_bytes(raw)
        state=project/".chief-of-staff"; state.mkdir(parents=True); (state/"project.json").write_text(json.dumps({"autonomy_policy_enabled":True})); (state/"project-plan.json").write_text(json.dumps({"execution_packages":[package]})); (state/"approval-queue.json").write_text(json.dumps({"requests":[{"request_id":"ap1","status":"approved","decision_receipt_sha256":package["approval_receipt_sha256"],"decision_evidence_ref":"native://approval.json"}]})); (state/"task-registry.json").write_text(json.dumps({"tasks":[{"task_id":"writer-1","project_id":"project-1","status":"running","write_surface":["repo://source"],"execution_work_id":"w1","execution_package_id":"p1","execution_root_id":"root-1","execution_branch":"branch"},{"task_id":"reviewer-1","project_id":"project-1","status":"running","write_surface":[],"execution_reviewer_for":"w1"}]})); return package

    def action_event(self, project, action_id, cost):
        value={"schema":"CHIEF_LOCAL_ACTION_REVALIDATION_V1","action_id":action_id,"action_class":"local_read","write_surface":None,"external_target":None,"data_classification":"synthetic","package_id":"p1","reverification":"passed"}; raw=(json.dumps(value,sort_keys=True)+"\n").encode(); path=project/"evidence.json"; path.write_bytes(raw)
        return {"action_id":action_id,"package_id":"p1","action_class":"local_read","write_surface":None,"external_target":None,"data_classification":"synthetic","cost":cost,"revalidation_ref":"repo://evidence.json","revalidation_sha256":hashlib.sha256(raw).hexdigest()}

    def defect_inputs(self, project, native, number):
        candidate = f"candidate-{number}"
        artifact = hashlib.sha256(f"artifact-{number}".encode()).hexdigest()
        progress = {"schema":"CHIEF_EXECUTION_PROGRESS_EVIDENCE_V1","kind":"acceptance_gain","evidence_id":f"progress-{number}","observation":{"before":"pending","after":f"verified-{number}"},"work_id":"w1","package_id":"p1","candidate_sha256":"a" * 64,"criterion_id":"done","artifact_sha256":artifact}
        progress_raw = (json.dumps(progress, sort_keys=True) + "\n").encode()
        progress_path = project / f"progress-{number}.json"; progress_path.write_bytes(progress_raw)
        progress_ref = {"kind":"acceptance_gain","evidence_id":f"progress-{number}","evidence_ref":f"repo://progress-{number}.json","evidence_sha256":hashlib.sha256(progress_raw).hexdigest(),"observation":progress["observation"]}
        measurement = {"schema":"CHIEF_EXECUTION_RESOURCE_MEASUREMENT_V1","work_id":"w1","package_id":"p1","resource_unit":"units","units_used":number}
        measurement_raw = (json.dumps(measurement, sort_keys=True) + "\n").encode(); measurement_path=project/f"measurement-{number}.json"; measurement_path.write_bytes(measurement_raw)
        measure_ref={"evidence_ref":f"repo://measurement-{number}.json","evidence_sha256":hashlib.sha256(measurement_raw).hexdigest()}
        review={"schema":"CHIEF_EXECUTION_REVIEW_EVIDENCE_V1","kind":"repair_review","repair_id":f"repair-{number}","review_id":f"review-{number}","reviewer_task_id":"reviewer-1","work_id":"w1","package_id":"p1","candidate_sha256":"a"*64,"candidate_id":candidate,"decision":"repair","coordinator_task_id":"coordinator-1","reviewed_artifact":{"candidate_id":candidate,"sha256":artifact,"outcome_ref":progress_ref["evidence_ref"],"outcome_sha256":progress_ref["evidence_sha256"]}}
        review_raw=(json.dumps(review,sort_keys=True)+"\n").encode(); review_path=native/f"review-{number}.json"; review_path.write_bytes(review_raw)
        review_ref={"evidence_ref":f"native://review-{number}.json","evidence_sha256":hashlib.sha256(review_raw).hexdigest()}
        defect={"schema":"CHIEF_CANDIDATE_DEFECT_EVIDENCE_V1","phase_id":"phase-2","candidate_id":candidate,"package_id":"p1","work_id":"w1"}
        defect_raw=(json.dumps(defect,sort_keys=True)+"\n").encode(); defect_path=project/f"defect-{number}.json"; defect_path.write_bytes(defect_raw)
        event={"event_id":f"defect-event-{number}","kind":"candidate_defect","scope":"repair","candidate_id":candidate,"failure_evidence_ref":f"repo://defect-{number}.json","failure_evidence_sha256":hashlib.sha256(defect_raw).hexdigest()}
        return candidate, progress_ref, measure_ref, review_ref, event

    def test_native_approved_action_is_idempotent_and_cumulative(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw); project=root/"project"; native=root/"native"; package=self.native_package(project,native,max_units=3)
            intake={"root_id":"native-root","coordinator_task_id":"coordinator-1","approval_sha256":package["approval_receipt_sha256"],"work_id":"w1","package_id":"p1","package_digest":continuous_execution.package_digest(package),"project":package["project"],"writer_task_id":"writer-1","candidate_sha256":"a"*64}
            event=self.action_event(project,"a1",2); self.assertEqual(retry_policy.consume_local_action(project,event,native_observation_root=native,native_intake=intake)["status"],"LOCAL_ACTION_INTENT")
            self.assertEqual(retry_policy.consume_local_action(project,event,native_observation_root=native,native_intake=intake)["status"],"OBSERVE_LOCAL_ACTION")
            with self.assertRaises(retry_policy.RetryPolicyError): retry_policy.consume_local_action(project,self.action_event(project,"a2",2),native_observation_root=native,native_intake=intake)
            self.assertEqual(json.loads((project/".chief-of-staff"/"repair-budget.json").read_text())["local_action_journal"][0]["cost"],2)

    def test_native_phase_reset_allows_only_numeric_local_stop_and_preserves_history(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw); project=root/"project"; native=root/"native"; package=self.native_package(project,native,max_units=50)
            state=project/".chief-of-staff"; state.joinpath("project.json").write_text(json.dumps({"autonomy_policy_enabled":True,"repair_one_shot":True,"repair_stop_provenance":{"repair_one_shot":"numeric_local_preparation_limit"}})); state.joinpath("repair-budget.json").write_text(json.dumps({"schema":"CHIEF_REPAIR_BUDGET_V1","cycles":[{"repair_id":"old"}]}))
            failure={"schema":"CHIEF_PHASE_FAILURE_EVIDENCE_V1","phase_id":"legacy","candidate_id":"old-candidate","verdict":"failed"}; failure_raw=(json.dumps(failure,sort_keys=True)+"\n").encode(); (project/"failure.json").write_bytes(failure_raw)
            intake={"root_id":"native-root","coordinator_task_id":"coordinator-1","approval_sha256":package["approval_receipt_sha256"],"work_id":"w1","package_id":"p1","package_digest":continuous_execution.package_digest(package),"project":package["project"],"writer_task_id":"writer-1","candidate_sha256":"a"*64}
            reset={"schema":"CHIEF_REPAIR_PHASE_TRANSITION_V1","prior_phase_id":"legacy","prior_candidate_id":"old-candidate","new_phase_id":"phase-2","prior_failure_evidence":[{"evidence_ref":"repo://failure.json","evidence_sha256":hashlib.sha256(failure_raw).hexdigest()}],"new_plan":"p1","new_candidate_id":"a"*64,"approval_id":"ap1","writer_task_id":"writer-1","stop_conditions":["new_permission"],"resource_limits":{"unit":"units","maximum":3}}
            receipt=retry_policy.begin_new_phase(project,reset,native_observation_root=native,native_intake=intake)
            self.assertEqual(receipt["active_phase_id"],"phase-2"); self.assertEqual(receipt["phases"][0]["cycles"],[{"repair_id":"old"}]); self.assertEqual(receipt["phases"][1]["cycles"],[])
            self.assertEqual(retry_policy.consume_local_action(project,self.action_event(project,"a1",1),native_observation_root=native,native_intake=intake)["status"],"LOCAL_ACTION_INTENT")
            state.joinpath("project.json").write_text(json.dumps({"autonomy_policy_enabled":True,"repair_one_shot":True,"repair_stop_provenance":{"repair_one_shot":"platform_safety"}}))
            with self.assertRaises(retry_policy.RetryPolicyError): retry_policy.begin_new_phase(project,{**reset,"prior_phase_id":"phase-2","new_phase_id":"phase-3"},native_observation_root=native,native_intake=intake)
            with self.assertRaises(retry_policy.RetryPolicyError): retry_policy.consume_local_action(project,self.action_event(project,"a2",1),native_observation_root=native,native_intake=intake)

    def test_native_phase_reset_then_three_repairs_and_fourth_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw); project=root/"project"; native=root/"native"; package=self.native_package(project,native,max_units=50)
            state=project/".chief-of-staff"; state.joinpath("project.json").write_text(json.dumps({"autonomy_policy_enabled":True,"max_repair_cycles":1,"repair_one_shot":True,"repair_stop_provenance":{"repair_one_shot":"numeric_local_preparation_limit"}})); state.joinpath("repair-budget.json").write_text(json.dumps({"schema":"CHIEF_REPAIR_BUDGET_V1","cycles":[{"repair_id":"legacy-old"}]}))
            failure={"schema":"CHIEF_PHASE_FAILURE_EVIDENCE_V1","phase_id":"legacy","candidate_id":"old-candidate","verdict":"completed"}; raw_failure=(json.dumps(failure,sort_keys=True)+"\n").encode(); (project/"failure.json").write_bytes(raw_failure)
            intake={"root_id":"native-root","coordinator_task_id":"coordinator-1","approval_sha256":package["approval_receipt_sha256"],"work_id":"w1","package_id":"p1","package_digest":continuous_execution.package_digest(package),"project":package["project"],"writer_task_id":"writer-1","candidate_sha256":"a"*64}
            reset={"schema":"CHIEF_REPAIR_PHASE_TRANSITION_V1","prior_phase_id":"legacy","prior_candidate_id":"old-candidate","new_phase_id":"phase-2","prior_failure_evidence":[{"evidence_ref":"repo://failure.json","evidence_sha256":hashlib.sha256(raw_failure).hexdigest()}],"new_plan":"p1","new_candidate_id":"a"*64,"approval_id":"ap1","writer_task_id":"writer-1","stop_conditions":["new_permission"],"resource_limits":{"unit":"units","maximum":3}}
            retry_policy.begin_new_phase(project,reset,native_observation_root=native,native_intake=intake)
            before = state.joinpath("repair-budget.json").read_bytes()
            with self.assertRaises(retry_policy.RetryPolicyError):
                retry_policy.consume_repair_cycle(project,"candidate-1","review-1","repair-1",reviewer_id="writer-1")
            self.assertEqual(before, state.joinpath("repair-budget.json").read_bytes())
            for number in range(1,4):
                candidate, progress, measurement, review, event = self.defect_inputs(project,native,number)
                retry_policy.consume_repair_cycle(project,candidate,f"review-{number}",f"repair-{number}",reviewer_id="reviewer-1",progress_evidence=progress,resource_measurement=measurement,review_evidence=review,native_observation_root=native,native_intake=intake,continuation_event=event)
            before_replay = state.joinpath("repair-budget.json").read_bytes()
            recorded = json.loads(before_replay)["phases"][1]["cycles"][-1]
            replay = retry_policy.consume_repair_cycle(project,recorded["candidate_id"],recorded["review_id"],recorded["repair_id"],reviewer_id=recorded["reviewer_id"],progress_evidence=recorded["progress_evidence"],resource_measurement=recorded["resource_measurement"],review_evidence=recorded["review_evidence"],native_observation_root=native,native_intake=intake,continuation_event=recorded["continuation_event"])
            self.assertEqual(before_replay, state.joinpath("repair-budget.json").read_bytes())
            self.assertEqual(len(replay["phases"][1]["cycles"]), 3)
            for changed_review in (
                {**recorded["review_evidence"], "evidence_ref": "native://changed-review.json"},
                {**recorded["review_evidence"], "evidence_sha256": "b" * 64},
                None,
                {"evidence_ref": recorded["review_evidence"]["evidence_ref"]},
            ):
                with self.subTest(changed_review=changed_review), self.assertRaisesRegex(retry_policy.RetryPolicyError, "review evidence"):
                    retry_policy.consume_repair_cycle(project,recorded["candidate_id"],recorded["review_id"],recorded["repair_id"],reviewer_id=recorded["reviewer_id"],progress_evidence=recorded["progress_evidence"],resource_measurement=recorded["resource_measurement"],review_evidence=changed_review,native_observation_root=native,native_intake=intake,continuation_event=recorded["continuation_event"])
                self.assertEqual(before_replay, state.joinpath("repair-budget.json").read_bytes())
            with self.assertRaisesRegex(retry_policy.RetryPolicyError, "conflicts"):
                retry_policy.consume_repair_cycle(project,recorded["candidate_id"],recorded["review_id"],recorded["repair_id"],reviewer_id=recorded["reviewer_id"],progress_evidence=recorded["progress_evidence"],resource_measurement=recorded["resource_measurement"],review_evidence=recorded["review_evidence"],native_observation_root=native,native_intake=intake,continuation_event={**recorded["continuation_event"],"event_id":"changed-event"})
            candidate, progress, measurement, review, event = self.defect_inputs(project,native,4)
            with self.assertRaisesRegex(retry_policy.RetryPolicyError, "defect allowance exhausted"): retry_policy.consume_repair_cycle(project,candidate,"review-4","repair-4",reviewer_id="reviewer-1",progress_evidence=progress,resource_measurement=measurement,review_evidence=review,native_observation_root=native,native_intake=intake,continuation_event=event)
            receipt=json.loads(state.joinpath("repair-budget.json").read_text()); self.assertEqual(receipt["phases"][0]["cycles"],[{"repair_id":"legacy-old"}]); self.assertEqual(len(receipt["phases"][1]["cycles"]),3)

    def test_legacy_one_and_two_cycle_limits_remain_exact(self):
        for maximum in (1, 2):
            with self.subTest(maximum=maximum):
                policy = retry_policy.RetryPolicy.from_mapping({"max_repair_cycles": maximum})
                self.assertTrue(policy.permit(reviews=1, repairs=maximum))
                self.assertFalse(policy.permit(reviews=1, repairs=maximum + 1))

    def test_phase_reset_never_resets_package_resource_account(self):
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw); project=root/"project"; native=root/"native"; package=self.native_package(project,native,max_units=4); state=project/".chief-of-staff"
            state.joinpath("project.json").write_text(json.dumps({"autonomy_policy_enabled":True,"max_repair_cycles":3,"repair_one_shot":True,"repair_stop_provenance":{"repair_one_shot":"numeric_local_preparation_limit"}})); state.joinpath("repair-budget.json").write_text(json.dumps({"schema":"CHIEF_REPAIR_BUDGET_V1","cycles":[]}))
            prior={"schema":"CHIEF_PHASE_FAILURE_EVIDENCE_V1","phase_id":"legacy","candidate_id":"old-candidate","verdict":"failed"}; prior_raw=(json.dumps(prior,sort_keys=True)+"\n").encode(); (project/"failure.json").write_bytes(prior_raw)
            intake={"root_id":"native-root","coordinator_task_id":"coordinator-1","approval_sha256":package["approval_receipt_sha256"],"work_id":"w1","package_id":"p1","package_digest":continuous_execution.package_digest(package),"project":package["project"],"writer_task_id":"writer-1","candidate_sha256":"a"*64}
            reset={"schema":"CHIEF_REPAIR_PHASE_TRANSITION_V1","prior_phase_id":"legacy","prior_candidate_id":"old-candidate","new_phase_id":"phase-2","prior_failure_evidence":[{"evidence_ref":"repo://failure.json","evidence_sha256":hashlib.sha256(prior_raw).hexdigest()}],"new_plan":"p1","new_candidate_id":"a"*64,"approval_id":"ap1","writer_task_id":"writer-1","stop_conditions":["new_permission"],"resource_limits":{"unit":"units","maximum":3}}
            receipt=retry_policy.begin_new_phase(project,reset,native_observation_root=native,native_intake=intake)
            _, _, old_measurement, _, _ = self.defect_inputs(project,native,2)
            receipt["phases"][0]["cycles"]=[{"repair_id":"old-resource","resource_measurement":old_measurement}]; state.joinpath("repair-budget.json").write_text(json.dumps(receipt))
            candidate, progress, low_measurement, review, event = self.defect_inputs(project,native,1); before=state.joinpath("repair-budget.json").read_bytes()
            with self.assertRaisesRegex(retry_policy.RetryPolicyError, "resource limit"):
                retry_policy.consume_repair_cycle(project,candidate,"review-1","repair-1",reviewer_id="reviewer-1",progress_evidence=progress,resource_measurement=low_measurement,review_evidence=review,native_observation_root=native,native_intake=intake,continuation_event=event)
            self.assertEqual(before,state.joinpath("repair-budget.json").read_bytes())
            self.assertEqual(retry_policy.consume_local_action(project,self.action_event(project,"a1",2),native_observation_root=native,native_intake=intake)["status"],"LOCAL_ACTION_INTENT")
            candidate, progress, total_measurement, review, event = self.defect_inputs(project,native,3)
            with self.assertRaisesRegex(retry_policy.RetryPolicyError, "resource limit"):
                retry_policy.consume_repair_cycle(project,candidate,"review-3","repair-3",reviewer_id="reviewer-1",progress_evidence=progress,resource_measurement=total_measurement,review_evidence=review,native_observation_root=native,native_intake=intake,continuation_event=event)
    def test_legacy_project_without_autonomy_key_retains_disabled_semantics(self):
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw)
            self.assertEqual(init_project.initialize(project, "Legacy"), 0)
            path = project / ".chief-of-staff" / "project.json"
            legacy = json.loads(path.read_text())
            del legacy["autonomy_policy_enabled"]
            path.write_text(json.dumps(legacy))
            self.assertFalse(any("autonomy_policy_enabled" in item for item in init_project.validate(project)))

    def test_approval_package_allows_read_only_and_no_deferred_decision(self):
        package = {
            "schema": "CHIEF_AUTONOMY_POLICY_V1", "package_id": "goal-1", "goal": "inspect local state",
            "write_surfaces": [], "action_classes": ["local_read"], "external_targets": [],
            "data_classification": "synthetic", "resource_limits": {"unit": "minutes", "maximum": 3},
            "reverification": ["recheck scope before action"], "stop_conditions": ["scope drift"],
            "rollback": "no mutation", "deferred_final_decisions": [],
        }
        self.assertEqual(autonomy_policy.validate_approval_package(package), package)
        action = {"action_class": "local_read", "write_surface": None, "external_target": None, "data_classification": "synthetic", "resource_cost": 1, "reverification_passed": True, "protected_action": "none"}
        self.assertEqual(autonomy_policy.evaluate_approved_local_action(package, action)["status"], "chief_approval_evidence_required")
        context = {"package_id": "goal-1", "action_class": "local_read", "write_surface": None, "external_target": None, "data_classification": "synthetic", "approved": True, "current": True, "resource_used": 1, "resource_max": 3}
        result = autonomy_policy.evaluate_approved_local_action(package, action, context)
        self.assertEqual(result["status"], "native_approval_consumer_required")
        self.assertTrue(result["todo_suppressed"])
        external = dict(action, action_class="external_send", protected_action="none")
        self.assertTrue(autonomy_policy.evaluate_approved_local_action(package, external, context)["operator_actionable_now"])
        missing = dict(action, reverification_passed=False)
        self.assertFalse(autonomy_policy.evaluate_approved_local_action(package, missing, context)["operator_actionable_now"])
        self.assertEqual(autonomy_policy.classify_continuation({"kind": "preparation", "scope": "local setup"}), "preparation")
        self.assertEqual(autonomy_policy.classify_continuation({"kind": "evidence_collection", "scope": "read logs"}), "evidence_collection")
        self.assertEqual(autonomy_policy.classify_continuation({"kind": "candidate_defect", "scope": "repair", "candidate_id": "c1", "failure_evidence": "repo://failure"}), "candidate_defect")

    def test_phase_transition_preserves_history_and_resets_only_active_cycles(self):
        state = {"schema": "CHIEF_REPAIR_BUDGET_V1", "cycles": [{"repair_id": "old"}], "diagnosis_requests": [], "extension": {"keep": True}}
        autonomy_policy.begin_new_phase(state, transition())
        cycles, journal = autonomy_policy.active_phase_state(state)
        self.assertEqual(cycles, [])
        self.assertEqual(journal, [])
        self.assertTrue(state["phases"][0]["closed"])
        self.assertEqual(state["phases"][0]["cycles"], [{"repair_id": "old"}])
        self.assertEqual(state["extension"], {"keep": True})
        with self.assertRaises(autonomy_policy.AutonomyPolicyError):
            autonomy_policy.begin_new_phase(state, transition(prior_phase_id="phase-2", new_phase_id="phase-2", new_candidate_id="b" * 64))

    def test_persisted_phase_reset_requires_existing_approved_plan_queue_and_writer(self):
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw) / "project"
            state = project / ".chief-of-staff"
            state.mkdir(parents=True)
            state.joinpath("project.json").write_text(json.dumps({"autonomy_policy_enabled": True}))
            package = {"package_id": "package-2", "candidate_sha256": "a" * 64, "approval_id": "approval-2", "writer_task_id": "writer-2", "work_id": "work-2", "resource_limits": {"resource_unit": "minutes", "max_resource_units": 8}}
            state.joinpath("project-plan.json").write_text(json.dumps({"execution_packages": [package]}))
            state.joinpath("approval-queue.json").write_text(json.dumps({"requests": [{"request_id": "approval-2", "status": "approved"}]}))
            state.joinpath("task-registry.json").write_text(json.dumps({"tasks": [{"task_id": "writer-2", "status": "running", "execution_package_id": "package-2", "execution_work_id": "work-2"}]}))
            state.joinpath("repair-budget.json").write_text(json.dumps({"schema": "CHIEF_REPAIR_BUDGET_V1", "cycles": [{"repair_id": "old"}]}))
            with self.assertRaises(retry_policy.RetryPolicyError):
                retry_policy.begin_new_phase(project, transition())

    def test_local_action_without_native_package_binding_never_writes_or_returns_intent(self):
        with tempfile.TemporaryDirectory() as raw:
            project = Path(raw) / "project"; state = project / ".chief-of-staff"; state.mkdir(parents=True)
            event = {"action_id":"a1","package_id":"p1","action_class":"local_read","write_surface":None,"external_target":None,"data_classification":"synthetic","cost":1,"revalidation_ref":"repo://evidence.json","revalidation_sha256":"a" * 64}
            with self.assertRaises(retry_policy.RetryPolicyError):
                retry_policy.consume_local_action(project, event, native_observation_root=Path(raw) / "native", native_intake={})
            self.assertFalse(state.joinpath("repair-budget.json").exists())
