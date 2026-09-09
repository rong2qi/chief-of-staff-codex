"""Protocol tests use byte-writing process doubles, never Android builds."""
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'build_execution.py'


class BuildExecutionTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'build execution protocol is not implemented')
        spec = importlib.util.spec_from_file_location('build_execution', SCRIPT)
        self.api = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.api
        spec.loader.exec_module(self.api)
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.calls = []

    def build(self, paths):
        self.calls.append('build')
        for kind, path in paths.items():
            path.write_bytes(b'generated-' + kind.encode())
        return True

    def run_build(self, **overrides):
        args = dict(repository=self.root, source_revision='abc123', mode='apk-only',
                    prechecks={'static': lambda: True}, admit_work=lambda: True,
                    build=self.build, validators={'apk': {name: lambda path: True for name in
                        ('parse', 'package', 'version', 'certificate')}}, prior_outputs=[])
        args.update(overrides)
        return self.api.execute_build(**args)

    def test_static_failure_never_builds(self):
        result = self.run_build(prechecks={'static': lambda: False})
        self.assertEqual(self.calls, [])
        self.assertEqual(result['build_status'], 'NOT_RUN')
        self.assertEqual(result['release_status'], 'NOT_FOR_PRODUCTION')

    def test_noncritical_failure_preserves_apk(self):
        result = self.run_build(noncritical_checks={'lint': lambda paths: False})
        artifact = result['artifacts']['apk']
        self.assertEqual(Path(artifact['path']).read_bytes(), b'generated-apk')
        self.assertEqual(result['validation_status'], 'PASSED_WITH_WARNINGS')
        self.assertEqual(result['release_status'], 'ELIGIBLE_FOR_REVIEW')
        self.assertTrue(artifact['sha256'])

    def test_apk_only_never_invokes_aab_validator(self):
        def forbidden(path):
            self.fail('AAB action in APK-only build')
        validators = {'apk': {name: lambda p: True for name in ('parse', 'package', 'version', 'certificate')},
                      'aab': {'parse': forbidden}}
        result = self.run_build(validators=validators)
        self.assertEqual(set(result['artifacts']), {'apk'})
        self.assertEqual(result['validation_status'], 'PASSED')

    def test_signature_failure_keeps_bytes_and_blocks_release(self):
        validators = {'apk': {name: lambda p: True for name in ('parse', 'package', 'version')}}
        validators['apk']['certificate'] = lambda p: False
        result = self.run_build(validators=validators)
        self.assertEqual(result['release_status'], 'NOT_FOR_PRODUCTION')
        self.assertEqual(Path(result['artifacts']['apk']['path']).read_bytes(), b'generated-apk')
        self.assertTrue((Path(result['attempt_path']) / 'NOT_FOR_PRODUCTION').exists())

    def test_prior_outputs_preserved_before_build(self):
        prior = self.root / 'old.apk'
        prior.write_bytes(b'old')
        def overwrite(paths):
            prior.write_bytes(b'new')
            return self.build(paths)
        result = self.run_build(build=overwrite, prior_outputs=[prior])
        self.assertEqual(Path(result['prior_artifacts'][0]['path']).read_bytes(), b'old')
        again = self.run_build()
        self.assertNotEqual(result['attempt_path'], again['attempt_path'])

    def test_build_exception_preserves_partial_output(self):
        def broken(paths):
            paths['apk'].write_bytes(b'partial')
            raise RuntimeError('build crashed')
        result = self.run_build(build=broken)
        self.assertEqual(result['build_status'], 'FAILED')
        self.assertEqual(Path(result['artifacts']['apk']['path']).read_bytes(), b'partial')
        self.assertEqual(result['release_status'], 'NOT_FOR_PRODUCTION')

    def test_validator_exception_and_mutation_cannot_destroy_preserved_bytes(self):
        def broken(path):
            path.unlink()
            raise RuntimeError('validator crashed')
        validators = {'apk': {name: lambda p: True for name in ('parse', 'package', 'version')}}
        validators['apk']['certificate'] = broken
        result = self.run_build(validators=validators)
        self.assertEqual(Path(result['artifacts']['apk']['path']).read_bytes(), b'generated-apk')
        self.assertEqual(result['release_status'], 'NOT_FOR_PRODUCTION')

    def test_missing_validator_and_unknown_results_fail_closed(self):
        for override in ({'validators': {}}, {'admit_work': lambda: None},
                         {'prechecks': {'static': lambda: 'yes'}}):
            with self.subTest(override=override):
                self.calls.clear()
                result = self.run_build(**override)
                self.assertEqual(result['release_status'], 'NOT_FOR_PRODUCTION')
                self.assertEqual(self.calls, [])

    def test_admission_exception_blocks_build(self):
        def broken():
            raise RuntimeError('budget unknown')
        result = self.run_build(admit_work=broken)
        self.assertEqual(self.calls, [])
        self.assertEqual(result['build_status'], 'NOT_RUN')

    def test_interruption_preserves_bytes_and_marks_build_failed(self):
        def interrupted(paths):
            paths['apk'].write_bytes(b'interrupted')
            raise KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):
            self.run_build(build=interrupted)
        import json
        report = json.loads(next(self.root.glob('artifacts/quarantine/*/report.json')).read_text())
        self.assertEqual(report['build_status'], 'FAILED')
        self.assertEqual(Path(report['artifacts']['apk']['path']).read_bytes(), b'interrupted')

    def test_aab_mode_requires_and_checks_both_artifacts(self):
        validators = {kind: {name: lambda p: True for name in
                      ('parse', 'package', 'version', 'certificate')} for kind in ('apk', 'aab')}
        result = self.run_build(mode='apk-and-aab', validators=validators)
        self.assertEqual(set(result['artifacts']), {'apk', 'aab'})
        self.assertEqual(result['release_status'], 'ELIGIBLE_FOR_REVIEW')
        self.calls.clear()
        result = self.run_build(mode='apk-and-aab')
        self.assertEqual(self.calls, [])
        self.assertEqual(result['release_status'], 'NOT_FOR_PRODUCTION')

    def test_missing_prior_artifact_blocks_possible_overwrite(self):
        result = self.run_build(prior_outputs=[self.root / 'missing.apk'])
        self.assertEqual(self.calls, [])
        self.assertEqual(result['release_status'], 'NOT_FOR_PRODUCTION')

    def test_work_wrapper_claims_only_after_prechecks_and_finishes_once(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        claim = Mock(return_value='event-1')
        finish = Mock()
        adapter = SimpleNamespace(claim_work=claim, finish_work=finish)
        args = dict(repository=self.root, source_revision='abc', mode='apk-only',
                    prechecks={'static': lambda: False}, build=self.build,
                    validators={'apk': {name: lambda p: True for name in
                        ('parse', 'package', 'version', 'certificate')}})
        with patch.dict(sys.modules, {'work_execution': adapter}):
            self.api.execute_work_build(self.root, 'work-1', **args)
            claim.assert_not_called()
            finish.assert_not_called()
            args['prechecks'] = {'static': lambda: True}
            result = self.api.execute_work_build(self.root, 'work-1', **args)
            claim.assert_called_once_with(self.root, 'work-1')
            finish.assert_called_once_with(self.root, 'work-1', 'event-1', result=result, failed=False)

    def test_work_wrapper_finishes_failure_on_interrupt(self):
        from types import SimpleNamespace
        from unittest.mock import Mock, patch
        def interrupted(paths):
            raise KeyboardInterrupt()
        claim, finish = Mock(return_value='event-2'), Mock()
        with patch.dict(sys.modules, {'work_execution': SimpleNamespace(claim_work=claim, finish_work=finish)}):
            with self.assertRaises(KeyboardInterrupt):
                self.api.execute_work_build(self.root, 'work-1', repository=self.root,
                    source_revision='abc', mode='apk-only', prechecks={'static': lambda: True},
                    build=interrupted, validators={'apk': {name: lambda p: True for name in
                        ('parse', 'package', 'version', 'certificate')}})
        finish.assert_called_once_with(self.root, 'work-1', 'event-2', result=None, failed=True)

    def test_work_wrapper_rejects_cross_project_repository_before_callbacks(self):
        from unittest.mock import Mock
        callback = Mock()
        other = self.root / 'other'
        other.mkdir()
        with self.assertRaises(ValueError):
            self.api.execute_work_build(self.root, 'work-1', repository=other,
                source_revision='abc', mode='apk-only', prechecks={'static': callback},
                build=callback, validators={})
        callback.assert_not_called()
        self.assertFalse((other / 'artifacts').exists())

    def test_empty_and_missing_outputs_fail_closed(self):
        for build in (lambda paths: True, lambda paths: paths['apk'].touch() or True):
            result = self.run_build(build=build)
            self.assertEqual(result['validation_status'], 'FAILED')
            self.assertEqual(result['release_status'], 'NOT_FOR_PRODUCTION')


if __name__ == '__main__':
    unittest.main()
