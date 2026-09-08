#!/usr/bin/env python3
"""Validate and render the Astra routing *candidate*; never mutates live files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 and earlier
    raise SystemExit("astra_routing.py requires Python 3.11+ (tomllib); it will not install dependencies.")


EXPECTED_MODELS = {
    "astra": "gpt-6-astra",
    "sol": "gpt-5.6-sol",
    "terra": "gpt-5.6-terra",
    "luna": "gpt-5.6-luna",
}
LEGACY_ROUTES = {
    "low": ["terra-implementer"],
    "medium": ["luna-scout", "terra-implementer", "luna-scout"],
    "high": ["sol-arbiter", "terra-implementer", "sol-arbiter"],
}
LEGACY_ROUTING_SECTION = """## 路由

| 模型 | 默认职责 |
| --- | --- |
| `gpt-5.6-sol` | 架构裁决及高风险复核 |
| `gpt-5.6-terra` | 唯一实施者 |
| `gpt-5.6-luna` | 低成本、只读的独立检查 |

保留用户显式指定的模型。模型选择是默认路由而非正确性保证；高风险结论仍需要证据和独立复核。

"""
ROUTING_START = "<!-- astra-chief-routing:managed:start -->"
ROUTING_END = "<!-- astra-chief-routing:managed:end -->"
OLD_HIGH_RISK_LINE = "高风险或方案冲突：Sol 裁决 → Terra 实施 → Sol 独立复核。"
NEW_HIGH_RISK_LINE = "复杂/跨模块高风险：Astra 裁决 → Terra 实施 → Sol 独立复核；明确高风险：Sol 裁决 → Terra 实施 → Sol 独立复核。"
OLD_HIGH_RISK_BULLET = "- " + OLD_HIGH_RISK_LINE
NEW_HIGH_RISK_BULLET = "- " + NEW_HIGH_RISK_LINE


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open("rb") as source:
        return tomllib.load(source)


def _is_int(value: Any) -> bool:
    return type(value) is int


def validate(config: dict[str, Any]) -> list[str]:
    """Return deterministic validation errors; absent/false enablement stays inert."""
    errors: list[str] = []
    enabled = config.get("enabled", False)
    if "enabled" in config and type(enabled) is not bool:
        errors.append("enabled must be a boolean")

    limits = (
        ("default_active_agents", 1),
        ("max_active_agents", 1),
        ("max_parallel_business_lanes", 1),
        ("max_heavy_local_tasks", 1),
        ("max_deliberation_rounds", 1),
        ("max_independent_verifications", 1),
        ("max_repair_cycles", 1),
    )
    for field, minimum in limits:
        if field in config and (not _is_int(config[field]) or config[field] < minimum):
            errors.append(f"{field} must be an integer at least {minimum}")

    if _is_int(config.get("default_active_agents")) and config["default_active_agents"] > 3:
        errors.append("default_active_agents must be at most 3")
    if _is_int(config.get("default_active_agents")) and _is_int(config.get("max_active_agents")):
        if config["default_active_agents"] > config["max_active_agents"]:
            errors.append("default_active_agents must be at most max_active_agents")
    if _is_int(config.get("max_active_agents")) and config["max_active_agents"] > 4:
        errors.append("max_active_agents must be at most 4")
    if _is_int(config.get("max_parallel_business_lanes")) and config["max_parallel_business_lanes"] > 2:
        errors.append("max_parallel_business_lanes must be at most 2")
    if _is_int(config.get("max_heavy_local_tasks")) and config["max_heavy_local_tasks"] > 1:
        errors.append("max_heavy_local_tasks must be at most 1")
    if _is_int(config.get("max_deliberation_rounds")) and config["max_deliberation_rounds"] > 2:
        errors.append("max_deliberation_rounds must be at most 2")
    if _is_int(config.get("max_independent_verifications")) and config["max_independent_verifications"] > 1:
        errors.append("max_independent_verifications must be at most 1")
    # Legacy routing remains capped at three.  An enabled autonomy policy may
    # create a new phase-local allowance only through retry-policy evidence.
    if _is_int(config.get("max_repair_cycles")) and config["max_repair_cycles"] > 3:
        errors.append("max_repair_cycles must be at most 3")

    if enabled is True:
        if not _is_int(config.get("schema_version")) or config.get("schema_version") != 2:
            errors.append("schema_version must be integer 2")
        if config.get("schema_version") != 2 or not _is_int(config.get("schema_version")):
            errors.append("enabled Astra routing requires schema_version 2")
        for field, _minimum in limits:
            if field not in config:
                errors.append(f"enabled Astra routing requires {field}")
        models = config.get("models")
        if not isinstance(models, dict):
            errors.append("enabled Astra routing requires a models table")
        else:
            for name, exact_model in EXPECTED_MODELS.items():
                if models.get(name) != exact_model:
                    errors.append(f"models.{name} must equal {exact_model}")
        risk = config.get("risk")
        expected_routes = {
            "low": LEGACY_ROUTES["low"],
            "medium": LEGACY_ROUTES["medium"],
            "high": ["astra-arbiter", "terra-implementer", "sol-arbiter"],
        }
        if not isinstance(risk, dict):
            errors.append("enabled Astra routing requires risk routes")
        else:
            for name, expected in expected_routes.items():
                entry = risk.get(name)
                if not isinstance(entry, dict) or entry.get("route") != expected:
                    errors.append(f"risk.{name}.route must equal {expected}")
    return errors


def route(
    config: dict[str, Any],
    *,
    risk: str,
    complex_task: bool,
    astra_available: bool,
    runtime_slots: int,
    independent_benefit: bool = False,
    explicit_model: str | None = None,
) -> dict[str, Any]:
    """Return a recommendation only; it cannot invoke agents or certify a PASS."""
    if risk not in LEGACY_ROUTES:
        raise ValueError("risk must be low, medium, or high")
    if not _is_int(runtime_slots) or runtime_slots < 1:
        raise ValueError("runtime_slots must be a positive integer")
    errors = validate(config)
    if errors:
        raise ValueError("invalid routing config: " + "; ".join(errors))
    enabled = config.get("enabled") is True
    if runtime_slots == 1 and (risk != "low" or complex_task):
        return {
            "roles": [], "writer": None, "model": explicit_model, "astra_enabled": enabled,
            "downgrade": None, "use_fourth_slot": False, "maximum_active_agents": 1,
            "status": "blocked", "blocked_reason": "capacity_shortfall",
            "independent_safety_review_required": risk == "high", "independent_safety_review_passed": False,
            "runtime_switched": False,
        }
    if explicit_model is not None:
        independent = risk == "high"
        return {
            "roles": ["explicit-model"] + (["sol-arbiter"] if independent else []),
            "model": explicit_model,
            "writer": "explicit-model",
            "astra_enabled": enabled,
            "downgrade": None,
            "use_fourth_slot": False,
            "maximum_active_agents": min(runtime_slots, config.get("default_active_agents", 3)),
            "status": "recommended",
            "blocked_reason": None,
            "independent_safety_review_required": independent,
            "independent_safety_review_passed": False,
            "runtime_switched": False,
        }

    fourth_slot = bool(enabled and independent_benefit and runtime_slots >= 4 and config.get("max_active_agents", 3) >= 4)
    if enabled and risk == "high" and complex_task:
        if astra_available:
            roles = ["astra-arbiter", "terra-implementer", "sol-arbiter"]
            downgrade = None
        else:
            roles = LEGACY_ROUTES["high"]
            downgrade = "astra_unavailable_to_sol"
    else:
        roles = LEGACY_ROUTES[risk]
        downgrade = None
    return {
        "roles": roles,
        "writer": "terra-implementer" if "terra-implementer" in roles else None,
        "astra_enabled": enabled,
        "downgrade": downgrade,
        "use_fourth_slot": fourth_slot,
        "maximum_active_agents": 4 if fourth_slot else min(runtime_slots, config.get("default_active_agents", 3)),
        "status": "recommended",
        "blocked_reason": None,
        "independent_safety_review_required": risk == "high",
        "independent_safety_review_passed": False,
        "runtime_switched": False,
    }


def generate_routing_section(config: dict[str, Any]) -> str:
    if config.get("enabled") is not True or validate(config):
        raise ValueError("invalid routing config: " + "; ".join(validate(config)))
    return f"""## 路由

