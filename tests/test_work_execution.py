"""Real project validation, admission and opt-in migration regressions."""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import init_project
import work_execution as we


def save(root, name, value):
    (root / '.chief-of-staff' / name).write_text(json.dumps(value))


def read(root, name):
    return json.loads((root / '.chief-of-staff' / name).read_text())


def proof(root, name='evidence.txt', text='approved existing behavior and verified result'):
    (root / name).write_text(text)
    return {'ref': 'repo://' + name, 'sha256': hashlib.sha256(text.encode()).hexdigest()}


class WorkExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve() / 'project'
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(init_project.initialize(self.root, 'Example'), 0)
        self.evidence = proof(self.root)
        self.inputs = [proof(self.root, 'source.txt', 'existing app source')]
        self.input_hash = hashlib.sha256(json.dumps(self.inputs, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        plan = read(self.root, 'project-plan.json')
        plan.update(goal_status='confirmed', project_status='active', final_goal='Existing app package',
                    confirmed_at='2026-09-09T00:00:00Z', current_phase_id='p1', deliverables=['APK'],
                    acceptance_criteria=[{'criterion_id': 'apk', 'description': 'Valid package',
                                          'status': 'pending', 'evidence': []}],
                    phases=[{'phase_id': 'p1', 'title': 'Package', 'objective': 'Package existing source',
                             'status': 'active', 'phase_class': 'production', 'acceptance_criteria': ['apk'],
                             'task_ids': [], 'result_summary': None}], work_items=[self.work()], work_history=[])
        save(self.root, 'project-plan.json', plan)

    def work(self):
        return {'work_id': 'w1', 'lineage_id': 'package-lineage', 'phase_id': 'p1', 'goal': 'Package existing source',
                'acceptance_ids': ['apk'], 'kind': 'operation', 'status': 'queued',
                'source': {'repository': 'https://example.test/actual.git', 'revision': 'abc',
                           'evidence': self.evidence}, 'executor': {'kind': 'chief', 'id': 'Chief of Example'},
                'write_surface': ['artifacts'], 'inputs': self.inputs, 'input_sha256': self.input_hash,
                'risk': {'level': 'low', 'domains': []},
                'discovery': {'basis': 'existing', 'existing_behavior_confirmed': True, 'evidence': [self.evidence],
                              'unresolved_product_decisions': [], 'affected_areas': []},
                'prechecks': [{'name': 'static', 'status': 'passed', 'input_sha256': self.input_hash,
                               'evidence': self.evidence}],
                'acceptance_checks': [{'name': 'package', 'status': 'pending', 'input_sha256': self.input_hash,
                                      'evidence': None}],
                'review': {'mode': 'self', 'reviewer': 'Chief of Example', 'evidence': [], 'input_sha256': self.input_hash},
                'budget': {'limit': 3, 'reason': 'Historical package checks finish within three attempts'},
                'resources': {'weight': 'heavy', 'memory_mb': None}}

    def edit(self, change):
        plan = read(self.root, 'project-plan.json')
        change(plan)
        save(self.root, 'project-plan.json', plan)

    def test_chief_direct_operation_passes_without_child_or_full_discovery(self):
        self.assertEqual(init_project.validate(self.root), [])
        we.check_work(self.root, 'w1')

    def test_new_product_and_unresolved_decisions_cannot_claim_operation_exemption(self):
        self.edit(lambda p: p['work_items'][0].update(kind='new_product'))
        self.assertTrue(init_project.validate(self.root))
        self.edit(lambda p: p['work_items'][0].update(kind='operation'))
        self.edit(lambda p: p['work_items'][0]['discovery'].update(unresolved_product_decisions=['New pricing']))
        with self.assertRaises(we.WorkExecutionError):
            we.check_work(self.root, 'w1')

    def test_failed_or_stale_precheck_never_invokes_action(self):
        for changes in ({'status': 'failed'}, {'input_sha256': 'b' * 64}):
            with self.subTest(changes=changes):
                self.edit(lambda p: p['work_items'][0]['prechecks'][0].update(changes))
                called = []
                with self.assertRaises(we.WorkExecutionError):
                    we.run_work(self.root, 'w1', lambda: called.append(True))
                self.assertEqual(called, [])

    def test_high_risk_cannot_self_review_or_impersonate_independent_reviewer(self):
        self.edit(lambda p: p['work_items'][0]['risk'].update(domains=['authentication']))
        self.assertTrue(init_project.validate(self.root))
        self.edit(lambda p: p['work_items'][0]['review'].update(mode='independent'))
        self.assertTrue(init_project.validate(self.root))

    def test_overlapping_surface_blocked_and_light_nonconflicting_work_allowed(self):
        other = self.work()
        other.update(work_id='w2', status='running')
        other['executor'] = {'kind': 'chief', 'id': 'Chief of Example'}
        self.edit(lambda p: p['work_items'].append(other))
        with self.assertRaises(we.WorkExecutionError):
            we.check_work(self.root, 'w1')
        other['write_surface'] = ['notes']
        other['resources'] = {'weight': 'light', 'memory_mb': None}
        self.edit(lambda p: p['work_items'].__setitem__(1, other))
        # One chief cannot be two simultaneous writers, even with disjoint paths.
        with self.assertRaises(we.WorkExecutionError):
            we.check_work(self.root, 'w1')

    def test_admission_records_spend_before_action_and_renaming_does_not_reset(self):
        self.edit(lambda p: p['work_items'][0]['budget'].update(limit=1))
        we.run_work(self.root, 'w1', lambda: None)
        self.edit(lambda p: p['work_items'][0].update(work_id='renamed'))
        with self.assertRaises(we.WorkExecutionError):
            we.check_work(self.root, 'renamed')
        self.assertEqual(len(read(self.root, 'project-plan.json')['work_history']), 1)

    def test_adoption_preview_idempotence_and_rollback_preserve_old_state(self):
        # Valid legacy project has no active production while discovery is pending.
        self.edit(lambda p: p.update(goal_status='unconfirmed', project_status='awaiting_goal',
                                    current_phase_id=None, confirmed_at=None, phases=[], work_items=[]))
        project = read(self.root, 'project.json')
        project.pop('work_execution_version')
        save(self.root, 'project.json', project)
        before = {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
        preview = we.adopt(self.root, decision_ref='user:adopt-v1', apply=False)
        self.assertTrue(preview['changes'])
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        with self.assertRaises(init_project.WriteTransactionError):
            we.adopt(self.root, decision_ref='user:adopt-v1', apply=True, fail_after_writes=1)
        self.assertEqual(before, {p.relative_to(self.root): p.read_bytes() for p in self.root.rglob('*') if p.is_file()})
        we.adopt(self.root, decision_ref='user:adopt-v1', apply=True)
        self.assertEqual(we.adopt(self.root, decision_ref='user:adopt-v1', apply=True)['changes'], [])

    def test_explicit_v3_sync_preserves_v2_unknown_history_approvals_and_failures(self):
        project = read(self.root, 'project.json')
        project.pop('goal_loop_version', None)
        project['chief_version'] = '2.0.2'
        project['unknown_extension'] = {'preserve': True}
        project['retained_approvals'] = ['approval-v2']
        project['retained_failures'] = [{'id': 'failure-v2', 'status': 'open'}]
        save(self.root, 'project.json', project)
        plan = read(self.root, 'project-plan.json')
        plan['unknown_history_extension'] = {'event_ids': ['event-v2']}
        save(self.root, 'project-plan.json', plan)
        lock = read(self.root, 'chief-lock.json')
        lock['version'] = '2.0.2'
        save(self.root, 'chief-lock.json', lock)
        approvals_before = (self.root / '.chief-of-staff/approval-queue.json').read_bytes()
        before = {
            path.relative_to(self.root): path.read_bytes()
            for path in self.root.rglob('*') if path.is_file()
        }

        preview = we.sync_project(
            self.root, decision_ref='user:chief-v3-approved', apply=False)
        self.assertIn('.chief-of-staff/project.json', preview['changes'])
        self.assertEqual(
            before,
            {path.relative_to(self.root): path.read_bytes()
             for path in self.root.rglob('*') if path.is_file()},
        )

        applied = we.sync_project(
            self.root, decision_ref='user:chief-v3-approved', apply=True)
        self.assertTrue(applied['applied'])
        migrated = read(self.root, 'project.json')
        self.assertEqual(migrated['goal_loop_version'], 'GOAL_LOOP_V1')
        self.assertEqual(migrated['unknown_extension'], {'preserve': True})
        self.assertEqual(migrated['retained_approvals'], ['approval-v2'])
        self.assertEqual(
            migrated['retained_failures'], [{'id': 'failure-v2', 'status': 'open'}])
        self.assertEqual(
            read(self.root, 'project-plan.json')['unknown_history_extension'],
            {'event_ids': ['event-v2']},
        )
        self.assertEqual(
            (self.root / '.chief-of-staff/approval-queue.json').read_bytes(),
            approvals_before,
        )

    def test_current_source_bytes_are_verified_before_action(self):
        (self.root / 'source.txt').write_text('changed source after static pass')
        with self.assertRaisesRegex(we.WorkExecutionError, 'evidence bytes changed'):
            we.check_work(self.root, 'w1')

    def test_public_retained_proof_validator_rejects_changed_bytes(self):
        retained = proof(self.root, 'claim.txt', 'observed user path passed')
        we.validate_retained_proof(self.root, retained)
        (self.root / 'claim.txt').write_text('changed')
        with self.assertRaisesRegex(we.WorkExecutionError, 'evidence bytes changed'):
            we.validate_retained_proof(self.root, retained)

    def test_cancelled_record_does_not_exempt_uncovered_production(self):
        self.edit(lambda p: p['work_items'][0].update(status='cancelled'))
        self.assertTrue(init_project.validate(self.root))

    def test_retained_product_conflict_cannot_be_relabelled_operation(self):
        d = read(self.root, 'product-discovery.json')
        d['gate_decision']['conditions'] = ['unresolved new payment product decision']
        save(self.root, 'product-discovery.json', d)
        with self.assertRaises(we.WorkExecutionError):
            we.check_work(self.root, 'w1')

    def test_current_product_conflict_preserves_completed_work_and_allows_investigation(self):
        def arrange(p):
            historical = p['work_items'][0]
            historical['status'] = 'completed'
            historical['acceptance_checks'][0].update(status='passed', evidence=self.evidence)
            historical['review']['evidence'] = [self.evidence]
            pending = self.work()
            pending.update(work_id='dependent', lineage_id='dependent-lineage')
            investigation = self.work()
            investigation.update(work_id='investigate', lineage_id='investigate-lineage',
                                 kind='investigation', write_surface=[])
            investigation['discovery']['basis'] = 'targeted'
            investigation['resources']['weight'] = 'light'
            p['work_items'].extend([pending, investigation])
        self.edit(arrange)
        d = read(self.root, 'product-discovery.json')
        d['gate_decision']['conditions'] = ['Unresolved payment requirement']
        save(self.root, 'product-discovery.json', d)
        self.assertEqual(init_project.validate(self.root), [])
        self.assertTrue(we.check_work(self.root, 'investigate'))
        with self.assertRaisesRegex(we.WorkExecutionError, 'unresolved product'):
            we.check_work(self.root, 'dependent')

    def test_unaffected_work_requires_current_gate_and_exact_surface_evidence(self):
        d = read(self.root, 'product-discovery.json')
        d['gate_decision']['conditions'] = ['Unresolved payment requirement']
        save(self.root, 'product-discovery.json', d)
        mapping = {'gate_sha256': hashlib.sha256(json.dumps(d, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                   'acceptance_ids': ['apk'], 'write_surface': ['artifacts'],
                   'reason': 'Existing offline artifact verification does not change payment behavior',
                   'evidence': proof(self.root, 'unaffected.txt', 'Reviewed exact offline inputs and output-only scope')}
        self.edit(lambda p: p['work_items'][0]['discovery'].update(unaffected_by_current_gate=mapping))
        self.assertTrue(we.check_work(self.root, 'w1'))
        self.edit(lambda p: p['work_items'][0].update(write_surface=['payments']))
        with self.assertRaisesRegex(we.WorkExecutionError, 'unresolved product'):
            we.check_work(self.root, 'w1')
        self.edit(lambda p: p['work_items'][0].update(write_surface=['artifacts']))
        d['gate_decision']['conditions'].append('New condition')
        save(self.root, 'product-discovery.json', d)
        with self.assertRaisesRegex(we.WorkExecutionError, 'unresolved product'):
            we.check_work(self.root, 'w1')

    def test_new_product_with_full_basis_still_requires_passed_current_gate(self):
        self.edit(lambda p: p['work_items'][0].update(kind='new_product'))
        self.edit(lambda p: p['work_items'][0]['discovery'].update(basis='full'))
        with self.assertRaisesRegex(we.WorkExecutionError, 'full product discovery'):
            we.check_work(self.root, 'w1')

    def test_two_stagnant_attempts_need_independent_bound_diagnosis(self):
        we.run_work(self.root, 'w1', lambda: None)
        cause = proof(self.root, 'cause1.txt', 'reproduction identifies cache fault')
        self.edit(lambda p: p['work_items'][0].update(retry={'correction': 'repair cache input', 'cause': cause}))
        we.run_work(self.root, 'w1', lambda: None)
        second = proof(self.root, 'cause2.txt', 'new trace identifies environment cause')
        self.edit(lambda p: p['work_items'][0].update(retry={'correction': 'fix env', 'cause': second}))
        with self.assertRaisesRegex(we.WorkExecutionError, 'independent diagnosis'):
            we.check_work(self.root, 'w1')
        ids = [e['event_id'] for e in read(self.root, 'project-plan.json')['work_history']]
        evidence = proof(self.root, 'diagnosis.txt', 'Independent reproduction and bounded corrective path')
        self.edit(lambda p: p['work_items'][0]['retry'].update(diagnosis={
            'reviewer': 'reviewer-independent', 'event_ids': ids, 'new_path': 'reproduce with corrected environment', 'evidence': evidence}))
        with self.assertRaisesRegex(we.WorkExecutionError, 'registered read-only'):
            we.check_work(self.root, 'w1')
        from test_init_project import task, classify_coordination
        classify_coordination(self.root)
        reviewer = task('reviewer-independent', 'coordination_only', 'p1', status='queued')
        reviewer['write_surface'] = []
        registry = read(self.root, 'task-registry.json')
        registry['tasks'] = [reviewer]
        save(self.root, 'task-registry.json', registry)
        self.edit(lambda p: p['phases'][0].update(phase_class='coordination', task_ids=['reviewer-independent']))
        self.assertTrue(we.check_work(self.root, 'w1'))
        reviewer['write_surface'] = ['other-source']
        save(self.root, 'task-registry.json', registry)
        with self.assertRaisesRegex(we.WorkExecutionError, 'registered read-only'):
            we.check_work(self.root, 'w1')

    def test_novel_log_bytes_do_not_count_as_progress(self):
        log = proof(self.root, 'new-log.txt', 'Trying again; no outcome changed')
        we.run_work(self.root, 'w1', lambda: {'progress': log})
        history = read(self.root, 'project-plan.json')['work_history']
        self.assertIsNone(history[0]['progress'])
        self.assertEqual(history[0]['status'], 'failed')

    def test_renamed_criteria_keep_lineage_budget(self):
        self.edit(lambda p: p['work_items'][0]['budget'].update(limit=1))
        we.run_work(self.root, 'w1', lambda: None)
        def rename(p):
            p['acceptance_criteria'][0]['criterion_id'] = 'apk-new-label'
            p['work_items'][0].update(work_id='new-id', goal='reworded objective', acceptance_ids=['apk-new-label'])
        self.edit(rename)
        with self.assertRaisesRegex(we.WorkExecutionError, 'budget exhausted'):
            we.check_work(self.root, 'new-id')

    def test_completed_self_work_closes_without_child(self):
        def complete(p):
            w = p['work_items'][0]
            w['status'] = 'completed'
            w['acceptance_checks'][0].update(status='passed', evidence=self.evidence)
            w['review']['evidence'] = [self.evidence]
            p['phases'][0]['status'] = 'completed'
            p['project_status'] = 'completed'
            p['acceptance_criteria'][0].update(status='verified', evidence=['repo://evidence.txt'])
        self.edit(complete)
        self.assertEqual(init_project.validate(self.root), [])

    def test_project_change_requires_affected_discovery(self):
        self.edit(lambda p: p['work_items'][0].update(kind='product_change'))
        with self.assertRaises(we.WorkExecutionError):
            we.check_work(self.root, 'w1')
        self.edit(lambda p: p['work_items'][0]['discovery'].update(basis='affected', affected_areas=['reservation labels']))
        self.assertTrue(we.check_work(self.root, 'w1'))

    def test_unknown_registry_workload_blocks_heavy_but_allows_disjoint_light(self):
        from test_init_project import task
        t = task('old-worker', 'coordination_only', 'p1', status='running')
        t['write_surface'] = ['other-area']
        registry = read(self.root, 'task-registry.json')
        registry['tasks'] = [t]
        save(self.root, 'task-registry.json', registry)
        # Bind the old coordination task to a separate legacy-valid goal-discovery
        # phase would be unnecessary; classify project coordination to retain old gate.
        from test_init_project import classify_coordination
        classify_coordination(self.root)
        self.edit(lambda p: p['phases'][0].update(phase_class='coordination', task_ids=['old-worker']))
        with self.assertRaisesRegex(we.WorkExecutionError, 'unmanaged running task'):
            we.check_work(self.root, 'w1')
        self.edit(lambda p: p['work_items'][0]['resources'].update(weight='light'))
        self.assertTrue(we.check_work(self.root, 'w1'))

    def test_resource_headroom_and_freshness(self):
        from datetime import datetime, timezone, timedelta
        t = read(self.root, 'throughput.json')
        t['resource_observation'] = {'heavy_limit': 2, 'available_memory_mb': 512,
                                    'observed_at': datetime.now(timezone.utc).isoformat(), 'evidence': self.evidence}
        save(self.root, 'throughput.json', t)
        self.edit(lambda p: p['work_items'][0]['resources'].update(memory_mb=1024))
        with self.assertRaisesRegex(we.WorkExecutionError, 'headroom'):
            we.check_work(self.root, 'w1')
        self.edit(lambda p: p['work_items'][0]['resources'].update(memory_mb=256))
        self.assertTrue(we.check_work(self.root, 'w1'))
        t['resource_observation']['observed_at'] = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
        save(self.root, 'throughput.json', t)
        with self.assertRaisesRegex(we.WorkExecutionError, 'stale'):
            we.check_work(self.root, 'w1')

    def test_legacy_without_adoption_does_not_get_exemption(self):
        project = read(self.root, 'project.json')
        project.pop('work_execution_version')
        save(self.root, 'project.json', project)
        self.assertTrue(init_project.validate(self.root))

    def test_real_build_adapter_does_not_spend_on_failed_static(self):
        from build_execution import execute_work_build
        report = execute_work_build(self.root, 'w1', repository=self.root, source_revision='abc', mode='apk-only',
            prechecks={'static': lambda: False}, build=lambda outputs: True,
            validators={'apk': {k: lambda path: True for k in ('parse', 'package', 'version', 'certificate')}})
        self.assertEqual(report['build_status'], 'NOT_RUN')
        self.assertEqual(read(self.root, 'project-plan.json')['work_history'], [])

    def test_sync_conflict_and_single_source_entry(self):
        # Fresh project already uses a thin source entry instead of a copied policy.
        agents = (self.root / 'AGENTS.md').read_text()
        self.assertIn('single source', agents)
        self.assertNotIn('## Lifecycle capability discovery', agents)
        original = (self.root / 'AGENTS.md').read_bytes()
        (self.root / 'AGENTS.md').write_bytes(original + b'\nManual managed edit\n')
        result = we.sync_project(self.root, decision_ref='user:sync', apply=False)
        self.assertTrue(result['conflicts'])
        self.assertEqual((self.root / 'AGENTS.md').read_bytes(), original + b'\nManual managed edit\n')


if __name__ == '__main__':
    unittest.main()
