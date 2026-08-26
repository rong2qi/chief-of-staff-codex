#!/usr/bin/env python3
"""Inspect Codex usage and build verifiable migration bundles."""
from __future__ import annotations

import argparse, hashlib, json, os, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LIMITS = (0.75, 0.85, 0.95)
BASE_FILES = ("manifest.json", "handoff.md", "artifacts.json", "transcript-ref.json")
AUTOMATION_FIELDS = (
    "id", "name", "kind", "target_thread_id", "status", "schedule",
    "prompt_sha256", "notification_policy",
)

def now(): return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
def home(): return Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()

def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""): h.update(chunk)
    return h.hexdigest()

def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix="." + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text); f.flush(); os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp): os.unlink(temp)

def write_json(path: Path, value: Any):
    write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

def state(ratio: float) -> str:
    return "emergency" if ratio >= LIMITS[2] else "rollover" if ratio >= LIMITS[1] else "checkpoint" if ratio >= LIMITS[0] else "normal"

def inspect(path: Path):
    meta, latest, stamp, model = {}, None, None, None
    with path.open(encoding="utf-8", errors="replace") as f:
        for line in f:
            try: event = json.loads(line)
            except json.JSONDecodeError: continue
            payload = event.get("payload", {})
            if event.get("type") == "session_meta": meta = payload
            elif event.get("type") == "event_msg" and payload.get("type") == "token_count":
                latest, stamp = payload.get("info"), event.get("timestamp")
            elif event.get("type") == "event_msg" and payload.get("type") == "task_started": model = payload.get("model") or model
    if not isinstance(latest, dict): return None
    used = (latest.get("last_token_usage") or {}).get("input_tokens")
    window = latest.get("model_context_window")
    if not isinstance(used, int) or not isinstance(window, int) or window <= 0: return None
    ratio = used / window
    return {"thread_id": meta.get("id") or meta.get("session_id"), "session_path": str(path.resolve()),
            "cwd": meta.get("cwd"), "model": model, "input_tokens": used, "model_context_window": window,
            "ratio": round(ratio, 6), "percent": round(ratio * 100, 2), "state": state(ratio),
            "sampled_at": stamp, "session_mtime": path.stat().st_mtime}

def scan(args):
    paths = [args.session_root] if args.session_root.is_file() else list(args.session_root.rglob("*.jsonl"))
    values = [v for p in paths if (v := inspect(p))]
    cutoff = datetime.now(timezone.utc).timestamp() - args.active_since_hours * 3600
    ranks = {"normal": 0, "checkpoint": 1, "rollover": 2, "emergency": 3}
    values = [v for v in values if v["session_mtime"] >= cutoff and (args.minimum_state == "all" or ranks[v["state"]] >= ranks[args.minimum_state])]
    print(json.dumps(sorted(values, key=lambda v: v["session_mtime"], reverse=True), ensure_ascii=False, indent=2)); return 0

def git(cwd: Path):
    try:
        run = lambda cmd, binary=False: subprocess.run(cmd, check=True, capture_output=True, text=not binary).stdout
        root = run(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"]).strip()
        head = run(["git", "-C", root, "rev-parse", "HEAD"]).strip()
        branch = run(["git", "-C", root, "branch", "--show-current"]).strip() or None
        raw = run(["git", "-C", root, "status", "--porcelain=v1", "-z"], True)
        dirty = [(x.decode(errors="replace")[3:]) for x in raw.split(b"\0") if x]
        return {"root": root, "head": head, "branch": branch, "dirty_paths": dirty}
    except (OSError, subprocess.CalledProcessError): return None

def object_file(path: Path):
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict): raise ValueError(f"{path} must contain an object")
    return value

