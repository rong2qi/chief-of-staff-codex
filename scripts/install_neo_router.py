"""Install/remove only the Neo routing block in an explicitly selected AGENTS.md."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

from preference_lib import PreferenceError, atomic_write_text


SOURCE = Path(__file__).resolve().parents[1] / "assets/neo-lean-router.md"
START = "<!-- neo-lean-router:start -->"
END = "<!-- neo-lean-router:end -->"


def updated_text(existing: str, *, remove: bool) -> str:
    starts, ends = existing.count(START), existing.count(END)
    if starts != ends or starts > 1:
        raise ValueError("incomplete or duplicate Neo router markers; no changes made")
    if starts:
        start, end = existing.index(START), existing.index(END)
        if end < start:
            raise ValueError("reversed Neo router markers; no changes made")
        end += len(END)
        # The installer owns exactly the two newlines following its block.
        if existing[end:end + 2] == "\n\n":
            end += 2
        existing = existing[:start] + existing[end:]
    if remove:
        return existing
    return SOURCE.read_text(encoding="utf-8").strip() + "\n\n" + existing


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path, help="Explicit AGENTS.md path on Neo")
    parser.add_argument("--remove", action="store_true", help="Remove only the managed Neo block")
    args = parser.parse_args()
    target = args.target.expanduser().absolute()
    try:
        if target.name != "AGENTS.md":
            raise ValueError("target must be named AGENTS.md")
        if any(path.is_symlink() for path in (target, *target.parents)):
            raise ValueError("refusing a symlinked target or ancestor")
        original = target.read_bytes().decode("utf-8") if target.exists() else ""
        result = updated_text(original, remove=args.remove)
        if result != original:
            atomic_write_text(target, result)
        print(f"Neo router {'removed' if args.remove else 'installed'}: {target}")
        return 0
    except (OSError, UnicodeError, ValueError, PreferenceError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
