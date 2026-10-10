"""Render a nine-chapter model manual as self-contained HTML; derived from F02."""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.parse import unquote, urlsplit


def image_data(source: str, root: Path) -> str:
    parts = urlsplit(source)
    if parts.scheme or parts.netloc or parts.query or parts.fragment:
        raise ValueError(f"图片必须为本地相对路径：{source}")
    candidate = (root / unquote(parts.path)).resolve()
    if not candidate.is_relative_to(root.resolve()):
        raise ValueError(f"图片不能跨出 Markdown 目录：{source}")
    data = candidate.read_bytes()
    mime = None
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        mime = 'image/png'
    elif data.startswith(b'\xff\xd8\xff'):
        mime = 'image/jpeg'
    elif data.startswith((b'GIF87a', b'GIF89a')):
        mime = 'image/gif'
    elif data.startswith(b'RIFF') and data[8:12] == b'WEBP':
        mime = 'image/webp'
    if mime is None:
        raise ValueError(f"不支持的图片格式：{source}")
    return f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"


def text_content(token) -> str:
    return ''.join(child.content for child in (token.children or [])
                   if child.type in ('text', 'code_inline', 'image')).strip()


def render(source: Path, status: str = 'draft') -> tuple[str, dict]:
    try:
        from markdown_it import MarkdownIt
    except ImportError as exc:
        raise ValueError('缺少 markdown-it-py；请使用已安装该依赖的 Python 环境。') from exc
    raw = source.read_bytes()
    text = raw.decode('utf-8-sig')
    pending = re.findall(r'\{\{[^}]*\}\}|\bTODO\b|\bTBD\b|待确认|待补充|待核实', text, re.I)
    placeholders = re.findall(r'\{\{[^}]*\}\}|\bTODO\b|\bTBD\b', text, re.I)
    if status != 'draft' and placeholders:
        raise ValueError('非草稿仍含模板占位符，请填写实际内容或使用 --status draft。')
    md = MarkdownIt('commonmark', {'html': False}).enable('table')
    tokens = md.parse(text)
    titles = []
    toc = []
    image_count = 0
    for i, token in enumerate(tokens):
        if token.type == 'heading_open':
            title = text_content(tokens[i + 1])
            if token.tag == 'h1':
                titles.append(title)
            elif token.tag in ('h2', 'h3'):
                anchor = f'section-{len(toc) + 1}'
                token.attrSet('id', anchor)
                toc.append({'id': anchor, 'level': int(token.tag[1]), 'title': title})

        def embed(children):
            nonlocal image_count
            for child in children or []:
                if child.type == 'image':
                    child.attrSet('src', image_data(child.attrGet('src') or '', source.parent))
                    image_count += 1
                elif child.children:
                    embed(child.children)
        embed(token.children)
    if len(titles) != 1 or not titles[0]:
        raise ValueError('文档需要且只能有一个非空 H1 标题。')
    if not toc or not any(item['level'] == 2 for item in toc):
        raise ValueError('文档至少需要一个 H2 章节。')

    expected = ['模型概述', '数据范围与粒度', '字段与业务口径', '数据形成规则',
                '时间与更新机制', '查询与关联规范', '典型使用示例',
                '数据质量与使用限制', '依据、版本与待确认事项']
    chapters = [entry['title'] for entry in toc if entry['level'] == 2]
    if chapters != [f'{i}. {title}' for i, title in enumerate(expected, 1)]:
        raise ValueError('需要按模板保留九章 H2 标题与顺序。')

    body = md.renderer.render(tokens, md.options, {})
    body = body.replace('<table>', '<div class="table-scroll" tabindex="0" role="region" aria-label="可横向滚动的表格"><table>')
    body = body.replace('</table>', '</table></div>')
    anchors = {item['id'] for item in toc}
    for target in re.findall(r'href="#([^"<>]+)"', body):
        if unquote(html.unescape(target)) not in anchors:
            raise ValueError(f'文内章节链接不存在：#{target}')
    navigation = '\n'.join(
        f'<a class="level-{item["level"]}" href="#{item["id"]}">{html.escape(item["title"])}</a>'
        for item in toc)
    template = (Path(__file__).resolve().parents[1] / 'assets' / 'manual.html').read_text(encoding='utf-8')
    # Single substitution pass: document text cannot become template instructions.
    values = {'TITLE': html.escape(titles[0]), 'TOC': navigation, 'BODY': body,
              'STATUS': {'draft': '草稿', 'limited': '限定范围可用', 'final': '使用说明'}[status],
              'STATUS_CLASS': status}
    result = re.sub(r'@@(TITLE|TOC|BODY|STATUS|STATUS_CLASS)@@', lambda m: values[m[1]], template)
    manifest = {'status': status, 'title': titles[0],
                'source_sha256': hashlib.sha256(raw).hexdigest(),
                'heading_count': len(toc), 'image_count': image_count,
                'pending_marker_count': len(pending), 'placeholder_count': len(placeholders),
                'chapter_count': len(chapters), 'toc': toc,
                'checks': {'nine_chapters': True, 'single_title': True, 'internal_links': True,
                           'local_images_embedded': True, 'raw_html_disabled': True}}
    return result, manifest


def atomic_write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.manual-', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(value)
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='UTF-8 Markdown')
    parser.add_argument('--output', type=Path, required=True, help='HTML destination')
    parser.add_argument('--check', type=Path, help='Optional generation manifest JSON')
    parser.add_argument('--status', choices=['draft', 'limited', 'final'], default='draft')
    parser.add_argument('--force', action='store_true', help='Overwrite specified outputs after backup')
    args = parser.parse_args()
    try:
        source, destination = args.input.resolve(), args.output.resolve()
        check = args.check.resolve() if args.check else None
        if source.suffix.lower() != '.md' or destination.suffix.lower() != '.html':
            raise ValueError('输入必须为 .md，输出必须为 .html。')
        if check and check.suffix.lower() != '.json':
            raise ValueError('--check 必须为 .json。')
        paths = [source, destination] + ([check] if check else [])
        if len(set(paths)) != len(paths):
            raise ValueError('输入、HTML 和校验文件必须为不同路径。')
        for path in paths[1:]:
            if path.exists() and not args.force:
                raise ValueError(f'输出已存在，请先备份再使用 --force：{path}')
        result, manifest = render(source, args.status)
        atomic_write(destination, result)
        if check:
            atomic_write(check, json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        print(f'html={destination}')
        print(f'status={args.status} headings={manifest["heading_count"]} images={manifest["image_count"]}')
        return 0
    except (OSError, ValueError, UnicodeError) as exc:
        print(f'error={exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
