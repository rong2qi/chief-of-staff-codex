import json
import hashlib
import base64
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import continuous_execution, retry_policy
from tests.private_authority_fixture import TESTING_REVIEWER_ID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import agent_os
import init_project


PACKAGE = {
    "schema": "CHIEF_EXECUTION_PACKAGE_V1",
    "package_id": "package-1",
    "approval_id": "approval-1",
    "approval_status": "approved",
    "approval_receipt_sha256": "c" * 64,
    "approval_evidence_ref": "repo://.chief-of-staff/evidence/approval.json",
    "work_id": "work-new",
    "project": {"project_id": "project-1", "root_id": "root-1", "branch": "candidate-branch"},
    "writer_task_id": "writer-1",
    "write_surface": ["repo://source"],
    "candidate_sha256": "a" * 64,
    "independent_reviewer_task_ids": ["reviewer-1"],
    "goal": "Produce a locally verified candidate",
    "endpoint": "local_delivered",
    "permissions": ["local_write", "local_commit"],
    "resource_limits": {"max_progress_cycles": 6, "max_resource_units": 10, "resource_unit": "test_minutes"},
    "acceptance": ["tests pass"],
    "stop_conditions": ["new_permission", "resource_limit", "protected_action"],
    "native_intake": {"root_id": "native-test", "coordinator_task_id": "coordinator-1"},
}


def evidence(number, kind="acceptance_gain", *, digest=None):
    return {
        "kind": kind, "evidence_id": f"e-{number}", "evidence_ref": f"repo://evidence-{number}.json",
        "evidence_sha256": digest or (format(number % 16, "x") * 64),
        "observation": {"before": "pending", "after": f"verified-{number}"},
    }


def write_retained_json(root, relative, value):
    path = Path(root) / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def runtime_package(root, native_root=None):
    package = dict(PACKAGE)
    native_root = Path(native_root or (Path(root).parent / "native-observations"))
    native_root.mkdir(parents=True, exist_ok=True)
    package["approval_evidence_ref"] = "native://approval.json"
    raw = (json.dumps({
        "schema": "CHIEF_EXECUTION_APPROVAL_EVIDENCE_V1", "kind": "execution_approval", "observation_id": "approval-1", "approval_id": "approval-1",
        "package_id": "package-1", "package_sha256": continuous_execution.package_digest(package),
        "decision": "approved", "observed_by": "operator-observer-1",
        "authority_kind": "native_coordinator_observation",
        "coordinator_task_id": "coordinator-1", "native_root_id": "native-test",
        "project": package["project"], "writer_task_id": "writer-1", "candidate_sha256": "a" * 64,
    }, sort_keys=True) + "\n").encode()
    (native_root / "approval.json").write_bytes(raw)
    return {**package, "approval_receipt_sha256": hashlib.sha256(raw).hexdigest()}


def round_artifact_hash(number):
    return hashlib.sha256(f"synthetic test artifact {number}".encode()).hexdigest()


def progress_payload(number, kind="acceptance_gain"):
    value = evidence(number, kind)
    return {
        "schema": "CHIEF_EXECUTION_PROGRESS_EVIDENCE_V1", "kind": value["kind"],
        "evidence_id": value["evidence_id"], "observation": value["observation"],
        "work_id": "work-new", "package_id": "package-1", "candidate_sha256": "a" * 64,
        "criterion_id": "tests-pass", "artifact_sha256": round_artifact_hash(number),
    }


def retained_progress(root, number, kind="acceptance_gain", *, digest=None):
    value = evidence(number, kind, digest=digest)
    receipt = write_retained_json(root, f".chief-of-staff/evidence/progress-{number}.json", progress_payload(number, kind))
    return {**value, "evidence_ref": f"repo://.chief-of-staff/evidence/progress-{number}.json", "evidence_sha256": receipt}


def retained_measurement(root, units_used=1):
    relative = f".chief-of-staff/evidence/measurement-{units_used}.json"
    receipt = write_retained_json(root, relative, {
        "schema": "CHIEF_EXECUTION_RESOURCE_MEASUREMENT_V1", "work_id": "work-new",
        "package_id": "package-1", "resource_unit": "test_minutes", "units_used": units_used,
    })
    return {"evidence_ref": "repo://" + relative, "evidence_sha256": receipt}


def stagnant_payload(number):
    return {"schema":"CHIEF_EXECUTION_STAGNANT_EVIDENCE_V1","repair_id":f"repair-{number}","work_id":"work-new","package_id":"package-1","candidate_sha256":"a"*64,"artifact_sha256":round_artifact_hash(number)}


def retained_review(native_root, number, reviewer="reviewer-1", candidate_id=None, outcome_kind="progress", diagnosis=None):
    value = {"schema":"CHIEF_EXECUTION_REVIEW_EVIDENCE_V1","kind":"repair_review","repair_id":f"repair-{number}","review_id":f"review-{number}","reviewer_task_id":reviewer,"work_id":"work-new","package_id":"package-1","candidate_sha256":"a"*64,"candidate_id":candidate_id or f"candidate-{number}","decision":"repair","coordinator_task_id":"coordinator-1"}
    outcome = stagnant_payload(number) if outcome_kind == "stagnant" else progress_payload(number)
    outcome_raw = (json.dumps(outcome, sort_keys=True)+"\n").encode()
    value["reviewed_artifact"] = {"candidate_id":value["candidate_id"], "sha256":round_artifact_hash(number), "outcome_ref":f"repo://.chief-of-staff/evidence/{outcome_kind}-{number}.json", "outcome_sha256":hashlib.sha256(outcome_raw).hexdigest()}
    if diagnosis is not None:
        value["diagnosis_used"] = diagnosis
    raw = (json.dumps(value, sort_keys=True) + "\n").encode(); path = Path(native_root) / f"review-{number}.json"; path.write_bytes(raw)
    return {"evidence_ref": "native://" + path.name, "evidence_sha256": hashlib.sha256(raw).hexdigest()}


