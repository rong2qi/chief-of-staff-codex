"""C2 independent-review consumer regressions (not schema-only probes)."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import continuous_execution, delivery_ledger, retry_policy
from tests.private_authority_fixture import TESTING_REVIEWER_ID
from tests.test_continuous_execution import native_intake, runtime_package, retained_measurement, retained_progress, retained_review, retained_stagnant, retained_diagnosis
from tests.test_gap_closure import observed


class RepairTwoConsumerRegressions(unittest.TestCase):
    def test_disposable_local_delivery_runs_red_green_review_docs_commit_and_restart(self):
        """Real subprocess workflow; native role events are explicitly test simulations."""
        with tempfile.TemporaryDirectory() as temporary:
            case = self._native_recovery_case(Path(temporary))
            project, native = case["project"], case["native"]
            source = project / "source"
            source.mkdir()
            module = source / "calculator.py"
            module.write_text("def add(a, b):\n    return a - b\n")
            (source / "test_calculator.py").write_text("import unittest\nfrom calculator import add\nclass Addition(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 2), 4)\n")
            command = [sys.executable, "-B", "-m", "unittest", "discover", "-s", "source", "-v"]
            red = subprocess.run(command, cwd=project, text=True, capture_output=True)
            self.assertEqual(red.returncode, 1)
            self.assertIn("Ran 1 test", red.stderr)
            self.assertIn("FAIL", red.stderr)
            module.write_text("def add(a, b):\n    return a + b\n")
            green = subprocess.run(command, cwd=project, text=True, capture_output=True)
            self.assertEqual(green.returncode, 0, green.stderr)
            self.assertIn("Ran 1 test", green.stderr)
            artifact_sha = hashlib.sha256(module.read_bytes()).hexdigest()
            progress = retained_progress(project, 1)
            outcome_path = project / progress["evidence_ref"].removeprefix("repo://")
            outcome = json.loads(outcome_path.read_text())
            outcome.update(artifact_sha256=artifact_sha, observation={"before": "one actual addition test failed", "after": "one actual addition test passed"})
            raw = (json.dumps(outcome, sort_keys=True)+"\n").encode()
            outcome_path.write_bytes(raw)
            progress.update(evidence_sha256=hashlib.sha256(raw).hexdigest(), observation=outcome["observation"])
            # A separate read-only verifier process reruns the check and binds
            # source bytes; it is not a real Testing Chief or production receipt.
            probe = subprocess.run([sys.executable, "-B", "-c", "import hashlib,json,pathlib,subprocess,sys; p=pathlib.Path(sys.argv[1]); r=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s','source','-v'],cwd=p,capture_output=True,text=True); assert r.returncode==0 and 'Ran 1 test' in r.stderr; print(json.dumps({'sha256':hashlib.sha256((p/'source/calculator.py').read_bytes()).hexdigest(),'tests':1,'simulated_native_observer':True}))", str(project)], text=True, capture_output=True)
            self.assertEqual(probe.returncode, 0, probe.stderr)
            observation = json.loads(probe.stdout)
            self.assertEqual(observation["sha256"], artifact_sha)
            review = retained_review(native, 1)
            review_path = native / "review-1.json"
            reviewed = json.loads(review_path.read_text())
            reviewed["reviewed_artifact"].update(sha256=observation["sha256"], outcome_sha256=progress["evidence_sha256"])
            review_raw = (json.dumps(reviewed, sort_keys=True)+"\n").encode()
            review_path.write_bytes(review_raw)
            review["evidence_sha256"] = hashlib.sha256(review_raw).hexdigest()
            result = retry_policy.consume_repair_cycle(project, "candidate-1", "review-1", "repair-1", reviewer_id="reviewer-1", progress_evidence=progress, resource_measurement=retained_measurement(project, 1), review_evidence=review, native_intake=native_intake(case["package"]), execution_package_id="package-1", execution_work_id="work-new", native_observation_root=native)
            self.assertEqual(result["cycles"][0]["reviewed_artifact"]["sha256"], artifact_sha)
            first = self._native_cli(case)
            self.assertEqual(first["next_action"], "DISPATCH_RETURNED_WORK")
            self.assertEqual(self._native_cli(case)["next_action"], "OBSERVE_RETURN_DISPATCH")
            (source / "README.md").write_text("# Disposable addition fixture\n\nOne actual test passed after the observed repair. Native role events are simulated; no Testing gate is claimed.\n\nRun: python -B -m unittest discover -s source -v\n")
            # Git is confined to the disposable fixture, without remote/hook/signing.
            environment = dict(os.environ)
            for key in tuple(environment):
                if key.startswith("GIT_"):
                    environment.pop(key)
            environment.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
            git = ["git", "-c", "core.hooksPath="+os.devnull, "-c", "commit.gpgsign=false", "-c", "user.name=Disposable fixture", "-c", "user.email=fixture@example.invalid"]
            for args in (("init", "--quiet"), ("add", "--", "source"), ("commit", "--quiet", "-m", "fixture: verified local delivery")):
                saved = subprocess.run([*git, *args], cwd=project, env=environment, text=True, capture_output=True)
                self.assertEqual(saved.returncode, 0, saved.stderr)
            listing = subprocess.run([*git, "ls-tree", "-r", "--name-only", "HEAD"], cwd=project, env=environment, text=True, capture_output=True)
            self.assertEqual(set(listing.stdout.splitlines()), {"source/calculator.py", "source/test_calculator.py", "source/README.md"})
            self.assertEqual(hashlib.sha256(module.read_bytes()).hexdigest(), artifact_sha)
            remote = subprocess.run([*git, "remote"], cwd=project, env=environment, text=True, capture_output=True)
            self.assertEqual(remote.stdout, "")

    def _retry(self, case, number, *, stagnant=False, diagnosis=None, review=None):
        kwargs = {"stagnant_evidence":retained_stagnant(case["project"], number)} if stagnant else {"progress_evidence":retained_progress(case["project"], number)}
        return retry_policy.consume_repair_cycle(case["project"], f"candidate-{number}", f"review-{number}", f"repair-{number}", reviewer_id="reviewer-1", resource_measurement=retained_measurement(case["project"], number), review_evidence=review or retained_review(case["native"], number, outcome_kind="stagnant" if stagnant else "progress"), diagnosis_evidence=diagnosis, native_intake=native_intake(case["package"]), execution_package_id="package-1", execution_work_id="work-new", native_observation_root=case["native"], **kwargs)

    def test_held_directory_identity_rejects_both_containment_directions_and_aliases(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent, child, sibling = root/"parent", root/"parent/child", root/"sibling"
            child.mkdir(parents=True); sibling.mkdir()
            descriptors = [retry_policy._open_project_directory(path) for path in (parent, child, sibling)]
            try:
                for first, second in ((0, 0), (0, 1), (1, 0)):
                    with self.assertRaises(retry_policy.RetryPolicyError):
                        retry_policy._require_disjoint_directories(descriptors[first], descriptors[second])
                retry_policy._require_disjoint_directories(descriptors[1], descriptors[2])
                if sys.platform == "darwin":
                    canonical = child.resolve()
                    alias = Path(str(canonical).replace("/private/var/", "/var/", 1).replace("/private/tmp/", "/tmp/", 1))
                    fd = retry_policy._open_project_directory(alias)
                    try:
                        with self.assertRaises(retry_policy.RetryPolicyError):
                            retry_policy._require_disjoint_directories(descriptors[0], fd)
                    finally:
                        os.close(fd)
            finally:
                for fd in descriptors:
                    os.close(fd)

    def test_review_actor_candidate_missing_binding_and_historical_artifact_refuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            for index, mutate in enumerate((lambda item: item.__setitem__("candidate_id", "wrong"), lambda item: item.__setitem__("reviewer_task_id", "unregistered"), lambda item: item.pop("reviewed_artifact"))):
                case = self._native_recovery_case(Path(temporary)/str(index))
                review = retained_review(case["native"], 1)
                path = case["native"] / "review-1.json"
                value = json.loads(path.read_text()); mutate(value)
                raw = (json.dumps(value, sort_keys=True)+"\n").encode(); path.write_bytes(raw)
                review["evidence_sha256"] = hashlib.sha256(raw).hexdigest()
                with self.assertRaises(retry_policy.RetryPolicyError):
                    self._retry(case, 1, review=review)
                self.assertFalse((case["project"] / ".chief-of-staff/repair-budget.json").exists())
            case = self._native_recovery_case(Path(temporary)/"history")
            first = self._retry(case, 1); second = self._retry(case, 2)
            self.assertNotEqual(first["cycles"][0]["reviewed_artifact"]["sha256"], second["cycles"][1]["reviewed_artifact"]["sha256"])
            budget = case["project"] / ".chief-of-staff/repair-budget.json"
            value = json.loads(budget.read_text()); value["cycles"][0]["reviewed_artifact"]["sha256"] = "c"*64
            budget.write_text(json.dumps(value)); before = budget.read_bytes()
            with self.assertRaises(retry_policy.RetryPolicyError):
                self._retry(case, 3)
            self.assertEqual(budget.read_bytes(), before)

    def test_missing_new_path_reproduction_never_consumes_diagnosis(self):
        with tempfile.TemporaryDirectory() as temporary:
            case = self._native_recovery_case(Path(temporary))
            self._retry(case, 1, stagnant=True); self._retry(case, 2, stagnant=True)
            diagnosis = retained_diagnosis(case["native"])
            (case["native"] / "diagnosis-path.json").unlink()
            budget = case["project"] / ".chief-of-staff/repair-budget.json"
            before = budget.read_bytes()
            with self.assertRaises(retry_policy.RetryPolicyError):
                self._retry(case, 2, stagnant=True, diagnosis=diagnosis)
            self.assertEqual(budget.read_bytes(), before)

    def test_consumed_diagnosis_requires_reproducible_path_and_next_review_binding(self):
        with tempfile.TemporaryDirectory() as temporary:
            case = self._native_recovery_case(Path(temporary))
            self._retry(case, 1, stagnant=True)
            self._retry(case, 2, stagnant=True)
            diagnosis = retained_diagnosis(case["native"])
            self._retry(case, 2, stagnant=True, diagnosis=diagnosis)
            budget = case["project"] / ".chief-of-staff/repair-budget.json"
            before = budget.read_bytes()
            # Mere consumption does not authorize a review that ignores the new path.
            with self.assertRaises(retry_policy.RetryPolicyError):
                self._retry(case, 3)
            self.assertEqual(budget.read_bytes(), before)
            original = json.loads((case["native"] / "diagnosis.json").read_text())
            used = {"request_id":original["request_id"], **diagnosis, "new_path_evidence_ref":original["new_path_evidence_ref"], "new_path_evidence_sha256":original["new_path_evidence_sha256"]}
            review = retained_review(case["native"], 3, diagnosis=used)
            accepted = self._retry(case, 3, review=review)
            self.assertEqual(accepted["cycles"][-1]["diagnosis_used"], used)
            before = budget.read_bytes()
            (case["native"] / "diagnosis-path.json").write_text("{}")
            with self.assertRaises(retry_policy.RetryPolicyError):
                self._retry(case, 4)
            self.assertEqual(budget.read_bytes(), before)

    def test_retry_round_artifact_is_native_bound_not_a_new_label(self):
        variants = (("candidate_id", "other"), ("sha256", "c"*64), ("outcome_sha256", "c"*64), ("outcome_ref", "repo://other.json"))
        with tempfile.TemporaryDirectory() as temporary:
            for index, (key, value) in enumerate(variants):
                case = self._native_recovery_case(Path(temporary)/str(index))
                progress = retained_progress(case["project"], 1)
                review = retained_review(case["native"], 1)
                path = case["native"] / "review-1.json"
                raw = json.loads(path.read_text())
                raw["reviewed_artifact"][key] = value
                changed = (json.dumps(raw, sort_keys=True)+"\n").encode()
                path.write_bytes(changed)
                review["evidence_sha256"] = hashlib.sha256(changed).hexdigest()
                with self.assertRaises(retry_policy.RetryPolicyError):
                    retry_policy.consume_repair_cycle(case["project"], "candidate-1", "review-1", "repair-1", reviewer_id="reviewer-1", progress_evidence=progress, resource_measurement=retained_measurement(case["project"], 1), review_evidence=review, native_intake=native_intake(case["package"]), execution_package_id="package-1", execution_work_id="work-new", native_observation_root=case["native"])
                self.assertFalse((case["project"] / ".chief-of-staff/repair-budget.json").exists())

    def _native_recovery_case(self, root, *, status="technical_blocked", owner="writer-1", candidate="a" * 64, testing=None, testing_mutator=None, return_kind="recovery"):
        project = root / "project"; state = project / ".chief-of-staff"; state.mkdir(parents=True)
        native = root / "native"; native.mkdir()
        package = runtime_package(project, native)
        if testing:
            package["testing_policy"]={"risk":testing,"scope":"local","sensitive":False,"production":False,"global_upgrade":testing=="high","disputed":False}
            approval={"schema":"CHIEF_EXECUTION_APPROVAL_EVIDENCE_V1","kind":"execution_approval","observation_id":"approval-1","approval_id":"approval-1","package_id":"package-1","package_sha256":continuous_execution.package_digest(package),"decision":"approved","observed_by":"operator-observer-1","authority_kind":"native_coordinator_observation","coordinator_task_id":"coordinator-1","native_root_id":"native-test","project":package["project"],"writer_task_id":"writer-1","candidate_sha256":"a"*64}
            approval_raw=(json.dumps(approval,sort_keys=True)+"\n").encode(); native.joinpath("approval.json").write_bytes(approval_raw); package["approval_receipt_sha256"]=hashlib.sha256(approval_raw).hexdigest()
        registry = {"tasks": [
            {"task_id":"writer-1","project_id":"project-1","status":"testing_queue" if testing else "technical_blocked","execution_work_id":"work-new","execution_package_id":"package-1","execution_root_id":"root-1","execution_branch":"candidate-branch","write_surface":["repo://source"]},
            {"task_id":"reviewer-1","project_id":"project-1","status":"running","execution_reviewer_for":"work-new","write_surface":[]},
        ]}
        state.joinpath("project.json").write_text(json.dumps({"max_repair_cycles": 3, "execution_package_id": "package-1", "execution_work_id": "work-new"}))
        state.joinpath("project-plan.json").write_text(json.dumps({"execution_packages": [package]}))
        state.joinpath("task-registry.json").write_text(json.dumps(registry))
        state.joinpath("approval-queue.json").write_text(json.dumps({"requests":[{"request_id":"approval-1","status":"approved","decision_receipt_sha256":package["approval_receipt_sha256"],"decision_evidence_ref":package["approval_evidence_ref"]}]}))
        ledger_root = project / "ledger"; ledger_root.mkdir()
        report_id="report-native-1"; return_id="return-native-1"; head="b" * 40
        recovery={"schema":"CHIEF_NATIVE_RECOVERY_RETURN_V1","kind":"recovery_return","observation_id":return_id,"authority_kind":"native_coordinator_observation","native_root_id":"native-test","coordinator_task_id":"coordinator-1","report_id":report_id,"work_id":"work-new","package_id":"package-1","package_digest":continuous_execution.package_digest(package),"candidate_sha256":"a"*64,"project":package["project"],"source_task_id":"writer-1","target_task_id":"coordinator-1","return_to_task_id":"writer-1","current_head":head,"status":"accepted"}
        if return_kind == "approval":
            recovery.update(schema="CHIEF_NATIVE_APPROVAL_RETURN_V1", kind="approval_return", approval_id=package["approval_id"], approval_evidence_ref=package["approval_evidence_ref"], approval_receipt_sha256=package["approval_receipt_sha256"])
        elif return_kind == "resource_recovered":
            recovery.update(schema="CHIEF_NATIVE_RESOURCE_RECOVERY_RETURN_V1", kind="resource_recovered_return", resource_unit=package["resource_limits"]["resource_unit"], resource_units_used=0, available=True, new_paid_capacity=False)
        delegation=None
        if testing:
            policy=package["testing_policy"]; recovery={"schema":"CHIEF_TESTING_GATE_RECEIPT_V1" if testing=="high" else "CHIEF_TESTING_REVIEW_RECEIPT_V1","issuer_task_id":TESTING_REVIEWER_ID if testing=="high" else "reviewer-1","status":"TESTING_GATE_PASS" if testing=="high" else "PASS","work_id":"work-new","package_id":"package-1","candidate_sha256":"a"*64,"project":package["project"],"writer_task_id":"writer-1","risk":policy["risk"],"scope":"local","sensitive":False,"production":False,"global_upgrade":policy["global_upgrade"],"disputed":False,"unresolved_findings":False}
            if testing != "high":
                delegation={"testing_chief_task_id":TESTING_REVIEWER_ID,"delegation_id":"delegate-1","reviewer_task_id":"reviewer-1","writer_task_id":"writer-1","reviewer_registered":True,"risk":"medium","candidate_sha256":"a"*64,"scope":"local","delegation_evidence_ref":"native://delegation.json","delegation_receipt_sha256":""}
                delegated={"schema":"CHIEF_TESTING_DELEGATION_EVIDENCE_V1","issuer_task_id":TESTING_REVIEWER_ID,"delegation_id":"delegate-1","reviewer_task_id":"reviewer-1","writer_task_id":"writer-1","candidate_sha256":"a"*64,"scope":"local","risk":"medium","work_id":"work-new","package_id":"package-1","sensitive":False,"production":False,"global_upgrade":False,"disputed":False,"authority_kind":"native_coordinator_observation","native_root_id":"native-test","coordinator_task_id":"coordinator-1","package_digest":continuous_execution.package_digest(package),"project":package["project"],"target_task_id":"reviewer-1","observation_id":"delegation-observation-1","native_event_id":"delegation-event-1"}; delegated_raw=(json.dumps(delegated,sort_keys=True)+"\n").encode(); native.joinpath("delegation.json").write_bytes(delegated_raw); delegation["delegation_receipt_sha256"]=hashlib.sha256(delegated_raw).hexdigest(); recovery["reviewer_task_id"]="reviewer-1"
            recovery.update({"authority_kind":"native_coordinator_observation","native_root_id":"native-test","coordinator_task_id":"coordinator-1","package_digest":continuous_execution.package_digest(package),"target_task_id":"writer-1","source_task_id":recovery["issuer_task_id"],"observation_id":"testing-observation-1","native_event_id":"testing-event-1"})
            if delegation is not None:
                recovery["delegation_id"]="delegate-1"
        if testing_mutator is not None:
            delegated = json.loads(native.joinpath("delegation.json").read_text()) if delegation is not None else None
            testing_mutator(recovery, delegation, delegated)
            if delegated is not None:
                delegated_raw=(json.dumps(delegated,sort_keys=True)+"\n").encode(); native.joinpath("delegation.json").write_bytes(delegated_raw); delegation["delegation_receipt_sha256"]=hashlib.sha256(delegated_raw).hexdigest()
        recovery_raw=(json.dumps(recovery,sort_keys=True)+"\n").encode(); native.joinpath("recovery.json").write_bytes(recovery_raw)
        payload={"schema":"CHIEF_CONTINUOUS_RETURN_V1","report_id":report_id,"return_id":return_id,"work_id":"work-new","package_id":"package-1","candidate_sha256":candidate,"kind":"test_pass" if testing else return_kind,"scope":"local","source_task_id":"writer-1","target_task_id":"coordinator-1","project_id":"project-1","return_to_task_id":"writer-1","native_receipt_ref":"native://recovery.json","native_receipt_sha256":hashlib.sha256(recovery_raw).hexdigest()}
        if delegation: payload["testing_delegation"]=delegation
        raw=(json.dumps(payload,sort_keys=True)+"\n").encode(); ledger_root.joinpath("return.json").write_bytes(raw)
        report={"report_id":report_id,"source_task_id":"writer-1","target_task_id":"coordinator-1","project_id":"project-1","payload_sha256":hashlib.sha256(raw).hexdigest(),"artifact_refs":["repo://return.json"],"continuous_payload_ref":"repo://return.json"}
        ledger=delivery_ledger.Ledger(ledger_root); ledger.ingest("ARTIFACT_FROZEN",report); ledger.ingest("SEND_ATTEMPTED",{**report,"attempt_id":"attempt-1"})
        identity={key:report[key] for key in ("report_id","source_task_id","target_task_id","project_id","payload_sha256")}
        ledger.ingest("TRANSPORT_ACCEPTED",{**report,"attempt_id":"attempt-1","tool_name":"native",**observed(ledger_root,"transport_accepted",{**identity,"attempt_id":"attempt-1"},{"status":"accepted","attempt_id":"attempt-1","tool_name":"native"},"raw_receipt_sha256")})
        ack={"ack_task_id":"coordinator-1","observed_by_task_id":"writer-1","observation_kind":"receiver_stream","receiver_event_id":"ack-native-1"}; ledger.ingest("RECEIVER_ACK_OBSERVED",{**report,"attempt_id":"attempt-1",**ack,**observed(ledger_root,"receiver_ack",{**identity,"attempt_id":"attempt-1"},ack,"raw_observation_sha256")})
        review={"decision":"accepted","reviewer_task_id":"coordinator-1"}; ledger.ingest("REVIEW_DECIDED",{**report,"attempt_id":"attempt-1",**review,**observed(ledger_root,"review_decision",{**identity,"attempt_id":"attempt-1"},review,"review_receipt_sha256")})
        task={"schema":"CHIEF_NATIVE_TASK_STATE_V1","kind":"current_task_state","observation_id":"task-observation-1","authority_kind":"native_coordinator_observation","native_root_id":"native-test","coordinator_task_id":"coordinator-1","work_id":"work-new","package_id":"package-1","package_digest":continuous_execution.package_digest(package),"project":package["project"],"candidate_sha256":"a"*64,"writer_task_id":"writer-1","task_id":"writer-1","owner_task_id":owner,"registered_status":"testing_queue" if testing else "technical_blocked","status":"testing_queue" if testing else status,"current_head":head,"resource_unit":"test_minutes","resource_units_used":0}
        task_raw=(json.dumps(task,sort_keys=True)+"\n").encode(); native.joinpath("task.json").write_bytes(task_raw)
        return {"project":project,"native":native,"ledger":ledger_root,"package":package,"report":report,"head":head,"task_sha":hashlib.sha256(task_raw).hexdigest(),"payload":payload}

    def _native_cli(self, case, *extra, raw=False):
        command=[sys.executable, str(Path(delivery_ledger.__file__)), "--ledger", str(case["ledger"]), "continuous-reconcile", "--project", str(case["project"]), "--execution-package-id", "package-1", "--execution-work-id", "work-new", "--native-observation-root", str(case["native"]), "--native-intake-json", json.dumps(native_intake(case["package"])), "--expected-head", case["head"], "--current-task-ref", "native://task.json", "--current-task-sha256", case["task_sha"], *extra]
        result=subprocess.run(command,text=True,capture_output=True)
        if raw: return result
        self.assertEqual(result.returncode,0,result.stderr)
        return json.loads(result.stdout)

    def test_medium_testing_rejects_unregistered_reviewer_and_policy_scope_without_writing_intent(self):
        with tempfile.TemporaryDirectory() as temporary:
            variants=(
                lambda receipt, delegation, delegated: (receipt.update({"issuer_task_id":"ghost-reviewer","reviewer_task_id":"ghost-reviewer"}), delegation.update({"reviewer_task_id":"ghost-reviewer"}), delegated.update({"reviewer_task_id":"ghost-reviewer"})),
                lambda receipt, delegation, delegated: (delegation.update({"scope":"other-scope"}), delegated.update({"scope":"other-scope"})),
            )
            for index, mutate in enumerate(variants):
                case=self._native_recovery_case(Path(temporary)/str(index),testing="medium",testing_mutator=mutate)
                before=(case["ledger"] / "events.jsonl").read_bytes()
                result=self._native_cli(case,raw=True)
                self.assertNotEqual(result.returncode,0,result.stdout)
                self.assertEqual((case["ledger"] / "events.jsonl").read_bytes(),before)

    def test_testing_receipt_flags_issuer_and_candidate_reject_without_writing_intent(self):
        with tempfile.TemporaryDirectory() as temporary:
            mutations=[]
            for field in ("sensitive","production","global_upgrade","disputed"):
                mutations += [lambda receipt, delegation, delegated, field=field: receipt.pop(field), lambda receipt, delegation, delegated, field=field: receipt.__setitem__(field,True), lambda receipt, delegation, delegated, field=field: receipt.__setitem__(field,0)]
                mutations += [lambda receipt, delegation, delegated, field=field: delegated.pop(field), lambda receipt, delegation, delegated, field=field: delegated.__setitem__(field,True)]
            mutations += [lambda receipt, delegation, delegated: receipt.__setitem__("candidate_sha256","c"*64)]
            for index, mutate in enumerate(mutations):
                case=self._native_recovery_case(Path(temporary)/str(index),testing="medium",testing_mutator=mutate); before=(case["ledger"] / "events.jsonl").read_bytes(); result=self._native_cli(case,raw=True)
                self.assertNotEqual(result.returncode,0,result.stdout); self.assertEqual((case["ledger"] / "events.jsonl").read_bytes(),before)
            direct=self._native_recovery_case(Path(temporary)/"direct",testing="high",testing_mutator=lambda receipt, delegation, delegated: receipt.__setitem__("issuer_task_id","ghost-Chief")); before=(direct["ledger"] / "events.jsonl").read_bytes(); result=self._native_cli(direct,raw=True)
            self.assertNotEqual(result.returncode,0,result.stdout); self.assertEqual((direct["ledger"] / "events.jsonl").read_bytes(),before)

    def test_testing_native_identity_fields_reject_without_writing_intent(self):
        with tempfile.TemporaryDirectory() as temporary:
            mutations=[lambda r,d,n: r.__setitem__("native_root_id","wrong"),lambda r,d,n:r.__setitem__("coordinator_task_id","wrong"),lambda r,d,n:r.__setitem__("package_digest","c"*64),lambda r,d,n:r.__setitem__("target_task_id","wrong"),lambda r,d,n:r.__setitem__("source_task_id","wrong"),lambda r,d,n:r.__setitem__("native_event_id","")]
            for i, mutate in enumerate(mutations):
                case=self._native_recovery_case(Path(temporary)/str(i),testing="medium",testing_mutator=mutate); before=(case["ledger"] / "events.jsonl").read_bytes(); result=self._native_cli(case,raw=True); self.assertNotEqual(result.returncode,0,result.stdout); self.assertEqual((case["ledger"] / "events.jsonl").read_bytes(),before)
            delegated_mutations=[lambda r,d,n:n.__setitem__("native_root_id","wrong"),lambda r,d,n:n.__setitem__("coordinator_task_id","wrong"),lambda r,d,n:n.__setitem__("package_digest","c"*64),lambda r,d,n:n.__setitem__("project",{}),lambda r,d,n:n.__setitem__("target_task_id","wrong"),lambda r,d,n:n.__setitem__("native_event_id","")]
            for i, mutate in enumerate(delegated_mutations):
                case=self._native_recovery_case(Path(temporary)/("delegated"+str(i)),testing="medium",testing_mutator=mutate); before=(case["ledger"] / "events.jsonl").read_bytes(); result=self._native_cli(case,raw=True); self.assertNotEqual(result.returncode,0,result.stdout); self.assertEqual((case["ledger"] / "events.jsonl").read_bytes(),before)

    def test_native_recovery_cli_prepares_observes_and_requires_exact_dispatch_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            case=self._native_recovery_case(Path(temporary))
            first=self._native_cli(case); self.assertEqual(first["next_action"],"DISPATCH_RETURNED_WORK")
            restarted=self._native_cli(case); self.assertEqual(restarted["next_action"],"OBSERVE_RETURN_DISPATCH"); self.assertEqual(first["action"]["action_id"],restarted["action_id"])
            receipt={"schema":"CHIEF_NATIVE_RETURN_DISPATCH_RECEIPT_V1","kind":"recovery_dispatch","observation_id":"dispatch-observation-1","authority_kind":"native_coordinator_observation","native_root_id":"native-test","coordinator_task_id":"coordinator-1","report_id":"report-native-1","return_id":"return-native-1","action_id":restarted["action_id"],"work_id":"work-new","package_id":"package-1","candidate_sha256":"a"*64,"project":case["package"]["project"],"source_task_id":"coordinator-1","target_task_id":"writer-1","current_task_observation_id":"task-observation-1","expected_head":case["head"],"status":"accepted","dispatch_tool":"native-observer","native_event_id":"native-event-1"}
            raw=(json.dumps(receipt,sort_keys=True)+"\n").encode(); case["native"].joinpath("dispatch.json").write_bytes(raw)
            done=self._native_cli(case,"--dispatch-report-id","report-native-1","--dispatch-action-id",restarted["action_id"],"--dispatch-evidence-ref","native://dispatch.json","--dispatch-evidence-sha256",hashlib.sha256(raw).hexdigest()); self.assertEqual(done["next_action"],"NO_ACTION")
            self.assertEqual(self._native_cli(case)["next_action"],"NO_ACTION")
            case["native"].joinpath("dispatch.json").write_bytes(raw+b"drift")
            before=(case["ledger"] / "events.jsonl").read_bytes(); drifted=self._native_cli(case,raw=True)
            self.assertNotEqual(drifted.returncode,0); self.assertEqual((case["ledger"] / "events.jsonl").read_bytes(),before)

    def test_native_approval_and_resource_returns_prepare_once_and_observe_dispatch(self):
        with tempfile.TemporaryDirectory() as temporary:
            for kind, status in (("approval", "awaiting_permission"), ("resource_recovered", "quota_limited")):
                with self.subTest(kind=kind):
                    case = self._native_recovery_case(Path(temporary)/kind, return_kind=kind, status=status)
                    first = self._native_cli(case)
                    self.assertEqual(first["next_action"], "DISPATCH_RETURNED_WORK")
                    pending = self._native_cli(case)
                    self.assertEqual(pending["next_action"], "OBSERVE_RETURN_DISPATCH")
                    receipt = {"schema":"CHIEF_NATIVE_RETURN_DISPATCH_RECEIPT_V1", "kind":kind+"_dispatch", "observation_id":"dispatch-"+kind, "authority_kind":"native_coordinator_observation", "native_root_id":"native-test", "coordinator_task_id":"coordinator-1", "report_id":"report-native-1", "return_id":"return-native-1", "action_id":pending["action_id"], "work_id":"work-new", "package_id":"package-1", "candidate_sha256":"a"*64, "project":case["package"]["project"], "source_task_id":"coordinator-1", "target_task_id":"writer-1", "current_task_observation_id":"task-observation-1", "expected_head":case["head"], "status":"accepted", "dispatch_tool":"native-observer", "native_event_id":"event-"+kind}
                    raw = (json.dumps(receipt, sort_keys=True)+"\n").encode()
                    case["native"].joinpath("dispatch.json").write_bytes(raw)
                    done = self._native_cli(case, "--dispatch-report-id", "report-native-1", "--dispatch-action-id", pending["action_id"], "--dispatch-evidence-ref", "native://dispatch.json", "--dispatch-evidence-sha256", hashlib.sha256(raw).hexdigest())
                    self.assertEqual(done["next_action"], "NO_ACTION")
                    self.assertEqual(self._native_cli(case)["next_action"], "NO_ACTION")

    def test_native_approval_resource_scope_flags_and_wait_reason_fail_closed(self):
        variants = [("approval", "awaiting_input", None), ("resource_recovered", "awaiting_permission", None)]
        variants += [("approval", "awaiting_permission", lambda receipt, *_: receipt.__setitem__("approval_receipt_sha256", "c"*64))]
        variants += [("resource_recovered", "quota_limited", lambda receipt, *_, key=key, value=value: receipt.__setitem__(key, value)) for key, value in (("available", False), ("available", 1), ("new_paid_capacity", True), ("new_paid_capacity", 0), ("resource_unit", "other"), ("resource_units_used", 1), ("resource_units_used", False))]
        with tempfile.TemporaryDirectory() as temporary:
            for index, (kind, status, mutate) in enumerate(variants):
                case = self._native_recovery_case(Path(temporary)/str(index), return_kind=kind, status=status, testing_mutator=mutate)
                before = case["ledger"].joinpath("events.jsonl").read_bytes()
                result = self._native_cli(case, raw=True)
                self.assertTrue(result.returncode != 0 or json.loads(result.stdout)["next_action"] != "DISPATCH_RETURNED_WORK")
                self.assertEqual(case["ledger"].joinpath("events.jsonl").read_bytes(), before)

    def test_native_testing_cli_medium_delegated_and_global_direct(self):
        with tempfile.TemporaryDirectory() as temporary:
            for mode in ("medium", "high"):
                case=self._native_recovery_case(Path(temporary)/mode,testing=mode)
                first=self._native_cli(case); self.assertEqual(first["next_action"],"DISPATCH_RETURNED_WORK")
                pending=self._native_cli(case); self.assertEqual(pending["next_action"],"OBSERVE_RETURN_DISPATCH")
                receipt={"schema":"CHIEF_NATIVE_RETURN_DISPATCH_RECEIPT_V1","kind":"test_pass_dispatch","observation_id":"dispatch-"+mode,"authority_kind":"native_coordinator_observation","native_root_id":"native-test","coordinator_task_id":"coordinator-1","report_id":"report-native-1","return_id":"return-native-1","action_id":pending["action_id"],"work_id":"work-new","package_id":"package-1","candidate_sha256":"a"*64,"project":case["package"]["project"],"source_task_id":"coordinator-1","target_task_id":"writer-1","current_task_observation_id":"task-observation-1","expected_head":case["head"],"status":"accepted","dispatch_tool":"native-observer","native_event_id":"event-"+mode}
                raw=(json.dumps(receipt,sort_keys=True)+"\n").encode(); case["native"].joinpath("dispatch.json").write_bytes(raw)
                done=self._native_cli(case,"--dispatch-report-id","report-native-1","--dispatch-action-id",pending["action_id"],"--dispatch-evidence-ref","native://dispatch.json","--dispatch-evidence-sha256",hashlib.sha256(raw).hexdigest()); self.assertEqual(done["next_action"],"NO_ACTION")
                self.assertEqual(self._native_cli(case)["next_action"],"NO_ACTION")

    def test_native_recovery_status_and_owner_holds_and_generic_ingest_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            for index,status in enumerate(("paused","archived","running")):
                case=self._native_recovery_case(Path(temporary)/str(index),status=status)
                self.assertNotEqual(self._native_cli(case)["next_action"],"DISPATCH_RETURNED_WORK")
            owner_case=self._native_recovery_case(Path(temporary)/"owner",owner="ghost-owner")
            self.assertEqual(self._native_cli(owner_case)["next_action"],"HOLD_OWNER_MISMATCH")
            candidate_case=self._native_recovery_case(Path(temporary)/"candidate",candidate="c"*64)
            self.assertNotEqual(self._native_cli(candidate_case)["next_action"],"DISPATCH_RETURNED_WORK")
            payload=Path(temporary)/"event.json"; payload.write_text("{}")
            result=subprocess.run([sys.executable,str(Path(delivery_ledger.__file__)),"--ledger",str(owner_case["ledger"]),"ingest","--event","RETURN_NATIVE_INTENT_PREPARED","--payload",str(payload)],text=True,capture_output=True)
            self.assertNotEqual(result.returncode,0); self.assertIn("require continuous-reconcile",result.stderr)
    def test_native_testing_delegation_rejects_one_field_forgery(self):
        delegation={"testing_chief_task_id":TESTING_REVIEWER_ID,"delegation_id":"d1","reviewer_task_id":"reviewer-1","writer_task_id":"writer-1","reviewer_registered":True,"risk":"medium","candidate_sha256":"a"*64,"scope":"local","delegation_evidence_ref":"native://d.json","delegation_receipt_sha256":"b"*64}
        observed={"schema":"CHIEF_TESTING_DELEGATION_EVIDENCE_V1","issuer_task_id":TESTING_REVIEWER_ID,"delegation_id":"d1","reviewer_task_id":"reviewer-1","writer_task_id":"writer-1","candidate_sha256":"a"*64,"scope":"local","risk":"medium","work_id":"work-new","package_id":"package-1","sensitive":False,"production":False,"global_upgrade":False,"disputed":False}
        loader=lambda *_: observed
        with tempfile.TemporaryDirectory() as temporary:
            project, native = Path(temporary) / "project", Path(temporary) / "native"
            project.mkdir(); native.mkdir()
            context = {"submitting_project": project, "native_observation_root": native}
            self.assertEqual(continuous_execution.validate_delegated_testing(delegation,native_observation_loader=loader,package={"work_id":"work-new","package_id":"package-1","candidate_sha256":"a"*64},**context)["delegation_id"],"d1")
            with self.assertRaises(continuous_execution.ContinuousExecutionError):
                continuous_execution.validate_delegated_testing({**delegation,"candidate_sha256":"c"*64},native_observation_loader=loader,package={"work_id":"work-new","package_id":"package-1","candidate_sha256":"c"*64},**context)
            observed["production"]=True
            with self.assertRaises(continuous_execution.ContinuousExecutionError):
                continuous_execution.validate_delegated_testing(delegation,native_observation_loader=loader,package={"work_id":"work-new","package_id":"package-1","candidate_sha256":"a"*64},**context)
    def test_retry_rejects_writer_surface_approval_observation(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "p"; state = project / ".chief-of-staff"; state.mkdir(parents=True)
            package = runtime_package(project)
            state.joinpath("project.json").write_text(json.dumps({"max_repair_cycles": 3, "execution_package_id": "package-1", "execution_work_id": "work-new"}))
            state.joinpath("project-plan.json").write_text(json.dumps({"execution_packages": [package]}))
            state.joinpath("task-registry.json").write_text(json.dumps({"tasks": [
                {"task_id":"writer-1","project_id":"project-1","status":"archived","execution_work_id":"work-new","execution_package_id":"package-1","execution_root_id":"root-1","execution_branch":"candidate-branch","write_surface":["repo://source"]},
                {"task_id":"reviewer-1","project_id":"project-1","status":"running","execution_reviewer_for":"work-new","write_surface":[]},
            ]}))
            state.joinpath("approval-queue.json").write_text(json.dumps({"requests":[{"request_id":"approval-1","status":"approved","decision_receipt_sha256":package["approval_receipt_sha256"],"decision_evidence_ref":package["approval_evidence_ref"]}]}))
            with self.assertRaises(retry_policy.RetryPolicyError):
                retry_policy.consume_repair_cycle(project,"c1","review-1","repair-1",reviewer_id="reviewer-1",progress_evidence=retained_progress(project,1),execution_package_id="package-1",execution_work_id="work-new",resource_measurement=retained_measurement(project,1))

    def test_missing_diagnosis_retained_bytes_cannot_continue(self):
        package = runtime_package(Path(tempfile.mkdtemp()))
        state = {"work_id":"work-new","package_id":"package-1","status":"running","owner_task_id":"writer-1","resource_units_used":1,
            "rounds":[{"round_id":"a","evidence":{"kind":"log_only"}},{"round_id":"b","evidence":{"kind":"log_only"}}],
            "independent_diagnosis":{"diagnosis_id":"d","reviewer_task_id":"reviewer-1","new_path":"x","evidence_ref":"repo://missing.json","round_ids":["a","b"],"work_id":"work-new","package_id":"package-1","candidate_sha256":"a"*64}}
        self.assertNotEqual(continuous_execution.reconcile_execution(state, package)["next_action"], "CONTINUE")
