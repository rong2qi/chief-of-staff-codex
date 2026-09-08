"""Pure, prospective repair-budget validation shared by Chief candidates."""
from __future__ import annotations

from dataclasses import dataclass
import argparse
import json
import os
from pathlib import Path
import secrets
import stat
import sys
from typing import Mapping

try:  # Package import when used as ``scripts.retry_policy`` or as a CLI file.
    from . import continuous_execution
    from . import autonomy_policy
except ImportError:  # pragma: no cover - exercised by the direct CLI path.
    import continuous_execution
    import autonomy_policy


class RetryPolicyError(ValueError):
    pass


AUTONOMY_PHASE_DEFECT_CYCLES = 3


def _package_resource_usage(state: Mapping[str, object], package: Mapping[str, object], loader) -> tuple[int, int]:
    """Return retained repair-watermark and local-action spend for one package.

    Phase transitions preserve every measurement: a new phase can reset only
    its defect counter, never its package resource account.
    """
    repair_used = 0
    phase_sets = state.get("phases") if isinstance(state, Mapping) else None
    cycle_sets = [phase.get("cycles") for phase in phase_sets if isinstance(phase, dict)] if isinstance(phase_sets, list) else [state.get("cycles")]
    for cycles in cycle_sets:
        if not isinstance(cycles, list):
            raise RetryPolicyError("repair budget resource history is invalid")
        for cycle in cycles:
            if not isinstance(cycle, dict) or "resource_measurement" not in cycle:
                continue
            measurement = cycle["resource_measurement"]
            if not isinstance(measurement, Mapping):
                raise RetryPolicyError("repair budget resource history is invalid")
            observed = loader(measurement.get("evidence_ref"), measurement.get("evidence_sha256"), "historical package resource measurement")
            if (observed.get("schema") != "CHIEF_EXECUTION_RESOURCE_MEASUREMENT_V1"
                or observed.get("work_id") != package.get("work_id")
                or observed.get("package_id") != package.get("package_id")
                or observed.get("resource_unit") != package.get("resource_limits", {}).get("resource_unit")
                or type(observed.get("units_used")) is not int or observed["units_used"] < 0):
                raise RetryPolicyError("historical package resource measurement is invalid or drifted")
            repair_used = max(repair_used, observed["units_used"])
    local_spent = 0
    journal = state.get("local_action_journal", [])
    if not isinstance(journal, list):
        raise RetryPolicyError("local action journal is invalid")
    for entry in journal:
        if not isinstance(entry, dict) or entry.get("package_id") != package.get("package_id"):
            continue
        cost = entry.get("cost")
        if type(cost) is not int or cost < 0:
            raise RetryPolicyError("local action resource journal is invalid")
        local_spent += cost
    return repair_used, local_spent


def consume_local_action(project: Path, event: Mapping[str, object], *, native_observation_root: Path, native_intake: Mapping[str, object]) -> dict:
    """Return one idempotent local intent only from a native-approved package.

    This is a directory-bound consumer, not a general approval evaluator.  It
    records action IDs and cumulative package units in the retained budget log.
    """
    project_fd, state_fd = _open_fixed_state(Path(project)); native_fd = None
    try:
        if not isinstance(event, Mapping) or set(event) != {"action_id", "package_id", "action_class", "write_surface", "external_target", "data_classification", "cost", "revalidation_ref", "revalidation_sha256"}:
            raise RetryPolicyError("local action event fields are incomplete or ambiguous")
        if any(not isinstance(event[k], str) or not event[k] for k in ("action_id", "package_id", "action_class", "data_classification", "revalidation_ref", "revalidation_sha256")) or type(event["cost"]) is not int or event["cost"] < 0:
            raise RetryPolicyError("local action event is invalid")
        if event["write_surface"] is not None and (not isinstance(event["write_surface"], str) or not event["write_surface"].strip()):
            raise RetryPolicyError("local action write_surface is invalid")
        if event["external_target"] is not None and (not isinstance(event["external_target"], str) or not event["external_target"]):
            raise RetryPolicyError("local action external_target is invalid")
        config = json.loads(_read_owned_text(state_fd, "project.json", required=True))
        raw_state = _read_owned_text(state_fd, "repair-budget.json", required=False)
        phase_state = json.loads(raw_state) if raw_state else {}
        active = next((p for p in phase_state.get("phases", []) if isinstance(p, dict) and p.get("phase_id") == phase_state.get("active_phase_id")), None) if isinstance(phase_state, dict) else None
        provenance = config.get("repair_stop_provenance", {}) if isinstance(config, dict) else {}
        started = active.get("started_from") if isinstance(active, dict) else None
        numeric_phase = config.get("autonomy_policy_enabled") is True and isinstance(started, dict) and isinstance(provenance, dict) and all(provenance.get(k) == "numeric_local_preparation_limit" for k in ("repair_failure_stop", "repair_one_shot", "repair_budget_status") if config.get(k) in {True, "exhausted"})
        if not isinstance(config, dict) or config.get("autonomy_policy_enabled") is not True or config.get("paused") is True or ((config.get("repair_budget_status") == "exhausted" or config.get("repair_failure_stop") is True or config.get("repair_one_shot") is True) and not numeric_phase):
            raise RetryPolicyError("local action is not enabled by retained project state")
        allowed_classes = {"local_read", "local_write", "local_test", "local_commit"}
        if event["action_class"] not in allowed_classes or event["external_target"] is not None or event["data_classification"] not in {"synthetic", "no_real_data"}:
            raise RetryPolicyError("local action class, target, or data classification is not locally safe")
        if event["action_class"] != "local_read" and event["write_surface"] is None:
            raise RetryPolicyError("local write/test/commit requires an exact surface")
        plan = json.loads(_read_owned_text(state_fd, "project-plan.json", required=True)); registry = json.loads(_read_owned_text(state_fd, "task-registry.json", required=True)); approvals = json.loads(_read_owned_text(state_fd, "approval-queue.json", required=True))
        native_fd = _open_project_directory(Path(native_observation_root)); _require_disjoint_directories(project_fd, native_fd)
        loader = lambda ref, digest, label: _read_retained_json(project_fd, ref, digest, label)
        def native_loader(ref, digest, label):
            if not isinstance(ref, str) or not ref.startswith("native://"): raise RetryPolicyError(f"{label}_ref must be native")
            return _read_retained_json(native_fd, "repo://" + ref.removeprefix("native://"), digest, label)
        continuous_execution.validate_execution_records(plan, registry, approvals, retained_loader=loader, native_observation_loader=native_loader, submitting_project=Path(project), native_observation_root=Path(native_observation_root))
        package = next((x for x in plan["execution_packages"] if x.get("package_id") == event["package_id"]), None)
        if not isinstance(package, dict): raise RetryPolicyError("local action package is not approved")
        if numeric_phase and (
            started.get("new_plan") != package.get("package_id")
            or started.get("new_candidate_id") != package.get("candidate_sha256")
            or started.get("approval_id") != package.get("approval_id")
            or started.get("writer_task_id") != package.get("writer_task_id")
        ):
            raise RetryPolicyError("numeric local-action override is not bound to the active native phase")
        _validate_native_intake(native_intake, package)
        allowed = package.get("approved_local_actions")
        if not isinstance(allowed, list) or not allowed or any(not isinstance(x, dict) or set(x) != {"action_id","action_class","write_surface","external_target","data_classification","max_cost"} for x in allowed) or len({x["action_id"] for x in allowed}) != len(allowed): raise RetryPolicyError("local action package has invalid approved actions")
        approved = next((x for x in allowed if isinstance(x, dict) and x.get("action_id") == event["action_id"]), None)
        exact = {"action_id": event["action_id"], "action_class": event["action_class"], "write_surface": event["write_surface"], "external_target": event["external_target"], "data_classification": event["data_classification"]}
        if not isinstance(approved, dict) or any(approved.get(k) != v for k, v in exact.items()) or type(approved.get("max_cost")) is not int or event["cost"] > approved["max_cost"] or event["action_class"] not in package["permissions"] or (event["write_surface"] is not None and event["write_surface"] not in package["write_surface"]):
            raise RetryPolicyError("local action is not an exact approved item")
        if any(token in event["action_class"] for token in ("external", "production", "release", "deploy", "payment", "permission")):
            raise RetryPolicyError("protected action cannot use local action consumer")
        observed = loader(event["revalidation_ref"], event["revalidation_sha256"], "local action revalidation")
        if observed != {"schema":"CHIEF_LOCAL_ACTION_REVALIDATION_V1", **exact, "package_id":package["package_id"], "reverification":"passed"}:
            raise RetryPolicyError("local action revalidation is missing or drifted")
        raw = _read_owned_text(state_fd, "repair-budget.json", required=False); state = json.loads(raw) if raw else {"schema":"CHIEF_REPAIR_BUDGET_V1","cycles":[]}
        if not isinstance(state, dict): raise RetryPolicyError("repair budget log schema is invalid")
        journal = state.setdefault("local_action_journal", [])
        if not isinstance(journal, list): raise RetryPolicyError("local action journal is invalid")
        prior = next((x for x in journal if isinstance(x, dict) and x.get("action_id") == event["action_id"]), None)
        if prior is not None:
            if prior.get("event") != dict(event): raise RetryPolicyError("local action ID conflicts with retained event")
            return {"status":"OBSERVE_LOCAL_ACTION", "operator_actionable_now":False, "todo_suppressed":True}
        repair_used, spent = _package_resource_usage(state, package, loader)
        if repair_used + spent + event["cost"] > package["resource_limits"]["max_resource_units"]: raise RetryPolicyError("local action resource allowance exhausted")
        journal.append({"action_id":event["action_id"], "package_id":package["package_id"], "cost":event["cost"], "event":dict(event)})
        _write_state(state_fd, state)
        return {"status":"LOCAL_ACTION_INTENT", "operator_actionable_now":False, "todo_suppressed":True, "action_id":event["action_id"]}
    finally:
        for fd in (native_fd, state_fd, project_fd):
            if fd is not None:
                try: os.close(fd)
                except OSError: pass