def retained_stagnant(root, number):
    value=stagnant_payload(number)
    return {"evidence_ref":"repo://.chief-of-staff/evidence/stagnant-%s.json"%number,"evidence_sha256":write_retained_json(root,f".chief-of-staff/evidence/stagnant-{number}.json",value)}


def retained_diagnosis(native_root):
    value={"schema":"CHIEF_EXECUTION_DIAGNOSIS_EVIDENCE_V1","request_id":"diagnosis:repair-1:repair-2","round_ids":["repair-1","repair-2"],"work_id":"work-new","package_id":"package-1","candidate_sha256":"a"*64,"reviewer_task_id":"reviewer-1","new_path":"synthetic new path"}
    path_observation = {**value, "schema":"CHIEF_EXECUTION_NEW_PATH_EVIDENCE_V1", "coordinator_task_id":"coordinator-1", "native_root_id":"native-test", "observation":{"before":"fixture fails with old path", "after":"fixture verifies different path"}, "reproduction":["synthetic disposable fixture observation; not a live Testing verdict"]}
    value["new_path_evidence_ref"] = "native://diagnosis-path.json"
    value["new_path_evidence_sha256"] = write_retained_json(native_root, "diagnosis-path.json", path_observation)
    raw=(json.dumps(value,sort_keys=True)+"\n").encode(); path=Path(native_root)/"diagnosis.json";path.write_bytes(raw)
    return {"evidence_ref":"native://diagnosis.json","evidence_sha256":hashlib.sha256(raw).hexdigest()}


def native_intake(package):
    return {"root_id":package["native_intake"]["root_id"],"coordinator_task_id":package["native_intake"]["coordinator_task_id"],"approval_sha256":package["approval_receipt_sha256"],"work_id":package["work_id"],"package_id":package["package_id"],"package_digest":continuous_execution.package_digest(package),"project":package["project"],"writer_task_id":package["writer_task_id"],"candidate_sha256":package["candidate_sha256"]}


def state(**changes):
    value = {
        "work_id": "work-new",
        "status": "running",
        "owner_task_id": "writer-1",
        "package_id": "package-1",
        "rounds": [],
        "dispatched_return_ids": [],
        "resource_units_used": 0,
    }
    value.update(changes)
    return value


