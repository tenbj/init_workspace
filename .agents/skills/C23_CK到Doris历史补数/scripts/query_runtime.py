"""Check the actual Python runtime locally; optionally dispatch C03 in that process.

No package installation, persistent environment changes, credentials or network
access during --check-only. --ddl-table invokes the existing C03 read-only tool.
Provide --deps-dir only after verifying the existing dependency directory's origin.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
from pathlib import Path
import runpy
import sys


def skill_script(workspace: Path, prefix: str, filename: str) -> Path:
    registry = json.loads((workspace / '.system/standards/workspace-spec.json').read_text(encoding='utf-8-sig'))
    matches = [x for x in registry['skillsManagement']['registeredSkills'] if x.startswith(prefix + '_')]
    if len(matches) != 1:
        raise ValueError(f'{prefix}: registry must contain exactly one match')
    path = workspace / '.agents/skills' / matches[0] / 'scripts' / filename
    if not path.is_file():
        raise ValueError(f'{prefix}: script does not exist')
    return path


def preflight(workspace: Path, deps_dir: Path | None) -> dict:
    report = {'status': 'blocked', 'python': sys.executable,
              'python_version': sys.version.split()[0], 'database_connected': False,
              'environment_modified_permanently': False}
    if deps_dir is not None:
        deps_dir = deps_dir.resolve()
        report['deps_dir'] = str(deps_dir)
        if not (deps_dir / 'pymysql/__init__.py').is_file():
            return {**report, 'error_type': 'DEPENDENCY_PATH_INVALID',
                    'message': 'Specified directory does not contain pymysql; verify the path before installing anything.'}
        sys.path.insert(0, str(deps_dir))
        importlib.invalidate_caches()
    try:
        pymysql = importlib.import_module('pymysql')
        loaded = Path(pymysql.__file__).resolve()
        if deps_dir is not None and deps_dir not in loaded.parents:
            return {**report, 'error_type': 'DEPENDENCY_ORIGIN_MISMATCH',
                    'message': 'Already loaded pymysql is outside the explicitly selected directory; use a fresh process.'}
        report.update(pymysql_path=str(loaded), pymysql_version=getattr(pymysql, '__version__', 'unknown'))
        c02 = skill_script(workspace, 'C02', 'doris_query_client.py')
        spec = importlib.util.spec_from_file_location('c23_checked_doris_client', c02)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # Do not instantiate a client: this preflight does not read credentials.
        if not hasattr(module, 'DorisQueryClient'):
            raise ValueError('C02 client class is missing')
        c03 = skill_script(workspace, 'C03', 'get_create_table.py')
        report.update(status='ready', c02_script=str(c02), c03_script=str(c03))
    except ModuleNotFoundError as exc:
        report.update(error_type='MODULE_NOT_VISIBLE', module=exc.name,
                      message='Module is not importable by this interpreter; this does not prove that it is absent on disk.')
    except Exception as exc:
        report.update(error_type='IMPORT_OR_REGISTRY_ERROR', exception_type=type(exc).__name__,
                      message='Inspect the selected dependency and skill registry locally; no database retry was made.')
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, default=Path(__file__).resolve().parents[4])
    parser.add_argument('--deps-dir', type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check-only', action='store_true')
    mode.add_argument('--ddl-table')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    if args.ddl_table and args.output_dir is None:
        parser.error('--ddl-table requires --output-dir')
    if args.check_only and args.output_dir is not None:
        parser.error('--output-dir is only for the C03 DDL file')
    report = preflight(args.workspace.resolve(), args.deps_dir)
    print(json.dumps(report, ensure_ascii=False), flush=True)
    if report['status'] != 'ready':
        return 2
    if args.check_only:
        return 0
    # The dependency path remains active for C03 and the C02 module it loads.
    sys.argv = [report['c03_script'], args.ddl_table, '--output-dir', str(args.output_dir.resolve())]
    runpy.run_path(report['c03_script'], run_name='__main__')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