def begin_new_phase(project: Path, transition: Mapping[str, object], *, native_observation_root: Path | None = None, native_intake: Mapping[str, object] | None = None) -> dict:
    """Persist an evidence-bound new phase whose repair allowance begins at zero."""
    project_fd, state_fd = _open_fixed_state(Path(project)); native_fd = None
    try:
        config_raw = _read_owned_text(state_fd, "project.json", required=True)
        config = json.loads(config_raw)
        if not isinstance(config, dict) or config.get("autonomy_policy_enabled") is not True:
            raise RetryPolicyError("phase reset requires an explicitly enabled autonomy policy")
        provenance = config.get("repair_stop_provenance", {})
        if not isinstance(provenance, dict):
            raise RetryPolicyError("repair-stop provenance is ambiguous")
        numeric_local = {"repair_budget_status", "repair_failure_stop", "repair_one_shot"}
        stopped = {key for key in numeric_local if config.get(key) in {True, "exhausted"}}
        if stopped and any(provenance.get(key) != "numeric_local_preparation_limit" for key in stopped):
            raise RetryPolicyError("phase reset cannot override a retained protected repair stop")
        if any(provenance.get(key) in {"permission", "platform_safety", "real_data", "paused", "archived", "production", "external", "denial"} for key in provenance):
            raise RetryPolicyError("phase reset cannot override retained protected-stop provenance")
        raw = _read_owned_text(state_fd, "repair-budget.json", required=False)
        state = json.loads(raw) if raw is not None else {"schema": "CHIEF_REPAIR_BUDGET_V1", "cycles": []}
        if not isinstance(state, dict) or state.get("schema") not in {"CHIEF_REPAIR_BUDGET_V1", "CHIEF_REPAIR_BUDGET_V2"}:
            raise RetryPolicyError("repair budget log schema is invalid")
        try:
            # A phase label is not authority: reuse the existing exact native
            # package/queue/registry binding rather than a Boolean approval.
            plan = json.loads(_read_owned_text(state_fd, "project-plan.json", required=True))
            registry = json.loads(_read_owned_text(state_fd, "task-registry.json", required=True))
            approvals = json.loads(_read_owned_text(state_fd, "approval-queue.json", required=True))
            if native_observation_root is None:
                raise RetryPolicyError("phase reset requires external native approval evidence")
            native_fd = _open_project_directory(Path(native_observation_root))
            _require_disjoint_directories(project_fd, native_fd)
            loader = lambda ref, digest, label: _read_retained_json(project_fd, ref, digest, label)
            def native_loader(ref, digest, label):
                if not isinstance(ref, str) or not ref.startswith("native://"):
                    raise RetryPolicyError(f"{label}_ref must be a native:// reference")
                return _read_retained_json(native_fd, "repo://" + ref.removeprefix("native://"), digest, label)
            continuous_execution.validate_execution_records(plan, registry, approvals, retained_loader=loader, native_observation_loader=native_loader, submitting_project=Path(project), native_observation_root=Path(native_observation_root))
            packages = plan.get("execution_packages") if isinstance(plan, dict) else None
            package = next((p for p in packages or [] if isinstance(p, dict) and p.get("package_id") == transition.get("new_plan")), None)
            requests = approvals.get("requests") if isinstance(approvals, dict) else None
            request = next((r for r in requests or [] if isinstance(r, dict) and r.get("request_id") == transition.get("approval_id")), None)
            tasks = registry.get("tasks") if isinstance(registry, dict) else None
            writer = next((t for t in tasks or [] if isinstance(t, dict) and t.get("task_id") == transition.get("writer_task_id")), None)
            limits = package.get("resource_limits") if isinstance(package, dict) else None
            requested_limits = transition.get("resource_limits") if isinstance(transition, Mapping) else None
            if (not isinstance(package, dict) or package.get("candidate_sha256") != transition.get("new_candidate_id")
                or package.get("approval_id") != transition.get("approval_id") or package.get("writer_task_id") != transition.get("writer_task_id")
                or not isinstance(request, dict) or request.get("status") != "approved"
                or not isinstance(writer, dict) or writer.get("status") in {"paused", "archived", "awaiting_permission"}
                or writer.get("execution_package_id") != package.get("package_id") or writer.get("execution_work_id") != package.get("work_id")
                or not isinstance(limits, dict) or not isinstance(requested_limits, Mapping)
                or requested_limits.get("unit") != limits.get("resource_unit")
                or type(requested_limits.get("maximum")) is not int or requested_limits["maximum"] > limits.get("max_resource_units", 0)):
                raise RetryPolicyError("phase transition is not bound to the approved plan, queue, and writer")
            _validate_native_intake(native_intake, package)
            for evidence in transition.get("prior_failure_evidence", []):
                observed = loader(evidence.get("evidence_ref"), evidence.get("evidence_sha256"), "prior phase failure")
                if not isinstance(observed, dict) or observed.get("schema") != "CHIEF_PHASE_FAILURE_EVIDENCE_V1" or observed.get("phase_id") != transition.get("prior_phase_id") or observed.get("candidate_id") != transition.get("prior_candidate_id") or observed.get("verdict") not in {"failed", "passed", "completed"} or set(observed) != {"schema", "phase_id", "candidate_id", "verdict"}:
                    raise RetryPolicyError("prior phase failure evidence is missing, drifted, or unbound")
            autonomy_policy.begin_new_phase(state, transition)
        except autonomy_policy.AutonomyPolicyError as exc:
            raise RetryPolicyError(str(exc)) from exc
        _write_state(state_fd, state)
        return state
    finally:
        if native_fd is not None: os.close(native_fd)
        os.close(state_fd)
        os.close(project_fd)


