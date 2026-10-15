"""Isolated checks using synthetic values; never reads real credential files."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

SRC = Path(__file__).resolve().parent
WORKSPACE = SRC.parents[3]
MANAGER = WORKSPACE / '.envs/env_manager.py'


def module_at(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


manager = module_at('env_manager_test', MANAGER)
initializer = module_at('initializer_env_test', SRC/'init_workspace.py')
maintenance = module_at('environment_maintenance_test', WORKSPACE/'.agents/skills/B12_环境维护/scripts/environment.py')


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='environment-fixture-',
            dir=Path(tempfile.gettempdir()).resolve())
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.workspace = self.root/'workspace'
        self.envdir = self.workspace/'.envs'
        (self.envdir/'examples').mkdir(parents=True)
        self.catalog = {'schema_version': 1, 'connections': [{
            'id': 'fixture.test.readonly', 'purpose': 'synthetic test',
            'environment': 'test', 'permission': 'readonly',
            'file': 'fixture.test.readonly.env', 'required_variables': ['FIXTURE_PASSWORD']}]}
        self.write_catalog()
        (self.envdir/'README.md').write_text('Synthetic public instructions', encoding='utf-8')
        shutil.copyfile(MANAGER, self.envdir/'env_manager.py')
        shutil.copyfile(WORKSPACE/'.envs/.gitignore', self.envdir/'.gitignore')
        (self.envdir/'examples/fixture.test.readonly.env.example').write_text('FIXTURE_PASSWORD=\n', encoding='utf-8')
        self.secret = 'synthetic-p@ss # 中文 $value'
        self.private = self.envdir/'fixture.test.readonly.env'
        self.private.write_text('FIXTURE_PASSWORD="'+self.secret+'"\n', encoding='utf-8')

    def write_catalog(self):
        (self.envdir/'catalog.json').write_text(json.dumps(self.catalog), encoding='utf-8')

    def test_special_characters_are_literal(self):
        values = manager.load_connection(self.workspace, 'fixture.test.readonly')
        self.assertEqual(values['FIXTURE_PASSWORD'], self.secret)
        self.assertEqual(manager.parse_values("FIXTURE_PASSWORD='synthetic-$(anything) C:\\path # x'"),
                         {'FIXTURE_PASSWORD': 'synthetic-$(anything) C:\\path # x'})

    def test_missing_duplicate_and_unknown_values_refused(self):
        for text in ['', 'FIXTURE_PASSWORD=\n', 'FIXTURE_PASSWORD=a\nFIXTURE_PASSWORD=b',
                     'FIXTURE_PASSWORD=a\nOTHER=b', 'FIXTURE_PASSWORD="unclosed']:
            with self.subTest(text=text):
                self.private.write_text(text, encoding='utf-8')
                with self.assertRaises(manager.ConfigError):
                    manager.load_connection(self.workspace, 'fixture.test.readonly')

    def test_paths_and_system_environment_names_refused(self):
        self.catalog['connections'][0]['file'] = '../outside.env'
        self.write_catalog()
        with self.assertRaises(manager.ConfigError):
            manager.read_catalog(self.workspace)
        self.catalog['connections'][0]['file'] = 'fixture.test.readonly.env'
        self.catalog['connections'][0]['required_variables'] = ['PATH']
        self.write_catalog()
        with self.assertRaises(manager.ConfigError):
            manager.read_catalog(self.workspace)

    def test_run_redacts_and_does_not_inherit_unrelated_credentials(self):
        script = ('import os,sys; from urllib.parse import quote; '
                  'v=os.environ["FIXTURE_PASSWORD"]; '
                  'print(v); print(quote(v,safe=""), file=sys.stderr); '
                  'assert "UNRELATED_API_KEY" not in os.environ; sys.exit(7)')
        output, error = io.StringIO(), io.StringIO()
        with patch.dict(os.environ, {'UNRELATED_API_KEY': 'synthetic-unrelated'}), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = manager.run_connection(self.workspace, 'fixture.test.readonly', [sys.executable, '-c', script])
        self.assertEqual(code, 7)
        self.assertNotIn(self.secret, output.getvalue()+error.getvalue())
        self.assertIn('[REDACTED]', output.getvalue())
        self.assertIn('[REDACTED]', error.getvalue())

    def test_existing_environment_conflict_does_not_launch(self):
        with patch.dict(os.environ, {'FIXTURE_PASSWORD': 'synthetic-conflict'}), \
                patch.object(manager.subprocess, 'run') as child:
            with self.assertRaises(manager.ConfigError):
                manager.run_connection(self.workspace, 'fixture.test.readonly', ['unused'])
        child.assert_not_called()

    def test_public_export_never_copies_private_file_and_refuses_filled_example(self):
        destination = self.root/'bundle'
        manager.export_public(self.workspace, destination)
        self.assertFalse((destination/self.private.name).exists())
        self.assertEqual(len([p for p in destination.rglob('*') if p.is_file()]), 5)
        self.assertTrue(all(self.secret.encode() not in p.read_bytes() for p in destination.rglob('*') if p.is_file()))
        (self.envdir/'examples/fixture.test.readonly.env.example').write_text(
            'FIXTURE_PASSWORD=synthetic-do-not-publish', encoding='utf-8')
        with self.assertRaises(manager.ConfigError):
            manager.export_public(self.workspace, self.root/'rejected')
        self.assertFalse((self.root/'rejected').exists())

    def test_symlink_file_refused(self):
        target = self.root/'outside'
        target.write_text('FIXTURE_PASSWORD=synthetic-outside', encoding='utf-8')
        self.private.unlink()
        try:
            self.private.symlink_to(target)
        except OSError:
            self.skipTest('OS does not permit creating symlink fixture')
        with self.assertRaises(manager.ConfigError):
            manager.load_connection(self.workspace, 'fixture.test.readonly')

    def prepare_templates(self):
        templates = self.root/'templates'
        (templates/'system/standards').mkdir(parents=True)
        (templates/'rules').mkdir()
        (templates/'skills').mkdir()
        spec = json.loads((WORKSPACE/'.system/standards/workspace-spec.json').read_text(encoding='utf-8'))
        spec['skillsManagement']['registeredSkills'] = []
        spec['environmentManagement']['publicFiles'] = list(manager.public_payload(self.workspace))
        (templates/'system/standards/workspace-spec.json').write_text(json.dumps(spec), encoding='utf-8')
        manager.export_public(self.workspace, templates/'environment')
        return templates

    def test_initializer_preserves_private_files_catalog_and_public_edits(self):
        templates = self.prepare_templates()
        target = self.root/'initialized'
        fresh = initializer.initialize_workspace(target, templates, 'initialize')
        self.assertFalse(fresh['errors'])
        envdir = target/'.envs'
        private = envdir/'fixture.test.readonly.env'
        private.write_bytes(self.private.read_bytes())
        catalog = envdir/'catalog.json'
        catalog.write_text('LOCAL_CATALOG_MARKER', encoding='utf-8')
        before = {p: p.read_bytes() for p in (private, catalog)}
        upgrade = initializer.initialize_workspace(target, templates, 'upgrade')
        self.assertFalse(upgrade['errors'])
        self.assertTrue(all(p.read_bytes() == text for p, text in before.items()))
        self.assertTrue(all(self.secret.encode() not in p.read_bytes() for p in (target/'.history').rglob('*') if p.is_file()))

    def test_initializer_rejects_polluted_bundle_before_creating_target(self):
        templates = self.prepare_templates()
        (templates/'environment/private.env').write_text('FIXTURE_PASSWORD=synthetic-leak', encoding='utf-8')
        target = self.root/'rejected-workspace'
        with self.assertRaises(ValueError):
            initializer.initialize_workspace(target, templates, 'initialize')
        self.assertFalse(target.exists())

    def test_git_ignores_private_file_but_keeps_public_files(self):
        subprocess.run(['git', 'init', '-q', str(self.workspace)], check=True)
        shutil.copyfile(WORKSPACE/'.gitignore', self.workspace/'.gitignore')
        def ignored(path):
            return subprocess.run(['git', '-C', str(self.workspace), 'check-ignore', '-q', path]).returncode == 0
        self.assertTrue(ignored('.envs/fixture.test.readonly.env'))
        self.assertTrue(ignored('.envs/token-cache.json'))
        self.assertTrue(ignored('misplaced.env'))
        for name in ['.gitignore', 'README.md', 'catalog.json', 'env_manager.py', 'examples/fixture.test.readonly.env.example']:
            self.assertFalse(ignored('.envs/'+name), name)

    def test_backup_preflight_refuses_private_data_without_creating_snapshot(self):
        powershell = shutil.which('pwsh') or shutil.which('powershell')
        if powershell is None:
            self.skipTest('PowerShell unavailable')
        helper = WORKSPACE/'.agents/skills/B02_版本控制备份/scripts/content_snapshot.ps1'
        command = """
