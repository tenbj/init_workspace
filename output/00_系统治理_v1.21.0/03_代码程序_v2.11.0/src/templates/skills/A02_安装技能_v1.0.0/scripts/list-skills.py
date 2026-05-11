#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
from pathlib import Path

from github_utils import github_api_contents_url, github_request


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_REPO = "openai/skills"
DEFAULT_PATH = "skills/.curated"
DEFAULT_REF = "main"


class ListError(Exception):
    pass


def installed_skills() -> set[str]:
    skills_root = PROJECT_ROOT / ".agents" / "skills"
    if not skills_root.is_dir():
        return set()
    aliases: set[str] = set()
    for path in skills_root.iterdir():
        if not path.is_dir():
            continue
        aliases.add(path.name)
        migration_note = path / "references" / "迁移说明.md"
        if not migration_note.is_file():
            continue
        text = migration_note.read_text(encoding="utf-8")
        path_match = re.search(r"^- 来源路径：`?(.+?)`?\s*$", text, re.MULTILINE)
        if path_match:
            aliases.add(Path(path_match.group(1)).name)
        name_match = re.search(r"^- 原始名称：(.+?)\s*$", text, re.MULTILINE)
        if name_match:
            aliases.add(name_match.group(1).strip())
    return aliases


def list_remote_skills(repo: str, path: str, ref: str) -> list[str]:
    url = github_api_contents_url(repo, path, ref)
    try:
        payload = github_request(url, "zqz-orchestrator-skill-list")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise ListError(f"找不到技能列表路径：https://github.com/{repo}/tree/{ref}/{path}") from exc
        raise ListError(f"拉取技能列表失败：HTTP {exc.code}") from exc

    data = json.loads(payload.decode("utf-8"))
    if not isinstance(data, list):
        raise ListError("技能列表返回格式异常。")
    return sorted(item["name"] for item in data if item.get("type") == "dir")


def main() -> int:
    parser = argparse.ArgumentParser(description="列出远端可安装 skill，并标注当前项目是否已安装。")
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--path", default=DEFAULT_PATH)
    parser.add_argument("--ref", default=DEFAULT_REF)
    parser.add_argument("--format", choices=["text", "json"], default="text")
    args = parser.parse_args()

    try:
        remote_skills = list_remote_skills(args.repo, args.path, args.ref)
    except ListError as exc:
        print(f"error={exc}", file=sys.stderr)
        return 1

    installed = installed_skills()
    if args.format == "json":
        payload = [{"name": name, "installed": name in installed} for name in remote_skills]
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    for index, name in enumerate(remote_skills, start=1):
        suffix = " (当前项目已安装)" if name in installed else ""
        print(f"{index}. {name}{suffix}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
