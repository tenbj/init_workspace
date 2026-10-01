"""Isolated real-Git integration checks; never modify the user's repositories."""
import ast
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid

BASE = Path(tempfile.mkdtemp(prefix='backup-validation-'))
STAGE = Path(__file__).resolve().parents[4]
GIT = shutil.which('git') or r'D:\Program Files\Git\cmd\git.exe'
ENGINES = [r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe',
           r'C:\Users\Administrator\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe']
RESULTS = []

def run(args, ok=True):
    p = subprocess.run(list(map(str, args)), capture_output=True, text=True, encoding='utf-8', errors='replace')
    if ok and p.returncode:
        raise AssertionError(f'Command failed: {args}\n{p.stdout}\n{p.stderr}')
    return p

def git(repo, *args):
    return run([GIT, '-c', 'user.name=Backup Test', '-c', 'user.email=backup-test@example.invalid', '-C', repo, *args]).stdout

def ps(engine, script, *args, ok=True):
    return run([engine, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', script, *args], ok=ok)

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')

def payload(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts}

def metadata(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file() and '.git' in p.relative_to(root).parts}

testroot = Path(tempfile.mkdtemp(prefix='backup-content-integration-', dir=BASE))
for number, engine in enumerate(ENGINES):
    root = testroot / f'engine-{number}'
    script = root / '.agents/skills/B02_版本控制备份/scripts/backup.ps1'
    script.parent.mkdir(parents=True)
    for name in ('backup.ps1', 'content_snapshot.ps1'):
        shutil.copy2(STAGE / '.agents/skills/B02_版本控制备份/scripts' / name, script.parent / name)
    (root / '.history').mkdir()
    project = root / 'output/01_测试 [数据]'
    repo = project / '03_代码程序/repo'
    repo.mkdir(parents=True)
    git(repo, 'init', '-b', 'main')
    write(repo / 'tracked.txt', 'committed\n')
    write(repo / '.gitignore', 'ignored.dat\n')
    git(repo, 'add', '.')
    git(repo, 'commit', '-m', 'isolated fixture')
    write(repo / 'tracked.txt', 'staged\n')
    git(repo, 'add', 'tracked.txt')
    write(repo / 'tracked.txt', 'working after staged\n')
    write(repo / 'untracked.txt', 'untracked\n')
    write(repo / 'ignored.dat', 'ignored local data\n')
    write(repo / '.hidden', 'hidden\n')
    run(['attrib', '+H', repo / '.hidden'])
    write(repo / '[字面].txt', 'literal path\n')
    (repo / 'empty').mkdir()
    nested = repo / 'nested'
    nested.mkdir()
    git(nested, 'init', '-b', 'develop')
    write(nested / 'nested-untracked.txt', 'nested dirty data\n')
    worktree = project / '03_代码程序/linked'
    git(repo, 'worktree', 'add', '--detach', worktree, 'HEAD')
    write(worktree / 'local.txt', 'worktree untracked\n')
    upstream = testroot / f'submodule-source-{number}'
    upstream.mkdir()
    git(upstream, 'init', '-b', 'main')
    write(upstream / 'module.txt', 'module\n')
    git(upstream, 'add', '.')
    git(upstream, 'commit', '-m', 'isolated module fixture')
    git(repo, '-c', 'protocol.file.allow=always', 'submodule', 'add', str(upstream), 'module')
    write(repo / 'module/module.txt', 'dirty submodule\n')
    write(project / '版本记录.md', '# 版本记录\n\n## v1.2.3\n')
    expected = payload(project)
    before_metadata = metadata(project)
    statuses = {str(r): git(r, 'status', '--porcelain=v1', '--untracked-files=all') for r in (repo, nested, worktree, repo / 'module')}
    ps(engine, script, '-TargetPath', str(project), '-Mode', 'PROJECT', '-ChangeType', 'PATCH')
    snapshots = list((root / '.history/output').iterdir())
    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert payload(snapshot) == expected
    assert not any(p.name.lower() == '.git' for p in snapshot.rglob('*'))
    assert (snapshot / '03_代码程序/repo/empty').is_dir()
    assert metadata(project) == before_metadata
    assert statuses == {str(r): git(r, 'status', '--porcelain=v1', '--untracked-files=all') for r in (repo, nested, worktree, repo / 'module')}
    assert 'v1.2.4' in (project / '版本记录.md').read_text(encoding='utf-8')
    RESULTS.append({'engine': Path(engine).name + str(number), 'case': 'PROJECT real nested git, submodule, worktree; staged/dirty/untracked/ignored/hidden/literal/empty preserved', 'passed': True})

    folder = root / '.agents/skills/example'
    write(folder / 'SKILL.md', 'skill fixture\n')
    write(folder / 'nested/.git', 'gitdir: outside\n')
    write(folder / 'nested/keep.txt', 'keep\n')
    ps(engine, script, '-TargetPath', str(folder), '-Mode', 'FOLDER')
    folder_snap = next((root / '.history/.agents/skills').iterdir())
    assert payload(folder_snap) == payload(folder)
    assert not (folder_snap / 'nested/.git').exists()
    RESULTS.append({'engine': number, 'case': 'FOLDER .git file excluded, contents preserved', 'passed': True})

    helper_runner = root / 'helper-check.ps1'
    helper_runner.write_text('param($Helper,$Source,$Destination)\n$ErrorActionPreference="Stop"\n. $Helper\nNew-ContentSnapshot -Source $Source -Destination $Destination\n', encoding='utf-8-sig')
    helper = script.parent / 'content_snapshot.ps1'
    original_snapshot = payload(snapshot)
    assert ps(engine, helper_runner, helper, project, snapshot, ok=False).returncode != 0
    assert payload(snapshot) == original_snapshot
    assert ps(engine, helper_runner, helper, project, project / 'recursive', ok=False).returncode != 0
    assert not (project / 'recursive').exists()
    for target in (root, project / '03_代码程序'):
        assert ps(engine, script, '-TargetPath', target, '-Mode', 'PROJECT', ok=False).returncode != 0
    RESULTS.append({'engine': number, 'case': 'existing snapshot, recursive destination and wrong PROJECT boundary refused', 'passed': True})

    linkproject = root / 'output/02_link'
    linkproject.mkdir()
    write(linkproject / '版本记录.md', '# versions\n\n## v1.0.0\n')
    target = root / 'link-target'
    target.mkdir()
    write(target / 'protected.txt', 'external fixture\n')
    junction = linkproject / 'junction'
    linkscript = root / 'create-link.ps1'
    linkscript.write_text('param($Link,$Target)\nNew-Item -ItemType Junction -Path $Link -Target $Target -ErrorAction Stop|Out-Null', encoding='utf-8-sig')
    ps(engine, linkscript, junction, target)
    assert ps(engine, script, '-TargetPath', linkproject, '-Mode', 'PROJECT', ok=False).returncode != 0
    assert 'v1.0.1' not in (linkproject / '版本记录.md').read_text(encoding='utf-8')
    assert not list((root / '.history/output').glob('02_link*'))
    RESULTS.append({'engine': number, 'case': 'junction aborts before snapshot/version mutation', 'passed': True})

    lockedproject = root / 'output/03_locked'
    write(lockedproject / '版本记录.md', '# versions\n\n## v1.0.0\n')
    locked = lockedproject / 'locked.bin'
    write(locked, 'cannot read while locked\n')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p]
    kernel.CreateFileW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    handle = kernel.CreateFileW(str(locked), 0x80000000, 0, None, 3, 0x80, None)
    assert handle not in (None, ctypes.c_void_p(-1).value)
    try:
        failed = ps(engine, script, '-TargetPath', lockedproject, '-Mode', 'PROJECT', ok=False)
        assert failed.returncode != 0
    finally:
        kernel.CloseHandle(handle)
    assert 'v1.0.1' not in (lockedproject / '版本记录.md').read_text(encoding='utf-8')
    partials = list((root / '.history/output').glob('03_locked*'))
    assert partials and all('.incomplete-' in p.name for p in partials)
    RESULTS.append({'engine': number, 'case': 'real file-lock copy failure: no success snapshot, no version bump, partial retained', 'passed': True})

    # Exercise the actual B06 snapshot function without running normalization/migration.
    normalized = (STAGE / '.agents/skills/B06_项目规范化/scripts/normalize.ps1').read_text(encoding='utf-8-sig')
    start = normalized.index('function Ensure-ProjectSnapshot(')
    end = normalized.index('\nfunction ', start + 1)
    b06run = root / 'b06-snapshot.ps1'
    b06run.write_text('param($Helper,$Root,$Project)\n$ErrorActionPreference="Stop"\n. $Helper\n$wn=$Root\n$S_anomaly="test"\n$script:snapshottedProjects=@{}\n$script:fixLog=@()\n' + normalized[start:end] + '\nEnsure-ProjectSnapshot $Project\nEnsure-ProjectSnapshot $Project\n', encoding='utf-8-sig')
    b06project = root / 'output/04_normalize'
    write(b06project / '.git/HEAD', 'metadata fixture\n')
    write(b06project / 'keep.txt', 'normalization protected data\n')
    ps(engine, b06run, helper, root, b06project)
    b06snaps = list((root / '.history/output').glob('04_normalize*'))
    assert len(b06snaps) == 1 and payload(b06snaps[0]) == payload(b06project)
    assert not (b06snaps[0] / '.git').exists()
    RESULTS.append({'engine': number, 'case': 'B06 actual snapshot function: Git excluded, contents preserved, duplicate within run avoided', 'passed': True})

# Execute only initializer backup function definitions against isolated fixtures.
source = (STAGE / 'output/00_系统治理/03_代码程序/src/init_workspace.py').read_text(encoding='utf-8')
tree = ast.parse(source)
names = {'ensure_dir', 'unique_path', 'backup_existing_dir', 'replace_managed_skill', 'copy_tree_no_pycache'}
functions = ast.Module(body=[n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names], type_ignores=[])
namespace = {'Path': Path, 'os': os, 'shutil': shutil, 'uuid': uuid}
exec(compile(functions, '<initializer-backup-functions>', 'exec'), namespace)
init_source = testroot / 'initializer-source'
write(init_source / '.git/HEAD', 'git\n')
write(init_source / 'nested/.git', 'gitdir\n')
write(init_source / 'nested/.hidden', 'local\n')
write(init_source / 'untracked.txt', 'untouched\n')
history = testroot / 'initializer-history'
snap = namespace['backup_existing_dir'](init_source, history, 'fixture')
assert payload(snap) == payload(init_source) and not any(p.name == '.git' for p in snap.rglob('*'))
RESULTS.append({'engine': 'Python initializer', 'case': 'directory upgrade backup excludes every .git and preserves work payload', 'passed': True})
namespace['backup_existing_dir'](init_source, history, 'fixture')
assert len(list(history.iterdir())) == 2
RESULTS.append({'engine': 'Python initializer', 'case': 'existing snapshots get unique names, never overwritten', 'passed': True})

try:
    namespace['backup_existing_dir'](init_source, init_source / 'recursive-history', 'fixture')
    raise AssertionError('Recursive initializer backup accepted')
except ValueError:
    pass
assert not (init_source / 'recursive-history').exists()
RESULTS.append({'engine': 'Python initializer', 'case': 'recursive destination rejected without writing', 'passed': True})
linksrc = testroot / 'initializer-with-link'
linksrc.mkdir()
ps(ENGINES[0], testroot / 'engine-0/create-link.ps1', linksrc / 'junction', init_source)
try:
    namespace['backup_existing_dir'](linksrc, testroot / 'must-not-create', 'fixture')
    raise AssertionError('Initializer junction accepted')
except ValueError:
    pass
assert not (testroot / 'must-not-create').exists()
RESULTS.append({'engine': 'Python initializer', 'case': 'junction rejected before history creation or managed-source replacement', 'passed': True})
before = metadata(init_source)
try:
    namespace['replace_managed_skill'](testroot / 'missing-template', init_source, testroot / 'must-not-replace', 'fixture')
    raise AssertionError('Managed Git source replacement accepted')
except ValueError:
    pass
assert before == metadata(init_source) and not (testroot / 'must-not-replace').exists()
RESULTS.append({'engine': 'Python initializer', 'case': 'managed skill repository replacement refused; Git metadata preserved live', 'passed': True})

for staged in list((STAGE / '.agents').rglob('*.ps1')) + list((STAGE / 'output/00_系统治理/03_代码程序/src').rglob('*.ps1')):
    assert staged.read_bytes().startswith(b'\xef\xbb\xbf'), staged
RESULTS.append({'case': 'all staged PowerShell scripts retain UTF-8 BOM', 'passed': True})
report = {'passed': len(RESULTS), 'fixtures': str(testroot), 'cases': RESULTS}
Path(os.environ.get('BACKUP_VERIFICATION_REPORT', str(BASE / 'backup-verification.json'))).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(report, ensure_ascii=False, indent=2))
