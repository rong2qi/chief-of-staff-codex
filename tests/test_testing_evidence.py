"""Real commits and retained native receipts exercise reuse rather than caller labels."""
import copy
import hashlib
import importlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import continuous_execution
from tests.private_authority_fixture import TESTING_REVIEWER_ID
from tests.test_continuous_execution import PACKAGE


class TestingEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((Path(__file__).parents[1] / 'scripts/testing_evidence.py').exists(),
                        'Evidence-aware Testing implementation is missing')
        self.api = importlib.import_module('scripts.testing_evidence')
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'repo'
        self.root.mkdir()
        self.native = Path(self.tmp.name) / 'native'
        self.native.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Testing fixture')
        self.git('config', 'user.email', 'fixture@example.test')
        for path in ('m1/code.py', 'm2/code.py', 'shared/api.json', 'requirements.lock'):
            target = self.root / path
            target.parent.mkdir(exist_ok=True)
            target.write_text('initial')
        self.base = self.commit()
        self.specs = [self.spec('m1'), self.spec('m2')]
        self.seq = 0

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], text=True).strip()

    def commit(self, path=None):
        if path:
            (self.root / path).write_text('changed')
        self.git('add', '.')
        self.git('commit', '-qm', 'fixture')
        return self.git('rev-parse', 'HEAD')

    def spec(self, name):
        return {'test_id': name, 'scope': name + ' behavior', 'tested_paths': [name],
                'tested_inputs': [], 'dependency_paths': ['shared', 'requirements.lock'],
                'depends_on': [], 'dependency_closure_complete': True}

    def freeze(self, specs=None, candidate=None, status='TESTING_GATE_PASS', risk='high', dependency_specs=None):
        subject = self.api.prepare(self.root, candidate or self.git('rev-parse', 'HEAD'),
                                   specs or self.specs, dependency_specs=dependency_specs or [])
        package = copy.deepcopy(PACKAGE)
        package['candidate_sha256'] = self.api.digest(subject)
        policy = {'risk': risk, 'scope': 'frozen evidence subject', 'sensitive': False,
                  'production': False, 'global_upgrade': False, 'disputed': False}
        package['testing_policy'] = policy
        self.seq += 1
        receipt = {**{k: package[k] for k in ('work_id', 'package_id', 'candidate_sha256',
                    'project', 'writer_task_id')}, **policy,
            'schema': 'CHIEF_TESTING_GATE_RECEIPT_V1', 'status': status,
            'issuer_task_id': TESTING_REVIEWER_ID, 'source_task_id': TESTING_REVIEWER_ID,
            'unresolved_findings': False, 'authority_kind': 'native_coordinator_observation',
            'native_root_id': package['native_intake']['root_id'],
            'coordinator_task_id': package['native_intake']['coordinator_task_id'],
            'package_digest': continuous_execution.package_digest(package),
            'target_task_id': package['writer_task_id'], 'observation_id': 'o1', 'native_event_id': 'e1'}
        raw = json.dumps(receipt).encode()
        name = f'gate-{self.seq}.json'
        (self.native / name).write_bytes(raw)
        observed = {'native_receipt_ref': 'native://' + name,
                    'native_receipt_sha256': hashlib.sha256(raw).hexdigest()}
        return self.api.freeze(self.root, subject, package, observed, self.native)

    def plan(self, evidence, specs=None, **kwargs):
        return self.api.plan(self.root, self.git('rev-parse', 'HEAD'), specs or self.specs,
                             evidence, self.native, **kwargs)

    def states(self, plan):
        return {row['test_id']: row['classification'] for row in plan['impact_map']}

    def test_unchanged_inherits_all_and_has_no_testing_payload(self):
        result = self.plan([self.freeze()])
        self.assertEqual(self.states(result), {'m1': 'INHERITED_PASS', 'm2': 'INHERITED_PASS'})
        self.assertEqual(result['testing_payload']['tests'], [])
        self.assertEqual(result['impact_map'][0]['source_candidate_sha'], self.base)
        self.assertEqual(result['impact_map'][0]['original_testing_gate']['status'], 'TESTING_GATE_PASS')

    def test_unrelated_file_change_inherits(self):
        evidence = self.freeze()
        self.commit('notes.md')
        result = self.plan([evidence])
        self.assertEqual(set(self.states(result).values()), {'INHERITED_PASS'})
        self.assertEqual(result['impact_map'][0]['changed_paths'], ['notes.md'])

    def test_related_path_change_retests_only_affected_item(self):
        evidence = self.freeze()
        self.commit('m1/code.py')
        result = self.plan([evidence])
        self.assertEqual(self.states(result), {'m1': 'RETEST_REQUIRED', 'm2': 'INHERITED_PASS'})
        self.assertEqual([s['test_id'] for s in result['testing_payload']['tests']], ['m1'])

    def test_dependency_fingerprint_change_retests(self):
        evidence = self.freeze()
        self.commit('requirements.lock')
        self.assertEqual(set(self.states(self.plan([evidence])).values()), {'RETEST_REQUIRED'})

    def test_original_testing_chief_direct_pass_for_low_risk_is_reusable(self):
        self.assertEqual(set(self.states(self.plan([self.freeze(risk='low')])).values()), {'INHERITED_PASS'})

    def test_modes_symlinks_and_missing_inputs_fail_safe(self):
        evidence = self.freeze()
        (self.root / 'm1/code.py').chmod(0o755)
        self.commit()
        self.assertEqual(self.states(self.plan([evidence]))['m1'], 'RETEST_REQUIRED')
        (self.root / 'm2/code.py').unlink()
        (self.root / 'm2/code.py').symlink_to('../m1/code.py')
        self.commit()
        self.assertEqual(self.states(self.plan([evidence]))['m2'], 'RETEST_REQUIRED')
        specs = copy.deepcopy(self.specs)
        specs[0]['tested_inputs'] = ['absent.contract']
        current = self.freeze(specs)
        self.assertEqual(self.states(self.plan([current], specs))['m1'], 'RETEST_REQUIRED')

    def test_scope_change_and_unknown_dependency_fail_safe(self):
        evidence = self.freeze()
        specs = copy.deepcopy(self.specs)
        specs[0]['scope'] = 'expanded acceptance'
        specs[1]['depends_on'] = ['unavailable-module']
        self.assertEqual(set(self.states(self.plan([evidence], specs)).values()), {'RETEST_REQUIRED'})

    def test_native_receipt_mutation_rejected_even_after_bundle_rehash(self):
        evidence = self.freeze()
        path = self.native / 'gate-1.json'
        receipt = json.loads(path.read_text())
        receipt['issuer_task_id'] = 'fake-reviewer'
        path.write_text(json.dumps(receipt))
        observed = copy.deepcopy(evidence['observed'])
        observed['native_receipt_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        with self.assertRaises(ValueError):
            self.api.freeze(self.root, evidence['subject'], evidence['package'], observed, self.native)
        self.assertEqual(set(self.states(self.plan([evidence])).values()), {'RETEST_REQUIRED'})

    def test_native_root_in_repo_and_abbreviated_candidate_rejected(self):
        with self.assertRaises(ValueError):
            self.api.prepare(self.root, self.base[:8], self.specs)
        evidence = self.freeze()
        with self.assertRaises(ValueError):
            self.api.freeze(self.root, evidence['subject'], evidence['package'], evidence['observed'], self.root)

    def test_successful_delta_handoff_contains_only_retested_scope(self):
        evidence = self.freeze()
        self.commit('m1/code.py')
        delta = self.plan([evidence])
        returned = self.freeze(delta['testing_payload']['tests'])
        self.assertEqual(self.api.accept(self.root, delta, [returned], self.native)['status'], 'DELTA_GATE_READY')

    def test_two_frozen_modules_integrate_with_only_smoke(self):
        first = self.freeze([self.specs[0]])
        self.commit('m2/code.py')
        second = self.freeze([self.specs[1]])
        result = self.plan([first, second], integration=True)
        self.assertEqual(self.states(result), {'m1': 'INHERITED_PASS', 'm2': 'INHERITED_PASS',
                                             'integration-smoke': 'INTEGRATION_ONLY'})
        self.assertEqual(len(result['testing_payload']['tests']), 1)

    def test_shared_interface_change_retests_consumers(self):
        evidence = self.freeze()
        self.commit('shared/api.json')
        result = self.plan([evidence], integration=True)
        self.assertEqual(self.states(result)['m1'], 'RETEST_REQUIRED')
        self.assertEqual(self.states(result)['m2'], 'RETEST_REQUIRED')

    def test_missing_evidence_and_unknown_closure_fail_safe(self):
        self.assertEqual(set(self.states(self.plan([])).values()), {'RETEST_REQUIRED'})
        evidence = self.freeze()
        specs = copy.deepcopy(self.specs)
        specs[0]['dependency_closure_complete'] = False
        self.assertEqual(self.states(self.plan([evidence], specs))['m1'], 'RETEST_REQUIRED')
        (self.native / 'gate-1.json').unlink()
        self.assertEqual(set(self.states(self.plan([evidence])).values()), {'RETEST_REQUIRED'})

    def test_fake_pass_rejected_and_tampered_frozen_evidence_not_inherited(self):
        with self.assertRaises(ValueError):
            self.freeze(status='PASS')
        evidence = self.freeze()
        evidence['subject']['tests'][0]['scope'] = 'forged scope'
        evidence['evidence_hash'] = self.api.digest({k: v for k, v in evidence.items() if k != 'evidence_hash'})
        self.assertEqual(set(self.states(self.plan([evidence])).values()), {'RETEST_REQUIRED'})

    def test_transitive_dependency_impact_propagates(self):
        self.specs[1]['depends_on'] = ['m1']
        evidence = self.freeze()
        self.commit('m1/code.py')
        self.assertEqual(set(self.states(self.plan([evidence])).values()), {'RETEST_REQUIRED'})

    def test_fresh_dependency_pass_does_not_refresh_old_consumer_evidence(self):
        self.specs[1]['depends_on'] = ['m1']
        old = self.freeze()
        self.commit('m1/code.py')
        fresh = self.freeze([self.specs[0]])
        result = self.plan([old, fresh])
        self.assertEqual(self.states(result)['m1'], 'INHERITED_PASS')
        self.assertEqual(self.states(result)['m2'], 'RETEST_REQUIRED')

    def test_delta_only_consumer_pass_retains_unexecuted_dependency_context(self):
        self.specs[1]['depends_on'] = ['m1']
        old = self.freeze()
        self.commit('m2/code.py')
        delta = self.plan([old])
        fresh = self.freeze(delta['testing_payload']['tests'], dependency_specs=delta['dependency_specs'])
        self.assertEqual(self.api.accept(self.root, delta, [fresh], self.native)['status'], 'DELTA_GATE_READY')
        again = self.plan([old, fresh])
        self.assertEqual(self.states(again)['m2'], 'INHERITED_PASS')
        # Metadata about m1 is not an executed m1 test and cannot mint its PASS.
        without_original_provider = self.plan([fresh])
        self.assertEqual(self.states(without_original_provider)['m1'], 'RETEST_REQUIRED')

    def test_hidden_index_flags_cannot_hide_changes_from_freeze(self):
        self.git('update-index', '--assume-unchanged', 'm1/code.py')
        (self.root / 'm1/code.py').write_text('hidden change')
        with self.assertRaises(ValueError):
            self.api.prepare(self.root, self.base, self.specs)

    def test_verified_unchanged_integration_smoke_is_also_inherited(self):
        evidence = self.freeze()
        first = self.plan([evidence], integration=True)
        smoke = self.freeze(first['testing_payload']['tests'])
        again = self.plan([evidence, smoke], integration=True)
        self.assertEqual(set(self.states(again).values()), {'INHERITED_PASS'})
        self.assertEqual(again['testing_payload']['tests'], [])

    def test_malformed_nested_evidence_fails_safe_to_retest(self):
        evidence = self.freeze()
        evidence['observed'] = []
        evidence['evidence_hash'] = self.api.digest({k: v for k, v in evidence.items() if k != 'evidence_hash'})
        self.assertEqual(set(self.states(self.plan([evidence])).values()), {'RETEST_REQUIRED'})

    def test_added_file_and_renamed_path_invalidate_directory_scope(self):
        evidence = self.freeze()
        self.commit('m1/new.py')
        self.assertEqual(self.states(self.plan([evidence]))['m1'], 'RETEST_REQUIRED')
        self.git('mv', 'm2/code.py', 'm2/renamed.py')
        self.commit()
        self.assertEqual(self.states(self.plan([evidence]))['m2'], 'RETEST_REQUIRED')

    def test_dirty_tree_does_not_masquerade_as_frozen_candidate(self):
        evidence = self.freeze()
        (self.root / 'm1/code.py').write_text('uncommitted')
        with self.assertRaises(ValueError):
            self.plan([evidence])

    def test_handoff_requires_pending_smoke_and_rechecks_original_evidence(self):
        evidence = self.freeze()
        result = self.plan([evidence], integration=True)
        with self.assertRaises(ValueError):
            self.api.accept(self.root, result, [], self.native)
        smoke = self.freeze(result['testing_payload']['tests'])
        accepted = self.api.accept(self.root, result, [smoke], self.native)
        self.assertEqual(accepted['status'], 'DELTA_GATE_READY')
        (self.native / 'gate-1.json').unlink()
        with self.assertRaises(ValueError):
            self.api.accept(self.root, result, [smoke], self.native)

    def test_handoff_rejects_full_resubmission_and_plan_tampering(self):
        evidence = self.freeze()
        self.commit('m1/code.py')
        result = self.plan([evidence])
        with self.assertRaises(ValueError):
            self.api.accept(self.root, result, [self.freeze()], self.native)
        result['testing_payload']['tests'] = []
        with self.assertRaises(ValueError):
            self.api.accept(self.root, result, [], self.native)

    def test_cli_prepare_freeze_plan_accept_and_nonzero_failure(self):
        def command(name, request):
            path = Path(self.tmp.name) / 'request.json'
            path.write_text(json.dumps(request))
            run = subprocess.run([sys.executable, str(Path(self.api.__file__)), name,
                                  '--repo', str(self.root), '--native-root', str(self.native),
                                  '--request', str(path)], capture_output=True, text=True)
            return run, json.loads(run.stdout)
        prepared, body = command('prepare', {'candidate_sha': self.base, 'tests': self.specs})
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        existing = self.freeze()
        self.assertEqual(body['subject'], existing['subject'])
        frozen, bundle = command('freeze', {k: existing[k] for k in ('subject', 'package', 'observed')})
        self.assertEqual(frozen.returncode, 0, frozen.stderr)
        planned, delta = command('plan', {'candidate_sha': self.base, 'tests': self.specs, 'evidence': [bundle]})
        self.assertEqual(planned.returncode, 0, planned.stderr)
        accepted, result = command('accept', {'delta': delta, 'returns': []})
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        self.assertEqual(result['status'], 'DELTA_GATE_READY')
        rejected, result = command('prepare', {'candidate_sha': 'HEAD', 'tests': self.specs})
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(result['status'], 'EVIDENCE_BLOCKED')


if __name__ == '__main__':
    unittest.main()
