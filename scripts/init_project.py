#!/usr/bin/env python3
"""Safely initialize or validate a Chief of Staff project."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10 and earlier
    tomllib = None


SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = SKILL_ROOT / "assets" / "project-template"
MUTABLE_STATE = {
    Path(".chief-of-staff/task-registry.json"),
    Path(".chief-of-staff/decisions.md"),
    Path(".chief-of-staff/status.md"),
    Path(".chief-of-staff/control-plane.json"),
}


def render(source: Path, project_name: str) -> bytes:
    data = source.read_bytes()
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return data
    json_name = json.dumps(project_name, ensure_ascii=False)[1:-1]
    return (
        text.replace("{{PROJECT_NAME_JSON}}", json_name)
        .replace("{{PROJECT_NAME}}", project_name)
        .encode("utf-8")
    )


def template_files() -> list[tuple[Path, Path]]:
    return [
        (source, source.relative_to(TEMPLATE_ROOT))
        for source in sorted(TEMPLATE_ROOT.rglob("*"))
        if source.is_file()
    ]


def safe_target(raw_target: str) -> Path:
    target = Path(raw_target).expanduser().resolve()
    if target == Path(target.anchor) or target == Path.home().resolve():
        raise ValueError("refusing to initialize a filesystem root or home directory")
    return target


def validate_toml(path: Path) -> str | None:
    if tomllib is not None:
        try:
            with path.open("rb") as handle:
                tomllib.load(handle)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            return str(exc)
        return None

    return "strict TOML parsing requires Python 3.11+"


def require_keys(value: dict, keys: set[str], relative: Path, errors: list[str]) -> None:
    missing = sorted(keys - set(value))
    if missing:
        errors.append(f"missing keys in {relative}: {', '.join(missing)}")


def validate_state(relative: Path, value: object, errors: list[str]) -> None:
    if not isinstance(value, dict):
        errors.append(f"top-level JSON value in {relative} must be an object")
        return
    if value.get("schema_version") != 1:
        errors.append(f"unsupported schema_version in {relative}")
        return

    if relative.name == "project.json":
        require_keys(
            value,
            {
                "schema_version", "project_name", "primary_task_title", "control_plane",
                "task_title_pattern", "approval_required",
            },
            relative,
            errors,
        )
        for key in ("project_name", "primary_task_title", "control_plane", "task_title_pattern"):
            if key in value and not isinstance(value[key], str):
                errors.append(f"{key} in {relative} must be a string")
        approvals = value.get("approval_required")
        if not isinstance(approvals, list) or not all(isinstance(item, str) for item in approvals):
            errors.append(f"approval_required in {relative} must be an array of strings")

    elif relative.name == "task-registry.json":
        require_keys(value, {"schema_version", "tasks"}, relative, errors)
        tasks = value.get("tasks")
        if not isinstance(tasks, list):
            errors.append(f"tasks in {relative} must be an array")
            return
        required_task_keys = {
            "task_id", "host_id", "title", "role", "objective", "status",
            "write_surface", "depends_on", "last_cursor", "result_summary",
        }
        statuses = {"queued", "running", "needs_attention", "completed", "failed", "archived"}
        for index, task in enumerate(tasks):
            label = f"{relative} task[{index}]"
            if not isinstance(task, dict):
                errors.append(f"{label} must be an object")
                continue
            require_keys(task, required_task_keys, Path(label), errors)
            for key in ("task_id", "title", "role", "objective"):
                if key in task and not isinstance(task[key], str):
                    errors.append(f"{key} in {label} must be a string")
            if task.get("status") not in statuses:
                errors.append(f"status in {label} is invalid")
            for key in ("write_surface", "depends_on"):
                if key in task and (
                    not isinstance(task[key], list)
                    or not all(isinstance(item, str) for item in task[key])
                ):
                    errors.append(f"{key} in {label} must be an array of strings")
            for key in ("host_id", "last_cursor", "result_summary"):
                if key in task and task[key] is not None and not isinstance(task[key], str):
                    errors.append(f"{key} in {label} must be a string or null")

    elif relative.name == "control-plane.json":
        require_keys(
            value,
            {"schema_version", "provider", "adapter", "adapter_config"},
            relative,
            errors,
        )
        if "provider" in value and not isinstance(value["provider"], str):
            errors.append(f"provider in {relative} must be a string")
        if value.get("adapter") is not None and not isinstance(value.get("adapter"), str):
            errors.append(f"adapter in {relative} must be a string or null")
        if "adapter_config" in value and not isinstance(value["adapter_config"], dict):
            errors.append(f"adapter_config in {relative} must be an object")


def validate(target: Path) -> list[str]:
    errors: list[str] = []
    required = [relative for _, relative in template_files()]
    for relative in required:
        if not (target / relative).is_file():
            errors.append(f"missing {relative}")

    for relative in (
        Path(".chief-of-staff/project.json"),
        Path(".chief-of-staff/task-registry.json"),
        Path(".chief-of-staff/control-plane.json"),
    ):
        path = target / relative
        if path.is_file():
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                validate_state(relative, value, errors)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                errors.append(f"invalid JSON in {relative}: {exc}")

    toml_files = [target / ".codex" / "config.toml"]
    toml_files.extend(sorted((target / ".codex" / "agents").glob("*.toml")))
    for path in toml_files:
        if path.is_file():
            if tomllib is None:
                relative = path.relative_to(target)
                template = TEMPLATE_ROOT / relative
                error = None if template.is_file() and path.read_bytes() == template.read_bytes() else (
                    "Python 3.10 fallback only accepts the validated v1 template"
                )
            else:
                error = validate_toml(path)
            if error:
                errors.append(f"invalid TOML in {path.relative_to(target)}: {error}")

    return errors


def initialize(target: Path, project_name: str) -> int:
    files = template_files()
    conflicts: list[Path] = []
    planned: list[tuple[Path, bytes]] = []

    for source, relative in files:
        destination = target / relative
        expected = render(source, project_name)
        cursor = target
        unsafe_parent = False
        for part in relative.parts[:-1]:
            cursor = cursor / part
            if cursor.is_symlink():
                unsafe_parent = True
                break
        if unsafe_parent or destination.is_symlink():
            conflicts.append(relative)
            continue
        if destination.exists():
            if relative in MUTABLE_STATE:
                if relative.suffix == ".json":
                    try:
                        value = json.loads(destination.read_text(encoding="utf-8"))
                        state_errors: list[str] = []
                        validate_state(relative, value, state_errors)
                        if state_errors:
                            raise ValueError("; ".join(state_errors))
                    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
                        conflicts.append(relative)
                        continue
                continue
            if destination.read_bytes() == expected:
                continue
            conflicts.append(relative)
        else:
            planned.append((destination, expected))

    if conflicts:
        print("Chief of Staff initialization stopped; existing files differ:", file=sys.stderr)
        for relative in conflicts:
            print(f"- {relative}", file=sys.stderr)
        print("No files were written. Reconcile or move the conflicts, then retry.", file=sys.stderr)
        return 2

    target.mkdir(parents=True, exist_ok=True)
    for destination, data in planned:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)

    errors = validate(target)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    action = "initialized" if planned else "already initialized"
    print(f"Chief of Staff {action}: {target}")
    print(f"Files created: {len(planned)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=".", help="Project root; defaults to the current directory")
    parser.add_argument("--project-name", help="Display name; defaults to the target directory name")
    parser.add_argument("--check", action="store_true", help="Validate an initialized project without writing")
    args = parser.parse_args()

    try:
        target = safe_target(args.target)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    project_name = (args.project_name or target.name).strip()
    if not project_name or any(ord(character) < 32 for character in project_name):
        print("ERROR: project name must be a non-empty single line", file=sys.stderr)
        return 2

    if args.check:
        errors = validate(target)
        if errors:
            for error in errors:
                print(f"ERROR: {error}", file=sys.stderr)
            return 1
        print(f"Chief of Staff project is valid: {target}")
        return 0
    return initialize(target, project_name)


if __name__ == "__main__":
    raise SystemExit(main())
