"""Docker交付证据校验。只读文件；不运行Compose、不生成成功证据。"""
from __future__ import annotations
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

STAGES = ('compose_config', 'build', 'startup', 'api', 'mcp', 'auth', 'diagrams',
          'recreate', 'upgrade', 'rollback', 'backup_restore', 'failure_recovery', 'secrets', 'cleanup')
SKIP_DIRS = {'.git', '__pycache__', '.pytest_cache', 'node_modules', '.venv'}


def draft_docker():
    return {'required': True, 'mcp_mode': 'embedded', 'stateful': True,
            'compose_files': ['compose.yaml'], 'dockerfiles': ['Dockerfile'],
            'ignore_files': ['.dockerignore'], 'guide': 'docs/Docker部署.md',
            'inputs': [], 'services': [], 'evidence': 'verification/docker-report.json'}


def inside(root, value):
    if not isinstance(value, str) or not value or '\\' in value:
        raise ValueError('路径必须为非空项目相对路径，使用/')
    path = Path(value)
    if path.is_absolute() or path.drive or '..' in path.parts:
        raise ValueError('路径不能越界或使用绝对路径')
    root = Path(root).resolve()
    target = root / path
    for parent in [target, *target.parents]:
        if parent == root:
            break
        if parent.is_symlink() or (hasattr(parent, 'is_junction') and parent.is_junction()):
            raise ValueError('来源路径不允许链接')
    if not target.resolve().is_relative_to(root):
        raise ValueError('路径越出项目')
    return target


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def snapshot(root, inputs):
    """显式输入目录递归指纹；不要声明runtime、私有配置或证据输出目录。"""
    if not isinstance(inputs, list) or not inputs:
        raise ValueError('Docker inputs必须包含实际源码、依赖、部署文件和发布资源')
    files = {}
    for value in inputs:
        path = inside(root, value)
        if not path.exists():
            raise ValueError('输入不存在：' + value)
        candidates = [path] if path.is_file() else sorted(path.rglob('*'))
        for item in candidates:
            rel = item.relative_to(Path(root).resolve()).as_posix()
            if set(Path(rel).parts) & SKIP_DIRS:
                continue
            inside(root, rel)
            if item.is_file():
                private_env = item.name.startswith('.env') and not item.name.endswith(('.example', '.sample', '.template'))
                if private_env or item.suffix in {'.pem', '.key'}:
                    raise ValueError('不可将私有配置作为公开证据输入：' + rel)
                files[rel] = sha(item)
    if not files:
        raise ValueError('Docker inputs没有文件')
    return [{'path': p, 'sha256': files[p]} for p in sorted(files)]


def validate_docker(root, contract, errors):
    _validate_docker(root, contract, errors)
    config = contract.get('docker', {})
    if not isinstance(config, dict):
        return
    variants = config.get('variants', [])
    if not isinstance(variants, list):
        errors.append('Docker：variants必须为独立部署组合数组')
        return
    seen = {config['evidence']} if isinstance(config.get('evidence'), str) else set()
    for variant in variants:
        if not isinstance(variant, dict) or variant.get('required') is not True or not isinstance(variant.get('evidence'), str) or not variant['evidence'] or variant['evidence'] in seen or 'variants' in variant:
            errors.append('Docker：额外部署组合须required=true且独立证据，不允许嵌套')
            continue
        seen.add(variant['evidence'])
        combined = {**contract, 'docker': variant, 'checks': [{'name': 'docker', 'status': 'passed', 'evidence': variant['evidence']}]}
        _validate_docker(root, combined, errors)