def automation_duty(item: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        item["name"], item["kind"],
        json.dumps(item["schedule"], ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        item["prompt_sha256"], item["notification_policy"],
    )

def automation_records(value: Any, label: str) -> list[dict[str, Any]]:
    if not isinstance(value, list): raise ValueError(f"{label} must contain an array")
    seen_ids, seen_duties = set(), set()
    for index, item in enumerate(value):
        item_label = f"{label}[{index}]"
        if not isinstance(item, dict) or set(item) != set(AUTOMATION_FIELDS):
            raise ValueError(f"{item_label} must contain exactly {', '.join(AUTOMATION_FIELDS)}")
        for key in AUTOMATION_FIELDS:
            if key == "schedule":
                if not isinstance(item[key], (str, dict)) or not item[key]:
                    raise ValueError(f"{item_label}.schedule must be a non-empty string or object")
            elif not isinstance(item[key], str) or not item[key]:
                raise ValueError(f"{item_label}.{key} must be a non-empty string")
        if item["status"] not in {"ACTIVE", "PAUSED"}:
            raise ValueError(f"{item_label}.status must be ACTIVE or PAUSED")
        prompt_hash = item["prompt_sha256"]
        if len(prompt_hash) != 64 or any(ch not in "0123456789abcdef" for ch in prompt_hash):
            raise ValueError(f"{item_label}.prompt_sha256 must be lowercase SHA-256 hex")
        if item["id"] in seen_ids: raise ValueError("automation IDs must be unique")
        duty = automation_duty(item)
        if item["status"] == "ACTIVE" and duty in seen_duties:
            raise ValueError("duplicate ACTIVE automation duty")
        seen_ids.add(item["id"])
        if item["status"] == "ACTIVE": seen_duties.add(duty)
    return value

def automation_file(path: Path) -> list[dict[str, Any]]:
    return automation_records(json.loads(path.read_text(encoding="utf-8")), str(path))

def build(args):
    sample = inspect(args.session)
    if not sample: raise ValueError("source session has no usable token_count")
    handoff, artifacts = args.handoff.read_text(encoding="utf-8"), object_file(args.artifacts)
    automations = automation_file(args.automations)
    if not handoff.strip(): raise ValueError("handoff must not be empty")
    lineage = args.lineage_id or sample["thread_id"]
    if not lineage: raise ValueError("missing lineage ID")
    store = args.project_root / ".codex/context-migrations" if args.project_root else home() / "context-migrations"
    root = store / str(lineage); root.mkdir(parents=True, exist_ok=True)
    existing = [int(p.name) for p in root.iterdir() if p.is_dir() and p.name.isdigit()]
    number = args.migration_number or max(existing, default=0) + 1
    bundle, lock = root / f"{number:04d}", root / ".migration.lock"
    try: lock.mkdir()
    except FileExistsError: raise RuntimeError(f"migration locked: {root}")
    try:
        bundle.mkdir(); write(bundle / "handoff.md", handoff.rstrip() + "\n"); write_json(bundle / "artifacts.json", artifacts)
        write_json(bundle / "automations.json", automations)
        source = args.session.resolve(); stat = source.stat()
        ref = {"thread_id": sample["thread_id"], "path": str(source), "sha256": digest(source), "size_bytes": stat.st_size,
               "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")}
        write_json(bundle / "transcript-ref.json", ref)
        agents = home() / "AGENTS.md"; cwd = Path(sample["cwd"] or Path.cwd()); stamp = now()
        manifest = {"schema_version": 2, "lineage_id": str(lineage), "migration_number": number, "status": "checkpoint_ready",
                    "predecessor_thread_id": sample["thread_id"], "successor_thread_id": None, "title": args.title,
                    "cwd": str(cwd), "project_root": str(args.project_root.resolve()) if args.project_root else None, "model": sample["model"],
                    "context": {k: sample[k] for k in ("input_tokens", "model_context_window", "ratio", "percent", "state", "sampled_at")},
                    "source_session": ref, "git": git(cwd),
                    "global_instructions": {"path": str(agents), "sha256": digest(agents) if agents.exists() else None, "operator_salutation": "妈妈"},
                    "automation_inheritance": {"bound": bool(automations), "count": len(automations)},
                    "parity": {"bundle": "pending", "automation": "pending", "pin": "pending"},
                    "takeover": {"authority_switched": False, "predecessor_active": True, "predecessor_archived": False},
                    "checksums": {n: digest(bundle / n) for n in ("handoff.md", "artifacts.json", "transcript-ref.json", "automations.json")},
                    "created_at": stamp, "updated_at": stamp}
        write_json(bundle / "manifest.json", manifest)
    finally: lock.rmdir()
    print(json.dumps({"bundle": str(bundle), "manifest": manifest}, ensure_ascii=False, indent=2)); return 0

