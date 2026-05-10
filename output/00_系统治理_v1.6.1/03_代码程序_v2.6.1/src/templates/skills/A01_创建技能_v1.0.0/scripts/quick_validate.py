#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


REQUIRED_HEADINGS = [
    "## 这项技能解决什么问题",
    "## 先读哪些本地知识",
    "## 固定动作",
    "## 什么时候再读本 skill 的 references",
    "## 边界",
]
FORBIDDEN_ROOT_FILES = {
    "README.md",
    "CHANGELOG.md",
    "INSTALLATION_GUIDE.md",
    "QUICK_REFERENCE.md",
}


def extract_frontmatter(text: str) -> str | None:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None
    return match.group(1)


def get_frontmatter_value(frontmatter: str, key: str) -> str | None:
    match = re.search(rf"^{re.escape(key)}:\s*(.+?)\s*$", frontmatter, re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def validate_skill(skill_root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    if not skill_root.is_dir():
        return [f"目录不存在：{skill_root}"], warnings

    skill_md = skill_root / "SKILL.md"
    agents_yaml = skill_root / "agents" / "openai.yaml"
    required_dirs = [
        skill_root / "references",
        skill_root / "scripts",
        skill_root / "assets",
    ]

    if not skill_md.exists():
        errors.append("缺少 SKILL.md")
        return errors, warnings

    text = skill_md.read_text(encoding="utf-8")
    frontmatter = extract_frontmatter(text)
    if not frontmatter:
        errors.append("SKILL.md 缺少 YAML frontmatter")
        return errors, warnings

    name = get_frontmatter_value(frontmatter, "name")
    description = get_frontmatter_value(frontmatter, "description")
    if not name:
        errors.append("frontmatter 缺少 name")
    elif not re.search(r"[\u4e00-\u9fff]", name):
        errors.append("frontmatter name 应包含中文")
    if not description:
        errors.append("frontmatter 缺少 description")

    for heading in REQUIRED_HEADINGS:
        if heading not in text:
            errors.append(f"缺少段落：{heading}")

    if "references/" not in text:
        errors.append("SKILL.md 没有给出 references 路由")

    line_count = len(text.splitlines())
    if line_count > 160:
        errors.append(f"SKILL.md 过长：{line_count} 行")
    elif line_count > 100:
        warnings.append(f"SKILL.md 偏长：{line_count} 行，建议继续变薄")

    if not agents_yaml.exists():
        errors.append("缺少 agents/openai.yaml")
    else:
        yaml_text = agents_yaml.read_text(encoding="utf-8")
        if "display_name:" not in yaml_text or "short_description:" not in yaml_text:
            errors.append("agents/openai.yaml 缺少 display_name 或 short_description")

    for directory in required_dirs:
        if not directory.is_dir():
            errors.append(f"缺少目录：{directory.name}")

    for forbidden in FORBIDDEN_ROOT_FILES:
        if (skill_root / forbidden).exists():
            errors.append(f"根目录不应保留噪音文件：{forbidden}")

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description="快速校验一个本地 skill 是否保持薄结构。")
    parser.add_argument("skill_dir", help="待校验的 skill 目录")
    args = parser.parse_args()

    errors, warnings = validate_skill(Path(args.skill_dir).resolve())
    for message in warnings:
        print(f"warning={message}")
    for message in errors:
        print(f"error={message}")
    if errors:
        return 1
    print("skill_validation=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
