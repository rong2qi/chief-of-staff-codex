"""Explicit build protocol. Callbacks are trusted adapters, not a shell/scheduler API."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from typing import Callable, Mapping, Sequence

REQUIRED_VALIDATORS = ('parse', 'package', 'version', 'certificate')


def execute_build(*, repository: Path, source_revision: str, mode: str,
                  prechecks: Mapping[str, Callable[[], bool]],
                  admit_work: Callable[[], bool],
                  build: Callable[[Mapping[str, Path]], bool],
                  validators: Mapping[str, Mapping[str, Callable[[Path], bool]]],
                  prior_outputs: Sequence[Path] = (),
                  noncritical_checks: Mapping[str, Callable[[Mapping[str, Path]], bool]] | None = None
                  ) -> dict:
    """Preserve first, validate copies, return and persist separate status evidence.

    Build must write to the supplied fresh paths and return exactly True on success.
    Admission must atomically enforce caller-owned work budgets/resource claims.
    The caller releases claims after this synchronous call, including exceptions.
    Validators check expected package/version/certificate against caller policy.
    Nothing here signs, installs, publishes, schedules or authorizes release.
    """
    repository = Path(repository).resolve(strict=True)
    if not repository.is_dir():
        raise ValueError('repository must be an existing directory')
    quarantine = repository / 'artifacts' / 'quarantine'
    if not quarantine.resolve().is_relative_to(repository):
        raise ValueError('quarantine must remain inside repository')
    quarantine.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix='build-', dir=quarantine))
    (attempt / 'NOT_FOR_PRODUCTION').write_text('Pending validation and separate release approval.\n')
    report = dict(attempt_path=str(attempt), source_revision=source_revision, mode=mode,
                  build_status='NOT_RUN', validation_status='NOT_RUN',
                  release_status='NOT_FOR_PRODUCTION', artifacts={}, prior_artifacts=[], checks={}, errors=[])

    def save():
        temporary = attempt / 'report.tmp'
        temporary.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
        temporary.replace(attempt / 'report.json')

    def check(name, callback, *args):
        try:
            result = callback(*args)
            passed = result is True
            report['checks'][name] = 'PASSED' if passed else 'FAILED_OR_UNKNOWN'
        except Exception as exc:
            passed = False
            report['checks'][name] = 'ERROR'
            report['errors'].append(f'{name}: {type(exc).__name__}: {exc}')
        return passed

    def preserve(source, destination):
        source = Path(source)
        if source.is_symlink() or not source.is_file():
            raise ValueError(f'artifact must be a regular non-symlink file: {source}')
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        return dict(path=str(destination), source_path=str(source), sha256=digest,
                    size=destination.stat().st_size)

    save()
    try:
        # Snapshot every declared prior output before any callback may overwrite it.
        for index, source in enumerate(prior_outputs):
            source = Path(source)
            record = preserve(source, attempt / 'prior' / f'{index}-{source.name}')
            report['prior_artifacts'].append(record)
        save()
        if mode not in ('apk-only', 'apk-and-aab'):
            raise ValueError('mode must be apk-only or apk-and-aab')
        kinds = ('apk',) if mode == 'apk-only' else ('apk', 'aab')
        if not isinstance(source_revision, str) or not source_revision.strip():
            raise ValueError('source revision evidence is required')
        if not prechecks or not all(callable(callback) for callback in prechecks.values()):
            raise ValueError('explicit cheap prechecks are required')
        for kind in kinds:
            if any(not callable(validators.get(kind, {}).get(name)) for name in REQUIRED_VALIDATORS):
                raise ValueError(f'{kind} requires parse, package, version and certificate validators')
        if not all([check(f'precheck:{name}', callback) for name, callback in prechecks.items()]):
            return report
        if not check('work_admission', admit_work):
            return report
        staging = attempt / 'build-output'
        staging.mkdir()
        paths = {kind: staging / f'output.{kind}' for kind in kinds}
        report['build_status'] = 'RUNNING'
        save()
        try:
            report['build_status'] = 'PASSED' if check('build', build, paths) else 'FAILED'
        finally:
            # Also runs on interrupted/failed builds. Never remove raw build outputs.
            if report['build_status'] == 'RUNNING':
                report['build_status'] = 'FAILED'
                report['errors'].append('build interrupted before completion')
            for kind, path in paths.items():
                if path.exists() or path.is_symlink():
                    try:
                        report['artifacts'][kind] = preserve(path, attempt / 'preserved' / path.name)
                    except Exception as exc:
                        report['errors'].append(f'preserve:{kind}: {type(exc).__name__}: {exc}')
            save()
        valid = report['build_status'] == 'PASSED'
        report['validation_status'] = 'FAILED'
        for kind in kinds:
            record = report['artifacts'].get(kind)
            present = record is not None and record['size'] > 0
            report['checks'][f'{kind}:exists_nonempty'] = 'PASSED' if present else 'FAILED'
            valid = valid and present
            if not present:
                continue
            # Each adapter gets its own copy; its cleanup cannot destroy preserved bytes.
            for name in REQUIRED_VALIDATORS:
                copy = attempt / 'validation' / f'{kind}-{name}' / f'output.{kind}'
                copy.parent.mkdir(parents=True)
                shutil.copyfile(record['path'], copy)
                passed = check(f'{kind}:{name}', validators[kind][name], copy)
                valid = valid and passed
        warnings = False
        for name, callback in (noncritical_checks or {}).items():
            copies = {}
            for kind, record in report['artifacts'].items():
                folder = Path(tempfile.mkdtemp(prefix='optional-', dir=attempt))
                copy = folder / f'output.{kind}'
                shutil.copyfile(record['path'], copy)
                copies[kind] = copy
            warnings = not check(f'noncritical:{name}', callback, copies) or warnings
        if valid:
            report['validation_status'] = 'PASSED_WITH_WARNINGS' if warnings else 'PASSED'
            report['release_status'] = 'ELIGIBLE_FOR_REVIEW'
        return report
    except Exception as exc:
        report['errors'].append(f'{type(exc).__name__}: {exc}')
        report['release_status'] = 'NOT_FOR_PRODUCTION'
        return report
    finally:
        save()


def execute_work_build(target: Path, work_id: str, **kwargs) -> dict:
    """Bind one build to atomic work admission after cheap prechecks.

    The work-state adapter owns persistent budgets and resources. Finish errors
    propagate so a caller cannot mistake an unreleased claim for settled work.
    """
    if 'repository' not in kwargs or Path(kwargs['repository']).resolve() != Path(target).resolve():
        raise ValueError('build repository must match the admitted work project')
    if 'admit_work' in kwargs:
        raise ValueError('execute_work_build owns the admission callback')
    try:
        from .work_execution import claim_work, finish_work
    except ImportError:
        from work_execution import claim_work, finish_work

    event_id = None
    claimed = False
    result = None

    def admit():
        nonlocal event_id, claimed
        event_id = claim_work(target, work_id)
        claimed = True
        return True

    try:
        result = execute_build(admit_work=admit, **kwargs)
        return result
    finally:
        if claimed:
            failed = result is None or result.get('release_status') != 'ELIGIBLE_FOR_REVIEW'
            finish_work(target, work_id, event_id, result=result, failed=failed)
