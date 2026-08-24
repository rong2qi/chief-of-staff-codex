#!/usr/bin/env python3
"""Render one configured American-English coaching clip or return text_only."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from preference_lib import PreferenceError, read_json, require_valid


def result(status: str, **values: object) -> int:
    print(json.dumps({"status": status, **values}, ensure_ascii=False))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--kind", choices=("written", "spoken"), required=True)
    parser.add_argument("--text", required=True)
    args = parser.parse_args()

    try:
        profile_path = Path(args.profile).expanduser()
        if not profile_path.is_absolute():
            raise PreferenceError("--profile must be an absolute path")
        profile = read_json(profile_path.resolve())
        require_valid(profile)
    except PreferenceError as exc:
        return result("text_only", reason=str(exc))

    coaching = profile["american_english_coaching"]
    audio = profile["audio_playback"]
    if not coaching["enabled"] or not audio["enabled"]:
        return result("text_only", reason="audio coaching is disabled")
    if audio["provider"] == "host_builtin":
        return result("text_only", reason="host built-in voice selected; no offline attachment generated")
    if args.kind not in audio["clips"]:
        return result("text_only", reason=f"{args.kind} clip is disabled")
    if not args.text.strip():
        return result("text_only", reason="empty text")

    root = Path(audio["storage_root"]).expanduser()
    if not root.is_absolute() or not root.exists() or not root.is_dir():
        return result("text_only", reason="configured storage root is unavailable")
    root = root.resolve()
    platform_name = os.environ.get("CHIEF_AUDIO_PLATFORM") or platform.system()
    if platform_name != "Darwin" or audio["provider"] not in {"auto", "macos_say"}:
        return result("text_only", reason="no supported offline audio provider")

    say_bin = os.environ.get("CHIEF_SAY_BIN") or shutil.which("say")
    if not say_bin:
        return result("text_only", reason="say is unavailable")

    voice = audio.get("voice")
    rate = audio["rate"]
    digest = hashlib.sha256(
        json.dumps(
            {"kind": args.kind, "text": args.text, "voice": voice, "rate": rate},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:24]
    destination = root / f"{args.kind}-{digest}.m4a"
    if destination.is_file() and destination.stat().st_size > 0:
        return result("ready", path=str(destination), cached=True, kind=args.kind)

    m4a_descriptor, m4a_name = tempfile.mkstemp(prefix=".chief-audio-", suffix=".m4a", dir=root)
    os.close(m4a_descriptor)
    m4a_path = Path(m4a_name)
    m4a_path.unlink()
    try:
        say_command = [say_bin]
        if voice:
            say_command.extend(["-v", voice])
        say_command.extend(["-r", str(rate), "-o", str(m4a_path), args.text])
        subprocess.run(say_command, check=True, capture_output=True, text=True)
        if not m4a_path.is_file() or m4a_path.stat().st_size == 0:
            return result("text_only", reason="audio renderer produced no output")
        os.replace(m4a_path, destination)
        return result("ready", path=str(destination), cached=False, kind=args.kind)
    except (OSError, subprocess.CalledProcessError) as exc:
        return result("text_only", reason=f"audio render failed: {exc}")
    finally:
        if m4a_path.exists():
            m4a_path.unlink()


if __name__ == "__main__":
    raise SystemExit(main())
