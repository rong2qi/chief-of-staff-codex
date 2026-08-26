import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.preference_lib import (
    PIN_CRITERIA,
    PreferenceError,
    atomic_write_json,
    read_json,
    recommend_optional_chief_pins,
    validate_preferences,
)
from scripts.legacy_terminology_migration import (
    CURRENT_PROFILE_KEY,
    LEGACY_PROFILE_KEY,
    LEGACY_SNAPSHOT_PIN_CLASS,
)


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
    def enabled_pin_profile(self):
        profile = json.loads(
            (ROOT / "assets/operator-preferences.example.json").read_text()
        )
        profile["pin_governance"]["enabled"] = True
        for index, role in enumerate(profile["pin_governance"]["mandatory_core_roles"]):
            role["thread_id"] = f"core-{index}"
        return profile

    def pin_candidate(self, thread_id, *, status="active", work_kind="product_delivery", score=0.8):
        return {
            "thread_id": thread_id,
            "title": f"Chief {thread_id}",
            "lifecycle_status": status,
            "work_kind": work_kind,
            "current": True,
            "evidence_fresh": True,
            "lineage_valid": True,
            "signals": {key: score for key in PIN_CRITERIA},
        }

    def test_public_pin_presets_are_safe_and_id_free(self):
        for relative in (
            "assets/operator-preferences.example.json",
            "assets/presets/operator-controlled-bilingual.json",
        ):
            profile = json.loads((ROOT / relative).read_text())
            self.assertEqual(validate_preferences(profile), [])
            pin = profile["pin_governance"]
            self.assertFalse(pin["enabled"])
            self.assertEqual({item["role"] for item in pin["mandatory_core_roles"]}, {
                "general_office", "todo", "creative_director", "context_migration_monitor"
            })
            self.assertTrue(all(item["thread_id"] is None for item in pin["mandatory_core_roles"]))
            self.assertEqual(pin["optional_chief_slots"]["limit"], 6)
            self.assertFalse(pin["optional_chief_slots"]["default_pin_primary_task"])
            self.assertEqual(pin["grandmothered_optional_chiefs"], [])
            self.assertEqual(pin["protected_manual_thread_ids"], [])
            self.assertEqual(pin["invalid_successor_thread_ids"], [])
            inheritance = profile["automation_inheritance"]
            self.assertFalse(inheritance["enabled"])
            self.assertEqual(inheritance["scope"], "bound_task_automations")
            self.assertEqual(inheritance["migration_gate"]["failure_status"], "MIGRATION_BLOCKED")
            self.assertTrue(inheritance["verification"]["live_evidence_required"])

    def test_automation_inheritance_contract_fails_closed_when_weakened(self):
        profile = json.loads(
            (ROOT / "assets/operator-preferences.example.json").read_text()
        )
        profile["automation_inheritance"]["verification"]["reference_or_receipt_is_not_proof"] = False
        self.assertTrue(any(
            "reference_or_receipt_is_not_proof" in item
            for item in validate_preferences(profile)
        ))

    def test_legacy_profile_alias_migrates_one_way_and_dual_equal_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            profile = self.enabled_pin_profile()
            current_value = [{"title": "Historical product Chief", "thread_id": "optional-1"}]
            profile["pin_governance"][CURRENT_PROFILE_KEY] = current_value
            profile["pin_governance"][LEGACY_PROFILE_KEY] = json.loads(json.dumps(current_value))
            source = root / "legacy-profile.json"
            source.write_text(json.dumps(profile), encoding="utf-8")
            checked = run_config("--check", source)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            migrated = read_json(source)
            self.assertEqual(migrated["pin_governance"][CURRENT_PROFILE_KEY], current_value)
            self.assertNotIn(LEGACY_PROFILE_KEY, migrated["pin_governance"])
            output = root / "normalized-profile.json"
            atomic_write_json(output, profile)
            persisted = json.loads(output.read_text())
            self.assertIn(CURRENT_PROFILE_KEY, persisted["pin_governance"])
            self.assertNotIn(LEGACY_PROFILE_KEY, persisted["pin_governance"])

    def test_conflicting_legacy_profile_alias_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            profile = self.enabled_pin_profile()
            profile["pin_governance"][CURRENT_PROFILE_KEY] = []
            profile["pin_governance"][LEGACY_PROFILE_KEY] = [
                {"title": "Conflicting Chief", "thread_id": "different"}
            ]
            errors = validate_preferences(profile)
            self.assertEqual(errors, ["legacy and current pin-governance aliases disagree"])
            path = Path(tmp) / "conflict.json"
            path.write_text(json.dumps(profile), encoding="utf-8")
            checked = run_config("--check", path)
            self.assertEqual(checked.returncode, 2)
            self.assertIn("aliases disagree", checked.stderr)
            with self.assertRaises(PreferenceError):
                read_json(path)

    def test_enabled_pin_governance_requires_four_unique_exact_ids(self):
        profile = self.enabled_pin_profile()
        self.assertEqual(validate_preferences(profile), [])
        profile["pin_governance"]["mandatory_core_roles"][0]["thread_id"] = None
        self.assertTrue(any("thread_id for every core role" in item for item in validate_preferences(profile)))
        profile = self.enabled_pin_profile()
        profile["pin_governance"]["mandatory_core_roles"][1]["thread_id"] = "core-0"
        self.assertTrue(any("must be unique" in item for item in validate_preferences(profile)))

    def test_pin_recommendation_is_bounded_and_excludes_stale_or_process_work(self):
        profile = self.enabled_pin_profile()
        candidates = [self.pin_candidate(f"candidate-{index}", score=0.9 - index / 20) for index in range(5)]
        candidates.extend([
            self.pin_candidate("paused", status="paused"),
            self.pin_candidate("process", work_kind="routine_push"),
        ])
        candidates[1]["evidence_fresh"] = False
        result = recommend_optional_chief_pins(profile, {
            "observed_capacity": 20,
            "pending_packs": 0,
            "pinned_threads": [],
            "candidates": candidates,
        })
        self.assertEqual(result["status"], "recommendation_ready")
        self.assertLessEqual(len(result["candidates"]), 3)
        reasons = {item["thread_id"]: item["reason"] for item in result["excluded"]}
        self.assertIn("paused", reasons["paused"])
        self.assertIn("routine_push", reasons["process"])
        self.assertIn("stale_evidence", reasons["candidate-1"])
        self.assertTrue(result["operator_approval_required"])
        self.assertFalse(result["mutation_performed"])

    def test_full_capacity_protects_manual_pin_and_only_pairs_optional_replacement(self):
        profile = self.enabled_pin_profile()
        profile["pin_governance"]["protected_manual_thread_ids"] = ["manual"]
        low = {key: 0.1 for key in PIN_CRITERIA}
        pinned = [
            {"thread_id": "manual", "title": "Manual", "pin_class": "manual_non_chief"},
            {"thread_id": "old-optional", "title": "Old", "pin_class": LEGACY_SNAPSHOT_PIN_CLASS, "signals": low},
        ]
        result = recommend_optional_chief_pins(profile, {
            "observed_capacity": 2,
            "pending_packs": 0,
            "pinned_threads": pinned,
            "candidates": [self.pin_candidate("new")],
        })
        self.assertEqual(result["status"], "paired_replacement_recommendation")
        self.assertEqual(result["paired_replacement"]["remove_thread_id"], "old-optional")
        self.assertFalse(result["paired_replacement"]["automatic_eviction"])
        self.assertIn("manual", result["protected_manual_thread_ids"])
        pending = recommend_optional_chief_pins(profile, {
            "observed_capacity": 3,
            "pending_packs": 1,
            "pinned_threads": pinned,
            "candidates": [self.pin_candidate("new")],
        })
        self.assertEqual(pending["status"], "pending_pack_exists")
        self.assertEqual(pending["candidates"], [])

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
            self.assertIn("automation_inheritance.enabled", content)
            self.assertIn("automation_rebind_failed", content)

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
