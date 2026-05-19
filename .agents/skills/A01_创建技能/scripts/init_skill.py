#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from generate_openai_yaml import write_openai_yaml


PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / ".agents" / "skills"
REQUIRED_DIRS = ["agents", "references", "scripts", "assets"]
SKILL_NAME_PATTERN = re.compile(r"^[A-Z]\d{2}_[^\\/:*?\"<>|]+$")
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")

SKILL_TEMPLATE = """---
name: {skill_name}
description: {description}
---

# {skill_name}

## 这项技能解决什么问题

- [TODO: 用 1-3 句写清楚这项 skill 解决什么问题]

## 先读哪些本地知识

- [TODO: 先读哪些本地 `knowledge/` 或已有规则]
- 需要展开细节时，再读 `references/扩展说明.md`

## 固定动作

1. [TODO: 写第一个固定动作]
2. [TODO: 写第二个固定动作]
3. [TODO: 写第三个固定动作]

## 什么时候再读本 skill 的 references

- 当默认动作已经不够覆盖复杂情况时，再读 `references/扩展说明.md`

## 边界

- [TODO: 写不该做的事]
- 不要把稳定业务真相直接塞进 `SKILL.md`
"""

REFERENCE_TEMPLATE = """# 扩展说明

把已经超出薄 `SKILL.md` 的内容收口到这里，例如：

- 参数表
- 长命令
- 兼容性说明
- 异常恢复手册
- 复杂样例

如果这些内容已经是工作区长期稳定真相，应考虑下沉到 `knowledge/`，而不是长期堆在这里。
"""


def skill_title_from_name(skill_name: str) -> str:
    match = re.match(r"^[A-Z]\d{2}_(.+)$", skill_name)
    return match.group(1) if match else skill_name


def normalize_description(skill_name: str, description: str | None) -> str:
    if description:
        return description.strip()
    skill_title = skill_title_from_name(skill_name)
    return f"当用户需要{skill_title}相关能力时使用；生成本地薄 Skill 骨架、references 路由和校验入口。"


def validate_description(description: str) -> None:
    if not description.strip():
        raise ValueError("description 不能为空。")
    if len(description) > 100:
        raise ValueError(f"description 不得超过 100 字，当前为 {len(description)} 字。")


def validate_skill_name(skill_name: str) -> None:
    if not skill_name.strip():
        raise ValueError("skill 名不能为空。")
    if any(sep in skill_name for sep in ("/", "\\")):
        raise ValueError("skill 名不能包含路径分隔符。")
    if not SKILL_NAME_PATTERN.match(skill_name):
        raise ValueError("skill 名必须符合 {域代码}{编号}_{技能名}，例如 F01_原子拆解技能。版本号只写入 agents/openai.yaml display_name。")
    if re.search(r"_v\d+\.\d+\.\d+$", skill_name):
        raise ValueError("skill live 文件夹名不得带版本号；版本号只写入 agents/openai.yaml display_name。")
    if not re.search(r"[\u4e00-\u9fff]", skill_name):
        raise ValueError("skill 名中的技能名应以中文为主，可包含必要英文术语。")


def validate_version(version: str) -> None:
    if not VERSION_PATTERN.match(version):
        raise ValueError("版本号必须为 MAJOR.MINOR.PATCH，例如 1.0.0。")


def ensure_absent(path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"目标 skill 已存在：{path}")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def create_skill_skeleton(skill_root: Path, skill_name: str, version: str, description: str, interfaces: list[str]) -> None:
    for dirname in REQUIRED_DIRS:
        (skill_root / dirname).mkdir(parents=True, exist_ok=True)

    write_text(
        skill_root / "SKILL.md",
        SKILL_TEMPLATE.format(skill_name=skill_name, description=description),
    )
    write_text(skill_root / "references" / "扩展说明.md", REFERENCE_TEMPLATE)
    write_text(skill_root / "scripts" / ".gitkeep", "")
    write_text(skill_root / "assets" / ".gitkeep", "")
    write_openai_yaml(skill_root, skill_name, interfaces, version=version)


def main() -> int:
    parser = argparse.ArgumentParser(description="在当前项目里初始化一个标准命名的中文薄 Skill 骨架。")
    parser.add_argument("skill_name", help="稳定 Skill 目录名，同时也是 frontmatter name，例如 F01_原子拆解技能")
    parser.add_argument("--version", default="1.0.0", help="写入 agents/openai.yaml display_name 的版本号，默认 1.0.0")
    parser.add_argument(
        "--path",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="skill 根目录，默认写入当前项目 /.agents/skills",
    )
    parser.add_argument("--description", help="覆盖默认 description")
    parser.add_argument(
        "--interface",
        action="append",
        default=[],
        help="传给 generate_openai_yaml.py 的 key=value 覆盖项，可重复传入",
    )
    args = parser.parse_args()

    try:
        validate_skill_name(args.skill_name)
        validate_version(args.version)
        description = normalize_description(args.skill_name, args.description)
        validate_description(description)
        target_root = Path(args.path).resolve()
        skill_root = target_root / args.skill_name
        ensure_absent(skill_root)
        create_skill_skeleton(
            skill_root,
            args.skill_name,
            args.version,
            description,
            args.interface,
        )
    except (ValueError, FileExistsError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"created={skill_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
