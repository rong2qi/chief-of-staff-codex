"""RED-first regression coverage for the V2 recover command."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path
from tests.private_authority_fixture import TESTING_REVIEWER_ID
from scripts import codex_agent_os_activation as activation


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "codex_agent_os_activation.py"
BLOCK_HASH = hashlib.sha256(
    b"<!-- agent-os-global:start -->\n# Agent OS global engineering floor (managed)\n"
    b"restore local facts before implementation.\n"
    b"Read the nearest README, implementation, tests, configuration, and ownership rules.\n"
    b"Copy the closest valid local pattern before introducing a new one.\n"
    b"Use evidence for the actual dependency and API versions in use.\n"
    b"Run real relevant commands and update documentation with observed behavior.\n"
    b"Separate verified facts, inference, and open items in reports.\n"
    b"Stop and ask when a semantic ambiguity changes scope, authority, or behavior.\n"
    b"Persist durable rules only through an approved RULE_CANDIDATE.\n"
    b"<!-- agent-os-global:end -->\n"
).hexdigest()


def inventory_hash(root: Path) -> str:
    entries = []
    for path in sorted(root.rglob("*")):
        info = path.lstat()
        entries.append({"path": path.relative_to(root).as_posix(), "type": "dir" if path.is_dir() else "file",
                        "mode": info.st_mode & 0o7777, "size": info.st_size if path.is_file() else 0,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None})
    return hashlib.sha256(json.dumps({"present": True, "entries": entries}, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


class ActivationV2Tests(unittest.TestCase):
    def make_case(self, root: Path, *, existing: bool = False):
        source, skills, evidence = root / "source", root / "skills", root / "evidence"
        global_agents = root / "global" / "AGENTS.md"
        (source / "scripts").mkdir(parents=True); skills.mkdir(); evidence.mkdir(); global_agents.parent.mkdir()
        (source / "SKILL.md").write_text("skill\n"); (source / "scripts" / "tool.py").write_text("pass\n")
        global_agents.write_text("global before\n")
        if existing:
            destination = skills / "chief-of-staff"; destination.mkdir(); (destination / "old.txt").write_text("old\n")
        candidate = root / "candidate.json"
        candidate.write_text(json.dumps({"schema": "CODEX_AGENT_OS_CANDIDATE_V1", "candidate_id": "v2-test",
            "activation_scope": "codex_only", "claude_runtime": "dormant_unvalidated",
            "package_inventory_hash": inventory_hash(source), "global_block_hash": BLOCK_HASH}))
        gate = root / "gate.json"
        gate.write_text(json.dumps({"schema": "CODEX_AGENT_OS_TESTING_GATE_V1", "status": "TESTING_GATE_PASS",
            "testing_chief_task_id": TESTING_REVIEWER_ID, "candidate_id": "v2-test",
            "candidate_manifest_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
            "package_inventory_hash": inventory_hash(source), "global_block_hash": BLOCK_HASH,
            "tested_lanes": ["CLI_SCRIPT", "SECURITY_PRIVACY"], "claude_runtime": "dormant_unvalidated"}))
        common = ["--source", str(source), "--skills-root", str(skills), "--global-agents", str(global_agents),
                  "--evidence-root", str(evidence), "--txid", "a" * 32, "--candidate", str(candidate),
                  "--testing-gate", str(gate), "--expected-testing-gate-sha256", hashlib.sha256(gate.read_bytes()).hexdigest()]
        return source, skills, global_agents, evidence, common

    def call(self, command, common, *extra, env=None):
        if command not in {"plan", "apply"} and "--source" in common:
            common = list(common); index = common.index("--source"); del common[index:index + 2]
        values = [sys.executable, str(SCRIPT), command, *common, *extra]
        return subprocess.run(values, text=True, capture_output=True, env=env)

    def test_recover_clean_baseline_is_idempotent_with_fixed_transaction_identity(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, skills, evidence = root / "source", root / "skills", root / "evidence"
            global_agents = root / "global" / "AGENTS.md"
            (source / "scripts").mkdir(parents=True); skills.mkdir(); evidence.mkdir(); global_agents.parent.mkdir()
            (source / "SKILL.md").write_text("skill\n"); global_agents.write_text("global\n")
            candidate = root / "candidate.json"
            candidate.write_text(json.dumps({"schema": "CODEX_AGENT_OS_CANDIDATE_V1", "candidate_id": "v2-red",
                "activation_scope": "codex_only", "claude_runtime": "dormant_unvalidated",
                "package_inventory_hash": inventory_hash(source), "global_block_hash": BLOCK_HASH}))
            gate = root / "gate.json"
            gate.write_text(json.dumps({"schema": "CODEX_AGENT_OS_TESTING_GATE_V1", "status": "TESTING_GATE_PASS",
                "testing_chief_task_id": TESTING_REVIEWER_ID, "candidate_id": "v2-red",
                "candidate_manifest_sha256": hashlib.sha256(candidate.read_bytes()).hexdigest(),
                "package_inventory_hash": inventory_hash(source), "global_block_hash": BLOCK_HASH,
                "tested_lanes": ["CLI_SCRIPT"], "claude_runtime": "dormant_unvalidated"}))
            common = ["--source", str(source), "--skills-root", str(skills), "--global-agents", str(global_agents),
                      "--evidence-root", str(evidence), "--txid", "a" * 32, "--candidate", str(candidate),
                      "--testing-gate", str(gate), "--expected-testing-gate-sha256",
                      hashlib.sha256(gate.read_bytes()).hexdigest()]
            first = self.call("recover", common)
            second = self.call("recover", common)
            self.assertNotEqual(first.returncode, 0)
            self.assertNotEqual(second.returncode, 0)

    def test_authority_config_inside_activation_evidence_is_rejected_before_plan_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, skills, global_agents, evidence, common = self.make_case(root)
            raw = (json.dumps({"schema": "CHIEF_PRIVATE_AUTHORITY_CONFIG_V1", "testing_reviewer_task_id": TESTING_REVIEWER_ID}, sort_keys=True, separators=(",", ":")) + "\n").encode()
            config = evidence / "authority.json"
            config.write_bytes(raw)
            environment = dict(os.environ)
            environment.update({
                "CHIEF_PRIVATE_AUTHORITY_CONFIG_PATH": str(config),
                "CHIEF_PRIVATE_AUTHORITY_CONFIG_SHA256": hashlib.sha256(raw).hexdigest(),
            })
            rejected = self.call("plan", common, env=environment)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertFalse((evidence / ("a" * 32)).exists())
            self.assertFalse((skills / "chief-of-staff").exists())

    def test_activation_preflight_rejects_config_in_candidate_skills_global_or_evidence_roots(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, skills, global_agents, evidence, common = self.make_case(root)
            candidate = Path(common[common.index("--candidate") + 1])
            gate = Path(common[common.index("--testing-gate") + 1])
            paths = activation.topology(source, skills, global_agents, evidence, "a" * 32)
            boundaries = (candidate.parent, gate.parent, source, skills, global_agents.parent, evidence, paths["destination"], paths["package_tx"], paths["global_tx"], paths["package_probe_parent"], paths["global_probe_parent"])
            raw = (json.dumps({"schema": "CHIEF_PRIVATE_AUTHORITY_CONFIG_V1", "testing_reviewer_task_id": TESTING_REVIEWER_ID}, sort_keys=True, separators=(",", ":")) + "\n").encode()
            for name, directory in (("candidate", candidate.parent), ("skills", skills), ("global", global_agents.parent), ("evidence", evidence)):
                config = directory / ("authority-" + name + ".json")
                config.write_bytes(raw)
                with self.subTest(surface=name), mock.patch.dict(os.environ, {
                    "CHIEF_PRIVATE_AUTHORITY_CONFIG_PATH": str(config),
                    "CHIEF_PRIVATE_AUTHORITY_CONFIG_SHA256": hashlib.sha256(raw).hexdigest(),
                }, clear=False), self.assertRaises(activation.ActivationError):
                    activation.validate_authority(candidate, gate, hashlib.sha256(gate.read_bytes()).hexdigest(), activation.inventory_hash(source), authority_boundaries=boundaries)

    def test_recovery_and_rollback_work_after_reviewed_source_disappears(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root, existing=True)
            planned = self.call("plan", common)
            self.assertEqual(planned.returncode, 0, planned.stderr)
            self.assertEqual(self.call("apply", common, "--operator-approval-id", "APPROVED").returncode, 0)
            shutil.rmtree(source)
            without_source = list(common); index = without_source.index("--source"); del without_source[index:index + 2]
            self.assertEqual(self.call("verify", without_source, "--state", "activated").returncode, 0)
            self.assertEqual(self.call("rollback-plan", without_source).returncode, 0)
            self.assertEqual(self.call("rollback", without_source, "--operator-approval-id", "APPROVED-ROLLBACK").returncode, 0)
            self.assertEqual(self.call("recover", without_source).returncode, 0)

    def test_present_and_absent_lifecycle_uses_fixed_transaction_topology(self):
        for existing in (False, True):
            with self.subTest(existing=existing), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root, existing=existing)
                before_global = global_agents.read_bytes()
                before_package = (skills / "chief-of-staff" / "old.txt").read_bytes() if existing else None
                self.assertEqual(self.call("plan", common).returncode, 0)
                applied = self.call("apply", common, "--operator-approval-id", "APPROVED-1")
                self.assertEqual(applied.returncode, 0, applied.stderr)
                self.assertEqual(self.call("verify", common, "--state", "activated").returncode, 0)
                package_tx = skills / ".agent-os-transactions" / ("a" * 32)
                global_tx = global_agents.parent / ".agent-os-transactions" / ("a" * 32)
                self.assertTrue((package_tx / "activation-intent.json").is_file())
                self.assertEqual((package_tx / "activation-intent.json").read_bytes(), (global_tx / "activation-intent.json").read_bytes())
                self.assertTrue((evidence / ("a" * 32) / "receipt.json").is_file())
                self.assertEqual(inventory_hash(skills / "chief-of-staff"), inventory_hash(source))
                self.assertEqual(self.call("rollback-plan", common).returncode, 0)
                rolled = self.call("rollback", common, "--operator-approval-id", "APPROVED-2")
                self.assertEqual(rolled.returncode, 0, rolled.stderr)
                verified = self.call("verify", common, "--state", "baseline")
                self.assertEqual(verified.returncode, 0, verified.stderr + " global=" + repr(global_agents.read_bytes()) + " package=" + repr(inventory_hash(skills / "chief-of-staff")))
                self.assertEqual(global_agents.read_bytes(), before_global)
                self.assertEqual((skills / "chief-of-staff").exists(), existing)
                if existing: self.assertEqual((skills / "chief-of-staff" / "old.txt").read_bytes(), before_package)
                self.assertTrue((evidence / ("a" * 32) / "rollback-receipt.json").is_file())

    def test_activation_faults_recover_twice_to_baseline(self):
        for existing in (False, True):
            labels = ("global-pre-to-backup", "package-stage-to-live", "global-stage-to-live")
            if existing: labels = ("package-pre-to-backup", *labels)
            for fault in ("before", "after", "keyboard-after", "systemexit-after", "exit-after"):
                for label in labels:
                    with self.subTest(existing=existing, fault=fault, label=label), tempfile.TemporaryDirectory() as temporary:
                        root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root, existing=existing)
                        baseline = global_agents.read_bytes(); self.assertEqual(self.call("plan", common).returncode, 0)
                        environment = dict(os.environ)
                        if fault == "exit-after": environment["AGENT_OS_RENAME_EXIT"] = f"after:{label}"
                        else: environment["AGENT_OS_RENAME_FAULT"] = f"{fault}:{label}"
                        failed = self.call("apply", common, "--operator-approval-id", "APPROVED", env=environment)
                        self.assertNotEqual(failed.returncode, 0)
                        first, second = self.call("recover", common), self.call("recover", common)
                        self.assertEqual(first.returncode, 0, first.stderr); self.assertEqual(second.returncode, 0, second.stderr)
                        self.assertEqual(global_agents.read_bytes(), baseline)
                        self.assertEqual((skills / "chief-of-staff").exists(), existing)
                        if existing: self.assertEqual((skills / "chief-of-staff" / "old.txt").read_text(), "old\n")

    def test_unrecognized_concurrent_target_is_preserved_and_conflicts(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root)
            self.assertEqual(self.call("plan", common).returncode, 0)
            destination = skills / "chief-of-staff"; destination.mkdir(); (destination / "concurrent.txt").write_text("do not touch\n")
            result = self.call("apply", common, "--operator-approval-id", "APPROVED")
            self.assertNotEqual(result.returncode, 0); self.assertEqual((destination / "concurrent.txt").read_text(), "do not touch\n")

    def test_interrupted_rollback_always_recovers_to_baseline(self):
        for existing in (False, True):
            labels = ("rollback-package-post-to-quarantine", "rollback-global-post-to-quarantine", "rollback-global-pre-to-live")
            if existing: labels = (*labels, "rollback-package-pre-to-live")
            for fault in ("before", "after", "keyboard-after", "systemexit-after", "exit-after"):
                for label in labels:
                    with self.subTest(existing=existing, fault=fault, label=label), tempfile.TemporaryDirectory() as temporary:
                        root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root, existing=existing)
                        baseline = global_agents.read_bytes(); self.assertEqual(self.call("plan", common).returncode, 0)
                        self.assertEqual(self.call("apply", common, "--operator-approval-id", "APPROVED-A").returncode, 0)
                        self.assertEqual(self.call("rollback-plan", common).returncode, 0)
                        environment = dict(os.environ)
                        if fault == "exit-after": environment["AGENT_OS_RENAME_EXIT"] = f"after:{label}"
                        else: environment["AGENT_OS_RENAME_FAULT"] = f"{fault}:{label}"
                        interrupted = self.call("rollback", common, "--operator-approval-id", "APPROVED-B", env=environment)
                        self.assertNotEqual(interrupted.returncode, 0)
                        self.assertEqual(self.call("recover", common).returncode, 0)
                        self.assertEqual(self.call("recover", common).returncode, 0)
                        verified = self.call("verify", common, "--state", "baseline")
                        self.assertEqual(verified.returncode, 0, verified.stderr)
                        self.assertEqual(global_agents.read_bytes(), baseline)
                        self.assertEqual((skills / "chief-of-staff").exists(), existing)
                        if existing: self.assertEqual((skills / "chief-of-staff" / "old.txt").read_text(), "old\n")

    def test_subprocess_abrupt_exit_after_rename_recovers_in_new_process(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root, existing=True)
            baseline = global_agents.read_bytes(); self.assertEqual(self.call("plan", common).returncode, 0)
            environment = dict(os.environ); environment["AGENT_OS_RENAME_EXIT"] = "after:global-pre-to-backup"
            dead = self.call("apply", common, "--operator-approval-id", "APPROVED", env=environment)
            self.assertEqual(dead.returncode, 92)
            recovered = self.call("recover", common)
            self.assertEqual(recovered.returncode, 0, recovered.stderr)
            self.assertEqual(global_agents.read_bytes(), baseline)

    def test_authority_and_plan_tampering_are_rejected_before_live_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root)
            self.assertEqual(self.call("plan", common).returncode, 0)
            plan = evidence / ("a" * 32) / "plan.json"; data = json.loads(plan.read_text()); data["destination"] = str(root / "other"); plan.write_text(json.dumps(data))
            rejected = self.call("apply", common, "--operator-approval-id", "APPROVED")
            self.assertNotEqual(rejected.returncode, 0); self.assertFalse((skills / "chief-of-staff").exists())
            bad = list(common); bad[bad.index("--expected-testing-gate-sha256") + 1] = "0" * 64
            self.assertNotEqual(self.call("recover", bad).returncode, 0)

    def test_txid_reuse_and_symlinked_evidence_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root)
            self.assertEqual(self.call("plan", common).returncode, 0)
            self.assertNotEqual(self.call("plan", common).returncode, 0)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root)
            outside = root / "outside"; outside.mkdir(); alias = root / "alias"; alias.symlink_to(outside, target_is_directory=True)
            aliased = list(common); aliased[aliased.index("--evidence-root") + 1] = str(alias)
            self.assertNotEqual(self.call("plan", aliased).returncode, 0)

    def test_hardlink_and_source_mutation_fail_before_any_live_move(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root)
            os.link(source / "SKILL.md", source / "hardlink.md")
            hardlink = self.call("plan", common)
            self.assertNotEqual(hardlink.returncode, 0); self.assertFalse((skills / "chief-of-staff").exists())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root)
            self.assertEqual(self.call("plan", common).returncode, 0)
            (source / "changed.txt").write_text("mutated after frozen authority\n")
            mutated = self.call("apply", common, "--operator-approval-id", "APPROVED")
            self.assertNotEqual(mutated.returncode, 0); self.assertFalse((skills / "chief-of-staff").exists())

    def test_gate_contract_rollback_plan_and_global_mode_are_frozen(self):
        for field, value in (("status", "PASS"), ("testing_chief_task_id", "wrong"), ("candidate_id", "wrong"), ("tested_lanes", ["NO_SUCH_LANE"])):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root)
                gate = Path(common[common.index("--testing-gate") + 1]); data = json.loads(gate.read_text()); data[field] = value; gate.write_text(json.dumps(data))
                bad = list(common); bad[bad.index("--expected-testing-gate-sha256") + 1] = hashlib.sha256(gate.read_bytes()).hexdigest()
                self.assertNotEqual(self.call("plan", bad).returncode, 0)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root, existing=True)
            os.chmod(global_agents, 0o640); mode = global_agents.stat().st_mode & 0o7777
            self.assertEqual(self.call("plan", common).returncode, 0)
            self.assertEqual(self.call("apply", common, "--operator-approval-id", "APPROVED").returncode, 0)
            self.assertEqual(global_agents.stat().st_mode & 0o7777, mode)
            missing = self.call("rollback", common, "--operator-approval-id", "APPROVED-R")
            self.assertNotEqual(missing.returncode, 0)
            self.assertEqual(self.call("rollback-plan", common).returncode, 0)
            rollback_plan = evidence / ("a" * 32) / "rollback-plan.json"; rollback_plan.write_text("{}")
            tampered = self.call("rollback", common, "--operator-approval-id", "APPROVED-R")
            self.assertNotEqual(tampered.returncode, 0)

    def test_partial_commit_replica_is_repaired_but_conflicting_receipt_is_not(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root)
            self.assertEqual(self.call("plan", common).returncode, 0)
            self.assertEqual(self.call("apply", common, "--operator-approval-id", "APPROVED").returncode, 0)
            global_commit = global_agents.parent / ".agent-os-transactions" / ("a" * 32) / "activation-commit.json"
            global_commit.unlink()
            self.assertEqual(self.call("recover", common).returncode, 0)
            self.assertTrue(global_commit.is_file())
            receipt = evidence / ("a" * 32) / "receipt.json"; receipt.write_text("{}")
            conflict = self.call("recover", common)
            self.assertNotEqual(conflict.returncode, 0)

    def test_clean_recover_and_missing_external_plan_fail_closed_or_recover_from_intents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root)
            self.assertNotEqual(self.call("recover", common).returncode, 0)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root, existing=True)
            self.assertEqual(self.call("plan", common).returncode, 0)
            environment = dict(os.environ); environment["AGENT_OS_RENAME_EXIT"] = "after:global-pre-to-backup"
            self.assertEqual(self.call("apply", common, "--operator-approval-id", "APPROVED", env=environment).returncode, 92)
            (evidence / ("a" * 32) / "plan.json").unlink()
            recovered = self.call("recover", common)
            self.assertEqual(recovered.returncode, 0, recovered.stderr)

    def test_topology_marker_and_authority_aliases_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root)
            global_agents.write_bytes((b"<!-- agent-os-global:start -->\n<!-- agent-os-global:end -->\n") * 2)
            self.assertNotEqual(self.call("plan", common).returncode, 0)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root)
            aliased = list(common); aliased[aliased.index("--skills-root") + 1] = str(global_agents.parent)
            self.assertNotEqual(self.call("plan", aliased).returncode, 0)
            outside = root / "outside"; outside.mkdir(); candidate_alias = root / "candidate-alias.json"; candidate_alias.symlink_to(Path(common[common.index("--candidate") + 1]))
            alias_args = list(common); alias_args[alias_args.index("--candidate") + 1] = str(candidate_alias)
            self.assertNotEqual(self.call("plan", alias_args).returncode, 0)

    def test_real_codex_parent_contains_skills_lifecycle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, _, global_agents, evidence, common = self.make_case(root, existing=False)
            codex = root / ".codex"; codex.mkdir(); global_agents.unlink(); global_agents = codex / "AGENTS.md"; global_agents.write_text("global before\n")
            skills = codex / "skills"; skills.mkdir()
            shaped = list(common)
            shaped[shaped.index("--skills-root") + 1] = str(skills)
            shaped[shaped.index("--global-agents") + 1] = str(global_agents)
            planned = self.call("plan", shaped)
            self.assertEqual(planned.returncode, 0, planned.stderr)
            self.assertEqual(self.call("apply", shaped, "--operator-approval-id", "APPROVED").returncode, 0)
            self.assertEqual(self.call("rollback-plan", shaped).returncode, 0)
            self.assertEqual(self.call("rollback", shaped, "--operator-approval-id", "APPROVED-R").returncode, 0)

    def test_rollback_recovery_uses_intents_when_plan_is_lost_at_each_boundary(self):
        for existing in (False, True):
            labels = ["rollback-package-post-to-quarantine", "rollback-global-post-to-quarantine", "rollback-global-pre-to-live"]
            if existing: labels.append("rollback-package-pre-to-live")
            for label in labels:
                with self.subTest(existing=existing, label=label), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root, existing=existing)
                    baseline = global_agents.read_bytes(); self.assertEqual(self.call("plan", common).returncode, 0)
                    self.assertEqual(self.call("apply", common, "--operator-approval-id", "A").returncode, 0)
                    self.assertEqual(self.call("rollback-plan", common).returncode, 0)
                    environment = dict(os.environ); environment["AGENT_OS_RENAME_EXIT"] = f"after:{label}"
                    self.assertEqual(self.call("rollback", common, "--operator-approval-id", "B", env=environment).returncode, 92)
                    (evidence / ("a" * 32) / "rollback-plan.json").unlink()
                    recovered = self.call("recover", common)
                    self.assertEqual(recovered.returncode, 0, recovered.stderr)
                    self.assertIn("evidence_gap", recovered.stdout)
                    self.assertEqual(global_agents.read_bytes(), baseline)
                    self.assertEqual((skills / "chief-of-staff").exists(), existing)

    def test_rollback_rejects_recognized_extra_stage_and_tampered_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root, existing=True)
            self.assertEqual(self.call("plan", common).returncode, 0)
            self.assertEqual(self.call("apply", common, "--operator-approval-id", "A").returncode, 0)
            self.assertEqual(self.call("rollback-plan", common).returncode, 0)
            package_tx = skills / ".agent-os-transactions" / ("a" * 32)
            shutil.copytree(source, package_tx / "package-stage")
            self.assertNotEqual(self.call("rollback", common, "--operator-approval-id", "B").returncode, 0)
            shutil.rmtree(package_tx / "package-stage")
            (package_tx / "package-backup" / "old.txt").write_text("tampered\n")
            self.assertNotEqual(self.call("rollback", common, "--operator-approval-id", "B").returncode, 0)

    def test_each_capability_probe_failure_precedes_intents_and_live_mutation(self):
        for label in ("skills-directory", "skills-file", "global-directory", "global-file"):
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root, existing=True)
                baseline = global_agents.read_bytes(); self.assertEqual(self.call("plan", common).returncode, 0)
                environment = dict(os.environ); environment["AGENT_OS_PROBE_FAIL"] = label
                failed = self.call("apply", common, "--operator-approval-id", "A", env=environment)
                self.assertNotEqual(failed.returncode, 0)
                self.assertEqual(global_agents.read_bytes(), baseline)
                self.assertTrue((skills / "chief-of-staff" / "old.txt").is_file())
                self.assertFalse((skills / ".agent-os-transactions" / ("a" * 32)).exists())

    def test_preexisting_rollback_receipt_blocks_new_rollback_without_live_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root, existing=True)
            self.assertEqual(self.call("plan", common).returncode, 0)
            self.assertEqual(self.call("apply", common, "--operator-approval-id", "A").returncode, 0)
            self.assertEqual(self.call("rollback-plan", common).returncode, 0)
            receipt = evidence / ("a" * 32) / "rollback-receipt.json"
            receipt.write_text("{}\n")
            before_global = global_agents.read_bytes(); before_package = inventory_hash(skills / "chief-of-staff")
            rejected = self.call("rollback", common, "--operator-approval-id", "B")
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(global_agents.read_bytes(), before_global)
            self.assertEqual(inventory_hash(skills / "chief-of-staff"), before_package)

    def test_no_change_surfaces_have_a_single_exact_rollback_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root, existing=True)
            shutil.rmtree(skills / "chief-of-staff"); shutil.copytree(source, skills / "chief-of-staff")
            global_agents.write_bytes(
                b"<!-- agent-os-global:start -->\n# Agent OS global engineering floor (managed)\n"
                b"restore local facts before implementation.\nRead the nearest README, implementation, tests, configuration, and ownership rules.\n"
                b"Copy the closest valid local pattern before introducing a new one.\nUse evidence for the actual dependency and API versions in use.\n"
                b"Run real relevant commands and update documentation with observed behavior.\nSeparate verified facts, inference, and open items in reports.\n"
                b"Stop and ask when a semantic ambiguity changes scope, authority, or behavior.\nPersist durable rules only through an approved RULE_CANDIDATE.\n"
                b"<!-- agent-os-global:end -->\n")
            self.assertEqual(self.call("plan", common).returncode, 0)
            self.assertEqual(self.call("apply", common, "--operator-approval-id", "A").returncode, 0)
            self.assertEqual(self.call("rollback-plan", common).returncode, 0)
            rolled = self.call("rollback", common, "--operator-approval-id", "B")
            self.assertEqual(rolled.returncode, 0, rolled.stderr)
            self.assertEqual(self.call("verify", common, "--state", "baseline").returncode, 0)

    def test_rollback_rejects_whitespace_approval_before_intent_or_live_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root, existing=True)
            self.assertEqual(self.call("plan", common).returncode, 0)
            self.assertEqual(self.call("apply", common, "--operator-approval-id", "APPLY-OK").returncode, 0)
            self.assertEqual(self.call("rollback-plan", common).returncode, 0)
            before_global = global_agents.read_bytes(); before_package = inventory_hash(skills / "chief-of-staff")
            rejected = self.call("rollback", common, "--operator-approval-id", " ROLLBACK-OK ")
            self.assertNotEqual(rejected.returncode, 0)
            package_tx = skills / ".agent-os-transactions" / ("a" * 32)
            global_tx = global_agents.parent / ".agent-os-transactions" / ("a" * 32)
            self.assertFalse((package_tx / "rollback-intent.json").exists())
            self.assertFalse((global_tx / "rollback-intent.json").exists())
            self.assertEqual(global_agents.read_bytes(), before_global)
            self.assertEqual(inventory_hash(skills / "chief-of-staff"), before_package)
            environment = dict(os.environ); environment["AGENT_OS_RENAME_EXIT"] = "after:rollback-package-post-to-quarantine"
            self.assertEqual(self.call("rollback", common, "--operator-approval-id", "ROLLBACK-OK", env=environment).returncode, 92)
            self.assertEqual(self.call("recover", common).returncode, 0)
            self.assertEqual(self.call("verify", common, "--state", "baseline").returncode, 0)

    def test_probe_aliases_reject_before_outside_txid_creation(self):
        for surface in ("skills", "global"):
            with self.subTest(surface=surface), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root)
                self.assertEqual(self.call("plan", common).returncode, 0)
                outside = root / "outside"; outside.mkdir()
                probe_parent = (skills if surface == "skills" else global_agents.parent) / ".agent-os-probes"
                probe_parent.symlink_to(outside, target_is_directory=True)
                rejected = self.call("apply", common, "--operator-approval-id", "A")
                self.assertNotEqual(rejected.returncode, 0)
                self.assertFalse((outside / ("a" * 32)).exists())
                self.assertFalse((skills / ".agent-os-transactions" / ("a" * 32)).exists())

    def test_evidence_root_cannot_alias_a_derived_probe_surface(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); source, skills, global_agents, _, common = self.make_case(root)
            probe_parent = skills / ".agent-os-probes"; probe_parent.mkdir()
            aliased = list(common); aliased[aliased.index("--evidence-root") + 1] = str(probe_parent)
            self.assertNotEqual(self.call("plan", aliased).returncode, 0)

    def test_post_probe_validation_substitution_preserves_held_evidence_and_blocks_intents(self):
        for surface in ("skills", "global"):
            with self.subTest(surface=surface), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary); source, skills, global_agents, evidence, common = self.make_case(root, existing=True)
                baseline = global_agents.read_bytes(); self.assertEqual(self.call("plan", common).returncode, 0)
                outside = root / "outside"; outside.mkdir()
                environment = dict(os.environ)
                environment["AGENT_OS_PROBE_SUBSTITUTE"] = surface
                environment["AGENT_OS_PROBE_SUBSTITUTE_OUTSIDE"] = str(outside)
                rejected = self.call("apply", common, "--operator-approval-id", "A", env=environment)
                self.assertNotEqual(rejected.returncode, 0)
                parent = skills if surface == "skills" else global_agents.parent
                retained = parent / ".agent-os-probes" / (("a" * 32) + ".retained-" + surface)
                self.assertTrue(retained.is_dir())
                self.assertTrue(any(retained.iterdir()))
                self.assertFalse(any(outside.iterdir()))
                self.assertEqual(global_agents.read_bytes(), baseline)
                self.assertTrue((skills / "chief-of-staff" / "old.txt").is_file())
                self.assertFalse((skills / ".agent-os-transactions" / ("a" * 32)).exists())


if __name__ == "__main__":
    unittest.main()
