"""Maintain local credentials and return precise routes without exposing values."""
from __future__ import annotations

import argparse
import base64
import csv
from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import io
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import tempfile
import uuid


class MaintenanceError(Exception):
    pass


@contextmanager
def maintenance_lock(workspace: Path, runtime: dict):
    path = workspace.absolute()/'.envs/.locks/maintenance.lock'
    runtime['assert_plain_path'](path)
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise MaintenanceError('maintenance_already_running_or_stale_lock') from None
    os.close(descriptor)
    try:
        yield
    finally:
        path.unlink()


def dpapi(data: bytes, *, decrypt=False) -> bytes:
    if os.name != 'nt':
        raise MaintenanceError('encrypted_recovery_unavailable_on_this_platform')

    class Blob(ctypes.Structure):
        _fields_ = [('size', wintypes.DWORD), ('data', ctypes.POINTER(ctypes.c_ubyte))]

    buffer = ctypes.create_string_buffer(data)
    source = Blob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
    output = Blob()
    library = ctypes.WinDLL('crypt32', use_last_error=True)
    operation = library.CryptUnprotectData if decrypt else library.CryptProtectData
    operation.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.POINTER(Blob),
                          ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(Blob)]
    operation.restype = wintypes.BOOL
    if not operation(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(output)):
        raise MaintenanceError('encrypted_recovery_operation_failed')
    free = ctypes.WinDLL('kernel32', use_last_error=True).LocalFree
    free.argtypes = [ctypes.c_void_p]
    free.restype = ctypes.c_void_p
    try:
        return ctypes.string_at(output.data, output.size)
    finally:
        free(ctypes.cast(output.data, ctypes.c_void_p))


def restrict_file(path: Path):
    if os.name != 'nt':
        path.chmod(0o600)
        return
    system = Path(os.environ['SystemRoot'])/'System32'
    identity = subprocess.run([str(system/'whoami.exe'), '/user', '/fo', 'csv', '/nh'],
                              capture_output=True, check=True)
    rows = list(csv.reader(io.StringIO(identity.stdout.decode('utf-8', errors='replace'))))
    sid = rows[-1][-1] if rows else ''
    if not re.fullmatch(r'S-1-\d+(?:-\d+)+', sid):
        raise MaintenanceError('current_user_identity_unavailable')
    result = subprocess.run([str(system/'icacls.exe'), str(path), '/inheritance:r',
                             '/grant:r', '*'+sid+':F'], capture_output=True)
    if result.returncode:
        raise MaintenanceError('private_file_acl_failed')


def bounded_read(path: Path, runtime: dict, limit=8 * 1024 * 1024) -> bytes:
    runtime['assert_plain_path'](path)
    with path.open('rb') as handle:
        data = handle.read(limit + 1)
    if not data or len(data) > limit:
        raise MaintenanceError('source_file_empty_or_too_large')
    return data


def atomic_write(path: Path, data: bytes, runtime: dict, *, replace: bool):
    runtime['assert_plain_path'](path)
    if path.exists() and not replace:
        raise MaintenanceError('target_exists_use_explicit_replace')
    path.parent.mkdir(parents=True, exist_ok=True)
    runtime['assert_plain_path'](path.parent)
    descriptor, temporary = tempfile.mkstemp(prefix='.pending-', dir=path.parent)
    pending = Path(temporary)
    os.close(descriptor)
    try:
        restrict_file(pending)
        with pending.open('wb') as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        runtime['assert_plain_path'](path)
        if replace:
            os.replace(pending, path)
        else:
            # A hard link publishes exclusively; never overwrite a concurrent file.
            os.link(pending, path)
            pending.unlink()
    finally:
        if pending.exists():
            pending.unlink()


def find_entry(workspace: Path, connection_id: str, runtime: dict) -> dict:
    entry = next((item for item in runtime['read_catalog'](workspace) if item['id'] == connection_id), None)
    if entry is None:
        raise MaintenanceError('connection_not_registered')
    return entry


def target_for(workspace: Path, entry: dict, name: str | None, runtime: dict) -> Path:
    if name:
        if name not in entry.get('secret_files', {}):
            raise MaintenanceError('secret_file_not_registered')
        relative = entry['secret_files'][name]
    else:
        if not entry['required_variables']:
            raise MaintenanceError('environment_variables_not_registered')
        relative = entry['file']
    target = workspace.absolute()/'.envs'/relative
    runtime['assert_plain_path'](target)
    return target


def protect_existing(workspace: Path, entry: dict, target: Path, runtime: dict) -> Path:
    relative = target.relative_to(workspace.absolute()/'.envs').as_posix()
    data = bounded_read(target, runtime)
    protected = dpapi(json.dumps({'path': relative, 'data': base64.b64encode(data).decode('ascii')}).encode('utf-8'))
    envelope = {'schema': 1, 'protection': 'dpapi-current-user',
                'payload': base64.b64encode(protected).decode('ascii')}
    snapshot = workspace.absolute()/'.envs'/'.recovery'/entry['id']/(uuid.uuid4().hex+'.json')
    atomic_write(snapshot, json.dumps(envelope).encode('ascii'), runtime, replace=False)
    return snapshot


def replace_private(workspace: Path, entry: dict, target: Path, data: bytes, runtime: dict, replace: bool) -> dict:
    backup = None
    if target.exists():
        if not replace:
            raise MaintenanceError('target_exists_use_explicit_replace')
        backup = protect_existing(workspace, entry, target, runtime)
    atomic_write(target, data, runtime, replace=replace)
    result = {'id': entry['id'], 'written': True, 'target': str(target)}
    if backup:
        result['backup'] = str(backup)
    return result


