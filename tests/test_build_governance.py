"""Guard delivery of build policy through the real instruction installers.

These checks establish propagation, not enforcement by arbitrary future agents.
"""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
POLICY_TITLE = "## Build execution governance"


class BuildGovernanceDeliveryTests(unittest.TestCase):
    def test_router_upgrade_installs_build_contract_without_losing_user_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp).resolve() / "AGENTS.md"
            target.write_text("<!-- neo-lean-router:start -->\nOld rules\n"
                              "<!-- neo-lean-router:end -->\n\nKeep my signing policy.\n")
            result = subprocess.run([sys.executable, str(ROOT / "scripts/install_neo_router.py"),
                                     "--target", str(target)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            installed = target.read_text()
            self.assertIn(POLICY_TITLE, installed)
            self.assertIn("static-first", installed)
            self.assertIn("NOT_FOR_PRODUCTION", installed)
            self.assertIn("Keep my signing policy.", installed)

    def test_initialized_project_receives_build_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, str(ROOT / "scripts/init_project.py"),
                                     "--target", tmp, "--project-name", "Build governance"],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            instructions = (Path(tmp) / "AGENTS.md").read_text()
            self.assertIn(POLICY_TITLE, instructions)
            self.assertIn("static-first", instructions)
            self.assertIn("NOT_FOR_PRODUCTION", instructions)


if __name__ == "__main__":
    unittest.main()