def _validate_native_intake(value: object, package: Mapping[str, object]) -> dict:
    """Check host/coordinator supplied expectations, never derive them from disk."""
    if not isinstance(value, Mapping):
        raise RetryPolicyError("continuous consume requires a host-supplied native intake")
    required = {"root_id", "coordinator_task_id", "approval_sha256", "work_id", "package_id", "package_digest", "project", "writer_task_id", "candidate_sha256"}
    if set(value) != required:
        raise RetryPolicyError("native intake fields are incomplete or ambiguous")
    expected = {"root_id": package["native_intake"]["root_id"], "coordinator_task_id": package["native_intake"]["coordinator_task_id"], "approval_sha256": package["approval_receipt_sha256"], "work_id": package["work_id"], "package_id": package["package_id"], "package_digest": continuous_execution.package_digest(package), "project": package["project"], "writer_task_id": package["writer_task_id"], "candidate_sha256": package["candidate_sha256"]}
    if dict(value) != expected:
        raise RetryPolicyError("host native intake does not match the exact approved package")
    return dict(value)


def _require_safe_dirfd_apis() -> None:
    """Fail closed where Python cannot keep path resolution directory-bound."""
    required = (os.open, os.unlink, os.stat)
    if (
        not hasattr(os, "O_NOFOLLOW")
        or not hasattr(os, "O_DIRECTORY")
        or not hasattr(os, "fsync")
        or not hasattr(os, "replace")
        or not hasattr(os, "supports_dir_fd")
        or not hasattr(os, "supports_follow_symlinks")
        or any(operation not in os.supports_dir_fd for operation in required)
        or os.stat not in os.supports_follow_symlinks
    ):
        raise RetryPolicyError("safe directory-bound repair budget APIs are unavailable")


def _require_owned_regular(fd: int) -> None:
    try:
        record = os.fstat(fd)
    except OSError as exc:
        raise RetryPolicyError("unsafe repair budget fixed-state path") from exc
    if not stat.S_ISREG(record.st_mode) or record.st_nlink != 1:
        raise RetryPolicyError("unsafe repair budget fixed-state path")


def _require_directory(fd: int) -> None:
    try:
        record = os.fstat(fd)
    except OSError as exc:
        raise RetryPolicyError("unsafe repair budget fixed-state path") from exc
    if not stat.S_ISDIR(record.st_mode):
        raise RetryPolicyError("unsafe repair budget fixed-state path")


def _open_directory_at(parent_fd: int, name: str) -> int:
    """Bind one checked component before allowing traversal through it."""
    before = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    if not stat.S_ISDIR(before.st_mode):
        raise RetryPolicyError("unsafe repair budget fixed-state path")
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    try:
        after = os.fstat(fd)
        if not stat.S_ISDIR(after.st_mode) or (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            raise RetryPolicyError("unsafe repair budget fixed-state path")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _open_project_directory(project: Path) -> int:
    """Walk from a retained root descriptor; never reopen a checked full path."""
    project = project.absolute()
    if project.anchor != "/" or ".." in project.parts:
        raise RetryPolicyError("unsafe repair budget fixed-state path")
    components = project.parts[1:]
    # Known macOS system aliases are lexical mappings, not a general symlink
    # resolution step. All remaining components use the same no-follow walk.
    if sys.platform == "darwin" and components and components[0] in {"tmp", "var"}:
        components = ("private", *components)
    fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        _require_directory(fd)
        for name in components:
            child_fd = _open_directory_at(fd, name)
            previous_fd, fd = fd, child_fd
            os.close(previous_fd)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _open_fixed_state(project: Path) -> tuple[int, int]:
    """Open and bind the project and managed-state directory identities."""
    _require_safe_dirfd_apis()
    project_fd: int | None = None
    state_fd: int | None = None
    try:
        project_fd = _open_project_directory(Path(project))
        state_fd = _open_directory_at(project_fd, ".chief-of-staff")
        try:
            os.fsync(state_fd)
        except OSError as exc:
            raise RetryPolicyError("safe directory-bound repair budget APIs are unavailable") from exc
        return project_fd, state_fd
    except (OSError, TypeError, RetryPolicyError) as exc:
        for fd in (state_fd, project_fd):
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
        if isinstance(exc, RetryPolicyError):
            raise
        raise RetryPolicyError("unsafe repair budget fixed-state path") from exc


def _require_disjoint_directories(first_fd: int, second_fd: int) -> None:
    """Compare retained identities and their parents, including OS path aliases."""
    def identity(fd):
        value = os.fstat(fd)
        return value.st_dev, value.st_ino

    def ancestors(fd):
        current = os.dup(fd)
        seen = set()
        try:
            for _ in range(1024):
                here = identity(current)
                if here in seen:
                    raise RetryPolicyError("directory ancestry is ambiguous")
                seen.add(here)
                parent = _open_directory_at(current, "..")
                if identity(parent) == here:
                    os.close(parent)
                    return seen
                os.close(current)
                current = parent
            raise RetryPolicyError("directory ancestry exceeds the safe bound")
        finally:
            os.close(current)

    if identity(first_fd) in ancestors(second_fd) or identity(second_fd) in ancestors(first_fd):
        raise RetryPolicyError("native observation root and writer project must be disjoint")


def _read_owned_text(state_fd: int, name: str, *, required: bool) -> str | None:
    """Read one fixed state file through the already-bound state directory."""
    fd: int | None = None
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=state_fd)
    except FileNotFoundError as exc:
        if required:
            raise RetryPolicyError("unsafe repair budget fixed-state path") from exc
        return None
    except OSError as exc:
        raise RetryPolicyError("unsafe repair budget fixed-state path") from exc
    try:
        _require_owned_regular(fd)
        with os.fdopen(fd, "r", encoding="utf-8") as source:
            fd = None
            return source.read()
    except (OSError, UnicodeError) as exc:
        raise RetryPolicyError("unsafe repair budget fixed-state path") from exc
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass


def _read_retained_json(project_fd: int, reference: object, expected_sha256: object, label: str) -> dict:
    """Read retained evidence from the already-held project fd without reopen.

    This is intentionally separate from ``Path.resolve``: after the caller has
    bound the project root, a replaced ancestor or evidence directory cannot
    redirect an approval/progress/resource read.
    """
    try:
        reference = continuous_execution._string(reference, f"{label}_ref")
        expected = continuous_execution._sha256(expected_sha256, f"{label}_sha256")
        if not reference.startswith("repo://"):
            raise RetryPolicyError(f"{label}_ref must be a repo:// reference")
        raw_relative = reference.removeprefix("repo://")
        if (not raw_relative or raw_relative.startswith("/") or "\\" in raw_relative
            or any(part in {"", ".", ".."} for part in raw_relative.split("/"))
            or (len(raw_relative) >= 2 and raw_relative[1] == ":")
            or any(ord(char) < 32 for char in raw_relative)):
            raise RetryPolicyError(f"{label}_ref escapes the project")
        parts = tuple(raw_relative.split("/"))
        parent_fd = os.dup(project_fd)
        try:
            for part in parts[:-1]:
                child_fd = _open_directory_at(parent_fd, part)
                os.close(parent_fd); parent_fd = child_fd
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent_fd)
            try:
                _require_owned_regular(fd)
                raw = b""
                while True:
                    block = os.read(fd, 65536)
                    if not block: break
                    raw += block
            finally:
                os.close(fd)
        finally:
            os.close(parent_fd)
        if continuous_execution.hashlib.sha256(raw).hexdigest() != expected:
            raise RetryPolicyError(f"{label} hash does not match retained bytes")
        result = json.loads(raw)
        if not isinstance(result, dict): raise RetryPolicyError(f"{label} must be a JSON object")
        return result
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        if isinstance(exc, RetryPolicyError): raise
        raise RetryPolicyError(f"{label} is not a retained project observation") from exc


def _read_native_observation(native_root: Path, reference: object, expected_sha256: object, label: str) -> dict:
    """Load an explicitly supplied external coordinator observation by fd."""
    if not isinstance(reference, str) or not reference.startswith("native://"):
        raise RetryPolicyError(f"{label}_ref must be a native:// reference")
    fd = _open_project_directory(native_root)
    try:
        return _read_retained_json(fd, "repo://" + reference.removeprefix("native://"), expected_sha256, label)
    finally:
        os.close(fd)


def _write_state(state_fd: int, state: dict) -> None:
    """Durably replace the receipt without resolving the state directory again."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    staged: str | None = None
    fd: int | None = None
    try:
        for _ in range(16):
            candidate = ".repair-budget-" + secrets.token_hex(16)
            try:
                fd = os.open(candidate, flags, 0o600, dir_fd=state_fd)
                staged = candidate
                break
            except FileExistsError:
                continue
        if fd is None or staged is None:
            raise RetryPolicyError("unable to create a unique repair budget receipt")
        _require_owned_regular(fd)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            fd = None
            output.write(json.dumps(state, sort_keys=True) + "\n")
            output.flush()
            os.fsync(output.fileno())
        os.replace(staged, "repair-budget.json", src_dir_fd=state_fd, dst_dir_fd=state_fd)
        staged = None
        os.fsync(state_fd)
    except (OSError, TypeError, RetryPolicyError) as exc:
        if isinstance(exc, RetryPolicyError):
            raise
        raise RetryPolicyError("safe directory-bound repair budget APIs are unavailable") from exc
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass
        if staged is not None:
            try:
                os.unlink(staged, dir_fd=state_fd)
                os.fsync(state_fd)
            except FileNotFoundError:
                pass
            except OSError:
                pass


@dataclass(frozen=True)
class RetryPolicy:
    max_repair_cycles: int = 3

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "RetryPolicy":
        maximum = value.get("max_repair_cycles", 3)
        if type(maximum) is not int or not 1 <= maximum <= 3:
            raise RetryPolicyError("max_repair_cycles must be an integer from 1 through 3")
        return cls(maximum)

    def permit(self, *, reviews: int, repairs: int, stricter_maximum: int | None = None) -> bool:
        if type(reviews) is not int or type(repairs) is not int or reviews < 0 or repairs < 0:
            raise RetryPolicyError("reviews and repairs must be non-negative integers")
        maximum = self.max_repair_cycles if stricter_maximum is None else min(self.max_repair_cycles, stricter_maximum)
        if type(maximum) is not int or maximum < 0:
            raise RetryPolicyError("stricter maximum must be a non-negative integer")
        # Initial independent review establishes the first candidate and is free.
        return reviews >= 1 and repairs <= maximum


def _validate_reviewed_artifact(review: Mapping, candidate_id: str, outcome: Mapping, loader, package: Mapping) -> dict:
    """A native review binds each round's artifact and exact outcome bytes."""
    artifact = review.get("reviewed_artifact")
    if not isinstance(artifact, dict) or set(artifact) != {"candidate_id", "sha256", "outcome_ref", "outcome_sha256"}:
        raise RetryPolicyError("native review lacks the exact reviewed artifact")
    continuous_execution._sha256(artifact["sha256"], "reviewed artifact sha256")
    if artifact["candidate_id"] != candidate_id or artifact["outcome_ref"] != outcome.get("evidence_ref") or artifact["outcome_sha256"] != outcome.get("evidence_sha256"):
        raise RetryPolicyError("native reviewed artifact does not bind the round outcome")
    observed = loader(artifact["outcome_ref"], artifact["outcome_sha256"], "reviewed outcome")
    if observed.get("artifact_sha256") != artifact["sha256"] or any(observed.get(key) != package[key] for key in ("work_id", "package_id", "candidate_sha256")):
        raise RetryPolicyError("retained outcome does not bind the reviewed artifact")
    return dict(artifact)


def _validate_diagnosis(receipt: Mapping, request: Mapping, package: Mapping, reviewer_id: str, native_loader) -> dict:
    """A new route requires the independent observer's retained reproduction."""
    if not isinstance(receipt, Mapping) or set(receipt) != {"evidence_ref", "evidence_sha256"}:
        raise RetryPolicyError("diagnosis receipt is incomplete or ambiguous")
    observed = native_loader(receipt["evidence_ref"], receipt["evidence_sha256"], "independent diagnosis")
    fixed = {"schema":"CHIEF_EXECUTION_DIAGNOSIS_EVIDENCE_V1", "request_id":request["request_id"], "round_ids":request["round_ids"], "work_id":package["work_id"], "package_id":package["package_id"], "candidate_sha256":package["candidate_sha256"], "reviewer_task_id":reviewer_id}
    if any(observed.get(key) != value for key, value in fixed.items()) or reviewer_id not in package["independent_reviewer_task_ids"]:
        raise RetryPolicyError("independent diagnosis does not bind the active stagnant pair")
    path = observed.get("new_path")
    if not isinstance(path, str) or not path.strip():
        raise RetryPolicyError("independent diagnosis lacks a new path")
    ref, digest = observed.get("new_path_evidence_ref"), observed.get("new_path_evidence_sha256")
    reproduction = native_loader(ref, digest, "independent new-path reproduction")
    expected = {**fixed, "schema":"CHIEF_EXECUTION_NEW_PATH_EVIDENCE_V1", "new_path":path, "coordinator_task_id":package["native_intake"]["coordinator_task_id"], "native_root_id":package["native_intake"]["root_id"]}
    observation, commands = reproduction.get("observation"), reproduction.get("reproduction")
    if (any(reproduction.get(key) != value for key, value in expected.items())
        or not isinstance(observation, dict) or set(observation) != {"before", "after"}
        or any(not isinstance(value, str) or not value.strip() for value in observation.values())
        or observation["before"] == observation["after"]
        or not isinstance(commands, list) or not commands
        or any(not isinstance(value, str) or not value.strip() for value in commands)):
        raise RetryPolicyError("new path lacks retained reproducible evidence")
    return {"request_id":request["request_id"], **dict(receipt), "new_path_evidence_ref":ref, "new_path_evidence_sha256":digest}