def perform(args, runtime: dict) -> dict:
    workspace = args.workspace.absolute()
    if args.action == 'route':
        return runtime['route_connection'](workspace, args.connection_id, args.variable, args.secret_file)
    if args.action == 'register':
        entries = runtime['read_catalog'](workspace)
        existing = next((e for e in entries if e['id'] == args.connection_id), None)
        if existing and not args.replace:
            raise MaintenanceError('connection_already_registered')
        files = {}
        for value in args.key_file or []:
            if '=' not in value:
                raise MaintenanceError('key_file_definition_invalid')
            name, filename = value.split('=', 1)
            if name in files:
                raise MaintenanceError('key_file_definition_duplicate')
            files[name] = 'keys/'+args.connection_id+'/'+filename
        entry = {'id': args.connection_id, 'purpose': args.purpose, 'environment': args.environment,
                 'permission': args.permission, 'file': args.connection_id+'.env',
                 'required_variables': args.variable or []}
        if files:
            entry['secret_files'] = files
        content = {'schema_version': 1, 'connections': [e for e in entries if e['id'] != args.connection_id]+[entry]}
        runtime['validate_catalog'](content)
        path = workspace/'.envs/catalog.json'
        atomic_write(path, (json.dumps(content, ensure_ascii=False, indent=2)+'\n').encode('utf-8'), runtime, replace=True)
        return {'id': args.connection_id, 'action': 'registered', 'target': str(path)}
    entry = find_entry(workspace, args.connection_id, runtime)
    if args.action == 'check':
        runtime['load_connection'](workspace, args.connection_id)
        return {'id': args.connection_id, 'configured': True, 'remote_tested': False}
    target = target_for(workspace, entry, getattr(args, 'name', None), runtime)
    if args.action == 'restore':
        snapshot = args.snapshot.absolute()
        expected = workspace/'.envs/.recovery'/entry['id']
        if snapshot.parent != expected:
            raise MaintenanceError('recovery_path_invalid')
        envelope = json.loads(bounded_read(snapshot, runtime, limit=32 * 1024 * 1024))
        if (not isinstance(envelope, dict) or set(envelope) != {'schema', 'protection', 'payload'} or
                envelope.get('schema') != 1 or envelope.get('protection') != 'dpapi-current-user' or
                not isinstance(envelope.get('payload'), str)):
            raise MaintenanceError('recovery_envelope_invalid')
        original = json.loads(dpapi(base64.b64decode(envelope['payload'], validate=True), decrypt=True))
        if (not isinstance(original, dict) or set(original) != {'path', 'data'} or
                not isinstance(original.get('path'), str) or not isinstance(original.get('data'), str)):
            raise MaintenanceError('recovery_plaintext_schema_invalid')
        if original['path'] != target.relative_to(workspace/'.envs').as_posix():
            raise MaintenanceError('recovery_target_mismatch')
        data = base64.b64decode(original['data'], validate=True)
        if not data or len(data) > 8 * 1024 * 1024:
            raise MaintenanceError('recovery_content_empty_or_too_large')
    else:
        data = bounded_read(args.source.absolute(), runtime)
        if args.action == 'put-env':
            values = runtime['parse_values'](data.decode('utf-8-sig'))
            if set(values) != set(entry['required_variables']) or any(not v for v in values.values()):
                raise MaintenanceError('source_variables_incomplete_or_unregistered')
    result = replace_private(workspace, entry, target, data, runtime, args.replace)
    result['action'] = args.action
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[4])
    actions = parser.add_subparsers(dest='action', required=True)
    route = actions.add_parser('route')
    route.add_argument('connection_id')
    route.add_argument('--variable', action='append')
    route.add_argument('--secret-file', action='append')
    register = actions.add_parser('register')
    register.add_argument('connection_id')
    for field in ['purpose', 'environment', 'permission']:
        register.add_argument('--'+field, required=True)
    register.add_argument('--variable', action='append')
    register.add_argument('--key-file', action='append')
    register.add_argument('--replace', action='store_true')
    for action in ['put-env', 'put-file', 'restore', 'check']:
        child = actions.add_parser(action)
        child.add_argument('connection_id')
        if action in {'put-file', 'restore'}:
            child.add_argument('--name', required=action == 'put-file')
        if action in {'put-env', 'put-file'}:
            child.add_argument('--source', type=Path, required=True)
        if action == 'restore':
            child.add_argument('--snapshot', type=Path, required=True)
        if action != 'check':
            child.add_argument('--replace', action='store_true')
    args = parser.parse_args(argv)
    try:
        loader = args.workspace.absolute()/'.envs/env_manager.py'
        for path in (loader, *loader.parents):
            if path.is_symlink() or (path.exists() and getattr(path.lstat(), 'st_file_attributes', 0) & 0x400):
                raise MaintenanceError('linked_loader_refused')
        runtime = runpy.run_path(str(loader))
        try:
            if args.action in {'route', 'check'}:
                result = perform(args, runtime)
            else:
                with maintenance_lock(args.workspace, runtime):
                    result = perform(args, runtime)
        except runtime['ConfigError'] as error:
            raise MaintenanceError(str(error)) from None
        print(json.dumps(result, ensure_ascii=True))
        return 0
    except MaintenanceError as error:
        print(json.dumps({'ok': False, 'error': str(error)}), file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print('{"ok":false,"error":"local_maintenance_failed"}', file=sys.stderr)
    return 2


if __name__ == '__main__':
    raise SystemExit(main())
