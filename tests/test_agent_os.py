import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import agent_os


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "agent_os.py"


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        text=True,
        capture_output=True,
    )


def directory_snapshot(root):
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def manifest_file(target):
    return target / ".agent-os" / "manifest.json"


def update_manifest_hash(target, relative_path):
    manifest = json.loads(manifest_file(target).read_text())
    manifest["file_hashes"][relative_path] = hashlib.sha256(
        (target / relative_path).read_bytes()
    ).hexdigest()
    manifest_file(target).write_text(json.dumps(manifest, indent=2) + "\n")


def write_work_packet(target, *, packet_id="work-1", task_id="task-1", surfaces=None):
    path = target / f"{packet_id}.json"
    path.write_text(json.dumps({
        "schema": "WORK_PACKET_V1",
        "packet_id": packet_id,
        "project_root_id": json.loads(manifest_file(target).read_text())["root_id"],
        "task_id": task_id,
        "objective": "Write the implementation",
        "write_surfaces": surfaces or ["src"],
        "acceptance_checks": ["python3 -m unittest"],
        "approval_status": "not_required",
    }) + "\n")
    return path


def write_result_packet(target, *, work_packet_id="work-1", task_id="task-1", root_id=None, surfaces=None):
    path = target / "result.json"
    path.write_text(json.dumps({
        "schema": "RESULT_PACKET_V1",
        "packet_id": "result-1",
        "work_packet_id": work_packet_id,
        "project_root_id": root_id or json.loads(manifest_file(target).read_text())["root_id"],
        "task_id": task_id,
        "status": "completed",
        "verified_facts": ["Focused tests passed."],
        "changed_surfaces": surfaces or ["src/owned.py"],
        "evidence": ["python3 -m unittest"],
        "next_step": "Submit for review.",
    }) + "\n")
    return path


