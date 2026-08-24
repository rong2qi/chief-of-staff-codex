import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "init_project.py"
TEMPLATE = ROOT / "assets" / "project-template"


def run(target, *args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--target", str(target), "--project-name", "Example", *args],
        text=True, capture_output=True,
    )


class InitProjectTests(unittest.TestCase):
    def test_fresh_init_creates_throughput_and_goals_feature(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            result = run(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            project = json.loads((target / ".chief-of-staff/project.json").read_text())
            throughput = json.loads((target / ".chief-of-staff/throughput.json").read_text())
            self.assertTrue(project["durable_goal_enabled"])
            self.assertEqual(project["execution_mode"], "effective_throughput")
            self.assertEqual(project["visual_selection_gate"], "disabled")
            self.assertEqual(project["visual_review_hub_title"], "一人之下")
            self.assertEqual(throughput["max_parallel_phase_lanes"], 2)
            self.assertIn("[features]\ngoals = true", (target / ".codex/config.toml").read_text())
            agents = (target / "AGENTS.md").read_text()
            self.assertIn("Optional salutation, coaching, audio, and pause title", agents)
            self.assertNotIn("End every complete user-facing reply", agents)
            self.assertFalse((target / ".chief-of-staff/deployment-registry.json").exists())

    def test_appledouble_agent_sidecars_are_ignored(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            (target / ".codex/agents/._scout.toml").write_bytes(b"not toml metadata")
            result = run(target, "--check")
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_older_project_gets_missing_policy_fields_without_overwriting_custom_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            project_path = target / ".chief-of-staff/project.json"
            project = json.loads(project_path.read_text())
            for key in (
                "durable_goal_enabled", "execution_mode", "max_parallel_phase_lanes",
                "no_evidence_checkpoint_limit", "visual_selection_gate",
                "visual_review_hub_title",
            ):
                project.pop(key)
            project["max_management_depth"] = 5
            project_path.write_text(json.dumps(project) + "\n")
            (target / ".chief-of-staff/throughput.json").unlink()
            old_config = (target / ".codex/config.toml").read_text().replace("\n[features]\ngoals = true\n", "\n")
            (target / ".codex/config.toml").write_text(old_config)
            result = run(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            upgraded = json.loads(project_path.read_text())
            self.assertEqual(upgraded["max_management_depth"], 5)
            self.assertEqual(upgraded["max_parallel_phase_lanes"], 2)
            self.assertEqual(upgraded["visual_selection_gate"], "disabled")
            self.assertEqual(upgraded["visual_review_hub_title"], "一人之下")
            self.assertTrue(json.loads((target / ".chief-of-staff/throughput.json").read_text())["execution_mode"] == "effective_throughput")
            self.assertIn("goals = true", (target / ".codex/config.toml").read_text())

    def test_existing_throughput_values_are_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            path = target / ".chief-of-staff/throughput.json"
            state = json.loads(path.read_text())
            state["max_parallel_phase_lanes"] = 4
            state["active_phase_lanes"] = ["delivery"]
            path.write_text(json.dumps(state) + "\n")
            result = run(target)
            self.assertEqual(result.returncode, 0, result.stderr)
            preserved = json.loads(path.read_text())
            self.assertEqual(preserved["max_parallel_phase_lanes"], 4)
            self.assertEqual(preserved["active_phase_lanes"], ["delivery"])

    def test_project_preferences_enable_visual_gate_without_public_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = root / "project"
            project.mkdir()
            configure = ROOT / "scripts" / "configure_preferences.py"
            configured = subprocess.run(
                [
                    sys.executable, str(configure),
                    "--preset", "operator-controlled-bilingual",
                    "--scope", "project",
                    "--project-root", str(project),
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(configured.returncode, 0, configured.stderr)
            profile = project / ".chief-of-staff/preferences.json"
            result = run(project, "--preferences", str(profile))
            self.assertEqual(result.returncode, 0, result.stderr)
            state = json.loads((project / ".chief-of-staff/project.json").read_text())
            self.assertEqual(
                state["visual_selection_gate"],
                "operator_after_clickable_preview",
            )
            self.assertEqual(
                json.loads(profile.read_text())["scope"],
                "project",
            )

    def test_invalid_or_conflicting_existing_values_stop_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project"
            self.assertEqual(run(target).returncode, 0)
            project_path = target / ".chief-of-staff/project.json"
            project = json.loads(project_path.read_text())
            valid_project = project_path.read_bytes()
            project["execution_mode"] = "unsafe_parallel"
            project_path.write_text(json.dumps(project) + "\n")
            before = project_path.read_bytes()
            result = run(target)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(project_path.read_bytes(), before)
            self.assertIn("project.json", result.stderr)

            project_path.write_bytes(valid_project)
            config_path = target / ".codex/config.toml"
            config_path.write_text(config_path.read_text().replace("goals = true", "goals = false"))
            result = run(target)
            self.assertEqual(result.returncode, 2)
            self.assertIn(".codex/config.toml", result.stderr)


if __name__ == "__main__":
    unittest.main()