{ROUTING_START}
| 模型 | 默认职责 |
| --- | --- |
| `gpt-6-astra` | 复杂 Chief 的综合裁决；默认 medium，复杂因果链才 high |
| `gpt-5.6-sol` | 高风险独立复核；high |
| `gpt-5.6-terra` | 唯一实施者；medium |
| `gpt-5.6-luna` | 低成本、只读的独立检查；low |

模型选择优先遵从用户显式指定。简单任务不机械 fanout；默认主代理占一槽、至多三槽，只有独立收益明确且运行时有四槽时才使用第四槽。最多两条业务 lane，最多一条本机重任务；共享 Git index 仅由唯一整合者操作。

该候选为非 Codex 原生运行时配置（not a Codex-native runtime configuration）：它只提供路由建议，不会切换运行时、创建代理、写入全局或安装配置。Astra 不可用时明确降级至 Sol。无独立安全复核不得判 PASS（no PASS without an independent safety review）。legacy 保留历史额度；启用 autonomy 后，真实新阶段仅可按已记录数值本地准备限制更新其 phase-local 三轮额度。暂停、权限、安全、拒绝、真实数据、生产和外发边界不重置，旧任务更窄的受保护合同优先。
{ROUTING_END}
"""


def generate_managed_block(config: dict[str, Any]) -> str:
    """Render an independently reviewable global candidate block to stdout only."""
    return generate_routing_section(config)


def prospective_global(text: str, config: dict[str, Any]) -> str:
    """Return a strict prospective global text without writing it anywhere."""
    section = generate_routing_section(config)
    starts = text.count("## 路由\n")
    ends = text.count("## 分诊与交接\n")
    if starts != 1 or ends != 1:
        raise ValueError("expected exactly one routing section and exactly one triage section")
    start = text.index("## 路由\n")
    end = text.index("## 分诊与交接\n")
    if end <= start:
        raise ValueError("expected routing section before triage section")
    current = text[start:end]
    triage_end = text.find("\n## ", end + 1)
    if triage_end == -1:
        triage_end = len(text)
    triage = text[end:triage_end]
    new_count = text.count(NEW_HIGH_RISK_LINE)
    old_count = text.count(OLD_HIGH_RISK_LINE)
    if current == section and new_count == 1 and old_count == 0:
        return text
    if current != LEGACY_ROUTING_SECTION or old_count != 1 or new_count != 0 or triage.count(OLD_HIGH_RISK_BULLET) != 1:
        raise ValueError("legacy routing text did not match exactly; refusing ambiguous rewrite")
    result = text[:start] + section + text[end:].replace(OLD_HIGH_RISK_BULLET, NEW_HIGH_RISK_BULLET, 1)
    if result.count(OLD_HIGH_RISK_LINE) != 0 or result.count(NEW_HIGH_RISK_LINE) != 1:
        raise ValueError("postcondition failed; refusing ambiguous rewrite")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate or render Astra routing candidates; never writes files.")
    parser.add_argument("command", choices=("validate", "route", "generate"))
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--risk", choices=("low", "medium", "high"), default="low")
    parser.add_argument("--complex-task", action="store_true")
    parser.add_argument("--astra-available", action="store_true")
    parser.add_argument("--runtime-slots", type=int, default=3)
    parser.add_argument("--independent-benefit", action="store_true")
    parser.add_argument("--explicit-model")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    if args.command == "validate":
        errors = validate(config)
        print(json.dumps({"valid": not errors, "errors": errors}, ensure_ascii=False, sort_keys=True))
        return 0 if not errors else 1
    if args.command == "generate":
        print(generate_managed_block(config), end="")
        return 0
    print(json.dumps(route(config, risk=args.risk, complex_task=args.complex_task, astra_available=args.astra_available, runtime_slots=args.runtime_slots, independent_benefit=args.independent_benefit, explicit_model=args.explicit_model), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
