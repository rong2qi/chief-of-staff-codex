"""Evidence index for stages that must never be inferred from each other."""
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from typing import Any


STAGES = ("rule", "source", "tests", "review", "testing", "installed", "global", "project", "runtime", "remote")


class CoverageError(ValueError):
    pass


@dataclass
class CoverageIndex:
    entries: dict[str, dict[str, dict[str, str]]] = field(default_factory=lambda: {stage: {} for stage in STAGES})

    def record(self, stage: str, evidence_id: str, sha256: str) -> None:
        if stage not in STAGES or not evidence_id or len(sha256) != 0 and (len(sha256) != 64 or any(char not in "0123456789abcdef" for char in sha256)):
            raise CoverageError("invalid stage, evidence ID, or SHA-256")
        prior = self.entries[stage].get(evidence_id)
        value = {"sha256": sha256}
        if prior is not None and prior != value:
            raise CoverageError("conflicting evidence ID")
        self.entries[stage][evidence_id] = value

    def ready_for(self, stage: str) -> bool:
        # The public report vocabulary calls the project stage "project adoption".
        if stage == "project_adoption":
            stage = "project"
        if stage not in STAGES:
            raise CoverageError("unknown stage")
        return all(self.entries[name] for name in STAGES[:STAGES.index(stage)])

    def to_dict(self) -> dict[str, Any]:
        return {"schema": "CHIEF_FEEDBACK_COVERAGE_V1", "stages": self.entries}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", required=True)
    parser.add_argument("--check-stage", choices=STAGES, required=True)
    args = parser.parse_args(argv)
    try:
        data = json.loads(open(args.index, encoding="utf-8").read())
        index = CoverageIndex(entries=data["stages"])
        print(json.dumps({"stage": args.check_stage, "ready": index.ready_for(args.check_stage)}))
        return 0 if index.ready_for(args.check_stage) else 1
    except (OSError, KeyError, TypeError, json.JSONDecodeError, CoverageError) as exc:
        print(f"error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