def verify(args):
    bundle, errors = args.bundle.resolve(), []
    manifest_path = bundle / "manifest.json"
    schema_version = None
    if manifest_path.is_file():
        try: schema_version = object_file(manifest_path).get("schema_version")
        except (OSError, ValueError, json.JSONDecodeError): pass
    if schema_version not in {1, 2}:
        errors.append("schema_version must be 1 or 2")
    files = BASE_FILES + (("automations.json",) if schema_version == 2 else ())
    for name in files:
        if not (bundle / name).is_file(): errors.append("missing: " + name)
    manifest = {}
    if not errors:
        try:
            manifest = object_file(bundle / "manifest.json"); object_file(bundle / "artifacts.json"); object_file(bundle / "transcript-ref.json")
            if manifest.get("schema_version") == 2: automation_file(bundle / "automations.json")
        except (OSError, ValueError, json.JSONDecodeError) as e: errors.append(str(e))
        checks = manifest.get("checksums", {})
        checked = ("handoff.md", "artifacts.json", "transcript-ref.json") + (("automations.json",) if manifest.get("schema_version") == 2 else ())
        for name in checked:
            if checks.get(name) != digest(bundle / name): errors.append("checksum mismatch: " + name)
        for name, expected_digest in checks.items():
            if name not in checked:
                path = bundle / name
                if not path.is_file() or expected_digest != digest(path): errors.append("checksum mismatch: " + name)
        source = manifest.get("source_session", {}); path = Path(source.get("path", ""))
        if not path.is_file(): errors.append("source session unavailable")
        elif source.get("sha256") != digest(path): errors.append("source session changed after capture")
    eligibility = "legacy_unassessed" if schema_version == 1 and not errors else "eligible_for_parity" if schema_version == 2 and not errors else "invalid"
    print(json.dumps({"bundle": str(bundle), "valid": not errors, "migration_eligibility": eligibility, "errors": errors}, ensure_ascii=False, indent=2)); return 0 if not errors else 1

