#!/usr/bin/env python3
"""Cheap-first Chief sync/fleet migration. No push, reset, stash, or business tests."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

SOURCE = Path(__file__).resolve().parents[1]
AUTHOR_EMAIL = '249084307+rong2qi@users.noreply.github.com'


class SyncConflict(ValueError):
    pass


def _git(target, *args):
    result = subprocess.run(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
                             '-c', 'commit.gpgsign=false', '-c', 'user.name=rong2qi',
                             '-c', f'user.email={AUTHOR_EMAIL}', '-C', str(target), *args],
                            text=True, capture_output=True, check=False)
    if result.returncode:
        raise SyncConflict(result.stderr.strip() or result.stdout.strip() or 'Git command failed')
    return result.stdout.strip()


def _sync_project(target, *, source=SOURCE, **kwargs):
    # Isolate module imports so --source selects both implementation and assets.
    # -B prevents Python cache writes during dry-run.
    code = ("import json,sys; sys.path.insert(0, sys.argv[1]); "
            "from work_execution import sync_project; "
            "print(json.dumps(sync_project(sys.argv[2], **json.loads(sys.argv[3]))))")
    result = subprocess.run([sys.executable, '-B', '-c', code, str(Path(source) / 'scripts'),
                             str(target), json.dumps(kwargs)], capture_output=True, text=True)
    if result.returncode:
        raise SyncConflict(result.stderr.strip() or 'Chief schema/migration validation failed')
    return json.loads(result.stdout)


def _managed(path):
    return path in ('AGENTS.md', '.agent-os/manifest.json') or path.startswith('.chief-of-staff/')


def _dirty_paths(target):
    # Preserve porcelain leading spaces and NUL-delimited filenames.
    result = subprocess.run(['git', '-c', 'core.fsmonitor=false', '-C', str(target),
                             'status', '--porcelain=v1', '-z', '--untracked-files=all'],
                            capture_output=True, check=True)
    records = result.stdout.decode('utf-8', errors='surrogateescape').split('\0')
    paths = []
    index = 0
    while index < len(records):
        entry = records[index]
        if entry:
            paths.append(entry[3:])
            if 'R' in entry[:2] or 'C' in entry[:2]:
                index += 1
                paths.append(records[index])
        index += 1
    return paths


def _source_info(source):
    version = json.loads((source / 'chief-version.json').read_text())
    if (not isinstance(version, dict) or version.get('version') not in {'2.0.0', '2.0.1', '2.0.2'}
            or version != {'version': version.get('version'), 'schema_version': 2,
                           'work_execution_version': 'WORK_EXECUTION_V1'}):
        raise SyncConflict('unsupported or invalid chief-version.json')
    commit = _git(source, 'rev-parse', 'HEAD')
    tag = 'v' + version['version']
    if _git(source, 'rev-parse', f'refs/tags/{tag}^{{commit}}') != commit:
        raise SyncConflict(f'source HEAD must be the fixed {tag} release')
    if _dirty_paths(source):
        raise SyncConflict('source checkout must be clean')
    return version['version'], commit


def _changes(plan):
    if not isinstance(plan, dict) or not isinstance(plan.get('changes'), list):
        raise SyncConflict('sync planner returned no verifiable changes list')
    if plan.get('conflicts'):
        raise SyncConflict(str(plan['conflicts']))
    paths = [entry if isinstance(entry, str) else entry['path'] for entry in plan['changes']]
    if any(not isinstance(path, str) or not _managed(path) or '..' in Path(path).parts or Path(path).is_absolute()
           for path in paths):
        raise SyncConflict('sync planner attempted an unmanaged path')
    return paths


def _existing_branch_path(target, branch, version, source_commit, base):
    refs = _git(target, 'for-each-ref', '--format=%(refname)', f'refs/heads/{branch}').splitlines()
    if f'refs/heads/{branch}' not in refs:
        return None
    head = _git(target, 'rev-parse', branch)
    message = _git(target, 'show', '-s', '--format=%B', head)
    expected = (f'Chief-Sync-Version: {version}', f'Chief-Sync-Source: {source_commit}')
    if not all(line in message.splitlines() for line in expected):
        raise SyncConflict('migration branch already exists without matching migration evidence')
    if base != head and f'Chief-Sync-Base: {base}' not in message.splitlines():
        raise SyncConflict('migration branch belongs to a different target base')
    for block in _git(target, 'worktree', 'list', '--porcelain').split('\n\n'):
        lines = block.splitlines()
        if f'branch refs/heads/{branch}' in lines:
            return Path(lines[0].removeprefix('worktree '))
    raise SyncConflict('migration branch exists without an attached checkout; inspect before reuse')


def sync_repository(target, *, source=SOURCE, dry_run=False, decision_ref='explicit-chief-sync'):
    target = Path(target).expanduser().resolve()
    result = {'target': str(target), 'status': 'failed', 'dry_run': dry_run,
              'validation_scope': 'Chief schema and migration checks only; no business build/test'}
    if not target.is_dir():
        return {**result, 'status': 'not_found', 'error': 'target directory not found'}
    try:
        if Path(_git(target, 'rev-parse', '--show-toplevel')).resolve() != target:
            raise SyncConflict('target must be a Git repository root')
        if not (target / '.chief-of-staff').is_dir():
            raise SyncConflict('target has no .chief-of-staff project')
        version, source_commit = _source_info(Path(source).expanduser().resolve())
        result.update(source_version=version, source_commit=source_commit)
        dirty = _dirty_paths(target)
        if any(_managed(path) or path.startswith('.agent-os/') for path in dirty):
            raise SyncConflict('uncommitted Chief-managed changes require conflict review')
        base = _git(target, 'rev-parse', 'HEAD')
        branch = f'chief/adopt-{version}'
        kwargs = dict(source=Path(source).expanduser().resolve(), decision_ref=decision_ref,
                      source_commit=source_commit, source_version=version)
        # Current managed content wins over historical migration branch position.
        # Routine business edits/commits do not invalidate a verified source lock.
        target_paths = _changes(_sync_project(target, apply=False, **kwargs))
        if not target_paths:
            return {**result, 'status': 'up_to_date', 'changes': [], 'branch': branch,
                    'execution_path': str(target), 'commit': base}
        execution = _existing_branch_path(target, branch, version, source_commit, base)
        if execution is not None and _dirty_paths(execution):
            raise SyncConflict('existing migration checkout is dirty')
        planning = execution or target
        plan = _sync_project(planning, apply=False, **kwargs)
        paths = _changes(plan)
        result.update(changes=paths, branch=branch, execution_path=str(planning))
        if not paths:
            return {**result, 'status': 'up_to_date', 'commit': _git(planning, 'rev-parse', 'HEAD')}
        if execution is not None:
            raise SyncConflict('existing migration branch has drift or incomplete migration')
        if dry_run:
            return {**result, 'status': 'success', 'execution_mode': 'worktree' if dirty else 'branch'}
        if dirty:
            suffix = hashlib.sha256(str(target).encode()).hexdigest()[:10]
            execution = target.parent / f'.chief-sync-{target.name}-{version}-{suffix}'
            if execution.exists():
                raise SyncConflict('migration worktree destination already exists')
            _git(target, 'worktree', 'add', '-b', branch, str(execution), base)
        else:
            _git(target, 'switch', '-c', branch)
            execution = target
        result['execution_path'] = str(execution)
        paths = _changes(_sync_project(execution, apply=True, **kwargs))
        changed = _dirty_paths(execution)
        if any(not _managed(path) or path not in paths for path in changed):
            raise SyncConflict('migration changed an undeclared or unmanaged path; retained for review')
        if not changed:
            return {**result, 'status': 'up_to_date', 'commit': _git(execution, 'rev-parse', 'HEAD')}
        _git(execution, 'add', '--', *changed)
        staged = _git(execution, 'diff', '--cached', '--name-only').splitlines()
        if set(staged) != set(changed):
            raise SyncConflict('staged migration paths do not match declared changes')
        message = (f'chore: sync Chief workflow {version}\n\nChief-Sync-Version: {version}\n'
                   f'Chief-Sync-Source: {source_commit}\nChief-Sync-Base: {base}')
        _git(execution, 'commit', '-m', message)
        commit = _git(execution, 'rev-parse', 'HEAD')
        if _git(execution, 'show', '-s', '--format=%an <%ae>|%cn <%ce>', commit) != f'rong2qi <{AUTHOR_EMAIL}>|rong2qi <{AUTHOR_EMAIL}>':
            raise SyncConflict('migration commit identity verification failed')
        return {**result, 'status': 'success', 'commit': commit}
    except SyncConflict as exc:
        return {**result, 'status': 'conflict', 'error': str(exc)}
    except Exception as exc:
        return {**result, 'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}


def fleet_sync(projects, *, source=SOURCE, pinned=False, dry_run=False):
    projects = Path(projects).expanduser().resolve()
    manifest = json.loads(projects.read_text())
    if not isinstance(manifest, dict) or manifest.get('version') != 1 or not isinstance(manifest.get('projects'), list):
        raise ValueError('projects manifest requires version 1 and projects list')
    results = []
    for entry in manifest['projects']:
        if not isinstance(entry, dict) or not isinstance(entry.get('name'), str) or not isinstance(entry.get('path'), str) or not isinstance(entry.get('pinned', False), bool):
            results.append({'status': 'failed', 'error': 'invalid project entry'})
            continue
        if pinned and not entry.get('pinned', False):
            continue
        try:
            path = Path(entry['path']).expanduser()
            if not path.is_absolute():
                path = projects.parent / path
            item = sync_repository(path, source=source, dry_run=dry_run)
        except Exception as exc:
            item = {'target': entry['path'], 'status': 'failed',
                    'error': f'{type(exc).__name__}: {exc}'}
        results.append({**item, 'name': entry['name']})
    return {'results': results, 'dry_run': dry_run}


def rollback(target, commit):
    target = Path(target).expanduser().resolve()
    result = {'target': str(target), 'status': 'conflict'}
    try:
        if _dirty_paths(target):
            raise SyncConflict('rollback requires a clean checkout')
        exact = _git(target, 'rev-parse', '--verify', f'{commit}^{{commit}}')
        if exact != commit:
            raise SyncConflict('rollback requires the full exact migration commit SHA')
        message = _git(target, 'show', '-s', '--format=%B', exact)
        if not any(line.startswith('Chief-Sync-Version: ') for line in message.splitlines()):
            raise SyncConflict('commit is not a Chief migration')
        parents = _git(target, 'show', '-s', '--format=%P', exact).split()
        paths = _git(target, 'diff-tree', '--no-commit-id', '--name-only', '-r', exact).splitlines()
        if len(parents) != 1 or not paths or not all(_managed(path) for path in paths):
            raise SyncConflict('migration commit contains unowned changes or invalid parents')
        _git(target, 'merge-base', '--is-ancestor', exact, 'HEAD')
        if _git(target, 'diff', exact, 'HEAD', '--', *paths):
            raise SyncConflict('managed files changed after migration; manual conflict review required')
        _git(target, 'revert', '--no-edit', exact)
        return {**result, 'status': 'success', 'commit': _git(target, 'rev-parse', 'HEAD'), 'reverted_commit': exact}
    except Exception as exc:
        return {**result, 'error': f'{type(exc).__name__}: {exc}'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('sync', 'fleet-sync'):
        command = sub.add_parser(name)
        command.add_argument('--target' if name == 'sync' else '--projects', required=True)
        command.add_argument('--dry-run', action='store_true')
        command.add_argument('--source', type=Path, default=SOURCE)
        command.add_argument('--report', type=Path)
        if name == 'fleet-sync':
            command.add_argument('--pinned', action='store_true')
    command = sub.add_parser('rollback')
    command.add_argument('--target', required=True)
    command.add_argument('--commit', required=True)
    command.add_argument('--report', type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == 'sync':
            result = sync_repository(args.target, source=args.source, dry_run=args.dry_run)
        elif args.command == 'fleet-sync':
            result = fleet_sync(args.projects, source=args.source, pinned=args.pinned, dry_run=args.dry_run)
        else:
            result = rollback(args.target, args.commit)
    except Exception as exc:
        result = {'status': 'failed', 'error': f'{type(exc).__name__}: {exc}'}
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    if args.report:
        try:
            args.report.write_text(rendered, encoding='utf-8')
        except OSError as exc:
            result['report_error'] = f'{type(exc).__name__}: {exc}'
            rendered = json.dumps(result, indent=2, ensure_ascii=False) + '\n'
    print(rendered, end='')
    return int('report_error' in result or any(item.get('status') not in ('success', 'up_to_date')
                                              for item in result.get('results', [result])))


if __name__ == '__main__':
    sys.exit(main())