class ContinuousExecutionTests(unittest.TestCase):
    def test_retry_does_not_pair_nonconsecutive_stagnant_rounds(self):
        with tempfile.TemporaryDirectory() as temporary:
            project=Path(temporary)/"project"; state=project/".chief-of-staff"; state.mkdir(parents=True); native=Path(temporary)/"native"; package=runtime_package(project,native)
            state.joinpath("project.json").write_text(json.dumps({"max_repair_cycles":3,"execution_package_id":"package-1","execution_work_id":"work-new"})); state.joinpath("project-plan.json").write_text(json.dumps({"execution_packages":[package]})); state.joinpath("task-registry.json").write_text(json.dumps({"tasks":[{"task_id":"writer-1","project_id":"project-1","status":"technical_blocked","write_surface":["repo://source"],"execution_work_id":"work-new","execution_package_id":"package-1","execution_root_id":"root-1","execution_branch":"candidate-branch"},{"task_id":"reviewer-1","project_id":"project-1","status":"running","write_surface":[],"execution_reviewer_for":"work-new"}]})); state.joinpath("approval-queue.json").write_text(json.dumps({"requests":[{"request_id":"approval-1","status":"approved","decision_receipt_sha256":package["approval_receipt_sha256"],"decision_evidence_ref":package["approval_evidence_ref"]}]})); common=dict(reviewer_id="reviewer-1",execution_package_id="package-1",execution_work_id="work-new",native_observation_root=native,native_intake=native_intake(package))
            retry_policy.consume_repair_cycle(project,"c1","review-1","repair-1",stagnant_evidence=retained_stagnant(project,1),resource_measurement=retained_measurement(project,1),review_evidence=retained_review(native,1,candidate_id="c1",outcome_kind="stagnant"),**common)
            retry_policy.consume_repair_cycle(project,"c2","review-2","repair-2",progress_evidence=retained_progress(project,2),resource_measurement=retained_measurement(project,2),review_evidence=retained_review(native,2,candidate_id="c2"),**common)
            receipt=retry_policy.consume_repair_cycle(project,"c3","review-3","repair-3",stagnant_evidence=retained_stagnant(project,3),resource_measurement=retained_measurement(project,3),review_evidence=retained_review(native,3,candidate_id="c3",outcome_kind="stagnant"),**common)
            self.assertEqual(receipt.get("diagnosis_requests",[]),[])
    def test_retry_rejects_progress_after_two_stagnant_without_consumed_diagnosis(self):
        with tempfile.TemporaryDirectory() as temporary:
            project=Path(temporary)/"project"; state=project/".chief-of-staff"; state.mkdir(parents=True); native=Path(temporary)/"native"; package=runtime_package(project,native)
            state.joinpath("project.json").write_text(json.dumps({"max_repair_cycles":3,"execution_package_id":"package-1","execution_work_id":"work-new"})); state.joinpath("project-plan.json").write_text(json.dumps({"execution_packages":[package]})); state.joinpath("task-registry.json").write_text(json.dumps({"tasks":[{"task_id":"writer-1","project_id":"project-1","status":"technical_blocked","write_surface":["repo://source"],"execution_work_id":"work-new","execution_package_id":"package-1","execution_root_id":"root-1","execution_branch":"candidate-branch"},{"task_id":"reviewer-1","project_id":"project-1","status":"running","write_surface":[],"execution_reviewer_for":"work-new"}]})); state.joinpath("approval-queue.json").write_text(json.dumps({"requests":[{"request_id":"approval-1","status":"approved","decision_receipt_sha256":package["approval_receipt_sha256"],"decision_evidence_ref":package["approval_evidence_ref"]}]})); common=dict(reviewer_id="reviewer-1",execution_package_id="package-1",execution_work_id="work-new",native_observation_root=native,native_intake=native_intake(package))
            for n in (1,2): retry_policy.consume_repair_cycle(project,f"c{n}",f"review-{n}",f"repair-{n}",resource_measurement=retained_measurement(project,n),review_evidence=retained_review(native,n,candidate_id=f"c{n}",outcome_kind="stagnant"),stagnant_evidence=retained_stagnant(project,n),**common)
            before=state.joinpath("repair-budget.json").read_bytes()
            with self.assertRaises(retry_policy.RetryPolicyError): retry_policy.consume_repair_cycle(project,"c3","review-3","repair-3",progress_evidence=retained_progress(project,3),resource_measurement=retained_measurement(project,3),review_evidence=retained_review(native,3,candidate_id="c3"),**common)
            self.assertEqual(state.joinpath("repair-budget.json").read_bytes(),before)
    def test_native_retry_rejects_native_parent_replaced_before_open(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); ancestor=root/"ancestor"; project=ancestor/"project"; state=project/".chief-of-staff"; state.mkdir(parents=True); native=ancestor/"native"; package=runtime_package(project,native)
            state.joinpath("project.json").write_text(json.dumps({"max_repair_cycles":3,"execution_package_id":"package-1","execution_work_id":"work-new"})); state.joinpath("project-plan.json").write_text(json.dumps({"execution_packages":[package]})); state.joinpath("task-registry.json").write_text(json.dumps({"tasks":[{"task_id":"writer-1","project_id":"project-1","status":"technical_blocked","write_surface":["repo://source"],"execution_work_id":"work-new","execution_package_id":"package-1","execution_root_id":"root-1","execution_branch":"candidate-branch"},{"task_id":"reviewer-1","project_id":"project-1","status":"running","write_surface":[],"execution_reviewer_for":"work-new"}]})); state.joinpath("approval-queue.json").write_text(json.dumps({"requests":[{"request_id":"approval-1","status":"approved","decision_receipt_sha256":package["approval_receipt_sha256"],"decision_evidence_ref":package["approval_evidence_ref"]}]})); original=os.open; descriptors=[]; replaced=[False]
            def at_open(path,flags,*args,**kwargs):
                if os.fspath(path)=="ancestor" and not replaced[0]:
                    replaced[0]=True; ancestor.rename(root/"retained"); (ancestor/"native").mkdir(parents=True); (ancestor/"native"/"sentinel").write_text("x")
                fd=original(path,flags,*args,**kwargs); descriptors.append(fd); return fd
            from unittest.mock import patch
            with patch.object(retry_policy.os,"open",side_effect=at_open) as intercepted, patch.object(retry_policy.os,"supports_dir_fd",os.supports_dir_fd|{intercepted}):
                with self.assertRaises(retry_policy.RetryPolicyError): retry_policy.consume_repair_cycle(project,"c1","review-1","repair-1",reviewer_id="reviewer-1",progress_evidence=retained_progress(project,1),resource_measurement=retained_measurement(project,1),review_evidence=retained_review(native,1,candidate_id="c1"),execution_package_id="package-1",execution_work_id="work-new",native_observation_root=native,native_intake=native_intake(package))
            self.assertTrue(replaced[0]); self.assertFalse((project/".chief-of-staff/repair-budget.json").exists()); self.assertEqual((ancestor/"native"/"sentinel").read_text(),"x")
            for fd in descriptors:
                with self.assertRaises(OSError): os.fstat(fd)
    def test_native_retry_keeps_open_root_after_ancestor_rename(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary); ancestor=root/"ancestor"; project=ancestor/"project"; state=project/".chief-of-staff"; state.mkdir(parents=True); native=ancestor/"native"; package=runtime_package(project,native)
            state.joinpath("project.json").write_text(json.dumps({"max_repair_cycles":3,"execution_package_id":"package-1","execution_work_id":"work-new"})); state.joinpath("project-plan.json").write_text(json.dumps({"execution_packages":[package]})); state.joinpath("task-registry.json").write_text(json.dumps({"tasks":[{"task_id":"writer-1","project_id":"project-1","status":"technical_blocked","write_surface":["repo://source"],"execution_work_id":"work-new","execution_package_id":"package-1","execution_root_id":"root-1","execution_branch":"candidate-branch"},{"task_id":"reviewer-1","project_id":"project-1","status":"running","write_surface":[],"execution_reviewer_for":"work-new"}]})); state.joinpath("approval-queue.json").write_text(json.dumps({"requests":[{"request_id":"approval-1","status":"approved","decision_receipt_sha256":package["approval_receipt_sha256"],"decision_evidence_ref":package["approval_evidence_ref"]}]})); captured=[]; opened=retry_policy._open_project_directory; original=retry_policy._read_retained_json
            def open_capture(path):
                fd=opened(path); captured.append(fd) if Path(path)==native else None; return fd
            renamed=[False]
            def read_wrap(fd,ref,digest,label):
                result=original(fd,ref,digest,label)
                if ref=="repo://approval.json" and not renamed[0]:
                    renamed[0]=True; ancestor.rename(root/"retained"); (root/"ancestor"/"native").mkdir(parents=True); (root/"ancestor"/"native"/"sentinel").write_text("x")
                return result
            from unittest.mock import patch
            with patch.object(retry_policy,"_open_project_directory",side_effect=open_capture), patch.object(retry_policy,"_read_retained_json",side_effect=read_wrap):
                result=retry_policy.consume_repair_cycle(project,"c1","review-1","repair-1",reviewer_id="reviewer-1",progress_evidence=retained_progress(project,1),resource_measurement=retained_measurement(project,1),review_evidence=retained_review(native,1,candidate_id="c1"),execution_package_id="package-1",execution_work_id="work-new",native_observation_root=native,native_intake=native_intake(package))
            self.assertEqual(len(result["cycles"]),1); self.assertEqual((root/"ancestor"/"native"/"sentinel").read_text(),"x")
            for fd in captured:
                with self.assertRaises(OSError): os.fstat(fd)
    def test_retry_rejects_drifted_historical_review_and_measurement_fields(self):
        fields=[("review-1.json","schema","bad"),("review-1.json","reviewer_task_id","bad"),("review-1.json","package_id","bad"),("review-1.json","decision","bad"),("review-1.json","coordinator_task_id","bad"),("measurement-1.json","resource_unit","bad")]
        for index,(filename,key,value) in enumerate(fields):
            with tempfile.TemporaryDirectory() as temporary:
                project=Path(temporary)/"project"; state=project/".chief-of-staff"; state.mkdir(parents=True); native=Path(temporary)/"native"; package=runtime_package(project,native)
                state.joinpath("project.json").write_text(json.dumps({"max_repair_cycles":3,"execution_package_id":"package-1","execution_work_id":"work-new"})); state.joinpath("project-plan.json").write_text(json.dumps({"execution_packages":[package]})); state.joinpath("task-registry.json").write_text(json.dumps({"tasks":[{"task_id":"writer-1","project_id":"project-1","status":"technical_blocked","write_surface":["repo://source"],"execution_work_id":"work-new","execution_package_id":"package-1","execution_root_id":"root-1","execution_branch":"candidate-branch"},{"task_id":"reviewer-1","project_id":"project-1","status":"running","write_surface":[],"execution_reviewer_for":"work-new"}]})); state.joinpath("approval-queue.json").write_text(json.dumps({"requests":[{"request_id":"approval-1","status":"approved","decision_receipt_sha256":package["approval_receipt_sha256"],"decision_evidence_ref":package["approval_evidence_ref"]}]})); common=dict(reviewer_id="reviewer-1",execution_package_id="package-1",execution_work_id="work-new",native_observation_root=native,native_intake=native_intake(package))
                retry_policy.consume_repair_cycle(project,"c1","review-1","repair-1",progress_evidence=retained_progress(project,1),resource_measurement=retained_measurement(project,1),review_evidence=retained_review(native,1,candidate_id="c1"),**common)
                location=(native if filename.startswith("review") else project/".chief-of-staff/evidence")/filename; data=json.loads(location.read_text()); data[key]=value; raw=(json.dumps(data,sort_keys=True)+"\n").encode(); location.write_bytes(raw); digest=hashlib.sha256(raw).hexdigest(); budget=json.loads(state.joinpath("repair-budget.json").read_text()); record=budget["cycles"][0]; (record["review_evidence"] if filename.startswith("review") else record["resource_measurement"])["evidence_sha256"]=digest; state.joinpath("repair-budget.json").write_text(json.dumps(budget)); before=state.joinpath("repair-budget.json").read_bytes()
                with self.assertRaises(retry_policy.RetryPolicyError): retry_policy.consume_repair_cycle(project,"c2","review-2","repair-2",progress_evidence=retained_progress(project,2),resource_measurement=retained_measurement(project,2),review_evidence=retained_review(native,2,candidate_id="c2"),**common)
                self.assertEqual(state.joinpath("repair-budget.json").read_bytes(),before)
    def test_retry_rejects_reused_native_review_event_id(self):
        with tempfile.TemporaryDirectory() as temporary:
            project=Path(temporary)/"project"; state_dir=project/".chief-of-staff"; state_dir.mkdir(parents=True); native=Path(temporary)/"native"; package=runtime_package(project,native)
            state_dir.joinpath("project.json").write_text(json.dumps({"max_repair_cycles":3,"execution_package_id":"package-1","execution_work_id":"work-new"}))
            state_dir.joinpath("project-plan.json").write_text(json.dumps({"execution_packages":[package]}))
            state_dir.joinpath("task-registry.json").write_text(json.dumps({"tasks":[{"task_id":"writer-1","project_id":"project-1","status":"technical_blocked","write_surface":["repo://source"],"execution_work_id":"work-new","execution_package_id":"package-1","execution_root_id":"root-1","execution_branch":"candidate-branch"},{"task_id":"reviewer-1","project_id":"project-1","status":"running","write_surface":[],"execution_reviewer_for":"work-new"}]}))
            state_dir.joinpath("approval-queue.json").write_text(json.dumps({"requests":[{"request_id":"approval-1","status":"approved","decision_receipt_sha256":package["approval_receipt_sha256"],"decision_evidence_ref":package["approval_evidence_ref"]}]}))
            common=dict(reviewer_id="reviewer-1",execution_package_id="package-1",execution_work_id="work-new",native_observation_root=native,native_intake=native_intake(package))
            retry_policy.consume_repair_cycle(project,"candidate-1","review-1","repair-1",progress_evidence=retained_progress(project,1),resource_measurement=retained_measurement(project,1),review_evidence=retained_review(native,1),**common)
            raw=json.loads((native/"review-2.json").read_text()) if (native/"review-2.json").exists() else {"schema":"CHIEF_EXECUTION_REVIEW_EVIDENCE_V1","kind":"repair_review","repair_id":"repair-2","review_id":"review-1","reviewer_task_id":"reviewer-1","work_id":"work-new","package_id":"package-1","candidate_sha256":"a"*64,"candidate_id":"candidate-2","decision":"repair","coordinator_task_id":"coordinator-1"}
            raw["repair_id"]="repair-2"; raw["review_id"]="review-1"; review_raw=(json.dumps(raw,sort_keys=True)+"\n").encode(); (native/"review-2.json").write_bytes(review_raw); reused={"evidence_ref":"native://review-2.json","evidence_sha256":hashlib.sha256(review_raw).hexdigest()}
            before=(state_dir/"repair-budget.json").read_bytes()
            with self.assertRaises(retry_policy.RetryPolicyError): retry_policy.consume_repair_cycle(project,"candidate-2","review-1","repair-2",progress_evidence=retained_progress(project,2),resource_measurement=retained_measurement(project,2),review_evidence=reused,**common)
            self.assertEqual((state_dir/"repair-budget.json").read_bytes(),before)
    def test_package_is_exact_and_does_not_imply_protected_actions(self):
        checked = continuous_execution.validate_execution_package(PACKAGE)
        self.assertEqual(checked["package_id"], "package-1")
        with self.assertRaisesRegex(continuous_execution.ContinuousExecutionError, "protected"):
            continuous_execution.validate_execution_package({**PACKAGE, "permissions": ["local_write", "remote_push"]})
        with self.assertRaises(continuous_execution.ContinuousExecutionError):
            continuous_execution.validate_execution_package({**PACKAGE, "resource_limits": {"max_progress_cycles": 6}})

    def test_real_progress_can_exceed_three_cycles_but_duplicate_log_cannot(self):
        rounds = [
            {"round_id": f"round-{n}", "kind": "repair", "evidence": evidence(n)}
            for n in range(1, 5)
        ]
        result = continuous_execution.reconcile_execution(state(rounds=rounds), PACKAGE)
        self.assertEqual(result["next_action"], "CONTINUE")
        duplicate = continuous_execution.reconcile_execution(state(rounds=rounds + [
            {"round_id": "round-5", "kind": "repair", "evidence": evidence(5, digest="4" * 64)},
            {"round_id": "round-6", "kind": "repair", "evidence": evidence(6, "log_only")},
        ]), PACKAGE)
        self.assertEqual(duplicate["next_action"], "REQUEST_INDEPENDENT_DIAGNOSIS")

    def test_two_stagnant_rounds_need_one_diagnosis_and_an_evidenced_new_path(self):
        stalled = state(rounds=[
            {"round_id": "round-1", "kind": "repair", "evidence": evidence(1, "log_only")},
            {"round_id": "round-2", "kind": "repair", "evidence": evidence(2, "log_only")},
        ])
        first = continuous_execution.reconcile_execution(stalled, PACKAGE)
        self.assertEqual(first["next_action"], "REQUEST_INDEPENDENT_DIAGNOSIS")
        repeated = continuous_execution.reconcile_execution({**stalled, "independent_diagnosis_requested": {"diagnosis_request_id": "diagnosis-request-1", "round_ids": ["round-1", "round-2"]}}, PACKAGE)
        self.assertEqual(repeated["next_action"], "AWAIT_DIAGNOSIS")
        diagnosis = {"diagnosis_id": "diagnosis-1", "reviewer_task_id": "reviewer-1", "new_path": "use retained receipt", "evidence_ref": "repo://diagnosis.json", "round_ids": ["round-1", "round-2"], "work_id": "work-new", "package_id": "package-1", "candidate_sha256": "a" * 64, "retained_verified": True}
        continued = continuous_execution.reconcile_execution({**stalled, "independent_diagnosis": diagnosis}, PACKAGE)
        self.assertEqual(continued["next_action"], "HOLD_DIAGNOSIS_REQUIRES_RETRY_RECEIPT")
        later_stagnation = {**stalled, "rounds": stalled["rounds"] + [
            {"round_id": "round-3", "kind": "repair", "evidence": evidence(3, "log_only")},
            {"round_id": "round-4", "kind": "repair", "evidence": evidence(4, "log_only")},
        ], "independent_diagnosis": diagnosis}
        self.assertEqual(continuous_execution.reconcile_execution(later_stagnation, PACKAGE)["next_action"], "HOLD_DIAGNOSIS_EVIDENCE_INSUFFICIENT")

    def test_resource_limits_and_legacy_stops_remain_stops(self):
        self.assertEqual(continuous_execution.reconcile_execution(state(resource_units_used=10), PACKAGE)["next_action"], "STOP_RESOURCE_LIMIT")
        for reason in ("one_shot", "stopped", "denied"):
            self.assertEqual(continuous_execution.reconcile_execution(state(legacy_stop=reason), PACKAGE)["next_action"], "HOLD_LEGACY_STOP")

    def test_old_completion_cannot_close_new_work_and_return_dispatch_is_once(self):
        old = {"work_id": "work-old", "kind": "completion", "return_id": "return-old"}
        result = continuous_execution.reconcile_execution(state(returns=[old]), PACKAGE)
        self.assertEqual(result["status"], "running")
        returned = {"work_id": "work-new", "package_id": "package-1", "return_id": "return-1", "kind": "test_pass", "candidate_sha256": "a" * 64, "scope": "local"}
        once = continuous_execution.reconcile_execution(state(returns=[returned], expected_candidate_sha256="a" * 64), PACKAGE)
        self.assertEqual(once["next_action"], "CONTINUE_RETURNED_WORK")
        again = continuous_execution.reconcile_execution(state(returns=[returned], dispatched_return_ids=["return-1"], expected_candidate_sha256="a" * 64), PACKAGE)
        self.assertEqual(again["next_action"], "NO_ACTION")
        self.assertEqual(continuous_execution.reconcile_execution(state(returns=[{**returned, "candidate_sha256": "b" * 64}], expected_candidate_sha256="a" * 64), PACKAGE)["next_action"], "HOLD_CANDIDATE_MISMATCH")
        self.assertEqual(continuous_execution.reconcile_execution(state(returns=[]), PACKAGE)["next_action"], "OBSERVATION_GAP")

    def test_return_requires_active_owner_and_never_reactivates_paused_or_archived(self):
        returned = {"work_id": "work-new", "package_id": "package-1", "return_id": "return-1", "kind": "approval", "scope": "local"}
        for status in ("paused", "archived"):
            self.assertEqual(continuous_execution.reconcile_execution(state(status=status, returns=[returned]), PACKAGE)["next_action"], "HOLD_INACTIVE_TARGET")
        self.assertEqual(continuous_execution.reconcile_execution(state(owner_task_id="other", returns=[returned]), PACKAGE)["next_action"], "HOLD_OWNER_MISMATCH")

    def test_delegated_testing_is_only_preregistered_low_medium_exact_scope(self):
        delegation = {
            "testing_chief_task_id": TESTING_REVIEWER_ID,
            "delegation_id": "delegation-1",
            "reviewer_task_id": "reviewer-1",
            "writer_task_id": "writer-1",
            "reviewer_registered": True,
            "risk": "medium",
            "candidate_sha256": "b" * 64,
            "scope": "local candidate",
            "delegation_evidence_ref": "repo://delegation.json",
            "delegation_receipt_sha256": "d" * 64,
        }
        with tempfile.TemporaryDirectory() as temporary:
            project, native = Path(temporary) / "project", Path(temporary) / "native"
            project.mkdir(); native.mkdir()
            context = {"submitting_project": project, "native_observation_root": native}
            self.assertEqual(continuous_execution.validate_delegated_testing(delegation, **context)["reviewer_task_id"], "reviewer-1")
            with self.assertRaises(continuous_execution.ContinuousExecutionError):
                continuous_execution.validate_delegated_testing({**delegation, "risk": "high"}, **context)
            with self.assertRaises(continuous_execution.ContinuousExecutionError):
                continuous_execution.validate_delegated_testing({**delegation, "global_upgrade": True}, **context)

    def test_existing_retry_budget_consumer_allows_fourth_only_with_retained_real_progress(self):
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary) / "project"
            state_dir = project / ".chief-of-staff"
            state_dir.mkdir(parents=True)
            native_root = Path(temporary) / "native-observations"
            package = runtime_package(project, native_root)
            (state_dir / "project.json").write_text(json.dumps({
                "max_repair_cycles": 3,
                "execution_package_id": "package-1",
                "execution_work_id": "work-new",
            }))
            (state_dir / "project-plan.json").write_text(json.dumps({"execution_packages": [package]}))
            (state_dir / "task-registry.json").write_text(json.dumps({"tasks": [{"task_id": "writer-1", "project_id": "project-1", "status": "running", "write_surface": ["repo://source"], "execution_work_id": "work-new", "execution_package_id": "package-1", "execution_root_id": "root-1", "execution_branch": "candidate-branch"}, {"task_id": "reviewer-1", "project_id": "project-1", "status": "running", "write_surface": [], "execution_reviewer_for": "work-new"}]}))
            (state_dir / "approval-queue.json").write_text(json.dumps({"requests": [{"request_id": "approval-1", "status": "approved", "decision_receipt_sha256": package["approval_receipt_sha256"], "decision_evidence_ref": package["approval_evidence_ref"]}]}))
            for number in range(1, 5):
                receipt = retry_policy.consume_repair_cycle(
                    project, f"candidate-{number}", f"review-{number}", f"repair-{number}", reviewer_id="reviewer-1",
                    progress_evidence=retained_progress(project, number),
                    execution_package_id="package-1", execution_work_id="work-new",
                    resource_measurement=retained_measurement(project, number),
                    native_observation_root=native_root,
                    review_evidence=retained_review(native_root, number, candidate_id=f"candidate-{number}"),
                    native_intake=native_intake(package),
                )
            self.assertEqual(len(receipt["cycles"]), 4)
            self.assertIn("progress_evidence", receipt["cycles"][-1])
            with self.assertRaisesRegex(retry_policy.RetryPolicyError, "exactly one progress or stagnant"):
                retry_policy.consume_repair_cycle(project, "candidate-5", "review-5", "repair-5", reviewer_id="reviewer-1", execution_package_id="package-1", execution_work_id="work-new", resource_measurement=retained_measurement(project, 5), native_observation_root=native_root, review_evidence=retained_review(native_root, 5), native_intake=native_intake(package))

    def test_retry_journal_persists_one_stagnant_pair_and_consumes_exact_native_diagnosis(self):
        with tempfile.TemporaryDirectory() as temporary:
            project=Path(temporary)/"project"; state=project/".chief-of-staff"; state.mkdir(parents=True); native=Path(temporary)/"native"; package=runtime_package(project,native)
            state.joinpath("project.json").write_text(json.dumps({"max_repair_cycles":3,"execution_package_id":"package-1"}))
            state.joinpath("project-plan.json").write_text(json.dumps({"execution_packages":[package]}))
            state.joinpath("task-registry.json").write_text(json.dumps({"tasks":[{"task_id":"writer-1","project_id":"project-1","status":"running","execution_work_id":"work-new","execution_package_id":"package-1","execution_root_id":"root-1","execution_branch":"candidate-branch","write_surface":["repo://source"]},{"task_id":"reviewer-1","project_id":"project-1","status":"running","execution_reviewer_for":"work-new","write_surface":[]}]}))
            state.joinpath("approval-queue.json").write_text(json.dumps({"requests":[{"request_id":"approval-1","status":"approved","decision_receipt_sha256":package["approval_receipt_sha256"],"decision_evidence_ref":package["approval_evidence_ref"]}]}))
            common=dict(execution_package_id="package-1",execution_work_id="work-new",native_observation_root=native,reviewer_id="reviewer-1",native_intake=native_intake(package))
            retry_policy.consume_repair_cycle(project,"c1","review-1","repair-1",resource_measurement=retained_measurement(project,1),review_evidence=retained_review(native,1,candidate_id="c1",outcome_kind="stagnant"),stagnant_evidence=retained_stagnant(project,1),**common)
            command=[sys.executable,"-B",str(ROOT/"scripts"/"retry_policy.py"),"--project",str(project),"consume","--candidate-id","c2","--review-id","review-2","--repair-id","repair-2","--reviewer-id","reviewer-1","--execution-package-id","package-1","--execution-work-id","work-new","--native-observation-root",str(native),"--native-intake-json",json.dumps(native_intake(package)),"--resource-measurement-json",json.dumps(retained_measurement(project,2)),"--review-evidence-json",json.dumps(retained_review(native,2,candidate_id="c2",outcome_kind="stagnant")),"--stagnant-evidence-json",json.dumps(retained_stagnant(project,2)),"--diagnosis-evidence-json",json.dumps(retained_diagnosis(native))]
            without_diagnosis=[value for value in command if value not in {"--diagnosis-evidence-json",json.dumps(retained_diagnosis(native))}]
            waiting=subprocess.run(without_diagnosis,text=True,capture_output=True); self.assertEqual(waiting.returncode,0,waiting.stderr); self.assertFalse(json.loads(waiting.stdout)["diagnosis_requests"][0]["consumed"])
            ran=subprocess.run(command,text=True,capture_output=True); self.assertEqual(ran.returncode,0,ran.stderr); receipt=json.loads(ran.stdout)
            missing=[item for item in command if item not in {"--native-intake-json",json.dumps(native_intake(package))}]
            rejected=subprocess.run(missing,text=True,capture_output=True); self.assertNotEqual(rejected.returncode,0)
            self.assertEqual(len(receipt["diagnosis_requests"]),1); self.assertTrue(receipt["diagnosis_requests"][0]["consumed"])
            replay=retry_policy.consume_repair_cycle(project,"c2","review-2","repair-2",resource_measurement=retained_measurement(project,2),review_evidence=retained_review(native,2,candidate_id="c2",outcome_kind="stagnant"),stagnant_evidence=retained_stagnant(project,2),diagnosis_evidence=retained_diagnosis(native),**common)
            self.assertEqual(replay, receipt); self.assertEqual(len(replay["cycles"]),2)
            wrong = retained_diagnosis(native)
            raw = json.loads((native / "diagnosis.json").read_text()); raw["work_id"] = "other-work"; bad = (json.dumps(raw, sort_keys=True)+"\n").encode(); (native / "diagnosis.json").write_bytes(bad); wrong["evidence_sha256"] = hashlib.sha256(bad).hexdigest()
            with self.assertRaises(retry_policy.RetryPolicyError):
                retry_policy.consume_repair_cycle(project,"c3","review-3","repair-3",resource_measurement=retained_measurement(project,3),review_evidence=retained_review(native,3,candidate_id="c3",outcome_kind="stagnant"),stagnant_evidence=retained_stagnant(project,3),diagnosis_evidence=wrong,**common)

    def test_package_records_bind_existing_plan_registry_and_approval_queue(self):
        plan = {"execution_packages": [PACKAGE]}
        registry = {"tasks": [{
            "task_id": "writer-1", "project_id": "project-1",
            "execution_work_id": "work-new", "execution_package_id": "package-1", "write_surface": ["repo://source"], "status": "running",
        }, {"task_id": "reviewer-1", "project_id": "project-1", "write_surface": [], "execution_reviewer_for": "work-new"}]}
        registry["tasks"][0].update({"execution_root_id": "root-1", "execution_branch": "candidate-branch"})
        approvals = {"requests": [{"request_id": "approval-1", "status": "approved", "decision_receipt_sha256": "c" * 64, "decision_evidence_ref": PACKAGE["approval_evidence_ref"]}]}
        continuous_execution.validate_execution_records(plan, registry, approvals)
        with self.assertRaisesRegex(continuous_execution.ContinuousExecutionError, "approved queue"):
            continuous_execution.validate_execution_records(plan, registry, {"requests": [{"request_id": "approval-1", "status": "approved"}]})
        with self.assertRaisesRegex(continuous_execution.ContinuousExecutionError, "writer_task_id"):
            continuous_execution.validate_execution_records(plan, {"tasks": [{**registry["tasks"][0], "task_id": "other"}]}, approvals)

    def _initializer_fixture(self, target, native_root):
        self.assertEqual(init_project.initialize(target, "Example"), 0)
        package = runtime_package(target, native_root)
        project_json_path = target / ".chief-of-staff" / "project.json"
        project_json = json.loads(project_json_path.read_text())
        project_json["execution_native_observation_root"] = str(native_root)
        project_json_path.write_text(json.dumps(project_json))
        plan_path = target / ".chief-of-staff" / "project-plan.json"
        registry_path = target / ".chief-of-staff" / "task-registry.json"
        approvals_path = target / ".chief-of-staff" / "approval-queue.json"
        plan = json.loads(plan_path.read_text())
        registry = json.loads(registry_path.read_text())
        approvals = json.loads(approvals_path.read_text())
        plan["execution_packages"] = [package]
        registry["tasks"] = [{
            "task_id": "writer-1", "host_id": None, "title": "writer", "role": "Role",
            "objective": "Complete approved local work", "status": "running",
            "work_class": "coordination_only", "write_surface": ["repo://source"],
            "depends_on": [], "last_cursor": None, "result_summary": None,
            "parent_task_id": None, "phase_id": None, "management_depth": 2,
            "project_id": "project-1", "coordination_with": [],
            "execution_work_id": "work-new", "execution_package_id": "package-1",
            "execution_root_id": "root-1", "execution_branch": "candidate-branch",
        }, {
            "task_id": "reviewer-1", "host_id": None, "title": "reviewer", "role": "Reviewer",
            "objective": "Independently diagnose", "status": "running", "work_class": "coordination_only",
            "write_surface": [], "depends_on": [], "last_cursor": None, "result_summary": None,
            "parent_task_id": None, "phase_id": None, "management_depth": 2, "project_id": "project-1",
            "coordination_with": [], "execution_reviewer_for": "work-new",
        }]
        approvals["requests"] = [{
            "request_id": "approval-1", "request_kind": "report_review", "task_id": "writer-1",
            "host_id": None, "task_title": "writer", "report_type": "progress",
            "submitted_at": "2026-09-07T00:00:00Z", "summary": "approved package",
            "requested_decision": "approve", "status": "approved",
            "decided_at": "2026-09-07T00:01:00Z", "decision_note": "approved",
            "decision_receipt_sha256": package["approval_receipt_sha256"], "decision_evidence_ref": package["approval_evidence_ref"],
        }]
        plan_path.write_text(json.dumps(plan))
        registry_path.write_text(json.dumps(registry))
        approvals_path.write_text(json.dumps(approvals))

    def test_initializer_validates_opt_in_records_without_changing_legacy_projects(self):
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "project"
            self._initializer_fixture(target, target.parent / "native-observations")
            self.assertFalse(any("continuous execution records" in error for error in init_project.validate(target)))
            registry_path = target / ".chief-of-staff/task-registry.json"
            registry = json.loads(registry_path.read_text())
            registry["tasks"][0]["execution_package_id"] = "wrong-package"
            registry_path.write_text(json.dumps(registry))
            self.assertTrue(any("continuous execution records" in error for error in init_project.validate(target)))

    def test_initializer_rejects_native_child_and_parent_containment(self):
        for variant in ("child", "parent", "same"):
            with self.subTest(variant=variant), tempfile.TemporaryDirectory() as temporary:
                target = Path(temporary) / "project"
                native = {"child":target/"native", "parent":target.parent, "same":target}[variant]
                self._initializer_fixture(target, native)
                before = {p.relative_to(target).as_posix():p.read_bytes() for p in target.rglob("*") if p.is_file()}
                errors = init_project.validate(target)
                self.assertTrue(any("continuous execution records" in error for error in errors), errors)
                self.assertEqual(before, {p.relative_to(target).as_posix():p.read_bytes() for p in target.rglob("*") if p.is_file()})

    def test_initializer_retains_native_identity_after_checked_directory_replacement(self):
        from importlib import import_module
        from unittest.mock import patch
        native_policy = import_module("retry_policy")
        for replacement in ("directory", "symlink"):
            with self.subTest(replacement=replacement), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); target = root/"project"; native = root/"native"
                self._initializer_fixture(target, native)
                self.assertFalse(any("continuous execution records" in error for error in init_project.validate(target)))
                outside = root/"outside"; outside.mkdir(); (outside/"approval.json").write_text("outside sentinel")
                opened = native_policy._open_project_directory; captured = []; identities = []
                def checked_open(path):
                    fd = opened(path)
                    if Path(path) == native and not captured:
                        captured.append(fd); identities.append((os.fstat(fd).st_dev, os.fstat(fd).st_ino))
                        native.rename(root/"retained-native")
                        if replacement == "symlink":
                            native.symlink_to(outside, target_is_directory=True)
                        else:
                            native.mkdir(); (native/"approval.json").write_text("replacement sentinel")
                    return fd
                reads = []; original_read = native_policy._read_retained_json
                def observe_read(fd, ref, digest, label):
                    if ref == "repo://approval.json":
                        reads.append((os.fstat(fd).st_dev, os.fstat(fd).st_ino))
                    return original_read(fd, ref, digest, label)
                with patch.object(native_policy, "_open_project_directory", side_effect=checked_open), patch.object(native_policy, "_read_retained_json", side_effect=observe_read):
                    errors = init_project.validate(target)
                self.assertFalse(any("continuous execution records" in error for error in errors), errors)
                self.assertEqual(reads, identities)
                self.assertEqual((outside/"approval.json").read_text(), "outside sentinel")
                if replacement == "directory":
                    self.assertEqual((native/"approval.json").read_text(), "replacement sentinel")
                for fd in captured:
                    with self.assertRaises(OSError): os.fstat(fd)

    def test_current_three_cycle_template_is_allowed(self):
        expected = (ROOT / "assets" / "project-template" / "AGENTS.md").read_text().replace("{{PROJECT_NAME}}", "Example")
        wrapped = agent_os.render_contract_files("Example", codex_instructions=expected)["AGENTS.md"].decode()
        self.assertTrue(init_project.compatible_chief_agents(wrapped, expected))

    def test_known_creative_one_cycle_payload_is_exactly_recognized(self):
        fixture = ROOT / "tests" / "fixtures" / "creative-managed-one-cycle.json"
        self.assertTrue(fixture.is_file(), "portable Creative legacy fixture is unavailable")
        fixture_value = json.loads(fixture.read_text())
        self.assertEqual(fixture_value["encoding"], "base64")
        payload = base64.b64decode(fixture_value["payload"], validate=True).decode("utf-8")
        self.assertIsNotNone(payload)
        self.assertEqual(hashlib.sha256(payload.encode()).hexdigest(), "486737cd990a2c1389dc14a92df7cf291c2a8c31e227e4f80f3380044ba8d8d5")
        expected = (ROOT / "assets" / "project-template" / "AGENTS.md").read_text().replace("{{PROJECT_NAME}}", "Example")
        wrapped = agent_os.render_contract_files("Example", codex_instructions=payload)["AGENTS.md"].decode()
        self.assertTrue(init_project.compatible_chief_agents(wrapped, expected))
        altered_wrapped = agent_os.render_contract_files("Example", codex_instructions=payload + "\n# unrecognized byte\n")["AGENTS.md"].decode()
        self.assertFalse(init_project.compatible_chief_agents(altered_wrapped, expected))
