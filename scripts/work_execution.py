"""Versioned work admission and explicit adoption; never a background scheduler.

Evidence is retained-file integrity, not independent authorization. Callers still
obey host permissions and existing approval/continuous-execution contracts.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import fcntl
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import uuid

VERSION = 'WORK_EXECUTION_V1'
ACTIVE = {'queued', 'running', 'needs_attention'}
KINDS = {'operation', 'repair', 'investigation', 'new_product', 'product_change'}
SENSITIVE = {'authentication', 'permissions', 'funds', 'migration', 'irreversible'}


class WorkExecutionError(ValueError):
    pass


def enabled(project):
    return project.get('work_execution_version') == VERSION


def _init():
    # Lazy import keeps init_project's validation integration acyclic.
    import init_project
    return init_project


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value) is not None


def _path(root, value):
    if not _text(value) or '\\' in value or ':' in value:
        raise WorkExecutionError('write surface must be a project-relative POSIX path')
    p = PurePosixPath(value)
    if p.is_absolute() or '..' in p.parts or value != p.as_posix() or value == '.':
        raise WorkExecutionError('unsafe or non-normalized project path')
    cursor = root
    for part in p.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise WorkExecutionError('symlinked project path')
    return cursor


def _proof(root, value):
    if not isinstance(value, dict) or not _digest(value.get('sha256')):
        raise WorkExecutionError('evidence needs a retained reference and SHA-256')
    ref = value.get('ref')
    if not isinstance(ref, str) or not ref.startswith('repo://'):
        raise WorkExecutionError('work evidence must use repo://')
    path = _path(root, ref[7:])
    if not path.is_file() or path.stat().st_nlink != 1:
        raise WorkExecutionError('evidence must be an existing single-link regular file')
    if hashlib.sha256(path.read_bytes()).hexdigest() != value['sha256']:
        raise WorkExecutionError('evidence bytes changed')


def _proofs(root, values, *, required=True):
    if not isinstance(values, list) or (required and not values):
        raise WorkExecutionError('required evidence list is missing')
    for value in values:
        _proof(root, value)


def continuity_key(work):
    # Owner, phase, revision, path, work ID and candidate changes deliberately
    # cannot mint another allowance for the same accepted outcome.
    values = sorted(work['acceptance_ids'])
    return hashlib.sha256(json.dumps(values, separators=(',', ':')).encode()).hexdigest()


def _overlap(left, right):
    return any(a == b or a.startswith(b + '/') or b.startswith(a + '/') for a in left for b in right)


def _read(root, filename):
    path = _path(root, '.chief-of-staff/' + filename)
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise WorkExecutionError(filename + ' must be an object')
    return value


def _root(target):
    root = Path(target).absolute()
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise WorkExecutionError('symlinked project root is not supported')
    return root


def validate_retained_proof(root, value):
    """Validate existing repository-bound proof bytes for trusted callers."""
    _proof(_root(root), value)


def _structure(root, project, plan, registry, work):
    if not isinstance(work, dict):
        raise WorkExecutionError('work item must be an object')
    for key in ('work_id', 'phase_id', 'goal', 'lineage_id'):
        if not _text(work.get(key)):
            raise WorkExecutionError('missing ' + key)
    if work.get('kind') not in KINDS or work.get('status') not in ACTIVE | {'blocked', 'completed', 'cancelled'}:
        raise WorkExecutionError('invalid work kind or status')
    if not _digest(work.get('input_sha256')):
        raise WorkExecutionError('work requires exact input_sha256')
    manifest = work.get('inputs')
    if not isinstance(manifest, list) or not manifest:
        raise WorkExecutionError('inputs must list current source files and hashes')
    if hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()).hexdigest() != work['input_sha256']:
        raise WorkExecutionError('input manifest does not match input_sha256')
    criteria = work.get('acceptance_ids')
    known = {c['criterion_id'] for c in plan.get('acceptance_criteria', []) if isinstance(c, dict) and 'criterion_id' in c}
    if not isinstance(criteria, list) or not criteria or any(not _text(c) or c not in known for c in criteria) or len(set(criteria)) != len(criteria):
        raise WorkExecutionError('work must bind existing final acceptance IDs')
    if work['phase_id'] not in {p.get('phase_id') for p in plan.get('phases', []) if isinstance(p, dict)}:
        raise WorkExecutionError('work phase does not exist')
    source = work.get('source', {})
    if not isinstance(source, dict) or not _text(source.get('repository')) or not _text(source.get('revision')):
        raise WorkExecutionError('source repository and revision required')
    _proof(root, source.get('evidence'))
    surface = work.get('write_surface')
    if not isinstance(surface, list):
        raise WorkExecutionError('write_surface must be a list')
    for path in surface:
        _path(root, path)
    executor = work.get('executor', {})
    if not isinstance(executor, dict) or not _text(executor.get('id')):
        raise WorkExecutionError('executor identity required')
    if executor.get('kind') == 'chief':
        if executor['id'] != project.get('primary_task_id', project.get('primary_task_title')):
            raise WorkExecutionError('chief executor identity mismatch')
    elif executor.get('kind') == 'task':
        task = next((t for t in registry.get('tasks', []) if t.get('task_id') == executor['id']), None)
        if not task or task.get('phase_id') != work['phase_id'] or task.get('execution_work_id') != work['work_id']:
            raise WorkExecutionError('delegation must bind an existing task and work ID')
        if sorted(task.get('write_surface', [])) != sorted(surface):
            raise WorkExecutionError('delegated surface does not match task contract')
        if work['status'] in ACTIVE and task.get('status') in {'completed', 'archived', 'failed'}:
            raise WorkExecutionError('inactive task cannot own active work')
    else:
        raise WorkExecutionError('executor kind must be chief or task')
    budget = work.get('budget', {})
    if not isinstance(budget, dict) or not _integer(budget.get('limit'), 1) or not _text(budget.get('reason')):
        raise WorkExecutionError('finite positive attempt budget and causal basis required')
    resources = work.get('resources', {})
    if not isinstance(resources, dict) or resources.get('weight') not in {'light', 'heavy'}:
        raise WorkExecutionError('resources weight must be light or heavy')
    if resources.get('memory_mb') is not None and not _integer(resources['memory_mb'], 1):
        raise WorkExecutionError('invalid memory estimate')
    risk = work.get('risk', {})
    if not isinstance(risk, dict) or risk.get('level') not in {'low', 'medium', 'high'} or not isinstance(risk.get('domains'), list):
        raise WorkExecutionError('risk classification required')
    if any(d not in SENSITIVE for d in risk['domains']):
        raise WorkExecutionError('unknown risk domain')
    review = work.get('review', {})
    if not isinstance(review, dict) or review.get('mode') not in {'self', 'independent'} or not _text(review.get('reviewer')):
        raise WorkExecutionError('review route and identity required')
    if risk['level'] == 'high' or risk['domains']:
        if review['mode'] != 'independent':
            raise WorkExecutionError('sensitive work requires independent review')
    if review['mode'] == 'independent':
        reviewers = [t for t in registry.get('tasks', []) if t.get('task_id') == review['reviewer']]
        if review['reviewer'] == executor['id'] or not reviewers or reviewers[0].get('write_surface'):
            raise WorkExecutionError('independent reviewer must be a registered read-only non-writer')
    if review['mode'] == 'self' and review['reviewer'] != executor['id']:
        raise WorkExecutionError('self review must identify writer')
    for field in ('prechecks', 'acceptance_checks'):
        if not isinstance(work.get(field), list) or not work[field]:
            raise WorkExecutionError(field + ' cannot be empty')
        names = set()
        for check in work[field]:
            if not isinstance(check, dict) or not _text(check.get('name')) or check['name'] in names:
                raise WorkExecutionError('check names must be unique')
            names.add(check['name'])
            if check.get('status') not in {'passed', 'pending', 'failed'}:
                raise WorkExecutionError('invalid check status')
            if check['status'] == 'passed':
                _proof(root, check.get('evidence'))
    d = work.get('discovery', {})
    if not isinstance(d, dict) or d.get('basis') not in {'existing', 'targeted', 'full', 'affected'}:
        raise WorkExecutionError('discovery basis required')
    if not isinstance(d.get('unresolved_product_decisions'), list) or not isinstance(d.get('affected_areas'), list):
        raise WorkExecutionError('discovery decisions/affected areas required')
    _proofs(root, d.get('evidence'))


def _discovery(work, discovery):
    d = work['discovery']
    if work['kind'] in {'operation', 'repair'}:
        if d.get('existing_behavior_confirmed') is not True:
            raise WorkExecutionError('operation requires an evidence-backed existing behavior confirmation')
    if d['unresolved_product_decisions'] and work['kind'] != 'investigation':
        raise WorkExecutionError('unresolved product decisions block execution')
    if work['kind'] == 'new_product':
        if d['basis'] != 'full':
            raise WorkExecutionError('new product requires full product discovery')
    elif work['kind'] == 'product_change':
        if d['basis'] != 'affected' or not d['affected_areas'] or any(not _text(x) for x in d['affected_areas']):
            raise WorkExecutionError('product change requires affected-area discovery')
    elif work['kind'] == 'investigation':
        if d['basis'] != 'targeted' or work['write_surface']:
            raise WorkExecutionError('targeted investigation is read-only until decisions resolve')
    elif d['basis'] != 'existing':
        raise WorkExecutionError('operation/repair must establish existing accepted behavior')


def _current_discovery(root, work, discovery):
    """Admit this surface against current decisions without invalidating history."""
    if work['kind'] == 'investigation':
        return
    if work['kind'] == 'new_product' and discovery.get('gate_status') != 'passed':
        raise WorkExecutionError('new product requires full product discovery')
    decision = discovery.get('gate_decision', {})
    blocked = (discovery.get('gate_status') == 'blocked'
               or decision.get('material_direction_status') not in {None, 'no_conflict', 'not_applicable', 'resolved'}
               or bool(decision.get('conditions')))
    if not blocked:
        return
    unaffected = work['discovery'].get('unaffected_by_current_gate', {})
    digest = hashlib.sha256(json.dumps(discovery, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    if (work['kind'] not in {'operation', 'repair'} or not isinstance(unaffected, dict)
            or unaffected.get('gate_sha256') != digest
            or unaffected.get('acceptance_ids') != work['acceptance_ids']
            or unaffected.get('write_surface') != work['write_surface']
            or not _text(unaffected.get('reason'))):
        raise WorkExecutionError('retained unresolved product requirements block dependent execution')
    _proof(root, unaffected.get('evidence'))


def _checks(root, checks, inputs):
    for check in checks:
        if check['status'] != 'passed' or check.get('input_sha256') != inputs:
            raise WorkExecutionError('required check is failed, missing, or stale')
        _proof(root, check.get('evidence'))


def validate_records(root, project, plan, registry, discovery):
    """Integrity and completion validation; queued failed prechecks are legal."""
    errors = []
    version = project.get('work_execution_version')
    if version is None:
        if plan.get('work_items'):
            errors.append('work_items require explicit WORK_EXECUTION_V1 adoption')
        return errors
    if version != VERSION:
        return ['unknown work_execution_version']
    if project.get('chief_schema_version') != 2 or not _text(project.get('chief_version')) or not isinstance(project.get('chief_source_commit'), str) or not re.fullmatch(r'[a-f0-9]{40}', project['chief_source_commit']):
        return ['adopted project requires Chief schema/version and exact source commit']
    works = plan.get('work_items', [])
    history = plan.get('work_history', [])
    if not isinstance(works, list) or not isinstance(history, list):
        return ['work_items and work_history must be lists']
    seen = set()
    for w in works:
        try:
            _structure(root, project, plan, registry, w)
            if w['work_id'] in seen:
                raise WorkExecutionError('duplicate work ID')
            seen.add(w['work_id'])
            if w['status'] in ACTIVE | {'completed'}:
                if plan.get('goal_status') != 'confirmed':
                    raise WorkExecutionError('active work requires confirmed goal')
                _discovery(w, discovery)
            if w['status'] == 'completed':
                _checks(root, w['acceptance_checks'], w['input_sha256'])
                r = w['review']
                if r.get('input_sha256') != w['input_sha256']:
                    raise WorkExecutionError('stale completion review')
                _proofs(root, r.get('evidence'))
        except (WorkExecutionError, TypeError, KeyError, AttributeError, OSError) as exc:
            errors.append('work item: ' + str(exc))
    if errors:
        return errors
    running = [w for w in works if isinstance(w, dict) and w.get('status') == 'running']
    for i, a in enumerate(running):
        for b in running[i + 1:]:
            if _overlap(a.get('write_surface', []), b.get('write_surface', [])) or a.get('executor') == b.get('executor'):
                errors.append('conflicting active writers')
        for task in registry.get('tasks', []):
            if task.get('status') == 'running' and task.get('task_id') != a.get('executor', {}).get('id') and _overlap(a.get('write_surface', []), task.get('write_surface', [])):
                errors.append('work conflicts with registered running task')
    event_ids = set()
    for e in history:
        try:
            if not isinstance(e, dict) or not _text(e.get('event_id')) or e['event_id'] in event_ids:
                raise WorkExecutionError('duplicate/missing history event')
            event_ids.add(e['event_id'])
            criteria = e.get('acceptance_ids')
            if not isinstance(criteria, list) or not criteria or any(not _text(c) for c in criteria):
                raise WorkExecutionError('history must retain original acceptance identity')
            if e.get('continuity_key') != continuity_key(e) or not _text(e.get('work_id')) or not _text(e.get('executor_id')) or not _digest(e.get('input_sha256')):
                raise WorkExecutionError('history identity is incomplete or changed')
            if not _digest(e.get('continuity_key')) or not _integer(e.get('budget_limit'), 1) or e.get('status') not in {'running', 'finished', 'failed'}:
                raise WorkExecutionError('invalid work history')
            if not _text(e.get('lineage_id')) or not _text(e.get('goal')):
                raise WorkExecutionError('history must preserve lineage and original goal')
            if e.get('progress') is not None:
                _progress(root, e['progress'], e['acceptance_ids'])
        except (WorkExecutionError, OSError) as exc:
            errors.append('work history: ' + str(exc))
    if plan.get('project_status') == 'completed' and any(w.get('status') not in {'completed', 'cancelled'} for w in works if isinstance(w, dict)):
        errors.append('project completion requires work closure')
    return errors


def _progress(root, value, criteria):
    if not isinstance(value, dict) or value.get('kind') not in {'acceptance_gain', 'blocker_removed', 'reproduced_cause'}:
        raise WorkExecutionError('progress needs an acceptance gain, removed blocker or reproduced cause')
    if value.get('criterion_id') not in criteria or not _text(value.get('before')) or not _text(value.get('after')) or value['before'] == value['after']:
        raise WorkExecutionError('progress must bind a changed observation to accepted outcome')
    _proof(root, value.get('evidence'))


def _usage(plan, work):
    # Overlapping final acceptance IDs share their retained allowance, including
    # a replacement that changes ID or combines an old outcome with a new one.
    history = [e for e in plan.get('work_history', []) if
               set(e.get('acceptance_ids', [])) & set(work['acceptance_ids'])
               or e.get('work_id') == work['work_id']
               or e.get('goal') == work['goal']
               or e.get('lineage_id') == work.get('lineage_id')]
    limit = min([work['budget']['limit']] + [e['budget_limit'] for e in history])
    return history, limit


def _admission(root, project, plan, registry, work):
    if work['status'] not in {'queued', 'needs_attention'}:
        raise WorkExecutionError('work is not ready for a new attempt')
    if project.get('paused') or plan.get('project_status') != 'active':
        raise WorkExecutionError('project is paused or inactive')
    if project.get('repair_failure_stop') or project.get('repair_one_shot') or project.get('repair_budget_status') == 'exhausted':
        raise WorkExecutionError('retained stricter repair stop applies')
    # Continuous packages retain their separate independently checked executor;
    # V1 cannot become a second entrypoint that bypasses native authorization.
    if plan.get('execution_packages'):
        raise WorkExecutionError('continuous packages must use their existing authorized consumer')
    for t in registry.get('tasks', []):
        if t.get('status') == 'running':
            for surface in t.get('write_surface', []):
                _path(root, surface)
    if any(t.get('status') == 'running' and t.get('task_id') != work['executor']['id'] and _overlap(work['write_surface'], t.get('write_surface', [])) for t in registry.get('tasks', [])):
        raise WorkExecutionError('write surface held by another task')
    other = [w for w in plan['work_items'] if w['work_id'] != work['work_id'] and w['status'] == 'running']
    if any(_overlap(work['write_surface'], w['write_surface']) or work['executor'] == w['executor'] for w in other):
        raise WorkExecutionError('write surface or executor already busy')
    _current_discovery(root, work, _read(root, 'product-discovery.json'))
    for entry in work['inputs']:
        _proof(root, entry)
    _checks(root, work['prechecks'], work['input_sha256'])
    history, limit = _usage(plan, work)
    if len(history) >= limit:
        raise WorkExecutionError('cumulative work budget exhausted')
    if any(e['status'] == 'running' for e in history):
        raise WorkExecutionError('unresolved previous attempt; observe before retry')
    if history:
        retry = work.get('retry', {})
        if not isinstance(retry, dict) or not _text(retry.get('correction')):
            raise WorkExecutionError('retry requires changed corrective action')
        _proof(root, retry.get('cause'))
        if retry['cause']['sha256'] in {e.get('cause_sha256') for e in history}:
            raise WorkExecutionError('replayed retry cause is not new information')
        stagnant = len(history) >= 2 and all(not e.get('progress') for e in history[-2:])
        if stagnant:
            diagnosis = retry.get('diagnosis', {})
            if not isinstance(diagnosis, dict) or not _text(diagnosis.get('reviewer')) or diagnosis['reviewer'] in {e['executor_id'] for e in history[-2:]} | {work['executor']['id']}:
                raise WorkExecutionError('two stagnant rounds require independent diagnosis')
            reviewers = [t for t in registry.get('tasks', []) if t.get('task_id') == diagnosis['reviewer']]
            prior_writers = {e['executor_id'] for e in history}
            if not reviewers or reviewers[0].get('write_surface') or diagnosis['reviewer'] in prior_writers:
                raise WorkExecutionError('independent diagnosis requires a registered read-only non-writer')
            if diagnosis.get('event_ids') != [e['event_id'] for e in history[-2:]] or not _text(diagnosis.get('new_path')):
                raise WorkExecutionError('diagnosis must bind stagnant rounds and new path')
            _proof(root, diagnosis.get('evidence'))
    if work['resources']['weight'] == 'heavy':
        heavy = [w for w in other if w['resources']['weight'] == 'heavy']
        represented = {w['executor']['id'] for w in other} | {work['executor']['id']}
        legacy = [t for t in registry.get('tasks', []) if t.get('status') == 'running' and t.get('task_id') not in represented]
        if any(t.get('resources', {}).get('weight') != 'light' for t in legacy):
            raise WorkExecutionError('classify or finish unmanaged running task before heavy admission')
        throughput = _read(root, 'throughput.json')
        observation = throughput.get('resource_observation')
        cap = 1
        if observation is not None:
            if not isinstance(observation, dict):
                raise WorkExecutionError('invalid resource observation')
            _proof(root, observation.get('evidence'))
            if not _integer(observation.get('heavy_limit'), 1) or not _integer(observation.get('available_memory_mb'), 1):
                raise WorkExecutionError('resource limits require measured memory and positive heavy limit')
            try:
                age = (datetime.now(timezone.utc) - datetime.fromisoformat(observation['observed_at'])).total_seconds()
            except (KeyError, ValueError, TypeError):
                raise WorkExecutionError('resource observation timestamp invalid')
            if not 0 <= age <= 300:
                raise WorkExecutionError('resource observation stale; refresh before heavy work')
            cap = observation['heavy_limit']
            requested = work['resources']['memory_mb']
            if requested is None or any(w['resources']['memory_mb'] is None for w in heavy):
                cap = 1
            elif sum(w['resources']['memory_mb'] for w in heavy) + requested > observation['available_memory_mb']:
                raise WorkExecutionError('insufficient observed memory headroom')
        if len(heavy) >= cap:
            raise WorkExecutionError('heavy work capacity unavailable')


def check_work(target, work_id):
    root = _root(target)
    errors = _init().validate(root)
    if errors:
        raise WorkExecutionError('; '.join(errors))
    project, plan, registry = (_read(root, n) for n in ('project.json', 'project-plan.json', 'task-registry.json'))
    if not enabled(project):
        raise WorkExecutionError('explicit work execution adoption required')
    _, source_version, source_commit = _source_identity()
    lock = _read(root, 'chief-lock.json')
    if lock.get('source_commit') != source_commit or project.get('chief_source_commit') != source_commit or lock.get('version') != source_version['version']:
        raise WorkExecutionError('installed Chief differs from project pin; use pinned source or explicit sync')
    for path, digest in lock.get('managed_files', {}).items():
        if _managed_hash(root, path) != digest:
            raise WorkExecutionError('Chief-managed instruction conflict; sync must not overwrite it')
    work = next((w for w in plan.get('work_items', []) if w['work_id'] == work_id), None)
    if work is None:
        raise WorkExecutionError('unknown work ID')
    _admission(root, project, plan, registry, work)
    return True


@contextmanager
def _lock(root):
    # Lock the existing directory, no sidecar on read-only previews.
    fd = __import__('os').open(root / '.chief-of-staff', __import__('os').O_RDONLY | __import__('os').O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    except BlockingIOError as exc:
        raise WorkExecutionError('project state writer is busy') from exc
    finally:
        __import__('os').close(fd)


def claim_work(target, work_id):
    """Atomically persist admission/spend before starting an expensive action."""
    root = _root(target)
    with _lock(root):
        check_work(root, work_id)
        plan = _read(root, 'project-plan.json')
        work = next(w for w in plan['work_items'] if w['work_id'] == work_id)
        event = {'event_id': str(uuid.uuid4()), 'work_id': work_id, 'goal': work['goal'], 'lineage_id': work['lineage_id'],
                 'continuity_key': continuity_key(work), 'acceptance_ids': work['acceptance_ids'],
                 'executor_id': work['executor']['id'], 'input_sha256': work['input_sha256'],
                 'budget_limit': work['budget']['limit'], 'status': 'running', 'progress': None,
                 'cause_sha256': work.get('retry', {}).get('cause', {}).get('sha256')}
        plan.setdefault('work_history', []).append(event)
        work['status'] = 'running'
        _init().transactional_write(root, [(root / '.chief-of-staff/project-plan.json', _init().encoded_json(plan))])
        return event['event_id']


def finish_work(target, work_id, event_id, *, result=None, failed=False):
    """Release only the exact persisted claim; leave crash claims held for diagnosis."""
    root = _root(target)
    with _lock(root):
        plan = _read(root, 'project-plan.json')
        event = next((e for e in plan.get('work_history', []) if e['event_id'] == event_id), None)
        if event is None or event['work_id'] != work_id:
            raise WorkExecutionError('unknown or wrong-work claim')
        if event['status'] != 'running':
            return  # idempotent completion never overwrites retained result
        work = next((w for w in plan['work_items'] if w['work_id'] == work_id), None)
        if work is None or work['executor']['id'] != event['executor_id'] or work['input_sha256'] != event['input_sha256']:
            raise WorkExecutionError('work changed while action was running; retain claim for diagnosis')
        event['status'] = 'failed' if failed else 'finished'
        if isinstance(result, dict) and result.get('progress') is not None:
            try:
                _progress(root, result['progress'], event['acceptance_ids'])
                prior = {e.get('progress', {}).get('evidence', {}).get('sha256') for e in plan['work_history'] if isinstance(e.get('progress'), dict)}
                if result['progress']['evidence']['sha256'] not in prior:
                    event['progress'] = result['progress']
            except (WorkExecutionError, OSError):
                event['status'] = 'failed'
        work['status'] = 'needs_attention'
        _init().transactional_write(root, [(root / '.chief-of-staff/project-plan.json', _init().encoded_json(plan))])


def run_work(target, work_id, action):
    """Run one admitted local callback. This does not authorize protected actions."""
    event_id = claim_work(target, work_id)
    result = None
    failed = True
    try:
        result = action()
        failed = False
        return result
    finally:
        finish_work(target, work_id, event_id, result=result, failed=failed)


def _source_identity():
    import subprocess
    source = Path(__file__).resolve().parents[1]
    version = json.loads((source / 'chief-version.json').read_text())
    commit = subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'], check=True,
                            capture_output=True, text=True).stdout.strip()
    return source, version, commit


def _managed_hash(root, path):
    file = _path(root, path)
    return hashlib.sha256(file.read_bytes()).hexdigest() if file.is_file() else None


def sync_project(target, *, decision_ref, apply=False, source_commit=None,
                 source_version=None, fail_after_writes=None):
    """Preview/apply only known Chief policy fields and managed instruction bytes.

    Caller supplies explicit adoption authority. Locks are provenance/conflict
    detection, never authorization receipts. Unknown legacy edits are conflicts.
    """
    root = _root(target)
    source, version, commit = _source_identity()
    if source_commit is not None and source_commit != commit:
        raise WorkExecutionError('source commit must match this fixed checkout')
    if source_version is not None and source_version != version['version']:
        raise WorkExecutionError('source version mismatch')
    if not _text(decision_ref):
        raise WorkExecutionError('explicit adoption decision reference required')
    with _lock(root):
        lock_path = _path(root, '.chief-of-staff/chief-lock.json')
        old_lock = json.loads(lock_path.read_text()) if lock_path.is_file() else None
        if old_lock is not None:
            if not isinstance(old_lock, dict) or old_lock.get('schema_version') != 2 or not isinstance(old_lock.get('managed_files'), dict):
                raise WorkExecutionError('unrecognized source lock; resolve migration conflict')
            for path, digest in old_lock['managed_files'].items():
                if _managed_hash(root, path) != digest:
                    return {'changes': [], 'conflicts': [path + ': managed content changed'], 'applied': False}
        errors = _init().validate(root)
        if errors:
            return {'changes': [], 'conflicts': errors, 'applied': False}
        project = _read(root, 'project.json')
        plan = _read(root, 'project-plan.json')
        goal_loop_version = version.get('goal_loop_version')
        if (old_lock and old_lock.get('source_commit') == commit
                and old_lock.get('version') == version['version']
                and enabled(project)
                and (goal_loop_version is None
                     or project.get('goal_loop_version') == goal_loop_version)):
            return {'changes': [], 'conflicts': [], 'applied': False}
        if project.get('work_execution_version') not in {None, VERSION}:
            raise WorkExecutionError('unknown work execution version')
        if project.get('paused') or any(t.get('status') == 'running' for t in _read(root, 'task-registry.json').get('tasks', [])) or any(w.get('status') == 'running' for w in plan.get('work_items', [])):
            return {'changes': [], 'conflicts': ['adopt at a safe boundary; running/paused work retained'], 'applied': False}
        project['work_execution_version'] = VERSION
        if goal_loop_version is not None:
            project['goal_loop_version'] = goal_loop_version
        project['chief_version'] = version['version']
        project['chief_schema_version'] = version['schema_version']
        project['chief_source_commit'] = commit
        project['work_execution_adoption'] = {'decision_ref': decision_ref, 'adopted_at': datetime.now(timezone.utc).isoformat()}
        plan.setdefault('work_items', [])
        plan.setdefault('work_history', [])
        instruction = (source / 'assets/chief-project-entry.md').read_text()
        agents = _path(root, 'AGENTS.md')
        original = agents.read_text()
        decisions = _path(root, '.chief-of-staff/decisions.md')
        planned = [(root / '.chief-of-staff/project.json', _init().encoded_json(project)),
                   (root / '.chief-of-staff/project-plan.json', _init().encoded_json(plan)),
                   (decisions, (decisions.read_text() + '\n- Adopt ' + version['version'] + ' @ ' + commit + ': ' + decision_ref + '. Preserve identity, approvals and failure history.\n').encode())]
        managed = {}
        if project.get('agent_os_mode') == _init().AGENT_OS_MODE:
            files = _init().agent_os.render_contract_files(project['project_name'], codex_instructions=instruction)
            for relative, data in files.items():
                path = _path(root, relative)
                if path.read_bytes() != data:
                    planned.append((path, data))
                # Track instruction adapters, not mutable project history.
                if relative in {'AGENTS.md', '.agent-os/manifest.json'}:
                    managed[relative] = hashlib.sha256(data).hexdigest()
        else:
            prior = (source / 'assets/compat/pre-work-execution-AGENTS.md').read_text().replace('{{PROJECT_NAME}}', project['project_name'])
            current = _init().render(_init().TEMPLATE_ROOT / 'AGENTS.md', project['project_name']).decode()
            if original not in {prior, current, instruction}:
                return {'changes': [], 'conflicts': ['AGENTS.md: unrecognized manual instructions'], 'applied': False}
            planned.append((agents, instruction.encode()))
            managed['AGENTS.md'] = hashlib.sha256(instruction.encode()).hexdigest()
        lock = {'schema_version': 2, 'version': version['version'], 'source_commit': commit,
                'repository': 'https://github.com/rong2qi/chief-of-staff-codex.git',
                'managed_files': managed}
        planned.append((lock_path, _init().encoded_json(lock)))
        planned = [(p, data) for p, data in planned if not p.is_file() or p.read_bytes() != data]
        if apply:
            _init().transactional_write(root, planned, fail_after_writes=fail_after_writes,
                                        post_write_check=lambda: _init().validate(root))
        return {'version': version['version'], 'source_commit': commit,
                'changes': [str(p.relative_to(root)) for p, _ in planned], 'conflicts': [], 'applied': apply}


def adopt(target, *, decision_ref, apply=False, fail_after_writes=None):
    result = sync_project(target, decision_ref=decision_ref, apply=apply,
                          fail_after_writes=fail_after_writes)
    if result['conflicts']:
        raise WorkExecutionError('; '.join(result['conflicts']))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--target', required=True, type=Path)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--preview-adoption', action='store_true')
    group.add_argument('--adopt', action='store_true')
    group.add_argument('--check-work')
    p.add_argument('--decision-ref')
    args = p.parse_args()
    try:
        result = check_work(args.target, args.check_work) if args.check_work else adopt(args.target, decision_ref=args.decision_ref or ('preview-only' if args.preview_adoption else ''), apply=args.adopt)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except (WorkExecutionError, OSError, ValueError, _init().WriteTransactionError) as exc:
        print(str(exc), file=__import__('sys').stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