def migration_parity(args):
    bundle, errors, bundle_ok = args.bundle.resolve(), [], True
    manifest_path = bundle / "manifest.json"
    try:
        manifest = object_file(manifest_path)
        expected = automation_file(bundle / "automations.json")
        evidence = object_file(args.live_automations)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc)); manifest, expected, evidence, bundle_ok = {}, [], {}, False
    if manifest.get("schema_version") != 2:
        errors.append("bundle parity requires schema_version 2"); bundle_ok = False
    predecessor_thread_id = manifest.get("predecessor_thread_id")
    if not isinstance(predecessor_thread_id, str) or not predecessor_thread_id:
        errors.append("bundle predecessor thread ID missing"); bundle_ok = False
    if args.successor_thread_id == predecessor_thread_id:
        errors.append("successor thread ID must differ from predecessor")
    recorded_successor = manifest.get("successor_thread_id")
    if recorded_successor not in {None, args.successor_thread_id}:
        errors.append("successor thread ID mismatch")
    for item in expected:
        if item["target_thread_id"] != predecessor_thread_id:
            errors.append(f"automation {item['id']} is not bound to the predecessor task")
    for name in ("handoff.md", "artifacts.json", "transcript-ref.json", "automations.json"):
        path = bundle / name
        if not path.is_file() or manifest.get("checksums", {}).get(name) != digest(path):
            errors.append("bundle checksum mismatch: " + name); bundle_ok = False
    source_ref = manifest.get("source_session", {})
    source_path = Path(source_ref.get("path", ""))
    if not source_path.is_file() or source_ref.get("sha256") != digest(source_path):
        errors.append("bundle source session parity failed"); bundle_ok = False
    if evidence.get("evidence_kind") != "live_automation_view":
        errors.append("live automation evidence missing; reference or receipt is not proof")
    if not isinstance(evidence.get("observed_at"), str) or not evidence.get("observed_at"):
        errors.append("live automation evidence observed_at missing")
    if evidence.get("query_scope") != "predecessor_target_and_recorded_ids":
        errors.append("live automation evidence query scope is invalid")
    if evidence.get("queried_predecessor_thread_id") != predecessor_thread_id:
        errors.append("live automation evidence predecessor target mismatch")
    recorded_ids = evidence.get("queried_recorded_automation_ids")
    if recorded_ids != [item["id"] for item in expected]:
        errors.append("live automation evidence recorded-ID query mismatch")
    authorization = evidence.get("authorization")
    if not isinstance(authorization, dict) or authorization.get("rebind_allowed") is not True:
        errors.append("existing automation rebind authorization missing")
        authorization = {}
    live = evidence.get("automations")
    absent = evidence.get("absent_automation_ids", [])
    if not isinstance(live, list) or not isinstance(absent, list) or not all(isinstance(x, str) and x for x in absent):
        errors.append("live automation evidence is malformed"); live = []
    live_path = args.live_automations
    if not errors:
        try: live = automation_records(live, f"{live_path}.automations")
        except ValueError as exc: errors.append(str(exc))
    live_by_duty: dict[tuple[str, str, str, str, str], list[dict[str, Any]]] = {}
    for item in live:
        live_by_duty.setdefault(automation_duty(item), []).append(item)
    for original in expected:
        matches = live_by_duty.get(automation_duty(original), [])
        if not matches:
            matches = [
                item for item in live
                if item["name"] == original["name"] and item["kind"] == original["kind"]
            ]
        if len(matches) != 1:
            errors.append(f"automation duty {original['name']}/{original['kind']} requires exactly one live automation")
            continue
        current = matches[0]
        if current["id"] != original["id"] and original["id"] not in absent:
            errors.append(f"automation {original['id']} was replaced without live missing evidence")
        if current["id"] != original["id"] and authorization.get("minimal_equivalent_if_missing_allowed") is not True:
            errors.append(f"automation {original['id']} replacement lacks existing authorization")
        if current["id"] != original["id"] and (not isinstance(authorization.get("authorization_ref"), str) or not authorization.get("authorization_ref")):
            errors.append(f"automation {original['id']} replacement authorization reference missing")
        if current["target_thread_id"] != args.successor_thread_id: errors.append(f"automation {original['id']} target mismatch")
        for key in ("status", "schedule", "prompt_sha256", "notification_policy"):
            if current[key] != original[key]: errors.append(f"automation {original['id']} {key} mismatch")
    automation_parity_ok = not errors
    pin_evidence = None
    pin_verified = False
    if args.pin_applicable:
        if not args.pin_evidence:
            errors.append("applicable pin parity live evidence missing")
        else:
            try: pin_evidence = object_file(args.pin_evidence)
            except (OSError, ValueError, json.JSONDecodeError) as exc: errors.append(str(exc)); pin_evidence = {}
            if pin_evidence.get("evidence_kind") != "live_list_threads" or not isinstance(pin_evidence.get("observed_at"), str) or not pin_evidence.get("observed_at"):
                errors.append("applicable pin parity requires fresh live list_threads evidence")
            pinned_ids = pin_evidence.get("pinned_thread_ids")
            if pin_evidence.get("successor_thread_id") != args.successor_thread_id or not isinstance(pinned_ids, list) or args.successor_thread_id not in pinned_ids:
                errors.append("applicable pin parity exact successor ID missing")
            pin_verified = not any("pin parity" in item for item in errors)
    historical = evidence.get("historical_state")
    if args.historical_repair:
        if historical != {"predecessor": "archived", "successor": "active", "repair": "without_unarchive_delete_or_duplicate"}:
            errors.append("historical repair state evidence is invalid")
        if manifest.get("takeover") != {"authority_switched": True, "predecessor_active": False, "predecessor_archived": True}:
            errors.append("historical repair requires an already archived predecessor manifest")
    status = ("REPAIR_VERIFIED" if args.historical_repair else "MIGRATION_READY") if not errors else "MIGRATION_BLOCKED"
    result = {"status": status, "bundle_parity": bundle_ok,
              "automation_parity": automation_parity_ok,
              "pin_parity": (not args.pin_applicable) or pin_verified,
              "failure_record": None if not errors else "automation_rebind_failed",
              "keep_predecessor_active_unarchived": bool(errors) and not args.historical_repair, "errors": errors}
    lock = bundle.parent / ".migration.lock"
    try: lock.mkdir()
    except FileExistsError: raise RuntimeError(f"migration locked: {bundle.parent}")
    try:
        evidence_name = "automation-parity.json"
        write_json(bundle / evidence_name, {
            "checked_at": now(), "successor_thread_id": args.successor_thread_id,
            "pin_applicable": args.pin_applicable,
            "pin_evidence": pin_evidence,
            "live_evidence": evidence, "historical_repair": args.historical_repair, "result": result,
        })
        manifest["checksums"][evidence_name] = digest(bundle / evidence_name)
        manifest["parity"] = {
            "bundle": "verified" if result["bundle_parity"] else "failed",
            "automation": ("verified" if expected else "not_applicable") if result["automation_parity"] else "failed",
            "pin": ("verified" if pin_verified else "failed") if args.pin_applicable else "not_applicable",
        }
        manifest["status"] = "verified" if not errors else "migration_blocked"
        manifest["updated_at"] = now()
        if errors:
            manifest["failure_record"] = "automation_rebind_failed"
            if not args.historical_repair:
                manifest["takeover"] = {"authority_switched": False, "predecessor_active": True, "predecessor_archived": False}
        else:
            manifest.pop("failure_record", None)
            if recorded_successor is None:
                manifest["successor_thread_id"] = args.successor_thread_id
            if args.historical_repair:
                manifest["takeover"] = {"authority_switched": True, "predecessor_active": False, "predecessor_archived": True}
        write_json(bundle / "manifest.json", manifest)
    finally: lock.rmdir()
    print(json.dumps(result, ensure_ascii=False, indent=2)); return 0 if not errors else 1

