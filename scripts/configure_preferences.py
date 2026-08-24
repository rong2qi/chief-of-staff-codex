#!/usr/bin/env python3
"""Configure optional Chief of Staff operator preferences without a UI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from preference_lib import (
    PreferenceError,
    SKILL_ROOT,
    atomic_write_json,
    managed_agents_block,
    preset_profile,
    read_json,
    require_valid,
    update_managed_agents,
)


def absolute_path(raw: str, label: str) -> Path:
    path = Path(raw).expanduser()
    if not path.is_absolute():
        raise PreferenceError(f"{label} must be an absolute path")
    return path.resolve()


def build_profile(args: argparse.Namespace) -> dict:
    if args.input:
        profile = read_json(absolute_path(args.input, "--input"))
        profile["preset"] = "custom"
    else:
        profile = preset_profile(args.preset)
    profile["scope"] = args.scope

    if args.salutation:
        profile["operator_salutation"] = {"enabled": True, "value": args.salutation}
    elif args.neutral_salutation:
        profile["operator_salutation"] = {"enabled": False, "value": None}

    if args.enable_reminders:
        profile["reminders"]["enabled"] = True
    if args.disable_reminders:
        profile["reminders"]["enabled"] = False

    if args.audio_provider:
        profile["audio_playback"]["provider"] = args.audio_provider
    if args.voice:
        profile["audio_playback"]["voice"] = args.voice
    if args.audio_rate is not None:
        profile["audio_playback"]["rate"] = args.audio_rate

    if args.scope == "global":
        data_root = absolute_path(
            args.data_root or str(Path.home() / ".codex" / "chief-of-staff"),
            "--data-root",
        )
        profile_path = absolute_path(
            args.profile_out or str(data_root / "chief-preferences.json"),
            "--profile-out",
        )
    else:
        if not args.project_root:
            raise PreferenceError("project scope requires --project-root")
        project_root = absolute_path(args.project_root, "--project-root")
        profile_path = absolute_path(
            args.profile_out or str(project_root / ".chief-of-staff" / "preferences.json"),
            "--profile-out",
        )
        data_root = absolute_path(
            args.data_root or str(project_root / ".chief-of-staff"),
            "--data-root",
        )

    if args.data_root and (not data_root.exists() or not data_root.is_dir()):
        raise PreferenceError("custom --data-root must already exist and be a directory")

    if (
        profile["audio_playback"]["enabled"]
        and profile["audio_playback"]["provider"] in {"auto", "macos_say"}
    ):
        profile["audio_playback"]["storage_root"] = str(data_root / "english-audio")
    else:
        profile["audio_playback"]["storage_root"] = None

    if profile["audio_playback"]["provider"] == "host_builtin" and args.voice:
        raise PreferenceError("--voice is only valid for auto or macos_say audio")

    if profile_path.exists():
        existing = read_json(profile_path)
        require_valid(existing)
        for key, value in existing.items():
            if key not in profile:
                profile[key] = value
    require_valid(profile)
    return profile, profile_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--preset",
        choices=("core", "operator-controlled-bilingual"),
        default="core",
    )
    parser.add_argument("--input", help="Custom profile JSON; preset becomes custom")
    parser.add_argument("--scope", choices=("global", "project"), default="global")
    parser.add_argument("--salutation", help="Enable and set an operator salutation")
    parser.add_argument("--neutral-salutation", action="store_true")
    reminder = parser.add_mutually_exclusive_group()
    reminder.add_argument("--enable-reminders", action="store_true")
    reminder.add_argument("--disable-reminders", action="store_true")
    parser.add_argument("--voice", help="Preferred installed en-US system voice")
    parser.add_argument(
        "--audio-provider",
        choices=("host_builtin", "auto", "macos_say"),
        help="Built-in host voice or an opt-in offline attachment renderer",
    )
    parser.add_argument("--audio-rate", type=int, help="Words per minute, 80-350")
    parser.add_argument("--data-root", help="Absolute persistent data root")
    parser.add_argument("--project-root", help="Required for project scope")
    parser.add_argument("--profile-out", help="Override the resolved profile path")
    parser.add_argument(
        "--agents-file",
        default=str(Path.home() / ".codex" / "AGENTS.md"),
        help="Global AGENTS.md updated only for global scope",
    )
    parser.add_argument("--check", metavar="PROFILE", help="Validate without writing")
    parser.add_argument("--print", action="store_true", dest="print_profile")
    args = parser.parse_args()

    try:
        if args.salutation and args.neutral_salutation:
            raise PreferenceError("choose --salutation or --neutral-salutation, not both")
        if args.check:
            profile_path = absolute_path(args.check, "--check")
            profile = read_json(profile_path)
            require_valid(profile)
            print(json.dumps({"status": "valid", "profile": str(profile_path)}))
            return 0

        profile, profile_path = build_profile(args)
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        audio_root = profile["audio_playback"]["storage_root"]
        if audio_root:
            Path(audio_root).mkdir(parents=True, exist_ok=True)
        atomic_write_json(profile_path, profile)

        agents_path = None
        if args.scope == "global":
            agents_path = absolute_path(args.agents_file, "--agents-file")
            renderer = (SKILL_ROOT / "scripts" / "render_english_audio.py").resolve()
            update_managed_agents(
                agents_path,
                managed_agents_block(profile_path.resolve(), renderer),
            )
        result = {
            "status": "configured",
            "scope": args.scope,
            "preset": profile["preset"],
            "profile": str(profile_path),
            "agents_file": str(agents_path) if agents_path else None,
        }
        print(json.dumps(result, ensure_ascii=False))
        if args.print_profile:
            print(json.dumps(profile, ensure_ascii=False, indent=2))
        return 0
    except PreferenceError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
