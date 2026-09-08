import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.project_paths import (
    PortabilityError,
    discover_project_root,
    resolve_project_path,
    stable_root_id,
)


ROOT = Path(__file__).resolve().parents[1]


class ProjectPathPortabilityTests(unittest.TestCase):
    def make_project(self, parent: Path, name: str = "portable-project") -> Path:
        project = parent / name
        state = project / ".chief-of-staff"
        state.mkdir(parents=True)
        (state / "project.json").write_text(
            json.dumps({"schema_version": 1, "project_name": "Portable Project"})
        )
        return project

    def test_native_marker_discovery_and_root_id_survive_copy_without_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            source = self.make_project(temp / "source-parent")
            anchor = source / "scripts" / "nested" / "tool.py"
            anchor.parent.mkdir(parents=True)
            anchor.write_text("# anchor\n")

            resolved = discover_project_root(anchor=anchor, cwd=temp, environ={})
            source_id = stable_root_id(resolved.path)
            self.assertEqual(resolved.path, source.resolve())
            self.assertEqual(resolved.source, "project_marker")

            copied = temp / "new-parent" / "copied-project"
            shutil.copytree(source, copied)
            copied_anchor = copied / "scripts" / "nested" / "tool.py"
            copied_root = discover_project_root(anchor=copied_anchor, cwd=temp, environ={})
            output = resolve_project_path(copied_root.path, "outputs/result.json", root_id=source_id)
            self.assertEqual(copied_root.path, copied.resolve())
            self.assertEqual(stable_root_id(copied_root.path), source_id)
            self.assertEqual(output.relative_path, "outputs/result.json")
            self.assertEqual(output.absolute_path, copied.resolve() / "outputs/result.json")

    def test_environment_override_is_optional_and_cannot_bypass_valid_root_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            project = self.make_project(temp)
            anchor = project / "config" / "settings.json"
            anchor.parent.mkdir()
            anchor.write_text("{}")
            discovered = discover_project_root(
                anchor=anchor, cwd=temp, env_var="APP_PROJECT_ROOT", environ={}
            )
            self.assertEqual(discovered.source, "project_marker")

            override = self.make_project(temp, "override")
            selected = discover_project_root(
                anchor=anchor,
                cwd=temp,
                env_var="APP_PROJECT_ROOT",
                environ={"APP_PROJECT_ROOT": str(override)},
            )
            self.assertEqual(selected.path, override.resolve())
            self.assertEqual(selected.source, "environment_override")

            with self.assertRaises(PortabilityError):
                discover_project_root(
                    anchor=anchor,
                    cwd=temp,
                    env_var="APP_PROJECT_ROOT",
                    environ={"APP_PROJECT_ROOT": "relative/project"},
                )

    def test_git_root_precedes_nearer_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            nested = root / "nested"
            nested.mkdir()
            (nested / "AGENTS.md").write_text("# nested marker\n")
            resolution = discover_project_root(anchor=nested, cwd=nested, environ={})
            self.assertEqual(resolution.path, root.resolve())
            self.assertEqual(resolution.source, "git_root")

    def test_library_has_no_machine_location_default(self):
        source = (ROOT / "scripts/project_paths.py").read_text()
        forbidden = (
            "/Vol" + "umes/",
            "/Us" + "ers/",
            "/private/" + "tmp",
            "C:" + "/",
        )
        for fragment in forbidden:
            self.assertNotIn(fragment, source)

    def test_absolute_parent_drive_and_symlink_escape_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            project = self.make_project(temp)
            root_id = stable_root_id(project)
            outside = temp / "outside"
            outside.mkdir()
            (project / "escape-link").symlink_to(outside, target_is_directory=True)
            for raw in (
                str(outside / "input.bin"),
                "../escape",
                "nested/../escape",
                "nested//file",
                "nested/./file",
                "C:/machine/path",
                "C:drive-relative",
                "D:",
                "escape-link/out.bin",
            ):
                with self.subTest(raw=raw), self.assertRaises(PortabilityError):
                    resolve_project_path(project, raw, root_id=root_id)

    def test_external_path_needs_exact_authorized_nonroot_intake(self):
        with tempfile.TemporaryDirectory() as tmp:
            temp = Path(tmp)
            project = self.make_project(temp)
            root_id = stable_root_id(project)
            external = temp / "sdk" / "tool"
            exact = str(external)
            registry = {
                exact: {
                    "authorized": True,
                    "identity": "sha256:" + "a" * 64,
                    "permissions": ["read"],
                    "project_root_dependency": False,
                }
            }
            with self.assertRaises(PortabilityError):
                resolve_project_path(project, exact, root_id=root_id)
            accepted = resolve_project_path(
                project, exact, root_id=root_id, external_registry=registry
            )
            self.assertEqual(accepted.scope, "external_registered")
            registry[exact]["project_root_dependency"] = True
            with self.assertRaises(PortabilityError):
                resolve_project_path(project, exact, root_id=root_id, external_registry=registry)

    def test_historical_evidence_is_excluded_from_active_resolution(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = self.make_project(Path(tmp))
            root_id = stable_root_id(project)
            for record_class in (
                "historical_audit",
                "frozen_candidate",
                "hash_manifest",
                "context_migration",
                "legacy_build",
                "provenance",
            ):
                with self.subTest(record_class=record_class), self.assertRaises(PortabilityError):
                    resolve_project_path(
                        project,
                        "evidence/record.json",
                        root_id=root_id,
                        record_class=record_class,
                    )

    def test_root_id_never_falls_back_to_absolute_path_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            empty = Path(tmp) / "empty"
            empty.mkdir()
            with self.assertRaises(PortabilityError):
                stable_root_id(empty)


if __name__ == "__main__":
    unittest.main()
