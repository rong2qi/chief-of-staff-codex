"""Consumer regressions captured from the C1 independent review.

These tests deliberately exercise the real retry/record consumers, rather than
only validating a schema-shaped helper payload.
"""
import copy
import tempfile
import unittest
from pathlib import Path

from scripts import continuous_execution
from tests.test_continuous_execution import PACKAGE, evidence


class RepairOneRegressions(unittest.TestCase):
    def test_progress_identity_is_semantic_not_a_new_log_id(self):
        first = evidence(1)
        same_change_new_log = copy.deepcopy(first)
        same_change_new_log.update({"evidence_id": "different-log", "evidence_sha256": "f" * 64})
        rounds = [
            {"round_id": "one", "evidence": first},
            {"round_id": "two", "evidence": same_change_new_log},
        ]
        self.assertEqual(continuous_execution.progress_summary(rounds)["real_progress_cycles"], 1)

    def test_progress_criterion_must_be_preapproved(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            payload = {
                "schema": "CHIEF_EXECUTION_PROGRESS_EVIDENCE_V1", "kind": "acceptance_gain",
                "evidence_id": "p1", "observation": {"before": "red", "after": "green"},
                "work_id": PACKAGE["work_id"], "package_id": PACKAGE["package_id"],
                "candidate_sha256": PACKAGE["candidate_sha256"], "criterion_id": "invented",
            }
            import hashlib, json
            raw = json.dumps(payload, sort_keys=True).encode(); (root / "p.json").write_bytes(raw)
            with self.assertRaises(continuous_execution.ContinuousExecutionError):
                continuous_execution.validate_progress_evidence({"kind": "acceptance_gain", "evidence_id": "p1", "observation": payload["observation"], "evidence_ref": "repo://p.json", "evidence_sha256": hashlib.sha256(raw).hexdigest()}, root, PACKAGE)

    def test_missing_resource_measurement_is_not_zero(self):
        state = {"work_id": PACKAGE["work_id"], "package_id": PACKAGE["package_id"], "status": "running", "owner_task_id": PACKAGE["writer_task_id"], "rounds": []}
        with self.assertRaises(continuous_execution.ContinuousExecutionError):
            continuous_execution.reconcile_execution(state, PACKAGE)

    def test_records_reject_archived_or_foreign_reviewer(self):
        plan = {"execution_packages": [PACKAGE]}
        registry = {"tasks": [
            {"task_id": "writer-1", "project_id": "project-1", "execution_work_id": "work-new", "execution_package_id": "package-1", "execution_root_id": "root-1", "execution_branch": "candidate-branch", "write_surface": ["repo://source"], "status": "running"},
            {"task_id": "reviewer-1", "project_id": "other-project", "execution_reviewer_for": "work-new", "write_surface": [], "status": "archived"},
        ]}
        approvals = {"requests": [{"request_id": "approval-1", "status": "approved", "decision_receipt_sha256": "c" * 64, "decision_evidence_ref": PACKAGE["approval_evidence_ref"]}]}
        with self.assertRaises(continuous_execution.ContinuousExecutionError):
            continuous_execution.validate_execution_records(plan, registry, approvals)
