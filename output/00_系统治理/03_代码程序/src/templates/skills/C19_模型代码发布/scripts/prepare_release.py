"""只读生成发布计划，可核对暂存对象；不提交、推送或复制文件。"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def git(repo, *args):
    p = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, timeout=15)
    if p.returncode:
        raise ValueError('Git 只读检查失败：' + args[0])
    return p.stdout


def identifier(value, name):
    if not isinstance(value, str) or not re.fullmatch(r'[a-z][a-z0-9_]*', value):
        raise ValueError(name + ' 必须是已确认的小写标识符')
    return value


def plan(data, check_staged=False):
    repo = Path(data['repo']).resolve()
    source = Path(data['source_sql']).resolve()
    if not (repo / '.git').exists():
        raise ValueError('repo 不是可用 Git 工作区')
    db = identifier(data['database'], 'database')
    domain = identifier(data['domain'], 'domain')
    layer = identifier(data['layer'].lower(), 'layer')
    table = identifier(data['table'], 'table')
    if not table.startswith(layer + '_' + domain + '_'):
        raise ValueError('表名的分层/域与输入元数据不一致，需核对规范')
    if source.name != table + '.sql' or source.parent.name != table:
        raise ValueError('仅接受 {规范表名}/{规范表名}.sql 正式加工文件')
    raw = source.read_bytes()
    if not raw.decode('utf-8-sig').strip():
        raise ValueError('SQL 为空')
    model = data['model_name'].strip()
    if not model or not re.search(r'[\u4e00-\u9fff]', model):
        raise ValueError('必须提供已确认模型中文名称')
    branch = data.get('branch') or ('codex/' + layer + '-' + table)
    remote = data.get('remote')
    base_branch = data.get('base_branch')
    if not isinstance(remote, str) or not remote or not isinstance(base_branch, str) or not base_branch:
        raise ValueError('remote/base_branch必须来自已确认的目标仓库')
    if remote.startswith('-') or base_branch.startswith('-'):
        raise ValueError('非法remote/base_branch')
    git(repo, 'check-ref-format', '--branch', base_branch)
    git(repo, 'check-ref-format', '--branch', branch)
    kind = data['change_type']
    summary = data.get('change_summary', '').strip()
    if kind not in ['add', 'modify'] or (kind == 'modify' and not summary):
        raise ValueError('change_type 为 add/modify；修改必须提供具体修改点')
    if any(c in model + summary for c in '\r\n\x00'):
        raise ValueError('标题不能含换行或空字符')
    relative = Path(db) / domain / layer / table / (table + '.sql')
    target = (repo / relative).resolve()
    if not target.is_relative_to(repo):
        raise ValueError('目标路径越过仓库边界')
    result = {'status': 'planned', 'repo': str(repo), 'source_sql': str(source),
              'source_sha256': hashlib.sha256(raw).hexdigest(), 'target_path': str(target),
              'target_relative': relative.as_posix(), 'branch': branch,
              'commit_message': data.get('commit_message') or ('feat(sql): 新增' + model if kind == 'add' else 'fix(sql): ' + model + '，' + summary),
              'remote': remote, 'base_branch': base_branch,
              'target_exists': target.exists(), 'source_utf8_valid': True}
    result['mr_title'] = result['commit_message']
    if check_staged:
        files = git(repo, 'diff', '--cached', '--name-only', '-z').decode('utf-8').split('\x00')
        if [f for f in files if f] != [relative.as_posix()]:
            raise ValueError('暂存集合不是唯一授权加工文件')
        git(repo, 'diff', '--cached', '--check')
        staged = git(repo, 'show', ':' + relative.as_posix())
        if staged.replace(b'\r\n', b'\n') != raw.replace(b'\r\n', b'\n'):
            raise ValueError('暂存对象与正式源不一致（仅允许CRLF/LF转换）')
        result['staged_verified'] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--check-staged', action='store_true')
    args = parser.parse_args()
    try:
        result = plan(json.loads(Path(args.input).read_text(encoding='utf-8-sig')), args.check_staged)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as exc:
        print(json.dumps({'status': 'blocked', 'error': str(exc)}, ensure_ascii=False))
        return 2
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
