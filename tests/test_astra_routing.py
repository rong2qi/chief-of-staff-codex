import importlib.util
import os
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "astra_routing.py"
CONFIG = Path(os.environ.get("ASTRA_ROUTING_CONFIG", ROOT / "agent-profiles" / "config.toml"))
if not CONFIG.is_file():
    # Installed Chief payloads keep the companion as a sibling of skills/.
    CONFIG = ROOT.parents[1] / "agent-profiles" / "config.toml"


def load_module():
    spec = importlib.util.spec_from_file_location("astra_routing", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AstraRoutingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.routing = load_module()

    def config_from(self, text):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "config.toml"
        path.write_text(text, encoding="utf-8")
        return self.routing.load_config(path)

    def test_missing_or_disabled_enablement_keeps_legacy_routes(self):
        legacy = self.config_from('schema_version = 1\n[risk.high]\nroute = ["sol-arbiter", "terra-implementer", "sol-arbiter"]\n')
        disabled = self.config_from('schema_version = 2\nenabled = false\n[risk.high]\nroute = ["sol-arbiter", "terra-implementer", "sol-arbiter"]\n')
        for config in (legacy, disabled):
            decision = self.routing.route(config, risk="high", complex_task=True, astra_available=True, runtime_slots=4)
            self.assertEqual(decision["roles"], ["sol-arbiter", "terra-implementer", "sol-arbiter"])
            self.assertFalse(decision["astra_enabled"])

    def test_invalid_enablement_and_limits_are_rejected(self):
        invalid_enabled = self.config_from('schema_version = 2\nenabled = "yes"\n')
        invalid_limits = self.config_from('schema_version = 2\nenabled = true\ndefault_active_agents = 4\nmax_active_agents = 3\n')
        self.assertIn("enabled must be a boolean", self.routing.validate(invalid_enabled))
        self.assertIn("default_active_agents must be at most max_active_agents", self.routing.validate(invalid_limits))

    def test_invalid_enabled_config_cannot_route_or_generate(self):
        invalid = self.config_from('schema_version = 2\nenabled = true\ndefault_active_agents = true\n')
        with self.assertRaisesRegex(ValueError, "invalid routing config"):
            self.routing.route(invalid, risk="high", complex_task=True, astra_available=True, runtime_slots=3)
        with self.assertRaisesRegex(ValueError, "invalid routing config"):
            self.routing.generate_managed_block(invalid)
        disabled = self.config_from('schema_version = 2\nenabled = false\n')
        with self.assertRaisesRegex(ValueError, "invalid routing config"):
            self.routing.generate_managed_block(disabled)

    def test_unavailable_astra_is_explicitly_downgraded_to_sol(self):
        config = self.routing.load_config(CONFIG)
        decision = self.routing.route(config, risk="high", complex_task=True, astra_available=False, runtime_slots=4)
        self.assertEqual(decision["roles"], ["sol-arbiter", "terra-implementer", "sol-arbiter"])
        self.assertEqual(decision["downgrade"], "astra_unavailable_to_sol")

    def test_low_risk_stays_single_agent(self):
        config = self.routing.load_config(CONFIG)
        decision = self.routing.route(config, risk="low", complex_task=False, astra_available=True, runtime_slots=4)
        self.assertEqual(decision["roles"], ["terra-implementer"])
        self.assertFalse(decision["use_fourth_slot"])

    def test_complex_high_risk_uses_astra_then_sole_writer_then_independent_sol(self):
        config = self.routing.load_config(CONFIG)
        decision = self.routing.route(config, risk="high", complex_task=True, astra_available=True, runtime_slots=4)
        self.assertEqual(decision["roles"], ["astra-arbiter", "terra-implementer", "sol-arbiter"])
        self.assertEqual(decision["writer"], "terra-implementer")
        self.assertTrue(decision["independent_safety_review_required"])

    def test_fourth_slot_requires_independent_benefit_and_capacity(self):
        config = self.routing.load_config(CONFIG)
        insufficient = self.routing.route(config, risk="high", complex_task=True, astra_available=True, runtime_slots=3, independent_benefit=True)
        no_benefit = self.routing.route(config, risk="high", complex_task=True, astra_available=True, runtime_slots=4, independent_benefit=False)
        approved = self.routing.route(config, risk="high", complex_task=True, astra_available=True, runtime_slots=4, independent_benefit=True)
        self.assertFalse(insufficient["use_fourth_slot"])
        self.assertFalse(no_benefit["use_fourth_slot"])
        self.assertTrue(approved["use_fourth_slot"])

    def test_explicit_model_overrides_writer_but_keeps_high_risk_independent_review(self):
        config = self.routing.load_config(CONFIG)
        decision = self.routing.route(config, risk="high", complex_task=True, astra_available=True, runtime_slots=4, explicit_model="gpt-5.6-terra")
        self.assertEqual(decision["roles"], ["explicit-model", "sol-arbiter"])
        self.assertEqual(decision["model"], "gpt-5.6-terra")
        self.assertTrue(decision["independent_safety_review_required"])
        self.assertFalse(decision["independent_safety_review_passed"])

    def test_one_slot_blocks_multi_agent_route_but_two_slots_can_stage(self):
        config = self.routing.load_config(CONFIG)
        blocked = self.routing.route(config, risk="high", complex_task=True, astra_available=True, runtime_slots=1)
        staged = self.routing.route(config, risk="high", complex_task=True, astra_available=True, runtime_slots=2)
        self.assertEqual(blocked["status"], "blocked")
        self.assertEqual(blocked["blocked_reason"], "capacity_shortfall")
        self.assertEqual(staged["status"], "recommended")
        self.assertEqual(staged["maximum_active_agents"], 2)

    def test_global_block_is_stable_and_marks_configuration_as_non_native(self):
        config = self.routing.load_config(CONFIG)
        first = self.routing.generate_managed_block(config)
        second = self.routing.generate_managed_block(config)
        self.assertEqual(first, second)
        self.assertIn("<!-- astra-chief-routing:managed:start -->", first)
        self.assertIn("非 Codex 原生运行时配置", first)
        self.assertIn("not a Codex-native runtime configuration", first)
        self.assertIn("无独立安全复核不得判 PASS", first)

    def test_prospective_global_replaces_only_the_exact_routing_section(self):
        config = self.routing.load_config(CONFIG)
        before = """preamble
## 路由

| 模型 | 默认职责 |
| --- | --- |
| `gpt-5.6-sol` | 架构裁决及高风险复核 |
| `gpt-5.6-terra` | 唯一实施者 |
| `gpt-5.6-luna` | 低成本、只读的独立检查 |

保留用户显式指定的模型。模型选择是默认路由而非正确性保证；高风险结论仍需要证据和独立复核。

## 分诊与交接

- 高风险或方案冲突：Sol 裁决 → Terra 实施 → Sol 独立复核。
trailer
"""
        after = self.routing.prospective_global(before, config)
        self.assertTrue(after.startswith("preamble\n"))
        self.assertTrue(after.endswith("trailer\n"))
        self.assertIn("`gpt-6-astra`", after)
        self.assertIn("- 复杂/跨模块高风险：Astra 裁决 → Terra 实施 → Sol 独立复核；明确高风险：Sol 裁决 → Terra 实施 → Sol 独立复核", after)
        self.assertNotIn("高风险或方案冲突：Sol 裁决 → Terra 实施 → Sol 独立复核", after)
        self.assertEqual(after, self.routing.prospective_global(after, config))

    def test_prospective_global_reads_the_current_live_text_without_writing_it(self):
        config = self.routing.load_config(CONFIG)
        live_input = os.environ.get("ASTRA_LIVE_AGENTS_TEST_INPUT")
        if not live_input:
            self.skipTest("set ASTRA_LIVE_AGENTS_TEST_INPUT for the optional read-only integration check")
        live_path = Path(live_input)
        before = live_path.read_text(encoding="utf-8")
        after = self.routing.prospective_global(before, config)
        self.assertEqual(before, live_path.read_text(encoding="utf-8"))
        self.assertEqual(after, self.routing.prospective_global(after, config))

    def test_bounds_and_malformed_risk_are_validation_errors(self):
        config = self.routing.load_config(CONFIG)
        for field, value, message in (
            ("default_active_agents", 4, "default_active_agents must be at most 3"),
            ("max_deliberation_rounds", 3, "max_deliberation_rounds must be at most 2"),
            ("max_independent_verifications", 2, "max_independent_verifications must be at most 1"),
            ("max_repair_cycles", 4, "max_repair_cycles must be at most 3"),
            ("max_active_agents", True, "max_active_agents must be an integer"),
            ("schema_version", 2.0, "schema_version must be integer 2"),
        ):
            candidate = dict(config)
            candidate[field] = value
            self.assertTrue(any(message in error for error in self.routing.validate(candidate)))
        malformed = dict(config)
        malformed["risk"] = {"low": []}
        self.assertTrue(self.routing.validate(malformed))

    def test_prospective_global_rejects_missing_or_duplicated_legacy_sections(self):
        config = self.routing.load_config(CONFIG)
        missing = "## 分诊与交接\n\n高风险或方案冲突：Sol 裁决 → Terra 实施 → Sol 独立复核。\n"
        duplicate = """## 路由

x
## 分诊与交接

高风险或方案冲突：Sol 裁决 → Terra 实施 → Sol 独立复核。
## 路由

x
## 分诊与交接

"""
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.routing.prospective_global(missing, config)
        with self.assertRaisesRegex(ValueError, "exactly one"):
            self.routing.prospective_global(duplicate, config)


if __name__ == "__main__":
    unittest.main()
