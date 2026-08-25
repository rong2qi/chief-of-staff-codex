import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIGURE = ROOT / "scripts" / "configure_preferences.py"
RENDER = ROOT / "scripts" / "render_english_audio.py"


def run_config(*args, env=None):
    return subprocess.run(
        [sys.executable, str(CONFIGURE), *map(str, args)],
        text=True,
        capture_output=True,
        env=env,
    )


class PreferenceTests(unittest.TestCase):
    def test_core_global_profile_preserves_existing_agents_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            agents = root / "AGENTS.md"
            agents.write_text("# Existing rule\n", encoding="utf-8")
            result = run_config(
                "--preset", "core",
                "--scope", "global",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            profile_path = data / "chief-preferences.json"
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            self.assertEqual(profile["report_review_mode"], "exception_only")
            self.assertFalse(profile["governance_model"]["enabled"])
            self.assertFalse(
                profile["governance_model"]["continuation_policy"]["enabled"]
            )
            self.assertFalse(profile["visual_selection_gate"]["enabled"])
            self.assertFalse(profile["american_english_coaching"]["enabled"])
            self.assertFalse(profile["audio_playback"]["enabled"])
            content = agents.read_text(encoding="utf-8")
            self.assertIn("# Existing rule", content)
            self.assertEqual(content.count("chief-of-staff-preferences:start"), 1)

    def test_operator_preset_reconfigures_managed_block_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            agents = root / "AGENTS.md"
            agents.write_text("# Keep me\n", encoding="utf-8")
            command = (
                "--preset", "operator-controlled-bilingual",
                "--scope", "global",
                "--salutation", "妈妈",
                "--audio-provider", "macos_say",
                "--voice", "Samantha",
                "--audio-rate", "170",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(run_config(*command).returncode, 0)
            self.assertEqual(run_config(*command).returncode, 0)
            profile = json.loads((data / "chief-preferences.json").read_text())
            self.assertTrue(profile["visual_selection_gate"]["enabled"])
            self.assertEqual(profile["report_review_mode"], "exception_only")
            self.assertFalse(profile["governance_model"]["enabled"])
            self.assertEqual(
                profile["visual_selection_gate"]["review_hub_title"],
                "Chief of Creative Direction｜创意总监",
            )
            self.assertTrue(profile["american_english_coaching"]["include_casual_chat"])
            self.assertEqual(profile["audio_playback"]["clips"], ["written", "spoken"])
            self.assertEqual(
                profile["audio_playback"]["storage_root"],
                str((data / "english-audio").resolve()),
            )
            self.assertEqual(profile["operator_salutation"]["value"], "妈妈")
            self.assertEqual(profile["audio_playback"]["voice"], "Samantha")
            self.assertEqual(profile["audio_playback"]["rate"], 170)
            content = agents.read_text()
            self.assertEqual(content.count("chief-of-staff-preferences:start"), 1)
            self.assertIn("# Keep me", content)

    def test_reconfigure_preserves_unknown_top_level_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            agents = root / "AGENTS.md"
            first = run_config(
                "--preset", "core",
                "--scope", "global",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            profile_path = data / "chief-preferences.json"
            profile = json.loads(profile_path.read_text())
            profile["future_extension"] = {"keep": True}
            profile_path.write_text(json.dumps(profile), encoding="utf-8")
            second = run_config(
                "--preset", "operator-controlled-bilingual",
                "--scope", "global",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(second.returncode, 0, second.stderr)
            updated = json.loads(profile_path.read_text())
            self.assertEqual(updated["future_extension"], {"keep": True})

    def test_custom_input_applies_independent_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            custom = json.loads(
                (ROOT / "assets/operator-preferences.example.json").read_text()
            )
            custom["american_english_coaching"]["enabled"] = True
            custom["american_english_coaching"]["include_casual_chat"] = True
            custom_path = root / "custom.json"
            custom_path.write_text(json.dumps(custom), encoding="utf-8")
            result = run_config(
                "--input", custom_path,
                "--scope", "global",
                "--data-root", data,
                "--agents-file", root / "AGENTS.md",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            profile = json.loads((data / "chief-preferences.json").read_text())
            self.assertEqual(profile["preset"], "custom")
            self.assertTrue(profile["american_english_coaching"]["enabled"])
            self.assertFalse(profile["visual_selection_gate"]["enabled"])
            self.assertFalse(profile["audio_playback"]["enabled"])

    def test_core_reconfigure_explicitly_disables_personal_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            agents = root / "AGENTS.md"
            enabled = run_config(
                "--preset", "operator-controlled-bilingual",
                "--scope", "global",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(enabled.returncode, 0, enabled.stderr)
            disabled = run_config(
                "--preset", "core",
                "--scope", "global",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(disabled.returncode, 0, disabled.stderr)
            profile = json.loads((data / "chief-preferences.json").read_text())
            for key in (
                "governance_model",
                "visual_selection_gate",
                "american_english_coaching",
                "audio_playback",
                "operator_salutation",
                "paused_title_prefix",
                "reminders",
            ):
                self.assertFalse(profile[key]["enabled"], key)

    def test_custom_chair_governance_requires_general_office_and_is_persisted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            custom = json.loads(
                (ROOT / "assets/operator-preferences.example.json").read_text()
            )
            custom["governance_model"]["enabled"] = True
            custom["governance_model"]["general_office_thread_id"] = "thread-general-office"
            custom["governance_model"]["continuation_policy"]["enabled"] = True
            custom_path = root / "custom.json"
            custom_path.write_text(json.dumps(custom), encoding="utf-8")
            result = run_config(
                "--input", custom_path,
                "--scope", "global",
                "--data-root", data,
                "--agents-file", root / "AGENTS.md",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            profile = json.loads((data / "chief-preferences.json").read_text())
            self.assertTrue(profile["governance_model"]["enabled"])
            self.assertEqual(
                profile["governance_model"]["general_office_thread_id"],
                "thread-general-office",
            )
            self.assertIn("CHAIR_BRIEF_READY", (root / "AGENTS.md").read_text())
            self.assertIn(
                "strongest evidence-backed safe in-scope continuation",
                (root / "AGENTS.md").read_text(),
            )

    def test_continuation_policy_requires_enabled_governance(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            custom = json.loads(
                (ROOT / "assets/operator-preferences.example.json").read_text()
            )
            custom["governance_model"]["continuation_policy"]["enabled"] = True
            custom_path = root / "custom.json"
            custom_path.write_text(json.dumps(custom), encoding="utf-8")
            result = run_config(
                "--input", custom_path,
                "--scope", "global",
                "--data-root", data,
                "--agents-file", root / "AGENTS.md",
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn(
                "enabled continuation_policy requires enabled governance_model",
                result.stderr,
            )

    def test_missing_custom_data_root_fails_without_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "missing-volume" / "data"
            result = run_config(
                "--preset", "operator-controlled-bilingual",
                "--scope", "global",
                "--data-root", missing,
                "--agents-file", root / "AGENTS.md",
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(missing.exists())
            self.assertFalse((root / "AGENTS.md").exists())

    def test_project_scope_writes_only_project_profile(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "project"
            project.mkdir()
            result = run_config(
                "--preset", "core",
                "--scope", "project",
                "--project-root", project,
                "--agents-file", Path(tmp) / "global-agents.md",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            profile = json.loads(
                (project / ".chief-of-staff/preferences.json").read_text()
            )
            self.assertEqual(profile["scope"], "project")
            self.assertFalse((Path(tmp) / "global-agents.md").exists())

    def test_audio_renderer_creates_separate_cached_clip(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            agents = root / "AGENTS.md"
            configured = run_config(
                "--preset", "operator-controlled-bilingual",
                "--scope", "global",
                "--salutation", "妈妈",
                "--audio-provider", "macos_say",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(configured.returncode, 0, configured.stderr)

            fake_say = root / "say"
            fake_say.write_text(
                "#!/bin/sh\nout=''\nwhile [ $# -gt 0 ]; do\n"
                "  if [ \"$1\" = '-o' ]; then shift; out=$1; fi\n"
                "  shift\ndone\nprintf 'M4A-DATA' > \"$out\"\n",
                encoding="utf-8",
            )
            fake_say.chmod(fake_say.stat().st_mode | stat.S_IXUSR)
            env = dict(
                os.environ,
                CHIEF_AUDIO_PLATFORM="Darwin",
                CHIEF_SAY_BIN=str(fake_say),
            )
            command = [
                sys.executable, str(RENDER),
                "--profile", str(data / "chief-preferences.json"),
                "--kind", "written",
                "--text", "Please resume the interrupted work.",
            ]
            first = subprocess.run(command, text=True, capture_output=True, env=env)
            second = subprocess.run(command, text=True, capture_output=True, env=env)
            self.assertEqual(first.returncode, 0, first.stderr)
            first_result = json.loads(first.stdout)
            second_result = json.loads(second.stdout)
            self.assertEqual(first_result["status"], "ready")
            self.assertFalse(first_result["cached"])
            self.assertTrue(second_result["cached"])
            self.assertEqual(first_result["path"], second_result["path"])
            self.assertEqual(Path(first_result["path"]).read_bytes(), b"M4A-DATA")
            self.assertFalse(list((data / "english-audio").glob(".chief-audio-*")))

    def test_audio_missing_root_returns_text_only_without_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = json.loads(
                (ROOT / "assets/presets/operator-controlled-bilingual.json").read_text()
            )
            profile["audio_playback"]["provider"] = "macos_say"
            profile["audio_playback"]["storage_root"] = str(root / "missing")
            profile_path = root / "profile.json"
            profile_path.write_text(json.dumps(profile), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable, str(RENDER),
                    "--profile", str(profile_path),
                    "--kind", "spoken",
                    "--text", "Pick up where you left off.",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout)["status"], "text_only")
            self.assertFalse((root / "missing").exists())

    def test_host_builtin_voice_generates_no_audio_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data"
            data.mkdir()
            agents = root / "AGENTS.md"
            configured = run_config(
                "--preset", "operator-controlled-bilingual",
                "--scope", "global",
                "--data-root", data,
                "--agents-file", agents,
            )
            self.assertEqual(configured.returncode, 0, configured.stderr)
            profile_path = data / "chief-preferences.json"
            profile = json.loads(profile_path.read_text())
            self.assertEqual(profile["audio_playback"]["provider"], "host_builtin")
            self.assertIsNone(profile["audio_playback"]["storage_root"])
            self.assertFalse((data / "english-audio").exists())

            rendered = subprocess.run(
                [
                    sys.executable, str(RENDER),
                    "--profile", str(profile_path),
                    "--kind", "spoken",
                    "--text", "Use the built-in voice.",
                ],
                text=True,
                capture_output=True,
            )
            self.assertEqual(rendered.returncode, 0, rendered.stderr)
            result = json.loads(rendered.stdout)
            self.assertEqual(result["status"], "text_only")
            self.assertIn("host built-in voice", result["reason"])


if __name__ == "__main__":
    unittest.main()
