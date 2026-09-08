"""Fail-closed tests for the host-owned private reviewer selection."""
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import continuous_execution, private_authority
from tests.private_authority_fixture import TESTING_REVIEWER_ID


def authority_bytes(reviewer: str = TESTING_REVIEWER_ID) -> bytes:
    return (json.dumps({
        "schema": private_authority.SCHEMA,
        "testing_reviewer_task_id": reviewer,
    }, sort_keys=True, separators=(",", ":")) + "\n").encode()


class PrivateAuthorityTests(unittest.TestCase):
    def test_host_pinned_external_config_resolves_synthetic_test_identity(self):
        self.assertEqual(
            private_authority.testing_reviewer_task_id(forbidden_paths=(Path(__file__).resolve().parents[1],)),
            TESTING_REVIEWER_ID,
        )

    def test_missing_or_drifted_host_config_fails_closed(self):
        with mock.patch.dict(os.environ, {
            private_authority.CONFIG_PATH_ENV: "",
            private_authority.CONFIG_SHA256_ENV: "",
        }, clear=False):
            with self.assertRaises(private_authority.PrivateAuthorityError):
                private_authority.testing_reviewer_task_id(forbidden_paths=())
        with tempfile.TemporaryDirectory() as temporary:
            config = Path(temporary) / "authority.json"
            config.write_bytes(authority_bytes())
            with mock.patch.dict(os.environ, {
                private_authority.CONFIG_PATH_ENV: str(config),
                private_authority.CONFIG_SHA256_ENV: "0" * 64,
            }, clear=False):
                with self.assertRaises(private_authority.PrivateAuthorityError):
                    private_authority.testing_reviewer_task_id(forbidden_paths=())

    def test_duplicate_keys_and_public_boundary_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            duplicate = root / "authority.json"
            raw = b'{"schema":"CHIEF_PRIVATE_AUTHORITY_CONFIG_V1","testing_reviewer_task_id":"one","testing_reviewer_task_id":"two"}\n'
            duplicate.write_bytes(raw)
            with mock.patch.dict(os.environ, {
                private_authority.CONFIG_PATH_ENV: str(duplicate),
                private_authority.CONFIG_SHA256_ENV: hashlib.sha256(raw).hexdigest(),
            }, clear=False):
                with self.assertRaises(private_authority.PrivateAuthorityError):
                    private_authority.testing_reviewer_task_id(forbidden_paths=())
            config = root / "inside-boundary.json"
            raw = authority_bytes()
            config.write_bytes(raw)
            with mock.patch.dict(os.environ, {
                private_authority.CONFIG_PATH_ENV: str(config),
                private_authority.CONFIG_SHA256_ENV: hashlib.sha256(raw).hexdigest(),
            }, clear=False):
                with self.assertRaises(private_authority.PrivateAuthorityError):
                    private_authority.testing_reviewer_task_id(forbidden_paths=(root,))

    def test_nonregular_fifo_is_rejected_without_waiting(self):
        with tempfile.TemporaryDirectory() as temporary:
            fifo = Path(temporary) / "authority.fifo"
            os.mkfifo(fifo)
            with mock.patch.dict(os.environ, {
                private_authority.CONFIG_PATH_ENV: str(fifo),
                private_authority.CONFIG_SHA256_ENV: "0" * 64,
            }, clear=False):
                with self.assertRaises(private_authority.PrivateAuthorityError):
                    private_authority.testing_reviewer_task_id(forbidden_paths=())

    def test_continuous_consumer_rejects_project_or_native_receipt_authority_config(self):
        delegation = {
            "testing_chief_task_id": TESTING_REVIEWER_ID,
            "delegation_id": "delegation-1",
            "reviewer_task_id": "reviewer-1",
            "writer_task_id": "writer-1",
            "reviewer_registered": True,
            "risk": "medium",
            "candidate_sha256": "a" * 64,
            "scope": "local",
            "delegation_evidence_ref": "native://delegation.json",
            "delegation_receipt_sha256": "b" * 64,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project, native = root / "project", root / "native"
            project.mkdir(); native.mkdir()
            raw = authority_bytes()
            for forbidden_root in (project, native):
                config = forbidden_root / "authority.json"
                config.write_bytes(raw)
                with mock.patch.dict(os.environ, {
                    private_authority.CONFIG_PATH_ENV: str(config),
                    private_authority.CONFIG_SHA256_ENV: hashlib.sha256(raw).hexdigest(),
                }, clear=False), self.assertRaises(continuous_execution.ContinuousExecutionError):
                    continuous_execution.validate_delegated_testing(
                        delegation,
                        submitting_project=project,
                        native_observation_root=native,
                    )
                config.unlink()
            with self.assertRaises(continuous_execution.ContinuousExecutionError):
                continuous_execution.validate_delegated_testing(delegation)
