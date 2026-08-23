#!/usr/bin/env python3
"""Inspect Codex usage and build verifiable migration bundles."""
from __future__ import annotations

import argparse, hashlib, json, os, subprocess, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LIMITS = (0.75, 0.85, 0.95)
FILES = ("manifest.json", "handoff.md", "artifacts.json", "transcript-ref.json")

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

def build(args):
    sample = inspect(args.session)
    if not sample: raise ValueError("source session has no usable token_count")
    handoff, artifacts = args.handoff.read_text(encoding="utf-8"), object_file(args.artifacts)
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
        source = args.session.resolve(); stat = source.stat()
        ref = {"thread_id": sample["thread_id"], "path": str(source), "sha256": digest(source), "size_bytes": stat.st_size,
               "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")}
        write_json(bundle / "transcript-ref.json", ref)
        agents = home() / "AGENTS.md"; cwd = Path(sample["cwd"] or Path.cwd()); stamp = now()
        manifest = {"schema_version": 1, "lineage_id": str(lineage), "migration_number": number, "status": "checkpoint_ready",
                    "predecessor_thread_id": sample["thread_id"], "successor_thread_id": None, "title": args.title,
                    "cwd": str(cwd), "project_root": str(args.project_root.resolve()) if args.project_root else None, "model": sample["model"],
                    "context": {k: sample[k] for k in ("input_tokens", "model_context_window", "ratio", "percent", "state", "sampled_at")},
                    "source_session": ref, "git": git(cwd),
                    "global_instructions": {"path": str(agents), "sha256": digest(agents) if agents.exists() else None, "operator_salutation": "妈妈"},
                    "checksums": {n: digest(bundle / n) for n in ("handoff.md", "artifacts.json", "transcript-ref.json")},
                    "created_at": stamp, "updated_at": stamp}
        write_json(bundle / "manifest.json", manifest)
    finally: lock.rmdir()
    print(json.dumps({"bundle": str(bundle), "manifest": manifest}, ensure_ascii=False, indent=2)); return 0

def verify(args):
    bundle, errors = args.bundle.resolve(), []
    for name in FILES:
        if not (bundle / name).is_file(): errors.append("missing: " + name)
    manifest = {}
    if not errors:
        try: manifest = object_file(bundle / "manifest.json"); object_file(bundle / "artifacts.json"); object_file(bundle / "transcript-ref.json")
        except (OSError, ValueError, json.JSONDecodeError) as e: errors.append(str(e))
        checks = manifest.get("checksums", {})
        for name in ("handoff.md", "artifacts.json", "transcript-ref.json"):
            if checks.get(name) != digest(bundle / name): errors.append("checksum mismatch: " + name)
        source = manifest.get("source_session", {}); path = Path(source.get("path", ""))
        if not path.is_file(): errors.append("source session unavailable")
        elif source.get("sha256") != digest(path): errors.append("source session changed after capture")
    print(json.dumps({"bundle": str(bundle), "valid": not errors, "errors": errors}, ensure_ascii=False, indent=2)); return 0 if not errors else 1

def cli():
    p = argparse.ArgumentParser(); sub = p.add_subparsers(required=True)
    s = sub.add_parser("scan"); s.add_argument("--session-root", type=Path, default=home() / "sessions"); s.add_argument("--minimum-state", choices=("all", "normal", "checkpoint", "rollover", "emergency"), default="checkpoint"); s.add_argument("--active-since-hours", type=float, default=168); s.set_defaults(run=scan)
    b = sub.add_parser("build"); b.add_argument("--session", type=Path, required=True); b.add_argument("--title", required=True); b.add_argument("--handoff", type=Path, required=True); b.add_argument("--artifacts", type=Path, required=True); b.add_argument("--project-root", type=Path); b.add_argument("--lineage-id"); b.add_argument("--migration-number", type=int); b.set_defaults(run=build)
    v = sub.add_parser("verify"); v.add_argument("--bundle", type=Path, required=True); v.set_defaults(run=verify)
    return p

def main():
    args = cli().parse_args()
    try: return args.run(args)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False), file=sys.stderr); return 2

if __name__ == "__main__": raise SystemExit(main())
