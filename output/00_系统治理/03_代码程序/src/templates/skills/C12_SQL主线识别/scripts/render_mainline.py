"""Render a model-reviewed SQL mainline as SQL comments and a two-column Markdown table.

No SQL execution or semantic classification occurs in this script.
"""
import argparse
import hashlib
import json
from pathlib import Path


def line(value, name):
    if not isinstance(value, str) or not value.strip() or any(ord(c) < 32 for c in value):
        raise ValueError(f'{name} must be a nonempty single line')
    return value.strip()


def cell(value):
    return value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '&#124;')


def render(source, plan_path, output_dir, stem=None):
    source, plan_path, output_dir = map(lambda p: Path(p).resolve(), (source, plan_path, output_dir))
    raw = source.read_bytes()
    text = raw.decode('utf-8-sig')
    lines = text.splitlines()
    digest = hashlib.sha256(raw).hexdigest()
    plan = json.loads(plan_path.read_text(encoding='utf-8-sig'))
    if plan.get('source_sha256') != digest:
        raise ValueError('Source SHA256 differs from the reviewed plan')
    analyses = plan.get('analyses')
    if not isinstance(analyses, list) or not analyses:
        raise ValueError('analyses must be a nonempty list')
    comments = ['-- SQL主线识别：仅添加说明；以下原SQL未执行、未改逻辑。', f'-- 来源SHA256：{digest}']
    markdown = ['# SQL主线识别', '']
    for a in analyses:
        name, flow = line(a.get('name'), 'name'), line(a.get('flow'), 'flow')
        nodes = a.get('nodes')
        if not isinstance(nodes, list) or not nodes:
            raise ValueError('nodes must be a nonempty list')
        comments.extend([f'-- 查询：{name}', f'-- 主线：{flow}', '-- 主线节点 | 代码动作'])
        markdown.extend([f'## {cell(name)}', '', f'**主线：{cell(flow)}**', '',
                         '| 主线节点 | 代码动作 |', '|---|---|'])
        for n in nodes:
            label, action = line(n.get('node'), 'node'), line(n.get('action'), 'action')
            if label not in flow:
                raise ValueError(f'Node absent from explicit flow: {label}')
            evidence = n.get('evidence')
            if not isinstance(evidence, list) or not evidence:
                raise ValueError(f'Missing code evidence: {label}')
            for e in evidence:
                start, end = e.get('start_line'), e.get('end_line')
                if type(start) is not int or type(end) is not int or not (1 <= start <= end <= len(lines)):
                    raise ValueError(f'Invalid source lines: {label}')
                excerpt = e.get('excerpt')
                if not isinstance(excerpt, str) or not excerpt.strip() or excerpt not in '\n'.join(lines[start-1:end]):
                    raise ValueError(f'Code evidence differs from source: {label}')
            comments.append(f'-- {label} | {action}')
            markdown.append(f'| {cell(label)} | {cell(action)} |')
        markdown.append('')
    comments.extend(['-- 原SQL正文开始', ''])
    markdown.extend([f'来源：{cell(source.name)}', '', f'SHA256：`{digest}`', '',
                     '说明：识别SQL的逻辑加工主线，不代表数据库物理执行计划；源SQL未执行。', ''])
    stem = source.stem if stem is None else line(stem, 'stem')
    if any(c in stem for c in '/\\:*?"<>|') or stem in ('.', '..'):
        raise ValueError('Invalid output stem')
    outputs = [output_dir / (stem+'_主线注释.sql'), output_dir / (stem+'_主线识别.md')]
    if any(p.exists() or p.resolve() in (source, plan_path) for p in outputs):
        raise FileExistsError('Output exists or would overwrite an input; choose a new destination')
    payloads = [('\n'.join(comments)+text).encode('utf-8'), '\n'.join(markdown).encode('utf-8')]
    output_dir.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        for p, data in zip(outputs, payloads):
            with p.open('xb') as f:
                created.append(p)
                f.write(data)
    except Exception:
        # Only roll back files created by this invocation; never delete preexisting files.
        for p in created:
            p.unlink()
        raise
    return {'sql': str(outputs[0]), 'markdown': str(outputs[1]), 'source_sha256': digest}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    parser.add_argument('--stem')
    args = parser.parse_args()
    print(json.dumps(render(args.source, args.plan, args.output_dir, args.stem), ensure_ascii=False))