def cli():
    p = argparse.ArgumentParser(); sub = p.add_subparsers(required=True)
    s = sub.add_parser("scan"); s.add_argument("--session-root", type=Path, default=home() / "sessions"); s.add_argument("--minimum-state", choices=("all", "normal", "checkpoint", "rollover", "emergency"), default="checkpoint"); s.add_argument("--active-since-hours", type=float, default=168); s.set_defaults(run=scan)
    b = sub.add_parser("build"); b.add_argument("--session", type=Path, required=True); b.add_argument("--title", required=True); b.add_argument("--handoff", type=Path, required=True); b.add_argument("--artifacts", type=Path, required=True); b.add_argument("--automations", type=Path, required=True); b.add_argument("--project-root", type=Path); b.add_argument("--lineage-id"); b.add_argument("--migration-number", type=int); b.set_defaults(run=build)
    v = sub.add_parser("verify"); v.add_argument("--bundle", type=Path, required=True); v.set_defaults(run=verify)
    m = sub.add_parser("verify-migration"); m.add_argument("--bundle", type=Path, required=True); m.add_argument("--live-automations", type=Path, required=True); m.add_argument("--successor-thread-id", required=True); m.add_argument("--pin-applicable", action="store_true"); m.add_argument("--pin-evidence", type=Path); m.add_argument("--historical-repair", action="store_true"); m.set_defaults(run=migration_parity)
    return p

def main():
    args = cli().parse_args()
    try: return args.run(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr); return 2

if __name__ == "__main__": raise SystemExit(main())
