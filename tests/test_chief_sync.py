import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/chief_sync.py'


def git(root, *args):
    return subprocess.check_output(['git', '-C', str(root), *args], text=True).strip()


class ChiefSyncTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.exists(), 'sync orchestration is missing')
        spec = importlib.util.spec_from_file_location('chief_sync', SCRIPT)
        self.api = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.api
        spec.loader.exec_module(self.api)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.repo('source')
        (self.source / 'chief-version.json').write_text(json.dumps(dict(version='2.0.0', schema_version=2,
                                                            work_execution_version='WORK_EXECUTION_V1')))
        git(self.source, 'add', '.')
        git(self.source, 'commit', '-qm', 'release')
        git(self.source, 'tag', 'v2.0.0')
        self.target = self.repo('target')
        self.addCleanup(patch.stopall)
        self.sync_patch = patch.object(self.api, '_sync_project', side_effect=self.project_sync)
        self.sync_patch.start()

    def repo(self, name):
        root = self.base / name
        root.mkdir()
        git(root, 'init', '-q')
        git(root, 'config', 'user.name', 'rong2qi')
        git(root, 'config', 'user.email', '249084307+rong2qi@users.noreply.github.com')
        (root / '.chief-of-staff').mkdir()
        (root / '.chief-of-staff' / 'project-plan.json').write_text('{}')
        (root / 'AGENTS.md').write_text('old chief')
        (root / 'business.txt').write_text('business')
        git(root, 'add', '.')
        git(root, 'commit', '-qm', 'initial')
        return root

    def project_sync(self, target, **kwargs):
        target = Path(target)
        changes = [] if (target / 'AGENTS.md').read_text() == 'thin chief' else ['AGENTS.md', '.chief-of-staff/chief-lock.json']
        if kwargs['apply'] and changes:
            (target / 'AGENTS.md').write_text('thin chief')
            (target / '.chief-of-staff/chief-lock.json').write_text(json.dumps({
                'source_commit': kwargs['source_commit'], 'source_version': kwargs['source_version']}))
        return {'changes': changes, 'conflicts': []}

    def test_clean_sync_commit_repeat_and_revert(self):
        result = self.api.sync_repository(self.target, source=self.source)
        self.assertEqual(result['status'], 'success', result)
        self.assertEqual(git(self.target, 'branch', '--show-current'), 'chief/adopt-2.0.0')
        self.assertEqual(git(self.target, 'show', '-s', '--format=%an'), 'rong2qi')
        self.assertEqual(self.api.sync_repository(self.target, source=self.source)['status'], 'up_to_date')
        reverted = self.api.rollback(self.target, result['commit'])
        self.assertEqual(reverted['status'], 'success', reverted)
        self.assertEqual((self.target / 'AGENTS.md').read_text(), 'old chief')

    def test_patch_release_requires_exact_matching_tag_and_syncs_fleet(self):
        version = self.source / 'chief-version.json'
        value = json.loads(version.read_text())
        value['version'] = '2.0.1'
        version.write_text(json.dumps(value))
        git(self.source, 'add', '.')
        git(self.source, 'commit', '-qm', 'patch release')
        refused = self.api.sync_repository(self.target, source=self.source)
        self.assertEqual(refused['status'], 'conflict')
        git(self.source, 'tag', 'v2.0.1')
        manifest = self.base / 'projects.json'
        manifest.write_text(json.dumps({'version': 1, 'projects': [
            {'name': 'fixture', 'path': 'target', 'pinned': True}]}))
        result = self.api.fleet_sync(manifest, source=self.source, pinned=True)['results'][0]
        self.assertEqual(result['status'], 'success', result)
        self.assertEqual(result['source_version'], '2.0.1')
        self.assertEqual(result['branch'], 'chief/adopt-2.0.1')
        (self.source / 'unreleased').write_text('new')
        git(self.source, 'add', '.')
        git(self.source, 'commit', '-qm', 'after tag')
        self.assertEqual(self.api.sync_repository(self.target, source=self.source)['status'], 'conflict')

    def test_v202_release_requires_exact_matching_tag(self):
        version = self.source / 'chief-version.json'
        value = json.loads(version.read_text())
        value['version'] = '2.0.2'
        version.write_text(json.dumps(value))
        git(self.source, 'add', '.')
        git(self.source, 'commit', '-qm', 'v2.0.2 release')
        self.assertEqual(self.api.sync_repository(self.target, source=self.source)['status'], 'conflict')
        git(self.source, 'tag', 'v2.0.2')
        result = self.api.sync_repository(self.target, source=self.source)
        self.assertEqual(result['status'], 'success', result)
        self.assertEqual(result['source_version'], '2.0.2')
        self.assertEqual(result['branch'], 'chief/adopt-2.0.2')

    def test_dirty_business_uses_worktree_preserving_original(self):
        original_branch = git(self.target, 'branch', '--show-current')
        (self.target / 'business.txt').write_text('uncommitted work')
        result = self.api.sync_repository(self.target, source=self.source)
        self.assertEqual(result['status'], 'success', result)
        self.assertNotEqual(result['execution_path'], str(self.target))
        self.assertEqual((self.target / 'business.txt').read_text(), 'uncommitted work')
        self.assertEqual(git(self.target, 'branch', '--show-current'), original_branch)
        again = self.api.sync_repository(self.target, source=self.source)
        self.assertEqual(again['status'], 'up_to_date', again)

    def test_dirty_managed_conflicts_and_missing_continues_fleet(self):
        (self.target / 'AGENTS.md').write_text('manual changes')
        manifest = self.base / 'projects.json'
        manifest.write_text(json.dumps({'version': 1, 'projects': [
            {'name': 'manual', 'path': 'target', 'pinned': True},
            {'name': 'missing', 'path': 'absent', 'pinned': True}]}))
        result = self.api.fleet_sync(manifest, source=self.source, pinned=True)
        self.assertEqual([item['status'] for item in result['results']], ['conflict', 'not_found'])
        self.assertEqual((self.target / 'AGENTS.md').read_text(), 'manual changes')

    def test_dry_run_has_no_branch_or_file_writes(self):
        before = git(self.target, 'branch', '--list')
        result = self.api.sync_repository(self.target, source=self.source, dry_run=True)
        self.assertEqual(result['status'], 'success', result)
        self.assertTrue(result['dry_run'])
        self.assertEqual(before, git(self.target, 'branch', '--list'))
        self.assertFalse((self.target / '.chief-of-staff/chief-lock.json').exists())

    def test_real_source_sync_schema_and_repeat(self):
        self.real_source_sync_schema_and_repeat('2.0.0')

    def test_real_patch_release_fleet_migration_preserves_user_state(self):
        self.real_source_sync_schema_and_repeat('2.0.1')

    def test_real_v202_fleet_migration_preserves_user_state(self):
        self.real_source_sync_schema_and_repeat('2.0.2')

    def real_source_sync_schema_and_repeat(self, version):
        import shutil
        self.sync_patch.stop()
        version_path = self.source / 'chief-version.json'
        value = json.loads(version_path.read_text())
        value['version'] = version
        version_path.write_text(json.dumps(value))
        for name in ('scripts', 'assets', 'references'):
            shutil.copytree(SCRIPT.parents[1] / name, self.source / name,
                            ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        git(self.source, 'add', '.')
        git(self.source, 'commit', '-qm', 'actual source fixtures')
        git(self.source, 'tag', '-f', 'v' + version)
        target = self.base / 'real-project'
        code = "import sys;sys.path.insert(0,sys.argv[1]);import init_project;from pathlib import Path;sys.exit(init_project.initialize(Path(sys.argv[2]), 'Example'))"
        initialized = subprocess.run([sys.executable, '-B', '-c', code, str(self.source / 'scripts'), str(target)],
                                     capture_output=True, text=True)
        self.assertEqual(initialized.returncode, 0, initialized.stderr + initialized.stdout)
        # Reconstruct the supported old full instruction contract, including its
        # real Agent OS manifest, rather than only deleting the new source lock.
        legacy_code = """
import json, sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import agent_os
root, source = Path(sys.argv[2]), Path(sys.argv[1]).parent
project_path = root / '.chief-of-staff/project.json'
project = json.loads(project_path.read_text())
for key in ('work_execution_version', 'chief_version', 'chief_schema_version',
            'chief_source_commit', 'work_execution_adoption'):
    project.pop(key, None)
project_path.write_text(json.dumps(project))
(root / '.chief-of-staff/chief-lock.json').unlink()
plan_path = root / '.chief-of-staff/project-plan.json'
plan = json.loads(plan_path.read_text())
plan.pop('work_items', None)
plan.pop('work_history', None)
plan_path.write_text(json.dumps(plan))
legacy = (source / 'assets/compat/pre-work-execution-AGENTS.md').read_text().replace('{{PROJECT_NAME}}', 'Example')
for name, data in agent_os.render_contract_files('Example', codex_instructions=legacy).items():
    (root / name).write_bytes(data)
"""
        legacy = subprocess.run([sys.executable, '-B', '-c', legacy_code,
                                 str(self.source / 'scripts'), str(target)], capture_output=True, text=True)
        self.assertEqual(legacy.returncode, 0, legacy.stderr)
        (target / 'business.txt').write_text('original business')
        git(target, 'init', '-q')
        git(target, 'config', 'user.name', 'rong2qi')
        git(target, 'config', 'user.email', '249084307+rong2qi@users.noreply.github.com')
        git(target, 'add', '.')
        git(target, 'commit', '-qm', 'existing full legacy Chief project')
        dirty, manual = self.base / 'real-dirty', self.base / 'real-manual'
        git(self.base, 'clone', '-q', str(target), str(dirty))
        git(self.base, 'clone', '-q', str(target), str(manual))
        (dirty / 'business.txt').write_text('staged business bytes')
        git(dirty, 'add', 'business.txt')
        (dirty / 'business.txt').write_text('unstaged business bytes')
        (dirty / 'new-business.txt').write_text('untracked business bytes')
        (manual / 'AGENTS.md').write_text((manual / 'AGENTS.md').read_text() + '\nManual instruction drift\n')
        git(manual, '-c', 'user.name=rong2qi', '-c', 'user.email=249084307+rong2qi@users.noreply.github.com',
            'commit', '-qam', 'manual managed change')
        snapshot = lambda root: {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*')
                                 if p.is_file() and '.git' not in p.relative_to(root).parts}
        before_clean, before_dirty, before_manual = snapshot(target), snapshot(dirty), snapshot(manual)
        dirty_status = git(dirty, 'status', '--porcelain=v1', '-z')
        staged_bytes = git(dirty, 'show', ':business.txt')
        original_dirty_branch = git(dirty, 'branch', '--show-current')
        manifest = self.base / 'real-fleet.json'
        manifest.write_text(json.dumps({'version': 1, 'projects': [
            {'name': 'clean', 'path': str(target), 'pinned': True},
            {'name': 'dirty', 'path': str(dirty), 'pinned': True},
            {'name': 'manual', 'path': str(manual), 'pinned': True}]}))
        preview = self.api.fleet_sync(manifest, source=self.source, pinned=True, dry_run=True)
        self.assertEqual([r['status'] for r in preview['results']], ['success', 'success', 'conflict'], preview)
        self.assertEqual(snapshot(target), before_clean)
        self.assertEqual(snapshot(dirty), before_dirty)
        self.assertEqual(snapshot(manual), before_manual)
        result = self.api.fleet_sync(manifest, source=self.source, pinned=True)
        self.assertEqual([r['status'] for r in result['results']], ['success', 'success', 'conflict'], result)
        self.assertEqual(snapshot(dirty), before_dirty)
        self.assertEqual(snapshot(manual), before_manual)
        self.assertEqual(git(dirty, 'status', '--porcelain=v1', '-z'), dirty_status)
        self.assertEqual(git(dirty, 'show', ':business.txt'), staged_bytes)
        self.assertEqual(git(dirty, 'branch', '--show-current'), original_dirty_branch)
        self.assertNotEqual(result['results'][1]['execution_path'], str(dirty.resolve()))
        for item in result['results'][:2]:
            execution = Path(item['execution_path'])
            lock = json.loads((execution / '.chief-of-staff/chief-lock.json').read_text())
            self.assertEqual(lock['source_commit'], git(self.source, 'rev-parse', 'HEAD'))
            self.assertEqual(lock['version'], version)
            self.assertNotEqual((execution / 'AGENTS.md').read_bytes(), before_clean['AGENTS.md'])
        again = self.api.fleet_sync(manifest, source=self.source, pinned=True)
        self.assertEqual([r['status'] for r in again['results']], ['up_to_date', 'up_to_date', 'conflict'], again)
        for item in result['results'][:2]:
            reverted = self.api.rollback(item['execution_path'], item['commit'])
            self.assertEqual(reverted['status'], 'success', reverted)
            self.assertEqual(snapshot(Path(item['execution_path'])), before_clean)
        self.assertEqual(snapshot(dirty), before_dirty)
        self.assertEqual(git(dirty, 'show', ':business.txt'), staged_bytes)

    def test_agent_os_manifest_is_owned_but_dirty_agent_os_conflicts(self):
        self.assertTrue(self.api._managed('.agent-os/manifest.json'))
        (self.target / '.agent-os').mkdir()
        (self.target / '.agent-os' / 'manual.json').write_text('{}')
        result = self.api.sync_repository(self.target, source=self.source)
        self.assertEqual(result['status'], 'conflict', result)

    def test_committed_managed_drift_blocks_rollback(self):
        result = self.api.sync_repository(self.target, source=self.source)
        (self.target / 'AGENTS.md').write_text('manual edit after migration')
        git(self.target, 'add', 'AGENTS.md')
        git(self.target, 'commit', '-qm', 'manual edit')
        self.assertEqual(self.api.rollback(self.target, result['commit'])['status'], 'conflict')
        self.assertEqual((self.target / 'AGENTS.md').read_text(), 'manual edit after migration')

    def test_existing_unrelated_migration_branch_conflicts(self):
        git(self.target, 'branch', 'chief/adopt-2.0.0')
        result = self.api.sync_repository(self.target, source=self.source)
        self.assertEqual(result['status'], 'conflict', result)
        self.assertEqual((self.target / 'AGENTS.md').read_text(), 'old chief')

    def test_repeat_after_business_edit_or_commit_is_current(self):
        self.assertEqual(self.api.sync_repository(self.target, source=self.source)['status'], 'success')
        (self.target / 'business.txt').write_text('ongoing work')
        self.assertEqual(self.api.sync_repository(self.target, source=self.source)['status'], 'up_to_date')
        git(self.target, 'add', 'business.txt')
        git(self.target, 'commit', '-qm', 'business update')
        self.assertEqual(self.api.sync_repository(self.target, source=self.source)['status'], 'up_to_date')

    def test_bad_home_path_does_not_abort_fleet(self):
        manifest = self.base / 'paths.json'
        manifest.write_text(json.dumps({'version': 1, 'projects': [
            {'name': 'bad', 'path': '~chief_sync_nonexistent_user_129812/path'},
            {'name': 'valid', 'path': 'target'}]}))
        result = self.api.fleet_sync(manifest, source=self.source, dry_run=True)
        self.assertEqual([r['status'] for r in result['results']], ['failed', 'success'])

    def test_report_write_failure_keeps_stdout_results(self):
        import contextlib
        import io
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = self.api.main(['sync', '--target', str(self.target), '--source', str(self.source),
                                    '--dry-run', '--report', str(self.base / 'missing' / 'report.json')])
        report = json.loads(output.getvalue())
        self.assertEqual(report['status'], 'success')
        self.assertIn('report_error', report)
        self.assertEqual(status, 1)

    def test_rollback_rejects_nonmigration_commit(self):
        initial = git(self.target, 'rev-parse', 'HEAD')
        self.assertEqual(self.api.rollback(self.target, initial)['status'], 'conflict')


if __name__ == '__main__':
    unittest.main()