def _validate_docker(root, contract, errors):
    try:
        config = contract.get('docker')
        if not isinstance(config, dict):
            raise ValueError('缺少docker合同；旧项目须增量补充，不能默认为已验证')
        if config.get('required') is False:
            exclusion = config.get('exclusion', {})
            if exclusion.get('basis') != 'user_instruction' or not all(
                    isinstance(exclusion.get(k), str) and exclusion[k].strip()
                    for k in ('reason', 'instruction')):
                raise ValueError('排除Docker须记录本任务用户明确指令及原因')
            return
        if config.get('required') is not True:
            raise ValueError('docker.required必须是布尔值')
        if config.get('mcp_mode') not in {'embedded', 'separate', 'stdio'}:
            raise ValueError('mcp_mode须依据实际实现选择embedded/separate/stdio')
        if not isinstance(config.get('stateful'), bool):
            raise ValueError('stateful必须明确')
        needed = set()
        for key in ('compose_files', 'dockerfiles', 'ignore_files'):
            values = config.get(key)
            if not isinstance(values, list) or not values:
                raise ValueError('缺少' + key)
            for value in values:
                if not inside(root, value).is_file():
                    raise ValueError('缺少部署文件：' + value)
                needed.add(value)
        guide = inside(root, config.get('guide'))
        if not guide.is_file() or not guide.read_text(encoding='utf-8-sig').strip():
            raise ValueError('缺少部署与恢复文档')
        needed.add(config['guide'])
        inputs = snapshot(Path(root).resolve(), config.get('inputs'))
        present = {row['path'] for row in inputs}
        for page in contract.get('diagrams', {}).values():
            needed.add(page.get('path'))
        if not needed <= present:
            raise ValueError('输入快照未覆盖部署文件、文档或双图')
        services = config.get('services')
        if not isinstance(services, list) or not services or not all(isinstance(s, str) and s for s in services):
            raise ValueError('未声明本轮验证服务')
        report = json.loads(inside(root, config.get('evidence')).read_text(encoding='utf-8-sig'))
        if report.get('passed') is not True or report.get('environment') != 'isolated':
            raise ValueError('缺少通过的隔离真实Docker验收')
        if not contract.get('delivery_id') or report.get('delivery_id') != contract['delivery_id']:
            raise ValueError('Docker证据不属于本轮delivery_id')
        if not isinstance(report.get('run_id'), str) or not report['run_id'].strip():
            raise ValueError('缺少run_id')
        start = datetime.fromisoformat(report['started_at'].replace('Z', '+00:00'))
        end = datetime.fromisoformat(report['finished_at'].replace('Z', '+00:00'))
        if not start.tzinfo or not end.tzinfo or end < start:
            raise ValueError('验收时间无效')
        if report.get('inputs') != inputs:
            raise ValueError('代码/依赖/配置/图示已变化，Docker证据过期')
        if report.get('mcp_mode') != config['mcp_mode']:
            raise ValueError('MCP部署模式与证据不一致')
        if not isinstance(report.get('compose_project'), str) or not report['compose_project'].strip():
            raise ValueError('缺少隔离Compose项目标识')
        images = report.get('images', [])
        if not isinstance(images, list) or {x.get('service') for x in images} != set(services):
            raise ValueError('运行镜像未覆盖声明服务')
        if any(not re.fullmatch(r'sha256:[0-9a-f]{64}', x.get('id', '')) for x in images):
            raise ValueError('缺少实际运行镜像ID')
        check = next((c for c in contract.get('checks', []) if c.get('name') == 'docker'), {})
        if check.get('status') != 'passed' or check.get('evidence') != config['evidence']:
            raise ValueError('checks.docker未通过或证据路径不一致')
        observations = report.get('checks', [])
        names = [row.get('name') for row in observations]
        if len(names) != len(set(names)):
            raise ValueError('Docker验收步骤重复')
        by_name = {row['name']: row for row in observations}
        for name in STAGES:
            row = by_name.get(name, {})
            if row.get('status') == 'not_applicable':
                if config['stateful'] or name not in {'recreate', 'backup_restore'} or not row.get('reason'):
                    raise ValueError('不得跳过必要验收：' + name)
                continue
            if row.get('status') != 'passed' or not row.get('observations'):
                raise ValueError('Docker验收未通过或无观测记录：' + name)
    except (ValueError, TypeError, KeyError, AttributeError, OSError) as exc:
        errors.append('Docker：' + str(exc))
