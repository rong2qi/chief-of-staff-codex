#!/usr/bin/env python3
"""Risk-based, non-blocking control for evidence-aware Chief Testing.

This module classifies policy and scheduling state only. It does not execute
tests, send messages, issue a Testing gate, install skills, build artifacts, or
authorize promotion. Git evidence remains owned by ``testing_evidence.py``.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


SCHEMA = "CHIEF_TESTING_CONTROL_V1"
JUSTIFICATION = "TESTING_JUSTIFICATION_V1"
RISK_LEVELS = {"L0", "L1", "L2", "L3"}
REAL_TESTING_VERDICTS = {
    "TESTING_GATE_PASS",
    "TESTING_GATE_FAIL",
    "TESTING_INFRA_ERROR",
}
WORK_PRIORITIES = {
    "USER_DECISION": 10,
    "IMPLEMENTER_COMPLETED": 20,
    "BUILD_FAILED": 30,
    "BUILD_SUCCEEDED": 31,
    "TESTING_GATE_FAIL": 40,
    "TESTING_GATE_PASS": 41,
    "TESTING_INFRA_ERROR": 42,
    "TESTING_SCOPE_CHANGED": 43,
}
TELEMETRY_SUFFIXES = (
    "_ACK",
    "_RECEIVED",
    "_QUEUED",
    "_STARTED",
    "_READY",
    "_HEARTBEAT",
    "_PROGRESS",
    "_RETRY_STATUS",
)


class TestingControlError(ValueError):
    pass


def _strings(value, label):
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) and item.strip() for item in value):
        raise TestingControlError(f"{label} must contain nonempty strings")
    return sorted(set(value))


def classify_event(event):
    """Classify before expensive reasoning; telemetry is record-only."""
    if not isinstance(event, dict) or not isinstance(event.get("type"), str):
        raise TestingControlError("event requires a type")
    kind = event["type"]
    if kind == "TESTING_SCOPE_CHANGED":
        risks = event.get("new_risk")
        if isinstance(risks, str):
            risks = [risks]
        if risks and all(isinstance(item, str) and item.strip() for item in risks):
            return "decision"
        return "telemetry"
    if kind in REAL_TESTING_VERDICTS:
        return "decision"
    if ((kind.startswith("TESTING_") and kind.endswith(TELEMETRY_SUFFIXES))
            or kind in {"HEARTBEAT", "PROGRESS", "RETRY_STATUS"}):
        return "telemetry"
    return "work"


def process_events(events, *, build_critical_path=False):
    """Filter telemetry and prioritize real work without scheduling a wait."""
    if not isinstance(events, list):
        raise TestingControlError("events must be a list")
    telemetry, actionable = [], []
    for index, event in enumerate(events):
        category = classify_event(event)
        recorded = {"type": event["type"], "category": category, "recorded": True}
        if category == "telemetry":
            telemetry.append(recorded)
        else:
            actionable.append((WORK_PRIORITIES.get(event["type"], 100), index, dict(event)))
    actionable.sort(key=lambda item: (item[0], item[1]))
    queue = [item[2] for item in actionable]
    return {
        "schema": SCHEMA,
        "status": "ACTIONABLE_EVENT" if queue else "TELEMETRY_RECORDED",
        "next_event": queue[0] if queue else None,
        "actionable_events": queue,
        "telemetry": telemetry,
        "reasoning_turns": 1 if queue else 0,
        "wait": False,
        "retry": False,
        "build_critical_path": bool(build_critical_path),
    }


def _pending_rows(delta):
    if not isinstance(delta, dict) or not isinstance(delta.get("impact_map"), list):
        raise TestingControlError("delta requires an impact_map")
    payload = delta.get("testing_payload")
    if not isinstance(payload, dict) or not isinstance(payload.get("candidate_sha"), str) or not isinstance(payload.get("tests"), list):
        raise TestingControlError("delta requires an exact testing_payload")
    pending_ids = {test.get("test_id") for test in payload["tests"] if isinstance(test, dict)}
    if None in pending_ids or len(pending_ids) != len(payload["tests"]):
        raise TestingControlError("testing payload requires unique test identities")
    rows = [row for row in delta["impact_map"] if isinstance(row, dict) and row.get("test_id") in pending_ids]
    if {row.get("test_id") for row in rows} != pending_ids:
        raise TestingControlError("testing payload and impact map disagree")
    return payload, rows


def decide_testing(delta, *, risk_level, local_evidence_sufficient=False,
                   new_risks=None, why_local_insufficient="",
                   sync_testing_required=False):
    """Return the smallest justified validation path for one candidate.

    A new candidate or stage is deliberately absent from the trigger logic.
    A Testing request needs a changed input, dependency impact, or explicit new
    risk. L0 always stays deterministic/local; L1 stays local when its evidence
    is sufficient. Only L3 or an explicit synchronous contract blocks the
    corresponding dangerous action.
    """
    if risk_level not in RISK_LEVELS:
        raise TestingControlError("risk_level must be L0, L1, L2, or L3")
    if type(local_evidence_sufficient) is not bool or type(sync_testing_required) is not bool:
        raise TestingControlError("policy flags must be booleans")
    risks = _strings(new_risks, "new_risks")
    payload, rows = _pending_rows(delta)
    if not payload["tests"]:
        return {
            "schema": SCHEMA,
            "status": "INHERITED_PASS",
            "candidate_state": "LOCAL_CANDIDATE_READY",
            "testing_request": None,
            "blocking": False,
            "wait": False,
        }

    changed = sorted({path for row in rows for path in row.get("changed_paths", [])
                      if isinstance(path, str) and path})
    dependency_impact = sorted({reason for row in rows for reason in row.get("reasons", [])
                                if isinstance(reason, str) and "dependenc" in reason.lower()})
    integration_rows = [row for row in rows if row.get("classification") == "INTEGRATION_ONLY"]
    if integration_rows:
        risks = sorted(set(risks + ["new cross-component wiring or shared-state interaction"]))
    invalidated = [{
        "test_id": row.get("test_id"),
        "source_candidate_sha": row.get("source_candidate_sha"),
        "evidence_id": row.get("evidence_hash"),
        "reasons": list(row.get("reasons", [])),
    } for row in rows if row.get("classification") == "RETEST_REQUIRED"]

    trigger_present = bool(changed or dependency_impact or risks)
    local_only = risk_level == "L0" or (risk_level == "L1" and local_evidence_sufficient)
    if local_only or not trigger_present:
        status = "LOCAL_CHECK_PASS" if local_evidence_sufficient else "LOCAL_VALIDATION_REQUIRED"
        return {
            "schema": SCHEMA,
            "status": status,
            "candidate_state": "LOCAL_CANDIDATE_READY" if local_evidence_sufficient else "LOCAL_CANDIDATE",
            "testing_request": None,
            "reason": "risk is covered by deterministic/local evidence" if local_only
                      else "no changed input, dependency impact, or new risk",
            "blocking": False,
            "wait": False,
        }

    if not isinstance(why_local_insufficient, str) or not why_local_insufficient.strip():
        raise TestingControlError("a Testing request requires why local evidence is insufficient")
    previous = sorted({
        (row.get("source_candidate_sha") or "", row.get("evidence_hash") or "")
        for row in delta["impact_map"] if isinstance(row, dict)
        and (row.get("source_candidate_sha") or row.get("evidence_hash"))
    })
    justification = {
        "schema": JUSTIFICATION,
        "current_candidate_sha": payload["candidate_sha"],
        "previous_tested_sha_evidence": [
            {"candidate_sha": sha, "evidence_id": evidence_id} for sha, evidence_id in previous
        ],
        "changed_paths_assets": changed,
        "dependency_impact": dependency_impact,
        "new_risk": risks,
        "invalidated_evidence": invalidated,
        "requested_testing_scope": [
            {"test_id": test["test_id"], "scope": test.get("scope", "")} for test in payload["tests"]
        ],
        "why_deterministic_local_evidence_is_insufficient": why_local_insufficient.strip(),
    }
    blocking = risk_level == "L3" or sync_testing_required
    return {
        "schema": SCHEMA,
        "status": "TESTING_REQUESTED",
        "candidate_state": "LOCAL_CANDIDATE_READY / TESTING_PENDING",
        "testing_request": {"testing_payload": payload, "justification": justification},
        "blocking": blocking,
        "blocked_action": "dangerous promotion" if blocking else None,
        "wait": False,
    }


def consume_delivery(state, result):
    """Classify one delivery result with one automatic retry maximum."""
    attempts = state.get("attempts") if isinstance(state, dict) else None
    if not isinstance(attempts, int) or attempts < 1 or attempts > 2:
        raise TestingControlError("delivery state attempts must be 1 or 2")
    if not isinstance(result, dict):
        infra = True
    else:
        status = result.get("status")
        items = result.get("items")
        valid_verdict = (status in {"TESTING_GATE_PASS", "TESTING_GATE_FAIL"}
                         and isinstance(items, list) and bool(items))
        infra = (status in {"timeout", "transport_failure", "turn_error", "no_report"}
                 or items == [] or (status is None and not result.get("report"))
                 or (status in {"TESTING_GATE_PASS", "TESTING_GATE_FAIL"} and not valid_verdict))
        if valid_verdict:
            return {"schema": SCHEMA, "status": status, "attempts": attempts,
                    "product_failed": status == "TESTING_GATE_FAIL", "retry": False, "wait": False}
    if not infra:
        raise TestingControlError("Testing delivery result has no recognized verdict")
    if attempts == 1:
        return {"schema": SCHEMA, "status": "RETRY_TESTING_DELIVERY", "attempts": 2,
                "product_failed": False, "retry": True, "wait": False}
    return {"schema": SCHEMA, "status": "TESTING_INFRA_ERROR", "attempts": 2,
            "candidate_state": "LOCAL_CANDIDATE_READY / TESTING_INFRA_ERROR",
            "product_failed": False, "retry": False, "wait": False}


def schedule_modules(modules):
    """Continue independent modules while only a non-synchronous gate is pending."""
    if not isinstance(modules, list) or not modules:
        raise TestingControlError("modules must be a nonempty list")
    runnable, blocking, pending_nonblocking = [], [], []
    for module in modules:
        if not isinstance(module, dict) or not isinstance(module.get("module_id"), str):
            raise TestingControlError("each module requires module_id")
        risk = module.get("risk_level", "L1")
        if risk not in RISK_LEVELS:
            raise TestingControlError("module risk_level is invalid")
        pending = module.get("testing_status") in {"TESTING_PENDING", "TESTING_INFRA_ERROR"}
        gate_blocks = pending and (risk == "L3" or module.get("sync_testing_required") is True)
        if gate_blocks:
            blocking.append(module["module_id"])
        elif module.get("runnable") is True:
            runnable.append(module["module_id"])
        elif pending:
            pending_nonblocking.append(module["module_id"])
    if runnable:
        status, wait = "CONTINUE_RUNNABLE_MODULE", False
    elif pending_nonblocking:
        status, wait = "LOCAL_CANDIDATE_READY / TESTING_PENDING", False
    elif blocking:
        status, wait = "WAIT_SYNC_TESTING_GATE", True
    else:
        status, wait = "COMPLETE_OR_NO_RUNNABLE_WORK", False
    return {"schema": SCHEMA, "status": status, "next_module": runnable[0] if runnable else None,
            "runnable_modules": runnable, "blocked_modules": blocking,
            "pending_nonblocking_modules": pending_nonblocking, "wait": wait}


def creative_iteration(revisions, *, risk_level="L1", sync_testing_required=False):
    """Batch a visual fast loop into at most one risk-justified validation round."""
    if risk_level not in RISK_LEVELS or not isinstance(revisions, list):
        raise TestingControlError("creative iteration requires revisions and a valid risk level")
    risks, boundaries = [], 0
    for revision in revisions:
        if not isinstance(revision, dict):
            raise TestingControlError("creative revisions must be objects")
        risks.extend(_strings(revision.get("new_risks"), "new_risks"))
        if revision.get("structure_changed"):
            risks.append("frozen visual structure changed")
        if revision.get("business_behavior_changed"):
            risks.append("business behavior changed")
        if revision.get("asset_provenance_changed"):
            risks.append("asset license or provenance changed")
        if revision.get("runtime_integration_changed"):
            risks.append("runtime integration changed")
        boundaries += int(revision.get("meaningful_boundary") is True)
    risks = sorted(set(risks))
    rounds = 1 if risks else 0
    return {"schema": SCHEMA, "status": "BATCHED_TESTING_BOUNDARY" if rounds else "CREATIVE_FAST_LOOP",
            "revision_count": len(revisions), "testing_round_trips": rounds,
            "new_risk": risks, "meaningful_boundaries": boundaries,
            "blocking": bool(rounds and (risk_level == "L3" or sync_testing_required)), "wait": False}


def replay_dogfood(fixture):
    """Replay named v2.0.x incidents through the same policy functions."""
    if not isinstance(fixture, dict) or fixture.get("schema") != "CHIEF_TESTING_DOGFOOD_V1":
        raise TestingControlError("unsupported dogfood fixture")
    results = []
    for case in fixture.get("cases", []):
        name, kind = case.get("name"), case.get("kind")
        if kind == "decision":
            after = decide_testing(case["delta"], **case["policy"])
        elif kind == "events":
            after = process_events(case["events"], build_critical_path=case.get("build_critical_path", False))
        elif kind == "modules":
            after = schedule_modules(case["modules"])
        elif kind == "creative":
            after = creative_iteration(case["revisions"], **case.get("policy", {}))
        else:
            raise TestingControlError("unknown dogfood case kind")
        results.append({"name": name, "before": case.get("before"), "after": after,
                        "expect": case.get("expect")})
    return {"schema": "CHIEF_TESTING_DOGFOOD_RESULT_V1", "results": results}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("events", "decide", "delivery", "schedule", "creative", "dogfood"))
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        request = json.loads(args.request.read_text(encoding="utf-8"))
        if args.command == "events":
            result = process_events(request["events"], build_critical_path=request.get("build_critical_path", False))
        elif args.command == "decide":
            result = decide_testing(request["delta"], **request["policy"])
        elif args.command == "delivery":
            result = consume_delivery(request["state"], request["result"])
        elif args.command == "schedule":
            result = schedule_modules(request["modules"])
        elif args.command == "creative":
            result = creative_iteration(request["revisions"], **request.get("policy", {}))
        else:
            result = replay_dogfood(request)
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        result = {"schema": SCHEMA, "status": "POLICY_ERROR", "error": str(exc)}
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