class AgentOsCliTests(unittest.TestCase):
    def initialise(self, target):
        result = run("init", "--target", str(target), "--project-name", "Portable Example")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_help_lists_all_deterministic_commands(self):
        result = run("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("init", result.stdout)
        self.assertIn("migrate", result.stdout)
        self.assertIn("verify", result.stdout)

    def test_fresh_init_generates_versioned_contract_and_distinct_adapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.initialise(target)

            required = {
                ".agent-os/CORE.md",
                ".agent-os/PROJECT.md",
                ".agent-os/COMMANDS.md",
                ".agent-os/references.json",
                ".agent-os/manifest.json",
                "AGENTS.md",
                "CLAUDE.md",
            }
            self.assertEqual(required, set(directory_snapshot(target)))
            manifest = json.loads(manifest_file(target).read_text())
            self.assertEqual(manifest["schema"], "AGENT_OS_V1")
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual(manifest["project_name"], "Portable Example")
            self.assertTrue(manifest["root_id"].startswith("agent-os:"))
            self.assertEqual(set(manifest["file_hashes"]), required - {".agent-os/manifest.json"})
            references = json.loads((target / ".agent-os/references.json").read_text())
            self.assertEqual(references["sources"], [
                {
                    "accessed_on": "2026-09-03",
                    "commit": "f10729445d12ca586ed31f7ec50c257a0b336664",
                    "source_id": "nmnmcc-agent-os-gist",
                    "url": "https://gist.github.com/nmnmcc/37c855a390166f8df441001b266ae2e1/f10729445d12ca586ed31f7ec50c257a0b336664",
                },
                {
                    "accessed_on": "2026-09-03",
                    "commit": "cfc89848f505ad5cc6538021debaf3d9e595819b",
                    "source_id": "nmnmcc-ceno-agents",
                    "url": "https://github.com/nmnmcc/ceno/blob/cfc89848f505ad5cc6538021debaf3d9e595819b/AGENTS.md",
                },
            ])
            self.assertNotEqual(
                (target / "AGENTS.md").read_text(), (target / "CLAUDE.md").read_text()
            )
            verified = run("verify", "--target", str(target))
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertIn("AGENT_OS_V1 verified", verified.stdout)

    def test_verify_leaves_projects_without_agent_os_in_legacy_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "legacy"
            target.mkdir()
            (target / "AGENTS.md").write_text("# Existing Chief project\n")

            result = run("verify", "--target", str(target))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("legacy", result.stdout)
            self.assertFalse((target / ".agent-os").exists())

    def test_explicit_migration_is_idempotent_after_first_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "legacy"
            target.mkdir()
            (target / "legacy-state.json").write_text('{"mode": "legacy"}\n')
            (target / "AGENTS.md").write_text("# Existing Chief instructions\n")

            first = run("migrate", "--target", str(target), "--project-name", "Portable Example")
            self.assertEqual(first.returncode, 0, first.stderr)
            first_snapshot = directory_snapshot(target)
            second = run("migrate", "--target", str(target), "--project-name", "Portable Example")

            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(directory_snapshot(target), first_snapshot)
            self.assertIn("# Existing Chief instructions", (target / "AGENTS.md").read_text())
            self.assertEqual(
                run("verify", "--target", str(target)).returncode,
                0,
            )

    def test_migration_preserves_a_legacy_payload_heading_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "legacy"
            target.mkdir()
            legacy_agents = (
                "# Existing Chief instructions\n\n"
                "## Preserved legacy instructions\n\n"
                "This heading belongs to the legacy payload.\n"
            )
            (target / "AGENTS.md").write_text(legacy_agents)

            first = run("migrate", "--target", str(target), "--project-name", "Portable Example")
            verified = run("verify", "--target", str(target))
            first_snapshot = directory_snapshot(target)
            second = run("migrate", "--target", str(target), "--project-name", "Portable Example")

            self.assertEqual(first.returncode, 0, first.stderr)
            self.assertEqual(verified.returncode, 0, verified.stderr)
            self.assertIn(legacy_agents, (target / "AGENTS.md").read_text())
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(directory_snapshot(target), first_snapshot)

    def test_failed_migration_restores_every_existing_byte_and_removes_partial_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "legacy"
            target.mkdir()
            (target / "AGENTS.md").write_text("# Original Chief instructions\n")
            (target / "legacy-state.json").write_text('{"mode": "legacy"}\n')
            before = directory_snapshot(target)

            with self.assertRaisesRegex(agent_os.AgentOsError, "rolled back"):
                agent_os._write_contract(
                    target,
                    "Portable Example",
                    migration=True,
                    fail_after_replacements=6,
                )

            self.assertEqual(directory_snapshot(target), before)
            self.assertFalse((target / ".agent-os").exists())

    def test_interrupted_migration_restores_backups_before_reraising(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "legacy"
            target.mkdir()
            (target / "AGENTS.md").write_text("# Original Chief instructions\n")
            before = directory_snapshot(target)

            with self.assertRaises(KeyboardInterrupt):
                agent_os._write_contract(
                    target,
                    "Portable Example",
                    migration=True,
                    interrupt_after_backups=1,
                )

            self.assertEqual(directory_snapshot(target), before)
            self.assertFalse((target / ".agent-os").exists())

    def test_failed_standalone_recovery_retains_its_backup_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "legacy"
            target.mkdir()
            (target / "AGENTS.md").write_text("# Original Chief instructions\n")

            with self.assertRaises(agent_os.RecoveryIncompleteError) as raised:
                agent_os._write_contract(
                    target,
                    "Portable Example",
                    migration=True,
                    fail_after_replacements=6,
                    fail_restore=True,
                )

            self.assertTrue(raised.exception.staging_path.is_dir())
            self.assertTrue((raised.exception.staging_path / ".rollback" / "AGENTS.md").is_file())

    def test_migration_ignores_legacy_text_that_collides_with_adapter_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "legacy"
            target.mkdir()
            (target / "AGENTS.md").write_text(
                "# Existing instructions\n"
                "source_version: LEGACY_V0\n"
                "adapter: claude\n"
                "core_sha256: not-a-real-hash\n"
            )

            migrated = run("migrate", "--target", str(target), "--project-name", "Portable Example")
            verified = run("verify", "--target", str(target))

            self.assertEqual(migrated.returncode, 0, migrated.stderr)
            self.assertEqual(verified.returncode, 0, verified.stderr)

    def test_conflicting_destination_leaves_target_byte_for_byte_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            target.mkdir()
            (target / "AGENTS.md").write_text("# User-owned instructions\n")
            before = directory_snapshot(target)

            result = run("init", "--target", str(target), "--project-name", "Portable Example")

            self.assertEqual(result.returncode, 2)
            self.assertIn("conflict", result.stderr.lower())
            self.assertEqual(directory_snapshot(target), before)

    def test_copied_project_verifies_with_project_relative_contract_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            source = temp / "source" / "project"
            self.initialise(source)
            copied = temp / "new-parent" / "copied-project"
            shutil.copytree(source, copied)

            result = run("verify", "--target", str(copied))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                json.loads(manifest_file(source).read_text())["root_id"],
                json.loads(manifest_file(copied).read_text())["root_id"],
            )

    def test_init_rejects_a_symlinked_contract_directory_without_writing_outside_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            target = temp / "project"
            outside = temp / "outside"
            target.mkdir()
            outside.mkdir()
            (target / ".agent-os").symlink_to(outside, target_is_directory=True)

            result = run("init", "--target", str(target), "--project-name", "Portable Example")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsafe destination", result.stderr.lower())
            self.assertEqual(directory_snapshot(outside), {})
            self.assertFalse((target / "AGENTS.md").exists())

    def test_verify_rejects_required_contract_file_symlinked_outside_the_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            target = temp / "project"
            outside = temp / "outside-core.md"
            self.initialise(target)
            core = target / ".agent-os" / "CORE.md"
            outside.write_bytes(core.read_bytes())
            core.unlink()
            core.symlink_to(outside)

            result = run("verify", "--target", str(target))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsafe contract path", result.stderr.lower())

    def test_verify_rejects_a_dangling_agent_os_symlink_instead_of_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "legacy"
            target.mkdir()
            (target / ".agent-os").symlink_to(target / "missing-agent-os")

            result = run("verify", "--target", str(target))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("dangling", result.stderr.lower())

    def test_verify_rejects_tampered_contract_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.initialise(target)
            (target / ".agent-os" / "CORE.md").write_text("tampered\n")

            result = run("verify", "--target", str(target))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("hash mismatch", result.stderr.lower())

    def test_verify_rejects_missing_and_stale_adapters(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.initialise(target)
            (target / "CLAUDE.md").unlink()
            missing = run("verify", "--target", str(target))
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("missing adapter", missing.stderr.lower())

            self.initialise(target := Path(tmp) / "fresh")
            core = target / ".agent-os" / "CORE.md"
            core.write_text(core.read_text() + "\nContract content changed without regenerating adapters.\n")
            update_manifest_hash(target, ".agent-os/CORE.md")
            stale = run("verify", "--target", str(target))
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("canonical contract", stale.stderr.lower())

    def test_verify_rejects_rehashed_claude_authority_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.initialise(target)
            claude = target / "CLAUDE.md"
            claude.write_text(claude.read_text().replace(
                "does not grant Claude Codex task, pin, automation, or Chief authority",
                "grants Claude Codex task, pin, automation, and Chief authority",
            ))
            update_manifest_hash(target, "CLAUDE.md")

            result = run("verify", "--target", str(target))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("canonical contract", result.stderr.lower())

    def test_verify_rejects_rehashed_provenance_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.initialise(target)
            references = target / ".agent-os" / "references.json"
            value = json.loads(references.read_text())
            value["sources"][0]["commit"] = "0" * 40
            references.write_text(json.dumps(value, indent=2) + "\n")
            update_manifest_hash(target, ".agent-os/references.json")

            result = run("verify", "--target", str(target))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("canonical contract", result.stderr.lower())

    def test_verify_rejects_source_version_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.initialise(target)
            manifest = json.loads(manifest_file(target).read_text())
            manifest["source_versions"]["core"] = "CORE_V0"
            manifest_file(target).write_text(json.dumps(manifest, indent=2) + "\n")

            result = run("verify", "--target", str(target))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("source-version mismatch", result.stderr.lower())

    def test_verify_rejects_two_work_packets_with_the_same_write_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.initialise(target)
            first = target / "work-a.json"
            second = target / "work-b.json"
            packet = {
                "schema": "WORK_PACKET_V1",
                "packet_id": "work-a",
                "project_root_id": json.loads(manifest_file(target).read_text())["root_id"],
                "task_id": "task-a",
                "objective": "Write the implementation",
                "write_surfaces": ["src/owned.py"],
                "acceptance_checks": ["python3 -m unittest"],
                "approval_status": "not_required",
            }
            first.write_text(json.dumps(packet) + "\n")
            packet.update({"packet_id": "work-b", "task_id": "task-b"})
            second.write_text(json.dumps(packet) + "\n")

            result = run(
                "verify", "--target", str(target),
                "--work-packet", str(first), "--work-packet", str(second),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unique-writer conflict", result.stderr.lower())

    def test_verify_rejects_two_work_packets_with_nested_write_surfaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.initialise(target)
            root_id = json.loads(manifest_file(target).read_text())["root_id"]
            packets = []
            for packet_id, task_id, surface in (
                ("work-a", "task-a", "src"),
                ("work-b", "task-b", "src/owned.py"),
            ):
                path = target / f"{packet_id}.json"
                path.write_text(json.dumps({
                    "schema": "WORK_PACKET_V1",
                    "packet_id": packet_id,
                    "project_root_id": root_id,
                    "task_id": task_id,
                    "objective": "Write the implementation",
                    "write_surfaces": [surface],
                    "acceptance_checks": ["python3 -m unittest"],
                    "approval_status": "not_required",
                }) + "\n")
                packets.append(path)

            result = run(
                "verify", "--target", str(target),
                "--work-packet", str(packets[0]), "--work-packet", str(packets[1]),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unique-writer conflict", result.stderr.lower())

    def test_verify_rejects_same_task_packets_with_overlapping_write_surfaces(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.initialise(target)
            first = write_work_packet(target, packet_id="work-a", task_id="task-a", surfaces=["src"])
            second = write_work_packet(target, packet_id="work-b", task_id="task-a", surfaces=["src/owned.py"])

            result = run(
                "verify", "--target", str(target),
                "--work-packet", str(first), "--work-packet", str(second),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unique-writer conflict", result.stderr.lower())

    def test_verify_rejects_nonexistent_or_non_directory_target_instead_of_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            missing = run("verify", "--target", str(temp / "missing"))
            target_file = temp / "not-a-directory"
            target_file.write_text("file\n")
            mistyped = run("verify", "--target", str(target_file))

            self.assertNotEqual(missing.returncode, 0)
            self.assertNotEqual(mistyped.returncode, 0)
            self.assertIn("existing directory", missing.stderr.lower())
            self.assertIn("existing directory", mistyped.stderr.lower())

    def test_verify_rejects_rule_candidate_without_explicit_operator_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.initialise(target)
            candidate = target / "rule.json"
            candidate.write_text(json.dumps({
                "schema": "RULE_CANDIDATE_V1",
                "candidate_id": "rule-1",
                "scope": "project",
                "proposed_rule": "Always use the new workflow.",
                "operator_approval": {"status": "pending", "approval_id": None},
            }) + "\n")

            result = run("verify", "--target", str(target), "--rule-candidate", str(candidate))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("explicit operator approval", result.stderr.lower())

    def test_verify_accepts_a_valid_result_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.initialise(target)
            work_packet = write_work_packet(target)
            result_packet = write_result_packet(target)

            result = run(
                "verify", "--target", str(target),
                "--work-packet", str(work_packet), "--result-packet", str(result_packet),
            )

            self.assertEqual(result.returncode, 0, result.stderr)

    def test_verify_rejects_an_invalid_result_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.initialise(target)
            result_packet = target / "result.json"
            result_packet.write_text(json.dumps({
                "schema": "RESULT_PACKET_V1",
                "packet_id": "result-1",
                "work_packet_id": "work-1",
                "project_root_id": json.loads(manifest_file(target).read_text())["root_id"],
                "task_id": "task-1",
                "status": "made_up",
                "verified_facts": ["Focused tests passed."],
                "changed_surfaces": ["src/owned.py"],
                "evidence": ["python3 -m unittest"],
                "next_step": "Submit for review.",
            }) + "\n")

            result = run("verify", "--target", str(target), "--result-packet", str(result_packet))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("result packet status", result.stderr.lower())

    def test_verify_rejects_result_without_a_supplied_work_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.initialise(target)
            result_packet = write_result_packet(target)

            result = run("verify", "--target", str(target), "--result-packet", str(result_packet))

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not resolve", result.stderr.lower())

    def test_verify_rejects_result_with_a_different_work_packet_task(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.initialise(target)
            work_packet = write_work_packet(target, task_id="task-a")
            result_packet = write_result_packet(target, task_id="task-b")

            result = run(
                "verify", "--target", str(target),
                "--work-packet", str(work_packet), "--result-packet", str(result_packet),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("task_id", result.stderr.lower())

    def test_verify_rejects_result_with_a_different_work_packet_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.initialise(target)
            work_packet = write_work_packet(target)
            result_packet = write_result_packet(target, root_id="agent-os:" + "0" * 24)

            result = run(
                "verify", "--target", str(target),
                "--work-packet", str(work_packet), "--result-packet", str(result_packet),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("project_root_id", result.stderr.lower())

    def test_verify_rejects_result_changes_outside_its_work_packet_surface(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.initialise(target)
            work_packet = write_work_packet(target, surfaces=["src/owned.py"])
            result_packet = write_result_packet(target, surfaces=["docs/outside.md"])

            result = run(
                "verify", "--target", str(target),
                "--work-packet", str(work_packet), "--result-packet", str(result_packet),
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("outside work packet", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
