"""Exercise the installed entrypoint, preserving unrelated operator instructions."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts/install_neo_router.py"


class NeoRouterTests(unittest.TestCase):
    def install(self, target, *args):
        return subprocess.run([sys.executable, str(INSTALLER), "--target", str(target), *args],
                              capture_output=True, text=True)

    def test_install_upgrade_and_remove_preserve_operator_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp).resolve() / "AGENTS.md"
            original = "# Personal rules\r\n\r\nKeep my preferences.\n"
            target.write_text(original)
            self.assertEqual(self.install(target).returncode, 0)
            installed = target.read_bytes()
            self.assertTrue(installed.endswith(original.encode()))
            self.assertIn(b"DIRECT", installed)
            self.assertEqual(self.install(target).returncode, 0)
            self.assertEqual(target.read_bytes(), installed)
            target.write_bytes(target.read_bytes().replace(b"Default to DIRECT", b"Old routing"))
            self.assertEqual(self.install(target).returncode, 0)
            self.assertEqual(target.read_bytes(), installed)
            self.assertEqual(self.install(target, "--remove").returncode, 0)
            self.assertEqual(target.read_bytes(), original.encode())

    def test_malformed_or_duplicate_markers_do_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp).resolve() / "AGENTS.md"
            for original in ("<!-- neo-lean-router:start -->\npersonal rules",
                             "<!-- neo-lean-router:end -->\n<!-- neo-lean-router:start -->",
                             "<!-- neo-lean-router:start -->\n<!-- neo-lean-router:end -->\n" * 2):
                target.write_text(original)
                self.assertNotEqual(self.install(target).returncode, 0)
                self.assertEqual(target.read_bytes(), original.encode())

    def test_symlink_target_does_not_modify_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            real = Path(tmp) / "real.md"
            real.write_text("preserve\n")
            target = Path(tmp).resolve() / "AGENTS.md"
            target.symlink_to(real)
            self.assertNotEqual(self.install(target).returncode, 0)
            self.assertEqual(real.read_text(), "preserve\n")

    def test_fresh_chief_has_serial_defaults_and_embedded_router(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(ROOT / "scripts/init_project.py"),
                                     "--target", tmp, "--project-name", "Neo"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            project = json.loads((Path(tmp) / ".chief-of-staff/project.json").read_text())
            throughput = json.loads((Path(tmp) / ".chief-of-staff/throughput.json").read_text())
            self.assertEqual(project["max_parallel_phase_lanes"], 1)
            self.assertEqual(throughput["max_parallel_phase_lanes"], 1)
            self.assertFalse(project["proactive_follow_up"])
            self.assertTrue(project["auto_advance_low_impact"])
            router = (ROOT / "assets/neo-lean-router.md").read_text().strip()
            self.assertIn(router, (Path(tmp).resolve() / "AGENTS.md").read_text())


if __name__ == "__main__":
    unittest.main()