def consume_repair_cycle(
    project: Path,
    candidate_id: str,
    review_id: str,
    repair_id: str,
    *,
    reviewer_id: str | None = None,
    progress_evidence: Mapping[str, object] | None = None,
    execution_package_id: str | None = None,
    execution_work_id: str | None = None,
    resource_measurement: Mapping[str, object] | None = None,
    native_observation_root: Path | None = None,
    review_evidence: Mapping[str, object] | None = None,
    stagnant_evidence: Mapping[str, object] | None = None,
    diagnosis_evidence: Mapping[str, object] | None = None,
    native_intake: Mapping[str, object] | None = None,
    continuation_event: Mapping[str, object] | None = None,
) -> dict:
    """Consume one observed repair ID in a project-owned, idempotent budget log."""
    native_fd: int | None = None
    project_fd, state_fd = _open_fixed_state(Path(project))
    try:
        if any(not isinstance(value, str) or not value for value in (candidate_id, review_id, repair_id)):
            raise RetryPolicyError("candidate, review, and repair IDs are required")
        try:
            config = json.loads(_read_owned_text(state_fd, "project.json", required=True))
        except (TypeError, json.JSONDecodeError) as exc:
            raise RetryPolicyError("project repair contract is unreadable") from exc
        policy = RetryPolicy.from_mapping(config)
        configured_reviewer = config.get("repair_reviewer_id")
        if configured_reviewer is not None and (not isinstance(configured_reviewer, str) or not configured_reviewer):
            raise RetryPolicyError("repair_reviewer_id must be a non-empty stable reviewer identity")
        if configured_reviewer is not None and reviewer_id is not None and reviewer_id != configured_reviewer:
            raise RetryPolicyError("configured reviewer identity cannot be overridden")
        reviewer_id = configured_reviewer or reviewer_id or review_id
        if not isinstance(reviewer_id, str) or not reviewer_id:
            raise RetryPolicyError("reviewer identity is required")
        failure_stop = config.get("repair_failure_stop")
        one_shot = config.get("repair_one_shot")
        if (failure_stop is not None and type(failure_stop) is not bool) or (one_shot is not None and type(one_shot) is not bool):
            raise RetryPolicyError("repair boolean fields must be exact booleans when present")
        if config.get("repair_budget_status") not in {None, "active", "exhausted"}:
            raise RetryPolicyError("repair contract is ambiguous")
        maximum = 1 if one_shot is True else policy.max_repair_cycles
        try:
            state_raw = _read_owned_text(state_fd, "repair-budget.json", required=False)
            state = json.loads(state_raw) if state_raw is not None else {"schema": "CHIEF_REPAIR_BUDGET_V1", "cycles": []}
        except (TypeError, json.JSONDecodeError) as exc:
            raise RetryPolicyError("repair budget log is unreadable") from exc
        if not isinstance(state, dict) or state.get("schema") not in {"CHIEF_REPAIR_BUDGET_V1", "CHIEF_REPAIR_BUDGET_V2"}:
            raise RetryPolicyError("repair budget log schema is invalid")
        try:
            cycles, diagnosis_requests = autonomy_policy.active_phase_state(state)
        except autonomy_policy.AutonomyPolicyError as exc:
            raise RetryPolicyError(str(exc)) from exc
        active = next((phase for phase in state.get("phases", []) if isinstance(phase, dict) and phase.get("phase_id") == state.get("active_phase_id")), None)
        phase_reset = isinstance(state.get("phases"), list) and config.get("autonomy_policy_enabled") is True
        provenance = config.get("repair_stop_provenance", {})
        numeric_override = phase_reset and isinstance(provenance, dict) and all(
            provenance.get(key) == "numeric_local_preparation_limit"
            for key in ("repair_one_shot", "repair_failure_stop", "repair_budget_status")
            if config.get(key) in {True, "exhausted"}
        )
        if phase_reset:
            # A fully evidence-bound autonomy phase has the explicitly
            # approved phase-local allowance.  Legacy project limits remain
            # authoritative everywhere outside this active native phase.
            maximum = AUTONOMY_PHASE_DEFECT_CYCLES
        if continuation_event is not None:
            if config.get("autonomy_policy_enabled") is not True:
                raise RetryPolicyError("continuation classification requires enabled autonomy policy")
            try:
                kind = autonomy_policy.classify_continuation(continuation_event)
            except autonomy_policy.AutonomyPolicyError as exc:
                raise RetryPolicyError(str(exc)) from exc
            if kind != "candidate_defect":
                journal = state.setdefault("continuation_journal", [])
                if not isinstance(journal, list):
                    raise RetryPolicyError("continuation journal is invalid")
                event_id = continuation_event.get("event_id")
                if not isinstance(event_id, str) or not event_id:
                    raise RetryPolicyError("preparation/evidence event_id is required")
                prior = next((item for item in journal if isinstance(item, dict) and item.get("event_id") == event_id), None)
                if prior is not None:
                    if prior != dict(continuation_event):
                        raise RetryPolicyError("preparation/evidence event ID conflicts with retained event")
                    return state
                journal.append(dict(continuation_event))
                _write_state(state_fd, state)
                return state
        if phase_reset:
            if continuation_event is None:
                raise RetryPolicyError("active autonomy phase requires a candidate_defect event")
            if kind != "candidate_defect" or continuation_event.get("candidate_id") != candidate_id:
                raise RetryPolicyError("candidate_defect event must bind the exact candidate")
            started = active.get("started_from") if isinstance(active, dict) else None
            if not isinstance(started, dict) or not isinstance(started.get("new_plan"), str):
                raise RetryPolicyError("active autonomy phase lacks transition package binding")
            required_event = {"event_id", "kind", "scope", "candidate_id", "failure_evidence_ref", "failure_evidence_sha256"}
            if set(continuation_event) != required_event or not isinstance(continuation_event.get("event_id"), str) or not continuation_event["event_id"]:
                raise RetryPolicyError("candidate_defect event must have one normalized retained identity")
            if not isinstance(continuation_event.get("failure_evidence_ref"), str) or not isinstance(continuation_event.get("failure_evidence_sha256"), str):
                raise RetryPolicyError("candidate_defect event requires retained failure evidence")
            if execution_package_id is not None and execution_package_id != started["new_plan"]:
                raise RetryPolicyError("active autonomy phase rejects a different execution package")
            execution_package_id = started["new_plan"]
            if execution_work_id is None:
                # The exact work id is resolved and checked by the C4 package path.
                execution_work_id = "__resolve_from_active_phase__"
        existing_cycle = None
        for cycle in cycles:
            if not isinstance(cycle, dict): raise RetryPolicyError("repair budget event is invalid")
            if cycle.get("repair_id") == repair_id:
                normalized = {"candidate_id": candidate_id, "review_id": review_id, "repair_id": repair_id, "reviewer_id": reviewer_id}
                if phase_reset:
                    normalized["continuation_event"] = dict(continuation_event)
                legacy = {"candidate_id": candidate_id, "review_id": review_id, "repair_id": repair_id}
                if cycle == normalized or cycle == legacy or (
                    set(cycle).issubset(set(normalized) | {"progress_evidence", "stagnant_evidence", "resource_measurement", "review_evidence", "reviewed_artifact", "diagnosis_used"})
                    and all(cycle.get(key) == value for key, value in normalized.items())
                ):
                    recorded_evidence = cycle.get("progress_evidence")
                    if recorded_evidence is not None and progress_evidence is not None and recorded_evidence != dict(progress_evidence):
                        raise RetryPolicyError("repair ID cannot be reused with changed progress evidence")
                    recorded_measurement = cycle.get("resource_measurement")
                    if recorded_measurement is not None and resource_measurement is not None and recorded_measurement != dict(resource_measurement):
                        raise RetryPolicyError("repair ID cannot be reused with changed resource measurement")
                    recorded_review = cycle.get("review_evidence")
                    if recorded_review is not None:
                        if not isinstance(review_evidence, Mapping) or recorded_review != dict(review_evidence):
                            raise RetryPolicyError("repair ID cannot be reused with changed review evidence")
                    # A stagnant round may later receive one native diagnosis
                    # attachment; defer the decision until the active package
                    # and native intake are available below.
                    if diagnosis_evidence is None:
                        return state
                    existing_cycle = cycle
                    break
                raise RetryPolicyError("repair ID conflicts with recorded cycle")
        # Exact retained receipts (and a diagnosis attachment to one) are
        # observations, not a fourth defect.  Apply the phase allowance only
        # after the repair-ID replay/conflict decision above.
        if phase_reset and existing_cycle is None and len(cycles) >= AUTONOMY_PHASE_DEFECT_CYCLES:
            raise RetryPolicyError("active autonomy phase defect allowance exhausted")
        # A retained exact receipt is idempotent even when a later stricter
        # contract stops new repairs.  Check the stop only after that comparison.
        if (failure_stop is True or config.get("repair_budget_status") == "exhausted") and not numeric_override:
            raise RetryPolicyError("repair budget is stopped by its retained stricter contract")
        reviewers = {cycle.get("reviewer_id", cycle.get("review_id")) for cycle in cycles if isinstance(cycle.get("reviewer_id", cycle.get("review_id")), str)}
        if reviewers and reviewers != {reviewer_id}:
            raise RetryPolicyError("repair reviewer identity conflicts with the established independent reviewer")
        configured_package_id = (active.get("started_from", {}).get("new_plan") if phase_reset and isinstance(active, dict) and isinstance(active.get("started_from"), dict) else config.get("execution_package_id"))
        cycle: dict[str, object] = {
            "candidate_id": candidate_id,
            "review_id": review_id,
            "repair_id": repair_id,
            "reviewer_id": reviewer_id,
        }
        if configured_package_id is None:
            if not policy.permit(reviews=1, repairs=len(cycles) + 1, stricter_maximum=maximum):
                raise RetryPolicyError("repair budget exhausted")
        else:
            try:
                if not isinstance(execution_package_id, str) or not execution_package_id or not isinstance(execution_work_id, str) or not execution_work_id:
                    raise continuous_execution.ContinuousExecutionError("continuous consume requires explicit execution_package_id and execution_work_id")
                if execution_package_id != configured_package_id:
                    raise continuous_execution.ContinuousExecutionError("explicit execution_package_id does not match the project contract")
                plan = json.loads(_read_owned_text(state_fd, "project-plan.json", required=True))
                registry = json.loads(_read_owned_text(state_fd, "task-registry.json", required=True))
                approvals = json.loads(_read_owned_text(state_fd, "approval-queue.json", required=True))
                loader = lambda ref, digest, label: _read_retained_json(project_fd, ref, digest, label)
                if native_observation_root is None:
                    raise continuous_execution.ContinuousExecutionError("continuous consume requires an explicit external native observation root")
                try:
                    Path(native_observation_root).absolute().relative_to(Path(project).absolute())
                except ValueError:
                    pass
                else:
                    raise continuous_execution.ContinuousExecutionError("native observation root must be outside the writer project")
                native_fd = _open_project_directory(Path(native_observation_root))
                _require_disjoint_directories(project_fd, native_fd)
                def native_loader(ref, digest, label):
                    if not isinstance(ref, str) or not ref.startswith("native://"):
                        raise RetryPolicyError(f"{label}_ref must be a native:// reference")
                    return _read_retained_json(native_fd, "repo://" + ref.removeprefix("native://"), digest, label)
                continuous_execution.validate_execution_records(plan, registry, approvals, retained_loader=loader, native_observation_loader=native_loader, submitting_project=Path(project), native_observation_root=Path(native_observation_root))
                package = next(
                    (item for item in plan["execution_packages"] if item.get("package_id") == execution_package_id),
                    None,
                )
                if package is None:
                    raise continuous_execution.ContinuousExecutionError("execution_package_id is not present in the approved plan")
                _validate_native_intake(native_intake, package)
                historical_repair_used, local_action_spent = _package_resource_usage(state, package, loader)
                if phase_reset:
                    if (
                        started.get("new_candidate_id") != package.get("candidate_sha256")
                        or started.get("approval_id") != package.get("approval_id")
                        or started.get("writer_task_id") != package.get("writer_task_id")
                    ):
                        raise RetryPolicyError("active autonomy phase native package drifted")
                    failure = loader(continuation_event["failure_evidence_ref"], continuation_event["failure_evidence_sha256"], "candidate defect failure")
                    if (
                        not isinstance(failure, dict)
                        or failure.get("schema") != "CHIEF_CANDIDATE_DEFECT_EVIDENCE_V1"
                        or failure.get("phase_id") != state.get("active_phase_id")
                        or failure.get("candidate_id") != candidate_id
                        or failure.get("package_id") != package.get("package_id")
                        or failure.get("work_id") != package.get("work_id")
                    ):
                        raise RetryPolicyError("candidate_defect failure evidence is missing, drifted, or unbound")
                def diagnosis_for_next_round(review, prior_cycles):
                    binding = None
                    if len(prior_cycles) >= 2 and all(isinstance(item.get("stagnant_evidence"), dict) for item in prior_cycles[-2:]):
                        pair = [item["repair_id"] for item in prior_cycles[-2:]]
                        matches = [item for item in diagnosis_requests if isinstance(item, dict) and item.get("round_ids") == pair]
                        if len(matches) != 1 or matches[0].get("consumed") is not True:
                            raise RetryPolicyError("two stagnant repairs require one consumed native diagnosis")
                        binding = _validate_diagnosis(matches[0].get("diagnosis_evidence"), matches[0], package, reviewer_id, native_loader)
                    if review.get("diagnosis_used") != binding:
                        raise RetryPolicyError("independent review does not bind the diagnosed new path")
                    return binding
                if execution_work_id == "__resolve_from_active_phase__":
                    execution_work_id = package["work_id"]
                if execution_work_id != package["work_id"]:
                    raise continuous_execution.ContinuousExecutionError("execution_work_id must bind the approved package work_id")
                if reviewer_id == package["writer_task_id"]:
                    raise continuous_execution.ContinuousExecutionError("continuous repair reviewer must be independent of the package writer")
                if not isinstance(review_evidence, Mapping):
                    raise continuous_execution.ContinuousExecutionError("continuous consume requires a native independent review receipt")
                observed_review = native_loader(review_evidence.get("evidence_ref"), review_evidence.get("evidence_sha256"), "independent review")
                if (
                    observed_review.get("schema") != "CHIEF_EXECUTION_REVIEW_EVIDENCE_V1"
                    or observed_review.get("kind") != "repair_review"
                    or observed_review.get("repair_id") != repair_id
                    or observed_review.get("review_id") != review_id
                    or observed_review.get("reviewer_task_id") != reviewer_id
                    or observed_review.get("reviewer_task_id") not in package["independent_reviewer_task_ids"]
                    or observed_review.get("work_id") != package["work_id"]
                    or observed_review.get("package_id") != package["package_id"]
                    or observed_review.get("candidate_sha256") != package["candidate_sha256"]
                    or observed_review.get("candidate_id") != candidate_id
                    or observed_review.get("decision") not in {"continue", "repair"}
                    or observed_review.get("coordinator_task_id") != package["native_intake"]["coordinator_task_id"]
                ):
                    raise continuous_execution.ContinuousExecutionError("independent review does not bind the exact active repair")
                if not isinstance(resource_measurement, Mapping):
                    raise continuous_execution.ContinuousExecutionError("continuous consume requires a retained resource measurement")
                observed_measurement = loader(resource_measurement.get("evidence_ref"), resource_measurement.get("evidence_sha256"), "resource measurement")
                if (
                    observed_measurement.get("schema") != "CHIEF_EXECUTION_RESOURCE_MEASUREMENT_V1"
                    or observed_measurement.get("work_id") != package["work_id"]
                    or observed_measurement.get("package_id") != package["package_id"]
                    or observed_measurement.get("resource_unit") != package["resource_limits"]["resource_unit"]
                ):
                    raise continuous_execution.ContinuousExecutionError("resource measurement does not bind the approved work package")
                used = observed_measurement.get("units_used")
                if type(used) is not int or used < 0:
                    raise continuous_execution.ContinuousExecutionError("resource measurement units_used must be a non-negative integer")
                if (existing_cycle is None and used <= historical_repair_used) or used + local_action_spent > package["resource_limits"]["max_resource_units"]:
                    raise continuous_execution.ContinuousExecutionError("execution package resource limit is exhausted")
                if isinstance(progress_evidence, Mapping) == isinstance(stagnant_evidence, Mapping):
                    raise continuous_execution.ContinuousExecutionError("continuous consume needs exactly one progress or stagnant retained observation")
                if isinstance(progress_evidence, Mapping):
                    cycle["progress_evidence"] = continuous_execution.validate_progress_evidence(progress_evidence, Path(project), package, retained_loader=loader)
                else:
                    stagnant = loader(stagnant_evidence.get("evidence_ref"), stagnant_evidence.get("evidence_sha256"), "stagnant observation")
                    if (stagnant.get("schema") != "CHIEF_EXECUTION_STAGNANT_EVIDENCE_V1" or stagnant.get("repair_id") != repair_id
                        or stagnant.get("work_id") != package["work_id"] or stagnant.get("package_id") != package["package_id"]
                        or stagnant.get("candidate_sha256") != package["candidate_sha256"]):
                        raise continuous_execution.ContinuousExecutionError("stagnant observation does not bind the exact active repair")
                    cycle["stagnant_evidence"] = dict(stagnant_evidence)
                cycle["reviewed_artifact"] = _validate_reviewed_artifact(observed_review, candidate_id, progress_evidence if isinstance(progress_evidence, Mapping) else stagnant_evidence, loader, package)
                rounds: list[dict[str, object]] = []
                prior_units: list[int] = []
                prior_measurement_hashes: set[str] = set()
                prior_review_hashes: set[str] = set()
                prior_review_ids: set[str] = set()
                for recorded_index, recorded in enumerate(cycles):
                    if not isinstance(recorded, dict) or not isinstance(recorded.get("repair_id"), str):
                        raise continuous_execution.ContinuousExecutionError("repair budget event is invalid for continuous execution")
                    evidence = recorded.get("progress_evidence")
                    stagnant_record = recorded.get("stagnant_evidence")
                    if not isinstance(evidence, dict) and not isinstance(stagnant_record, dict):
                        raise continuous_execution.ContinuousExecutionError("earlier continuous repair lacks retained outcome evidence")
                    measurement = recorded.get("resource_measurement")
                    if not isinstance(measurement, dict):
                        raise continuous_execution.ContinuousExecutionError("earlier continuous repair lacks retained resource measurement")
                    old_review = recorded.get("review_evidence")
                    if not isinstance(old_review, dict):
                        raise continuous_execution.ContinuousExecutionError("earlier continuous repair lacks native review receipt")
                    old_review_observed = native_loader(old_review.get("evidence_ref"), old_review.get("evidence_sha256"), "historical independent review")
                    old_review_sha = old_review.get("evidence_sha256")
                    if (not isinstance(old_review_sha, str) or old_review_sha in prior_review_hashes or old_review_observed.get("review_id") in prior_review_ids
                        or old_review_observed.get("schema") != "CHIEF_EXECUTION_REVIEW_EVIDENCE_V1" or old_review_observed.get("kind") != "repair_review"
                        or old_review_observed.get("repair_id") != recorded["repair_id"] or old_review_observed.get("review_id") != recorded.get("review_id")
                        or old_review_observed.get("reviewer_task_id") != recorded.get("reviewer_id") or old_review_observed.get("reviewer_task_id") not in package["independent_reviewer_task_ids"]
                        or old_review_observed.get("work_id") != package["work_id"] or old_review_observed.get("package_id") != package["package_id"]
                        or old_review_observed.get("candidate_sha256") != package["candidate_sha256"] or old_review_observed.get("decision") not in {"continue", "repair"}
                        or old_review_observed.get("candidate_id") != recorded.get("candidate_id")
                        or old_review_observed.get("coordinator_task_id") != package["native_intake"]["coordinator_task_id"]):
                        raise continuous_execution.ContinuousExecutionError("independent review receipt cannot be replayed or drift")
                    prior_review_hashes.add(old_review_sha)
                    prior_review_ids.add(old_review_observed["review_id"])
                    old_artifact = _validate_reviewed_artifact(old_review_observed, recorded["candidate_id"], evidence if isinstance(evidence, dict) else stagnant_record, loader, package)
                    if recorded.get("reviewed_artifact") != old_artifact:
                        raise continuous_execution.ContinuousExecutionError("historical reviewed artifact drifted")
                    if recorded.get("diagnosis_used") != diagnosis_for_next_round(old_review_observed, cycles[:recorded_index]):
                        raise RetryPolicyError("historical diagnosis binding drifted")
                    # Re-verify every earlier progress and measurement receipt
                    # through the same held root fd before it contributes again.
                    if isinstance(evidence, dict):
                        evidence = continuous_execution.validate_progress_evidence(evidence, Path(project), package, retained_loader=loader)
                    else:
                        old_stagnant = loader(stagnant_record.get("evidence_ref"), stagnant_record.get("evidence_sha256"), "historical stagnant observation")
                        if old_stagnant.get("repair_id") != recorded["repair_id"] or old_stagnant.get("work_id") != package["work_id"] or old_stagnant.get("package_id") != package["package_id"]:
                            raise continuous_execution.ContinuousExecutionError("historical stagnant observation drifted")
                    historical_measurement = loader(measurement.get("evidence_ref"), measurement.get("evidence_sha256"), "historical resource measurement")
                    if (
                        historical_measurement.get("schema") != "CHIEF_EXECUTION_RESOURCE_MEASUREMENT_V1"
                        or historical_measurement.get("work_id") != package["work_id"]
                        or historical_measurement.get("package_id") != package["package_id"]
                        or historical_measurement.get("resource_unit") != package["resource_limits"]["resource_unit"]
                    ):
                        raise continuous_execution.ContinuousExecutionError("historical resource measurement does not bind the approved work package")
                    historical_used = historical_measurement.get("units_used")
                    if type(historical_used) is not int or historical_used < 0:
                        raise continuous_execution.ContinuousExecutionError("historical resource measurement units_used is invalid")
                    digest = measurement.get("evidence_sha256")
                    if not isinstance(digest, str) or digest in prior_measurement_hashes:
                        raise continuous_execution.ContinuousExecutionError("resource measurement receipt cannot be replayed")
                    prior_measurement_hashes.add(digest); prior_units.append(historical_used)
                    rounds.append({"round_id": recorded["repair_id"], "evidence": evidence if isinstance(evidence, dict) else {"kind":"log_only"}})
                if existing_cycle is not None:
                    if existing_cycle is not cycles[-1] or not isinstance(existing_cycle.get("stagnant_evidence"), dict) or len(cycles) < 2 or not isinstance(cycles[-2].get("stagnant_evidence"), dict):
                        raise continuous_execution.ContinuousExecutionError("diagnosis attachment requires the exact latest stagnant pair")
                    if any(existing_cycle.get(k) != v for k, v in (("resource_measurement", dict(resource_measurement)), ("review_evidence", dict(review_evidence)), ("stagnant_evidence", dict(stagnant_evidence or {})))):
                        raise continuous_execution.ContinuousExecutionError("diagnosis attachment references drifted")
                    requests = diagnosis_requests
                    pair = [cycles[-2]["repair_id"], existing_cycle["repair_id"]]
                    request = next((x for x in requests if isinstance(x, dict) and x.get("round_ids") == pair), None)
                    if not isinstance(request, dict): raise continuous_execution.ContinuousExecutionError("diagnosis request is missing")
                    _validate_diagnosis(diagnosis_evidence, request, package, reviewer_id, native_loader)
                    if request.get("consumed") and request.get("diagnosis_evidence") != dict(diagnosis_evidence): raise continuous_execution.ContinuousExecutionError("diagnosis receipt conflicts")
                    request["consumed"] = True; request["diagnosis_evidence"] = dict(diagnosis_evidence); _write_state(state_fd, state); return state
                current_review_sha = review_evidence.get("evidence_sha256")
                if current_review_sha in prior_review_hashes or review_id in prior_review_ids:
                    raise continuous_execution.ContinuousExecutionError("independent review receipt cannot be replayed or drift")
                if prior_units and used <= prior_units[-1]:
                    raise continuous_execution.ContinuousExecutionError("resource measurement must be fresh and cumulative")
                if resource_measurement.get("evidence_sha256") in prior_measurement_hashes:
                    raise continuous_execution.ContinuousExecutionError("resource measurement receipt cannot be replayed")
                diagnosis_binding = diagnosis_for_next_round(observed_review, cycles)
                if diagnosis_binding is not None:
                    cycle["diagnosis_used"] = diagnosis_binding
                rounds.append({"round_id": repair_id, "evidence": cycle.get("progress_evidence", {"kind":"log_only"})})
                if isinstance(progress_evidence, Mapping) and not continuous_execution.permits_continuous_cycle(package, rounds):
                    raise continuous_execution.ContinuousExecutionError("continuous repair requires distinct real progress within its approved bound")
                if maximum < 3 and len(cycles) + 1 > maximum:
                    raise continuous_execution.ContinuousExecutionError("retained stricter legacy repair limit wins over continuous execution")
                cycle["resource_measurement"] = dict(resource_measurement)
                cycle["review_evidence"] = dict(review_evidence)
                if phase_reset:
                    cycle["continuation_event"] = dict(continuation_event)
                if isinstance(stagnant_evidence, Mapping):
                    previous = cycles[-1] if cycles else None
                    if isinstance(previous, dict) and isinstance(previous.get("stagnant_evidence"), dict):
                        request_id = "diagnosis:" + previous["repair_id"] + ":" + repair_id
                        requests = diagnosis_requests
                        if not any(isinstance(item, dict) and item.get("request_id") == request_id for item in requests):
                            requests.append({"request_id":request_id,"round_ids":[previous["repair_id"],repair_id],"work_id":package["work_id"],"package_id":package["package_id"],"candidate_sha256":package["candidate_sha256"],"consumed":False})
                        if isinstance(diagnosis_evidence, Mapping):
                            request = requests[-1]
                            if request.get("consumed") is True:
                                raise RetryPolicyError("diagnosis already consumed")
                            _validate_diagnosis(diagnosis_evidence, request, package, reviewer_id, native_loader)
                            request["consumed"] = True; request["diagnosis_evidence"] = dict(diagnosis_evidence)
            except continuous_execution.ContinuousExecutionError as exc:
                raise RetryPolicyError(str(exc)) from exc
        if existing_cycle is not None:
            # The diagnosis branch above updated only diagnosis_requests.  It
            # must not duplicate the repair cycle, resource receipt, or budget.
            _write_state(state_fd, state)
            return state
        cycles.append(cycle)
        _write_state(state_fd, state)
        return state
    finally:
        for fd in (native_fd, state_fd, project_fd):
            if fd is None:
                continue
            try:
                os.close(fd)
            except OSError:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True)
    parser.add_argument("consume")
    parser.add_argument("--candidate-id", required=True); parser.add_argument("--review-id", required=True); parser.add_argument("--repair-id", required=True); parser.add_argument("--reviewer-id"); parser.add_argument("--progress-evidence-json"); parser.add_argument("--stagnant-evidence-json"); parser.add_argument("--diagnosis-evidence-json"); parser.add_argument("--review-evidence-json"); parser.add_argument("--native-intake-json"); parser.add_argument("--execution-package-id"); parser.add_argument("--execution-work-id"); parser.add_argument("--resource-measurement-json"); parser.add_argument("--continuation-event-json"); parser.add_argument("--native-observation-root")
    args = parser.parse_args(argv)
    try:
        def mapping(raw: str | None) -> dict | None:
            value = json.loads(raw) if raw else None
            if value is not None and not isinstance(value, dict):
                raise RetryPolicyError("CLI evidence JSON must be an object")
            return value
        print(json.dumps(consume_repair_cycle(Path(args.project), args.candidate_id, args.review_id, args.repair_id, reviewer_id=args.reviewer_id, progress_evidence=mapping(args.progress_evidence_json), stagnant_evidence=mapping(args.stagnant_evidence_json), diagnosis_evidence=mapping(args.diagnosis_evidence_json), review_evidence=mapping(args.review_evidence_json), native_intake=mapping(args.native_intake_json), execution_package_id=args.execution_package_id, execution_work_id=args.execution_work_id, resource_measurement=mapping(args.resource_measurement_json), continuation_event=mapping(args.continuation_event_json), native_observation_root=Path(args.native_observation_root) if args.native_observation_root else None), sort_keys=True)); return 0
    except (OSError, json.JSONDecodeError, RetryPolicyError) as exc:
        print(f"error: {exc}"); return 2


if __name__ == "__main__":
    raise SystemExit(main())
