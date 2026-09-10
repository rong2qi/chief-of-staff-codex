"""Goal Record, one-step action, proof, and real-path replay tests."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import goal_loop
import work_execution


def run(command, cwd):
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=True)


def git(cwd, *arguments):
    return run(['git', *arguments], cwd).stdout.strip()


def write(path, value, *, binary=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    if binary:
        path.write_bytes(value)
    else:
        path.write_text(value)


def init_repository(root, files):
    root.mkdir(parents=True)
    git(root, 'init', '-q')
    for name, value in files.items():
        write(root / name, value, binary=isinstance(value, bytes))
    git(root, 'add', '.')
    git(root, '-c', 'user.name=ChiefV3', '-c',
        'user.email=chief-v3@example.invalid', 'commit', '-qm', 'fixture')
    return git(root, 'rev-parse', 'HEAD')


class GoalLoopTests(unittest.TestCase):
    def setUp(self):
        self.project = {'approval_required': ['release', 'external_message']}
        self.plan = {
            'goal_status': 'confirmed',
            'final_goal': 'Refactor local reservation behavior',
            'non_goals': ['visual change', 'remote delivery'],
            'acceptance_criteria': [
                {'criterion_id': 'reservation-path', 'status': 'pending', 'evidence': []},
            ],
            'work_items': [{
                'work_id': 'reservation-v13',
                'status': 'queued',
                'input_sha256': 'a' * 64,
                'write_surface': ['src/reservation.py'],
                'risk': {'level': 'medium', 'domains': []},
                'review': {'mode': 'independent', 'reviewer': 'reviewer-luna'},
                'reference_sources': [{
                    'repository': 'https://github.com/zodorganization/zod-reservation.git',
                    'revision': '8d1f9382033e70a35c9c08514caa298d6948d459',
                    'purpose': 'architecture',
                    'access': 'read_only',
                }],
            }],
        }
        self.host = {
            'root_id': 'project:reservation-v13',
            'path': '/disposable/local/reservation-v13',
            'revision': 'b' * 40,
            'repository': 'local://reservation-v13',
        }
        self.authorizations = [{
            'effect': 'local_modify',
            'surfaces': ['src/reservation.py'],
            'decision_ref': 'user:chief-v3-approved',
        }]

    def record(self):
        return goal_loop.build_goal_record(
            self.project,
            self.plan,
            'reservation-v13',
            self.host,
            self.authorizations,
        )

    def action(self, **changes):
        value = {
            'effect': 'local_modify',
            'surface': 'src/reservation.py',
            'expected_candidate_sha256': 'a' * 64,
            'closes_criterion_id': 'reservation-path',
        }
        value.update(changes)
        return value

    def claim(self, **changes):
        value = {
            'criterion_id': 'reservation-path',
            'host_root_id': 'project:reservation-v13',
            'candidate_sha256': 'a' * 64,
            'effect': 'local_modify',
            'surface': 'src/reservation.py',
            'method': 'user_path',
            'result': 'passed',
            'observer_id': 'host:user-path',
            'proofs': [{
                'ref': 'repo://proof.json',
                'sha256': 'd' * 64,
                'source_role': 'delivery_host',
            }],
            'unresolved_findings': [],
        }
        value.update(changes)
        return value

    def observation(self, **changes):
        value = {
            'host_root_id': 'project:reservation-v13',
            'candidate_sha256': 'a' * 64,
            'effect': 'local_modify',
            'surface': 'src/reservation.py',
            'method': 'user_path',
            'result': 'passed',
            'observer_id': 'host:user-path',
            'observed_effect': True,
            'user_path_available': True,
            'proof_sha256s': ['d' * 64],
        }
        value.update(changes)
        return value

    def test_goal_record_separates_delivery_host_reference_and_permissions(self):
        record = self.record()
        self.assertEqual(record['version'], 'GOAL_LOOP_V1')
        self.assertEqual(record['goal'], 'Refactor local reservation behavior')
        self.assertEqual(record['non_goals'], ['visual change', 'remote delivery'])
        self.assertEqual(record['delivery_host']['root_id'], 'project:reservation-v13')
        self.assertEqual(record['delivery_host']['repository'], 'local://reservation-v13')
        self.assertEqual(record['references'][0]['access'], 'read_only')
        self.assertNotEqual(record['references'][0]['repository'], record['delivery_host']['repository'])
        self.assertEqual(record['permissions']['local_modify']['surfaces'], ['src/reservation.py'])
        self.assertEqual(record['permissions']['push']['status'], 'not_granted')
        self.assertEqual(record['permissions']['release']['status'], 'not_granted')
        self.assertEqual(record['candidate_sha256'], 'a' * 64)
        self.assertEqual(record['criteria'][0]['criterion_id'], 'reservation-path')
        self.assertEqual(record['proof_gaps'], ['reservation-path'])
        self.assertEqual(record['stop_condition'], 'all criteria have current proof')

    def test_goal_record_rejects_unconfirmed_goal(self):
        self.plan['goal_status'] = 'unconfirmed'
        with self.assertRaisesRegex(goal_loop.GoalLoopError, 'confirmed goal'):
            self.record()

    def test_goal_record_rejects_malformed_or_moving_reference(self):
        for revision in ('main', '8d1f938', 'g' * 40, ''):
            with self.subTest(revision=revision):
                self.plan['work_items'][0]['reference_sources'][0]['revision'] = revision
                with self.assertRaisesRegex(goal_loop.GoalLoopError, 'full 40-hex revision'):
                    self.record()

    def test_goal_record_rejects_non_read_only_reference(self):
        self.plan['work_items'][0]['reference_sources'][0]['access'] = 'write'
        with self.assertRaisesRegex(goal_loop.GoalLoopError, 'read_only'):
            self.record()

    def test_goal_record_rejects_host_reference_role_collision(self):
        self.host['repository'] = self.plan['work_items'][0]['reference_sources'][0]['repository']
        with self.assertRaisesRegex(goal_loop.GoalLoopError, 'delivery host and reference'):
            self.record()

    def test_goal_record_rejects_missing_host_identity(self):
        for key in ('root_id', 'path', 'revision', 'repository'):
            with self.subTest(key=key):
                host = dict(self.host)
                host.pop(key)
                with self.assertRaisesRegex(goal_loop.GoalLoopError, 'delivery host identity'):
                    goal_loop.build_goal_record(
                        self.project, self.plan, 'reservation-v13', host, self.authorizations)

    def test_goal_record_rejects_duplicate_work_id(self):
        self.plan['work_items'].append(copy.deepcopy(self.plan['work_items'][0]))
        with self.assertRaisesRegex(goal_loop.GoalLoopError, 'exactly one work item'):
            self.record()

    def test_goal_record_rejects_authorization_outside_write_surface(self):
        self.authorizations[0]['surfaces'] = ['visual/current.png']
        with self.assertRaisesRegex(goal_loop.GoalLoopError, 'outside write_surface'):
            self.record()

    def test_goal_record_scopes_criteria_to_current_work_acceptance_ids(self):
        self.plan['acceptance_criteria'].append({
            'criterion_id': 'unrelated-release',
            'status': 'pending',
            'evidence': [],
        })
        self.plan['work_items'][0]['acceptance_ids'] = ['reservation-path']
        record = self.record()
        self.assertEqual(
            [criterion['criterion_id'] for criterion in record['criteria']],
            ['reservation-path'],
        )

    def test_next_action_returns_exact_terminal_verdicts(self):
        record = self.record()
        self.assertEqual(
            goal_loop.next_action(
                record,
                self.action(),
                {'accepted_claims': [{
                    'status': 'ACCEPTED',
                    'criterion_id': 'reservation-path',
                    'candidate_sha256': 'a' * 64,
                }]},
            ),
            {'verdict': 'STOP_ACCEPTED', 'action': None,
             'reason': 'all criteria have current proof'},
        )

        incomplete = copy.deepcopy(record)
        incomplete['delivery_host']['revision'] = ''
        self.assertEqual(
            goal_loop.next_action(incomplete, self.action(), {'accepted_claims': []})['verdict'],
            'EVIDENCE_REQUIRED',
        )

        denied = self.action(effect='push')
        self.assertEqual(
            goal_loop.next_action(record, denied, {'accepted_claims': []})['verdict'],
            'PERMISSION_REQUIRED',
        )

        self.assertEqual(
            goal_loop.next_action(
                record, self.action(),
                {'accepted_claims': [], 'material_decision': 'Choose changed product behavior'},
            )['verdict'],
            'DECISION_REQUIRED',
        )

        self.assertEqual(
            goal_loop.next_action(record, self.action(), {'accepted_claims': []}),
            {'verdict': 'ACTION_READY', 'action': self.action(),
             'reason': 'one admitted action closes the next proof gap'},
        )

    def test_next_action_rejects_graphs_extra_fields_and_candidate_drift(self):
        record = self.record()
        with self.assertRaisesRegex(goal_loop.GoalLoopError, 'one proposed action'):
            goal_loop.next_action(record, [self.action()], {'accepted_claims': []})
        with self.assertRaisesRegex(goal_loop.GoalLoopError, 'exactly'):
            goal_loop.next_action(
                record, self.action(follow_up_actions=[]), {'accepted_claims': []})
        with self.assertRaisesRegex(goal_loop.GoalLoopError, 'candidate'):
            goal_loop.next_action(
                record,
                self.action(expected_candidate_sha256='c' * 64),
                {'accepted_claims': []},
            )

    def test_next_action_requires_a_known_gap_and_granted_surface(self):
        record = self.record()
        with self.assertRaisesRegex(goal_loop.GoalLoopError, 'criterion'):
            goal_loop.next_action(
                record,
                self.action(closes_criterion_id='unknown'),
                {'accepted_claims': []},
            )
        nested = self.action(surface='src/reservation.py/generated')
        self.assertEqual(
            goal_loop.next_action(record, nested, {'accepted_claims': []})['verdict'],
            'PERMISSION_REQUIRED',
        )

    def test_stop_requires_current_acceptance_receipts_and_complete_identity(self):
        record = self.record()
        with self.assertRaisesRegex(goal_loop.GoalLoopError, 'accepted claim'):
            goal_loop.next_action(
                record,
                self.action(),
                {'accepted_claims': ['reservation-path']},
            )
        stale = {
            'status': 'ACCEPTED',
            'criterion_id': 'reservation-path',
            'candidate_sha256': 'c' * 64,
        }
        self.assertNotEqual(
            goal_loop.next_action(
                record, self.action(), {'accepted_claims': [stale]})['verdict'],
            'STOP_ACCEPTED',
        )
        incomplete = copy.deepcopy(record)
        incomplete['delivery_host']['revision'] = ''
        current = dict(stale, candidate_sha256='a' * 64)
        self.assertEqual(
            goal_loop.next_action(
                incomplete, self.action(), {'accepted_claims': [current]})['verdict'],
            'EVIDENCE_REQUIRED',
        )

    def test_acceptance_requires_exact_observed_user_path_and_retained_proof(self):
        validated = []
        result = goal_loop.validate_acceptance(
            self.record(),
            self.claim(),
            self.observation(),
            validated.append,
        )
        self.assertEqual(
            result,
            {'status': 'ACCEPTED', 'criterion_id': 'reservation-path',
             'candidate_sha256': 'a' * 64},
        )
        self.assertEqual(validated, self.claim()['proofs'])

    def test_acceptance_rejects_identity_result_and_proof_mismatches(self):
        cases = [
            ('proof', self.claim(proofs=[]), self.observation()),
            ('host', self.claim(host_root_id='project:reference'), self.observation()),
            ('candidate', self.claim(candidate_sha256='c' * 64), self.observation()),
            ('criterion', self.claim(criterion_id='unknown'), self.observation()),
            ('candidate', self.claim(), self.observation(candidate_sha256='c' * 64)),
            ('observed host', self.claim(), self.observation(host_root_id='project:other')),
            ('observed effect', self.claim(), self.observation(observed_effect=False)),
            ('result', self.claim(), self.observation(result='failed')),
            ('proof', self.claim(), self.observation(proof_sha256s=['e' * 64])),
            ('source role', self.claim(proofs=[{
                'ref': 'repo://proof.json',
                'sha256': 'd' * 64,
                'source_role': 'architecture_reference',
            }]), self.observation()),
            ('unresolved findings', self.claim(unresolved_findings=['visual drift']), self.observation()),
        ]
        for message, claim, observation in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(goal_loop.GoalLoopError, message):
                    goal_loop.validate_acceptance(
                        self.record(), claim, observation, lambda value: None)

    def test_acceptance_rejects_component_only_or_admission_boolean(self):
        with self.assertRaisesRegex(goal_loop.GoalLoopError, 'user_path'):
            goal_loop.validate_acceptance(
                self.record(),
                self.claim(method='component_test'),
                self.observation(method='component_test'),
                lambda value: None,
            )

    def test_acceptance_rejects_unauthorized_effect_and_build_as_release_proof(self):
        with self.assertRaisesRegex(goal_loop.GoalLoopError, 'authorized'):
            goal_loop.validate_acceptance(
                self.record(),
                self.claim(effect='release'),
                self.observation(effect='release'),
                lambda value: None,
            )
        record = self.record()
        record['permissions']['release'] = {
            'status': 'granted',
            'surfaces': ['src/reservation.py'],
            'decision_ref': 'user:release-test-only',
        }
        with self.assertRaisesRegex(goal_loop.GoalLoopError, 'method'):
            goal_loop.validate_acceptance(
                record,
                self.claim(effect='release', method='artifact_validation'),
                self.observation(
                    effect='release',
                    method='artifact_validation',
                    user_path_available=False,
                ),
                lambda value: None,
            )

    def test_acceptance_rejects_self_authored_independent_review(self):
        record = self.record()
        record['current_work']['executor'] = {'id': 'writer-terra'}
        record['review'] = {
            'mode': 'independent',
            'reviewer': 'reviewer-luna',
        }
        with self.assertRaisesRegex(goal_loop.GoalLoopError, 'independent reviewer'):
            goal_loop.validate_acceptance(
                record,
                self.claim(
                    method='independent_review',
                    observer_id='writer-terra',
                    proofs=[{
                        'ref': 'repo://proof.json',
                        'sha256': 'd' * 64,
                        'source_role': 'independent_reviewer',
                    }],
                ),
                self.observation(
                    method='independent_review',
                    observer_id='writer-terra',
                    user_path_available=False,
                ),
                lambda value: None,
            )

    def test_real_host_reference_confusion_replay_stops_after_observed_path(self):
        fixture = json.loads(
            (ROOT / 'tests/fixtures/host-reference-confusion-v3.json').read_text())
        self.assertEqual(fixture['schema'], 'CHIEF_V3_HOST_REFERENCE_REPLAY_V1')
        self.assertEqual(
            fixture['architecture_reference']['revision'],
            '8d1f9382033e70a35c9c08514caa298d6948d459',
        )

        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary).resolve()
            host = temporary_root / '重构预约v1.3'
            reference = temporary_root / 'architecture-reference'
            proof_root = temporary_root / 'proof'
            proof_root.mkdir()

            user_path = (
                "import subprocess\n"
                "import sys\n"
                "result = subprocess.run([sys.executable, 'src/reservation.py'], "
                "text=True, capture_output=True)\n"
                "if result.returncode or result.stdout.strip() != 'reservation:v1.3':\n"
                "    raise SystemExit(1)\n"
                "print(result.stdout.strip())\n"
            )
            host_head_before = init_repository(host, {
                'src/reservation.py': (
                    "def reservation_version():\n"
                    "    return 'v1.2'\n\n"
                    "if __name__ == '__main__':\n"
                    "    print(f'reservation:{reservation_version()}')\n"
                ),
                'checks/reservation_user_path.py': user_path,
                fixture['protected_visual']: b'current visual bytes remain fixed\n',
            })
            remote = temporary_root / 'delivery-origin.git'
            run(['git', 'clone', '--bare', str(host), str(remote)], temporary_root)
            git(host, 'remote', 'add', 'origin', str(remote))

            reference_head_before = init_repository(reference, {
                'architecture.txt': 'target_version=v1.3\nlayer=reservation-domain\n',
            })
            reference_tree_before = git(
                reference, 'rev-parse', reference_head_before + '^{tree}')
            visual_sha_before = hashlib.sha256(
                (host / fixture['protected_visual']).read_bytes()).hexdigest()
            remote_refs_before = git(remote, 'show-ref')

            effect_audit = []
            architecture = git(
                reference, 'show', reference_head_before + ':architecture.txt')
            effect_audit.append('reference_read')
            self.assertIn('target_version=v1.3', architecture)

            initial_candidate = hashlib.sha256(
                (host / 'src/reservation.py').read_bytes()).hexdigest()
            plan = copy.deepcopy(self.plan)
            plan['acceptance_criteria'][0]['criterion_id'] = fixture['criterion_id']
            work = plan['work_items'][0]
            work['input_sha256'] = initial_candidate
            work['reference_sources'] = [{
                'repository': 'local://architecture-reference',
                'revision': reference_head_before,
                'purpose': fixture['architecture_reference']['purpose'],
                'access': fixture['architecture_reference']['access'],
            }]
            observation = {
                'root_id': 'project:reservation-v13',
                'path': str(host),
                'revision': host_head_before,
                'repository': 'local://reservation-v13',
            }
            authorizations = [{
                'effect': 'local_modify',
                'surfaces': fixture['allowed_effects']['local_modify'],
                'decision_ref': 'user:chief-v3-approved',
            }]
            record = goal_loop.build_goal_record(
                self.project, plan, 'reservation-v13', observation, authorizations)
            proposed = {
                'effect': 'local_modify',
                'surface': 'src/reservation.py',
                'expected_candidate_sha256': initial_candidate,
                'closes_criterion_id': fixture['criterion_id'],
            }
            self.assertEqual(
                goal_loop.next_action(record, proposed, {'accepted_claims': []})['verdict'],
                'ACTION_READY',
            )

            # Revalidate the exact host candidate and effect immediately before writing.
            self.assertEqual(
                hashlib.sha256((host / 'src/reservation.py').read_bytes()).hexdigest(),
                proposed['expected_candidate_sha256'],
            )
            self.assertEqual(
                goal_loop.next_action(record, proposed, {'accepted_claims': []})['verdict'],
                'ACTION_READY',
            )
            source = (host / 'src/reservation.py').read_text()
            (host / 'src/reservation.py').write_text(source.replace("'v1.2'", "'v1.3'"))
            effect_audit.append('local_modify')
            modifying_action_count = 1

            command = [sys.executable, 'checks/reservation_user_path.py']
            accepted_path = run(command, host)
            effect_audit.append('user_path_check')
            proof_bytes = accepted_path.stdout.encode()
            write(proof_root / 'user-path.txt', proof_bytes, binary=True)
            proof_sha = hashlib.sha256(proof_bytes).hexdigest()
            retained = {'ref': 'repo://user-path.txt', 'sha256': proof_sha}
            retained['source_role'] = 'delivery_host'

            resulting_candidate = hashlib.sha256(
                (host / 'src/reservation.py').read_bytes()).hexdigest()
            work['input_sha256'] = resulting_candidate
            observed_record = goal_loop.build_goal_record(
                self.project, plan, 'reservation-v13', observation, authorizations)
            claim = {
                'criterion_id': fixture['criterion_id'],
                'host_root_id': observation['root_id'],
                'candidate_sha256': resulting_candidate,
                'effect': 'local_modify',
                'surface': 'src/reservation.py',
                'method': 'user_path',
                'result': 'passed',
                'observer_id': 'host:user-path',
                'proofs': [retained],
                'unresolved_findings': [],
            }
            post_action = {
                'host_root_id': observation['root_id'],
                'candidate_sha256': resulting_candidate,
                'effect': 'local_modify',
                'surface': 'src/reservation.py',
                'method': 'user_path',
                'result': 'passed',
                'observer_id': 'host:user-path',
                'observed_effect': True,
                'user_path_available': True,
                'proof_sha256s': [proof_sha],
            }
            accepted = goal_loop.validate_acceptance(
                observed_record,
                claim,
                post_action,
                lambda value: work_execution.validate_retained_proof(proof_root, value),
            )
            self.assertEqual(accepted['status'], 'ACCEPTED')
            final_decision = goal_loop.next_action(
                observed_record,
                dict(proposed, expected_candidate_sha256=resulting_candidate),
                {'accepted_claims': [accepted]},
            )

            changed_paths = git(host, 'diff', '--name-only').splitlines()
            reference_head_after = git(reference, 'rev-parse', 'HEAD')
            reference_tree_after = git(
                reference, 'rev-parse', reference_head_before + '^{tree}')
            visual_sha_after = hashlib.sha256(
                (host / fixture['protected_visual']).read_bytes()).hexdigest()
            remote_refs_after = git(remote, 'show-ref')
            host_head_after = git(host, 'rev-parse', 'HEAD')

            self.assertEqual(changed_paths, ['src/reservation.py'])
            self.assertEqual(reference_head_before, reference_head_after)
            self.assertEqual(reference_tree_before, reference_tree_after)
            self.assertEqual(visual_sha_before, visual_sha_after)
            self.assertEqual(remote_refs_before, remote_refs_after)
            self.assertEqual(host_head_before, host_head_after)
            self.assertEqual(
                effect_audit,
                ['reference_read', 'local_modify', 'user_path_check'],
            )
            self.assertEqual(modifying_action_count, 1)
            self.assertEqual(final_decision['verdict'], 'STOP_ACCEPTED')
        with self.assertRaisesRegex(goal_loop.GoalLoopError, 'proof'):
            goal_loop.validate_acceptance(
                self.record(),
                self.claim(proofs=[True]),
                self.observation(),
                lambda value: None,
            )


if __name__ == '__main__':
    unittest.main()