param($helper, $source, $destination)
$ErrorActionPreference = 'Stop'
. $helper
try {
    New-ContentSnapshot -Source $source -Destination $destination
    exit 5
} catch {
    if (Test-Path -LiteralPath $destination) { exit 6 }
    if ($_.Exception.Message -notmatch 'Private environment files') { exit 7 }
    exit 0
}
"""
        script = self.root/'backup-private-fixture.ps1'
        script.write_text(command, encoding='utf-8-sig')
        result = subprocess.run([powershell, '-NoProfile', '-File', str(script),
            str(helper), str(self.workspace), str(self.root/'snapshot')], capture_output=True)
        self.assertEqual(result.returncode, 0, 'Backup should refuse before copying private payload')
        self.assertFalse((self.root/'snapshot').exists())

    def test_backup_guard_allows_public_and_refuses_direct_credentials(self):
        powershell = shutil.which('pwsh') or shutil.which('powershell')
        if powershell is None:
            self.skipTest('PowerShell unavailable')
        helper = WORKSPACE/'.agents/skills/B02_版本控制备份/scripts/content_snapshot.ps1'
        command = """
param($helper, $public, $private)
$ErrorActionPreference = 'Stop'
. $helper
Assert-EnvironmentBackupPath $public
try { Assert-EnvironmentBackupPath $private; exit 8 }
catch {
    if ($_.Exception.Message -notmatch 'Private environment files') { exit 9 }
}
exit 0
"""
        script = self.root/'backup-path-fixture.ps1'
        script.write_text(command, encoding='utf-8-sig')
        result = subprocess.run([powershell, '-NoProfile', '-File', str(script),
            str(helper), str(self.envdir/'README.md'), str(self.private)], capture_output=True)
        self.assertEqual(result.returncode, 0)

    def test_initializer_refuses_private_data_in_managed_skill_backup(self):
        skill = self.root/'managed-skill'
        skill.mkdir()
        (skill/'.env').write_text('FIXTURE_PASSWORD=synthetic-private', encoding='utf-8')
        history = self.root/'history'
        with self.assertRaises(ValueError):
            initializer.backup_existing_dir(skill, history, 'fixture')
        self.assertFalse(history.exists())

    def test_route_reads_only_public_catalog_and_returns_requested_variable(self):
        entry = self.catalog['connections'][0]
        entry['required_variables'].append('OTHER_API_KEY')
        entry['secret_files'] = {'CLIENT_KEY_FILE': 'keys/fixture.test.readonly/client.pem'}
        self.write_catalog()
        original = Path.read_text
        opened = []
        def read_public(path, *args, **kwargs):
            opened.append(path)
            self.assertEqual(path, self.envdir/'catalog.json')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', read_public):
            route = manager.route_connection(self.workspace, 'fixture.test.readonly', ['FIXTURE_PASSWORD'], None)
        self.assertEqual(route['variables'], ['FIXTURE_PASSWORD'])
        self.assertEqual(route['secret_files'], {})
        self.assertEqual(route['environment_file'], str(self.private))
        self.assertEqual(opened, [self.envdir/'catalog.json'])
        self.assertNotIn('OTHER_API_KEY', json.dumps(route))

    def test_file_only_route_excludes_environment_and_other_key(self):
        entry = self.catalog['connections'][0]
        entry['secret_files'] = {'CLIENT_KEY_FILE':'keys/fixture.test.readonly/client.pem',
                                 'OTHER_KEY_FILE':'keys/fixture.test.readonly/other.pem'}
        self.write_catalog()
        route = manager.route_connection(self.workspace, 'fixture.test.readonly', None, ['CLIENT_KEY_FILE'])
        self.assertNotIn('environment_file', route)
        self.assertEqual(route['variables'], [])
        self.assertEqual(set(route['secret_files']), {'CLIENT_KEY_FILE'})
        with self.assertRaises(manager.ConfigError):
            manager.route_connection(self.workspace, 'fixture.test.readonly', ['UNKNOWN_SECRET'], None)

    def test_key_route_cannot_escape_its_connection(self):
        entry = self.catalog['connections'][0]
        for value in ['../outside.pem', 'keys/another/key.pem', 'keys/fixture.test.readonly/../key.pem']:
            entry['secret_files'] = {'CLIENT_KEY_FILE': value}
            self.write_catalog()
            with self.assertRaises(manager.ConfigError):
                manager.read_catalog(self.workspace)

    def test_environment_local_gitignore_protects_without_root_rules(self):
        subprocess.run(['git', 'init', '-q', str(self.workspace)], check=True)
        self.assertFalse((self.workspace/'.gitignore').exists())
        for name in ['.envs/fixture.test.readonly.env', '.envs/keys/fixture.test.readonly/key.pem',
                     '.envs/.recovery/fixture.test.readonly/backup.json', '.envs/.locks/maintenance.lock']:
            result = subprocess.run(['git', '-C', str(self.workspace), 'check-ignore', '-q', name])
            self.assertEqual(result.returncode, 0)
        for name in ['.gitignore', 'README.md', 'catalog.json', 'env_manager.py', 'examples/fixture.test.readonly.env.example']:
            result = subprocess.run(['git', '-C', str(self.workspace), 'check-ignore', '-q', '.envs/'+name])
            self.assertEqual(result.returncode, 1)

    def test_maintenance_lock_rejects_parallel_writer(self):
        with maintenance.maintenance_lock(self.workspace, vars(manager)):
            with self.assertRaises(maintenance.MaintenanceError):
                with maintenance.maintenance_lock(self.workspace, vars(manager)):
                    pass
        self.assertFalse((self.envdir/'.locks/maintenance.lock').exists())

    def maintenance_args(self, action, **kwargs):
        from argparse import Namespace
        return Namespace(action=action, workspace=self.workspace, connection_id='fixture.test.readonly',
                         name=kwargs.pop('name', None), replace=kwargs.pop('replace', False), **kwargs)

    def test_maintenance_rejects_unknown_source_variables_without_overwriting(self):
        source = self.root/'incoming.env'
        source.write_text('UNKNOWN_SECRET=synthetic-value', encoding='utf-8')
        original = self.private.read_bytes()
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.perform(self.maintenance_args('put-env', source=source, replace=True), vars(manager))
        self.assertEqual(self.private.read_bytes(), original)
        self.assertFalse((self.envdir/'.recovery').exists())

    def test_maintenance_never_overwrites_without_explicit_replace(self):
        source = self.root/'incoming.env'
        source.write_text('FIXTURE_PASSWORD=synthetic-new', encoding='utf-8')
        original = self.private.read_bytes()
        with self.assertRaises(maintenance.MaintenanceError):
            maintenance.perform(self.maintenance_args('put-env', source=source), vars(manager))
        self.assertEqual(self.private.read_bytes(), original)

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI and ACL integration')
    def test_private_update_and_restore_uses_encrypted_backup(self):
        source = self.root/'incoming.env'
        source.write_text('FIXTURE_PASSWORD=synthetic-new', encoding='utf-8')
        original = self.private.read_bytes()
        result = maintenance.perform(self.maintenance_args('put-env', source=source, replace=True), vars(manager))
        self.assertEqual(self.private.read_bytes(), source.read_bytes())
        backup = Path(result['backup'])
        self.assertNotIn(self.secret.encode(), backup.read_bytes())
        self.assertNotIn(self.secret, json.dumps(result))
        restored = maintenance.perform(self.maintenance_args('restore', snapshot=backup, replace=True), vars(manager))
        self.assertEqual(self.private.read_bytes(), original)
        self.assertTrue(Path(restored['backup']).is_file())

    def test_file_key_import_touches_only_selected_source(self):
        self.catalog['connections'][0]['secret_files']={'CLIENT_KEY_FILE':'keys/fixture.test.readonly/client.pem'}
        self.write_catalog()
        source = self.root/'incoming.pem'
        source.write_bytes(b'synthetic-private-key-payload')
        original_read = maintenance.bounded_read
        opened = []
        def read_selected(path, runtime):
            opened.append(path)
            return original_read(path, runtime)
        with patch.object(maintenance, 'bounded_read', read_selected):
            result = maintenance.perform(self.maintenance_args('put-file', source=source, name='CLIENT_KEY_FILE'), vars(manager))
        self.assertEqual(opened, [source])
        self.assertEqual(Path(result['target']).read_bytes(), b'synthetic-private-key-payload')
        self.assertNotIn('synthetic-private-key-payload', json.dumps(result))

    def test_restore_bad_envelope_returns_fixed_error_and_preserves_original(self):
        folder = self.envdir/'.recovery/fixture.test.readonly'
        folder.mkdir(parents=True)
        snapshot = folder/'bad.json'
        snapshot.write_text('[]', encoding='utf-8')
        original = self.private.read_bytes()
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = maintenance.main(['--workspace', str(self.workspace), 'restore',
                'fixture.test.readonly', '--snapshot', str(snapshot), '--replace'])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(error.getvalue())['error'], 'recovery_envelope_invalid')
        self.assertNotIn('Traceback', error.getvalue())
        self.assertEqual(self.private.read_bytes(), original)

    def test_windows_device_names_and_trailing_dots_are_not_valid_routes(self):
        for connection_id in ['nul', 'con.prod', 'com1']:
            entry = dict(self.catalog['connections'][0], id=connection_id, file=connection_id+'.env')
            with self.assertRaises(manager.ConfigError):
                manager.validate_catalog({'schema_version':1, 'connections':[entry]})
        for filename in ['NUL.pem', 'Lpt1.key', 'client.']:
            entry = dict(self.catalog['connections'][0], secret_files={
                'CLIENT_KEY_FILE':'keys/fixture.test.readonly/'+filename})
            with self.assertRaises(manager.ConfigError):
                manager.validate_catalog({'schema_version':1, 'connections':[entry]})


if __name__ == '__main__':
    unittest.main(verbosity=2)
