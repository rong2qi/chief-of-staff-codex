#!/usr/bin/env python3
"""Evidence-aware Testing: authenticated freeze, Git delta, narrow handoff.

No tests are executed, messages sent, or Testing PASS receipts issued here.
Native observation storage is a host-controlled trust boundary, as in Ledger.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys

try:
    from . import continuous_execution as ce, retry_policy
except ImportError:
    import continuous_execution as ce
    import retry_policy

SUBJECT = 'CHIEF_TESTING_SUBJECT_V1'
LEGACY_EVIDENCE = 'CHIEF_FROZEN_TESTING_EVIDENCE_V1'
EVIDENCE = 'CHIEF_FROZEN_TESTING_EVIDENCE_V2'
DELTA = 'CHIEF_TESTING_DELTA_V1'
FIELDS = {'test_id', 'scope', 'tested_paths', 'tested_inputs', 'dependency_paths',
          'depends_on', 'dependency_closure_complete'}


class EvidenceError(ValueError):
    pass


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def _git(repo, *args):
    result = subprocess.run(['git', '--no-replace-objects', '-c', 'core.fsmonitor=false',
                             '-C', str(repo), *args], capture_output=True)
    if result.returncode:
        raise EvidenceError('Git observation unavailable: ' + result.stderr.decode(errors='replace').strip())
    return result.stdout


def _candidate(repo, sha, *, current=False):
    if not isinstance(sha, str) or not re.fullmatch(r'[a-f0-9]{40}|[a-f0-9]{64}', sha):
        raise EvidenceError('candidate requires a full commit SHA')
    if _git(repo, 'rev-parse', '--verify', sha + '^{commit}').decode().strip() != sha:
        raise EvidenceError('candidate must identify a commit, not a tag object')
    if current:
        if _git(repo, 'rev-parse', 'HEAD').decode().strip() != sha:
            raise EvidenceError('current candidate must be checked out')
        if _git(repo, 'status', '--porcelain=v1', '-z', '--untracked-files=all'):
            raise EvidenceError('freeze requires a clean current candidate; retain outputs outside checkout')
        flags = _git(repo, 'ls-files', '-v', '-z').split(b'\0')
        if any(record and (record[:1].islower() or record[:1] == b'S') for record in flags):
            raise EvidenceError('assume-unchanged/skip-worktree flags prevent verified candidate freeze')


def _specs(tests):
    if not isinstance(tests, list) or not tests:
        raise EvidenceError('explicit nonempty test scope is required')
    result, ids = [], set()
    for test in tests:
        if not isinstance(test, dict) or set(test) != FIELDS:
            raise EvidenceError('test scope fields are incomplete or unknown')
        for key in ('test_id', 'scope'):
            if not isinstance(test[key], str) or not test[key].strip():
                raise EvidenceError('test identity and scope must be nonempty')
        if test['test_id'] in ids or type(test['dependency_closure_complete']) is not bool:
            raise EvidenceError('duplicate identity or ambiguous dependency closure')
        ids.add(test['test_id'])
        for key in ('tested_paths', 'tested_inputs', 'dependency_paths', 'depends_on'):
            items = test[key]
            if (not isinstance(items, list) or not all(isinstance(p, str) and p for p in items)
                    or len(items) != len(set(items))):
                raise EvidenceError('scope lists must contain unique strings')
            if key != 'depends_on':
                for p in items:
                    path = PurePosixPath(p)
                    if (path.is_absolute() or '..' in path.parts or p != path.as_posix()
                            or p == '.' or '\\' in p or ':' in p or '.git' in path.parts):
                        raise EvidenceError('inputs must be literal relative Git paths or directories')
        if not test['tested_paths'] and not test['tested_inputs']:
            raise EvidenceError('test needs observed inputs')
        result.append(json.loads(json.dumps(test)))
    return sorted(result, key=lambda item: item['test_id'])


def _tree(repo, sha):
    tree = {}
    for record in _git(repo, 'ls-tree', '-rz', '--full-tree', sha).split(b'\0'):
        if record:
            metadata, name = record.split(b'\t', 1)
            tree[name.decode('utf-8', errors='surrogateescape')] = metadata.decode().split()
    return tree


def _matches(path, roots):
    return any(path == root or path.startswith(root + '/') for root in roots)


def _snapshot(tree, paths):
    selected = {p: value for p, value in tree.items() if _matches(p, paths)}
    # Missing roots and unsupported symlink/submodule inputs cannot prove reuse.
    verified = (all(any(_matches(p, [root]) for p in tree) for root in paths)
                and all(value[0] in {'100644', '100755'} and value[1] == 'blob'
                        for value in selected.values()))
    return {'entries': selected, 'verifiable': verified, 'fingerprint': digest(selected)}


def _subject(repo, candidate_sha, tests, dependency_specs=None):
    _candidate(repo, candidate_sha)
    tree = _tree(repo, candidate_sha)
    tests = _specs(tests)
    context = _specs(dependency_specs) if dependency_specs else []
    executed = {t['test_id']: t for t in tests}
    for item in context:
        if item['test_id'] in executed and executed[item['test_id']] != item:
            raise EvidenceError('dependency context conflicts with executed test definition')
    context = [item for item in context if item['test_id'] not in executed]
    observations = {}
    for test in tests + context:
        inputs = _snapshot(tree, test['tested_paths'] + test['tested_inputs'])
        deps = _snapshot(tree, test['dependency_paths'])
        observations[test['test_id']] = {'inputs': inputs, 'dependencies': deps,
            'dependency_fingerprint': deps['fingerprint'], 'definition_hash': digest(test)}
    return {'schema': SUBJECT, 'candidate_sha': candidate_sha, 'tests': tests,
            'dependency_specs': context, 'observations': observations}


def prepare(repo, candidate_sha, tests, *, dependency_specs=None):
    """Create the exact subject whose digest Testing must bind in its package."""
    _candidate(repo, candidate_sha, current=True)
    return _subject(repo, candidate_sha, tests, dependency_specs)


def _native_pass(repo, subject, package, observed, native_root):
    if not isinstance(observed, dict):
        raise EvidenceError('native Testing observation must be an object')
    ce.validate_execution_package(package)
    if package['candidate_sha256'] != digest(subject):
        raise EvidenceError('Testing package does not bind the frozen subject')
    root, project = Path(native_root).resolve(strict=True), Path(repo).resolve(strict=True)
    if root == project or root in project.parents or project in root.parents:
        raise EvidenceError('native observation root and writer repository must be disjoint')
    descriptor = retry_policy._open_project_directory(Path(native_root))
    try:
        def loader(ref, sha, label):
            if not isinstance(ref, str) or not ref.startswith('native://'):
                raise EvidenceError('Testing requires an original native:// receipt')
            return retry_policy._read_retained_json(descriptor, 'repo://' + ref[9:], sha, label)
        receipt = loader(observed.get('native_receipt_ref'), observed.get('native_receipt_sha256'), 'Testing gate')
        # Reusable PASS must originate with the Testing Chief. Delegated local
        # PASS and phase/transport labels cannot mint a reusable gate.
        reviewer = ce._testing_reviewer_task_id(submitting_project=project, native_observation_root=root)
        if (receipt.get('schema') != 'CHIEF_TESTING_GATE_RECEIPT_V1'
                or receipt.get('status') != 'TESTING_GATE_PASS'
                or receipt.get('issuer_task_id') != reviewer):
            raise EvidenceError('original Testing Chief TESTING_GATE_PASS is required')
        ce.validate_native_testing_return(observed, package=package, native_loader=loader,
                                         submitting_project=project, native_observation_root=root)
        return {'ref': observed['native_receipt_ref'], 'sha256': observed['native_receipt_sha256'],
                'status': receipt['status'], 'issuer_task_id': receipt['issuer_task_id']}
    finally:
        os.close(descriptor)


def freeze(repo, subject, package, observed, native_root, *, recorded_at=None):
    """Validate, never issue, a Testing gate and retain its immutable subject."""
    if not isinstance(subject, dict) or subject != _subject(repo, subject['candidate_sha'], subject['tests'], subject.get('dependency_specs')):
        raise EvidenceError('subject no longer matches its exact Git inputs')
    gate = _native_pass(repo, subject, package, observed, native_root)
    timestamp = recorded_at or datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
    if not isinstance(timestamp, str):
        raise EvidenceError('evidence timestamp must be an RFC 3339 string')
    try:
        datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
    except ValueError as exc:
        raise EvidenceError('evidence timestamp must be an RFC 3339 string') from exc
    policy = package.get('testing_policy', {})
    metadata = {
        'evidence_id': observed['native_receipt_sha256'],
        'timestamp': timestamp,
        'result': gate['status'],
        'risk_scope': {'risk': policy.get('risk'), 'scope': policy.get('scope')},
        'tested_paths_assets': sorted({path for test in subject['tests']
                                      for key in ('tested_paths', 'tested_inputs') for path in test[key]}),
    }
    result = {'schema': EVIDENCE, 'subject': subject, 'package': package,
              'observed': observed, 'original_testing_gate': gate,
              'evidence_metadata': metadata, 'conclusion': 'TESTING_GATE_PASS'}
    # Detach mutable caller state so a later edit cannot alter retained evidence.
    result = json.loads(json.dumps(result))
    result['evidence_hash'] = digest(result)
    return result


def _verify(repo, evidence, native_root):
    if not isinstance(evidence, dict) or evidence.get('schema') not in {LEGACY_EVIDENCE, EVIDENCE}:
        raise EvidenceError('frozen evidence missing or unsupported')
    unsigned = {k: v for k, v in evidence.items() if k != 'evidence_hash'}
    if digest(unsigned) != evidence.get('evidence_hash'):
        raise EvidenceError('evidence hash mismatch')
    subject = evidence['subject']
    if subject != _subject(repo, subject['candidate_sha'], subject['tests'], subject.get('dependency_specs')):
        raise EvidenceError('frozen evidence subject no longer matches its exact Git inputs')
    gate = _native_pass(repo, subject, evidence['package'], evidence['observed'], native_root)
    if evidence.get('original_testing_gate') != gate or evidence.get('conclusion') != 'TESTING_GATE_PASS':
        raise EvidenceError('frozen evidence does not match original Testing gate')
    if evidence['schema'] == EVIDENCE:
        metadata = evidence.get('evidence_metadata')
        policy = evidence['package'].get('testing_policy', {})
        expected = {
            'evidence_id': evidence['observed']['native_receipt_sha256'],
            'result': 'TESTING_GATE_PASS',
            'risk_scope': {'risk': policy.get('risk'), 'scope': policy.get('scope')},
            'tested_paths_assets': sorted({path for test in subject['tests']
                                          for key in ('tested_paths', 'tested_inputs') for path in test[key]}),
        }
        if not isinstance(metadata, dict) or any(metadata.get(key) != value for key, value in expected.items()):
            raise EvidenceError('evidence metadata does not match the tested subject and gate')
        timestamp = metadata.get('timestamp')
        if not isinstance(timestamp, str):
            raise EvidenceError('evidence timestamp is missing')
        try:
            datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError as exc:
            raise EvidenceError('evidence timestamp is invalid') from exc
    return json.loads(json.dumps(evidence))


def plan(repo, candidate_sha, tests, evidence, native_root, *, integration=False):
    """Recompute evidence validity per item; unreadable evidence fails to RETEST."""
    current = prepare(repo, candidate_sha, tests)
    if not isinstance(evidence, list) or type(integration) is not bool:
        raise EvidenceError('evidence list and explicit integration flag required')
    valid, rejected = [], []
    for index, item in enumerate(evidence):
        try:
            checked = _verify(repo, item, native_root)
            old = checked['subject']['candidate_sha']
            # --no-renames lists both old and new names. NUL preserves unusual names.
            changed = [p.decode('utf-8', errors='surrogateescape') for p in
                       _git(repo, 'diff', '--no-ext-diff', '--no-renames', '--name-only', '-z', old, candidate_sha, '--').split(b'\0') if p]
            valid.append((checked, changed))
        except (ValueError, KeyError, TypeError, OSError, RuntimeError) as exc:
            rejected.append({'index': index, 'reason': str(exc)})
    sources = {item['subject']['candidate_sha'] for item, _ in valid}
    parents = _git(repo, 'show', '-s', '--format=%P', candidate_sha).split()
    combination = integration or len(sources) > 1 or len(parents) > 1
    original_tests = current['tests']
    if any(t['test_id'] == 'integration-smoke' for t in original_tests):
        raise EvidenceError('integration-smoke is reserved for combination-only checks')
    if combination:
        smoke = {'test_id': 'integration-smoke',
                 'scope': 'Minimal cross-module wiring/shared-state smoke; inventory ' + digest(original_tests),
                 'tested_paths': sorted({p for test in original_tests for p in test['tested_paths']}),
                 'tested_inputs': sorted({p for test in original_tests for p in test['tested_inputs']}),
                 'dependency_paths': sorted({p for test in original_tests for p in test['dependency_paths']}),
                 'depends_on': [], 'dependency_closure_complete': all(t['dependency_closure_complete'] for t in original_tests)}
        current = _subject(repo, candidate_sha, original_tests + [smoke])
    impact = []
    for test in current['tests']:
        tid = test['test_id']
        now = current['observations'][tid]
        row = {'test_id': tid, 'classification': 'RETEST_REQUIRED', 'current_candidate_sha': candidate_sha,
               'source_candidate_sha': None, 'original_testing_gate': None, 'changed_paths': [],
               'reasons': ['missing or unverifiable frozen evidence'], 'attempts': []}
        for item, changed in valid:
            source = item['subject']
            if tid not in {t['test_id'] for t in source['tests']}:
                continue  # Dependency context was observed, never executed.
            old = source['observations'].get(tid)
            if old is None:
                continue
            reasons = []
            if not test['dependency_closure_complete']:
                reasons.append('dependency closure is unproven')
            if old['definition_hash'] != now['definition_hash']:
                reasons.append('test scope, inputs or dependency definition changed')
            if not all(snapshot['verifiable'] for snapshot in
                       (old['inputs'], old['dependencies'], now['inputs'], now['dependencies'])):
                reasons.append('input coverage is missing or unsupported')
            if old['inputs']['fingerprint'] != now['inputs']['fingerprint']:
                reasons.append('tested code/resource/contract/input fingerprint changed')
            if old['dependency_fingerprint'] != now['dependency_fingerprint']:
                reasons.append('dependency fingerprint changed')
            affected = [p for p in changed if _matches(p, test['tested_paths'] + test['tested_inputs'] + test['dependency_paths'])]
            if affected:
                reasons.append('Git diff intersects tested inputs or dependencies')
            # Consumer evidence binds its dependencies at the consumer's source
            # commit. A fresh PASS for a changed provider never refreshes it.
            source_defs = {t['test_id']: t for t in source['tests'] + source['dependency_specs']}
            remaining, seen = list(test['depends_on']), set()
            while remaining:
                dep = remaining.pop()
                if dep in seen:
                    continue
                seen.add(dep)
                before = source['observations'].get(dep)
                after = current['observations'].get(dep)
                if (before is None or after is None or before != after
                        or not source_defs[dep]['dependency_closure_complete']
                        or not all(before[k]['verifiable'] for k in ('inputs', 'dependencies'))):
                    reasons.append('dependency changed or unproven at consumer source: ' + dep)
                else:
                    remaining.extend(source_defs[dep]['depends_on'])
            row.update(source_candidate_sha=source['candidate_sha'], original_testing_gate=item['original_testing_gate'],
                       evidence_hash=item['evidence_hash'], changed_paths=changed,
                       dependency_fingerprint=now['dependency_fingerprint'], reasons=reasons or ['Git diff and all reviewed inputs/dependencies unchanged'])
            row['attempts'].append({'source_candidate_sha': source['candidate_sha'],
                                    'evidence_hash': item['evidence_hash'], 'reasons': row['reasons']})
            if not reasons:
                row['classification'] = 'INHERITED_PASS'
                break
        impact.append(row)
    by_id = {row['test_id']: row for row in impact}
    # Detect cycles/unknown references, then propagate failures to all consumers.
    definitions = {test['test_id']: test for test in current['tests']}
    def unresolved(tid, visiting):
        if tid in visiting or tid not in definitions:
            return True
        return any(unresolved(dep, visiting | {tid}) for dep in definitions[tid]['depends_on'])
    for test in current['tests']:
        if unresolved(test['test_id'], set()):
            row = by_id[test['test_id']]
            row['classification'] = 'RETEST_REQUIRED'
            row['reasons'].append('dependency graph is incomplete or cyclic')
    for _ in current['tests']:
        for test in current['tests']:
            affected = [dep for dep in test['depends_on'] if dep not in by_id or by_id[dep]['classification'] != 'INHERITED_PASS']
            row = by_id[test['test_id']]
            if affected and row['classification'] == 'INHERITED_PASS':
                row['classification'] = 'RETEST_REQUIRED'
                row['reasons'].append('transitive dependency impact: ' + ', '.join(affected))
    if combination and by_id['integration-smoke']['source_candidate_sha'] is None:
        by_id['integration-smoke']['classification'] = 'INTEGRATION_ONLY'
        by_id['integration-smoke']['reasons'].append('combination-only wiring/shared-state risk; minimum smoke, not module retests')
    payload = [test for test in current['tests'] if by_id[test['test_id']]['classification'] != 'INHERITED_PASS']
    result = {'schema': DELTA, 'current_candidate_sha': candidate_sha, 'impact_map': impact,
              'rejected_evidence': rejected, 'testing_payload': {'candidate_sha': candidate_sha, 'tests': payload},
              'dependency_specs': original_tests,
              'request': {'candidate_sha': candidate_sha, 'tests': original_tests, 'evidence': evidence, 'integration': integration}}
    result['delta_hash'] = digest(result)
    return result


def accept(repo, delta, returns, native_root):
    """Revalidate source inheritance and exact delta returns at handoff/acceptance."""
    request = delta['request']
    fresh = plan(repo, request['candidate_sha'], request['tests'], request['evidence'], native_root,
                 integration=request['integration'])
    if fresh != delta:
        raise EvidenceError('delta changed or evidence expired; regenerate impact map before acceptance')
    pending = {test['test_id']: test for test in fresh['testing_payload']['tests']}
    covered = set()
    for item in returns:
        checked = _verify(repo, item, native_root)
        if checked['subject']['candidate_sha'] != fresh['current_candidate_sha']:
            raise EvidenceError('Testing return belongs to a different current candidate')
        for test in checked['subject']['tests']:
            tid = test['test_id']
            if tid in covered or pending.get(tid) != test:
                raise EvidenceError('Testing return includes duplicate, inherited or unrequested scope')
            covered.add(tid)
    if covered != set(pending):
        raise EvidenceError('delta Testing returns are incomplete')
    return {'status': 'DELTA_GATE_READY', 'candidate_sha': fresh['current_candidate_sha'],
            'delta_hash': fresh['delta_hash'], 'impact_map': fresh['impact_map'],
            'return_evidence_hashes': [item['evidence_hash'] for item in returns],
            'note': 'Evidence complete for handoff; not a newly issued TESTING_GATE_PASS or release permission'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'freeze', 'plan', 'accept'))
    parser.add_argument('--repo', type=Path, required=True)
    parser.add_argument('--request', type=Path, required=True)
    parser.add_argument('--native-root', type=Path)
    args = parser.parse_args(argv)
    try:
        request = json.loads(args.request.read_text())
        if args.command == 'prepare':
            result = prepare(args.repo, request['candidate_sha'], request['tests'],
                             dependency_specs=request.get('dependency_specs'))
            result = {'subject': result, 'candidate_sha256': digest(result)}
        else:
            if args.native_root is None:
                raise EvidenceError('host-provided --native-root is required')
            if args.command == 'freeze':
                result = freeze(args.repo, request['subject'], request['package'], request['observed'], args.native_root,
                                recorded_at=request.get('recorded_at'))
            elif args.command == 'plan':
                result = plan(args.repo, request['candidate_sha'], request['tests'], request['evidence'],
                              args.native_root, integration=request.get('integration', False))
            else:
                result = accept(args.repo, request['delta'], request['returns'], args.native_root)
        print(json.dumps(result, indent=2, ensure_ascii=True))
        return 0
    except (ValueError, KeyError, TypeError, OSError, RuntimeError) as exc:
        print(json.dumps({'status': 'EVIDENCE_BLOCKED', 'error': str(exc)}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
