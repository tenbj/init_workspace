#!/usr/bin/env python3
"""Validate the static and rendered contract of a single-canvas ERD HTML."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlencode


PASS_ATTRS = (
    "data-geometry-status",
    "data-entity-uniqueness-status",
    "data-relation-integrity-status",
    "data-crowfoot-status",
    "data-label-anchor-status",
    "data-label-clearance-status",
    "data-label-overlap-status",
    "data-fields-visible-status",
    "data-fields-hidden-status",
)
ZERO_ATTRS = (
    "data-crossings",
    "data-label-overlaps",
    "data-path-entity-intrusions",
)


def find_browser(explicit: str | None) -> str | None:
    if explicit:
        return explicit
    candidates = (
        shutil.which("msedge"),
        shutil.which("chrome"),
        shutil.which("chromium"),
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    )
    return next((item for item in candidates if item and Path(item).exists()), None)


def static_errors(source: str) -> list[str]:
    checks = {
        "存在外部资源 URL": r"""<(?:script|link|img|iframe|source)\b[^>]*(?:src|href)\s*=\s*["'](?:https?:)?//""",
        "存在网络 API": r"\b(?:fetch|XMLHttpRequest|WebSocket|EventSource)\s*\(",
        "存在持久化字段状态": r"\b(?:localStorage|sessionStorage|indexedDB)\b",
        "存在箭头 marker": r"""(?:marker-(?:start|end)\s*=\s*["'][^"']*arrow|<marker\b[^>]*id\s*=\s*["'][^"']*arrow)""",
    }
    return [message for message, pattern in checks.items() if re.search(pattern, source, re.I)]


def html_attrs(rendered: str) -> dict[str, str]:
    match = re.search(r"<html\b([^>]*)>", rendered, re.I | re.S)
    if not match:
        return {}
    return {
        key.lower(): value
        for key, _, value in re.findall(
            r"""([\w:-]+)\s*=\s*(["'])(.*?)\2""", match.group(1), re.S
        )
    }


def rendered_errors(attrs: dict[str, str], entities: int | None, relations: int | None) -> list[str]:
    errors = [f"{name} 未通过（实际：{attrs.get(name, '缺失')}）" for name in PASS_ATTRS if attrs.get(name) != "pass"]
    errors.extend(f"{name} 应为 0（实际：{attrs.get(name, '缺失')}）" for name in ZERO_ATTRS if attrs.get(name) != "0")
    for name, expected in (("data-tables", entities), ("data-relations", relations)):
        if expected is not None and attrs.get(name) != str(expected):
            errors.append(f"{name} 应为 {expected}（实际：{attrs.get(name, '缺失')}）")
    return errors


def dump_dom(browser: str, html_path: Path) -> str:
    query = urlencode({"qa": "all"})
    url = f"{html_path.resolve().as_uri()}?{query}"
    with tempfile.TemporaryDirectory(prefix="erd-qa-") as profile:
        command = [
            browser,
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={profile}",
            "--virtual-time-budget=10000",
            "--dump-dom",
            url,
        ]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or f"浏览器退出码 {completed.returncode}")
    return completed.stdout


def main() -> int:
    parser = argparse.ArgumentParser(description="校验单画布 ER 图 HTML 的离线与双态几何契约")
    parser.add_argument("html", type=Path)
    parser.add_argument("--entities", type=int)
    parser.add_argument("--relations", type=int)
    parser.add_argument("--browser", help="Edge/Chrome/Chromium 可执行文件路径")
    args = parser.parse_args()

    if not args.html.is_file():
        print(f"[FAIL] 文件不存在：{args.html}")
        return 2
    source = args.html.read_text(encoding="utf-8")
    errors = static_errors(source)
    browser = find_browser(args.browser)
    if not browser:
        errors.append("未找到 Edge/Chrome/Chromium，无法完成真实浏览器双态验收")
    else:
        try:
            errors.extend(rendered_errors(html_attrs(dump_dom(browser, args.html)), args.entities, args.relations))
        except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
            errors.append(f"浏览器验收失败：{exc}")

    if errors:
        print("[FAIL] ERD 验收未通过")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("[PASS] 离线约束、实体/关系计数及展开/隐藏双态几何契约全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
