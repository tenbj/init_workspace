#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


ALLOWED_INTERFACE_KEYS = {
    "display_name",
    "short_description",
    "icon_small",
    "icon_large",
    "brand_color",
    "default_prompt",
}


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def extract_frontmatter(text: str) -> str | None:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return None
    return match.group(1)


def read_frontmatter_name(skill_dir: Path) -> str | None:
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None
    frontmatter = extract_frontmatter(skill_md.read_text(encoding="utf-8"))
    if not frontmatter:
        return None
    match = re.search(r"^name:\s*(.+?)\s*$", frontmatter, re.MULTILINE)
    if not match:
        return None
    return match.group(1).strip().strip('"').strip("'")


def parse_interface_overrides(raw_overrides: list[str]) -> tuple[dict[str, str], list[str]]:
    overrides: dict[str, str] = {}
    optional_order: list[str] = []
    for item in raw_overrides:
        if "=" not in item:
            raise ValueError(f"无效的 interface 覆盖项：{item}")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key not in ALLOWED_INTERFACE_KEYS:
            allowed = ", ".join(sorted(ALLOWED_INTERFACE_KEYS))
            raise ValueError(f"未知 interface 字段：{key}。允许字段：{allowed}")
        overrides[key] = value
        if key not in ("display_name", "short_description") and key not in optional_order:
            optional_order.append(key)
    return overrides, optional_order


def build_short_description(display_name: str) -> str:
    text = f"用于{display_name}相关任务"
    if len(text) <= 64:
        return text
    return text[:64].rstrip()


def write_openai_yaml(skill_dir: Path, skill_name: str, raw_overrides: list[str]) -> Path:
    overrides, optional_order = parse_interface_overrides(raw_overrides)
    display_name = overrides.get("display_name") or skill_name
    short_description = overrides.get("short_description") or build_short_description(display_name)

    lines = [
        "interface:",
        f"  display_name: {yaml_quote(display_name)}",
        f"  short_description: {yaml_quote(short_description)}",
    ]
    for key in optional_order:
        lines.append(f"  {key}: {yaml_quote(overrides[key])}")

    agents_dir = skill_dir / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    output_path = agents_dir / "openai.yaml"
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path


def main() -> int:
    parser = argparse.ArgumentParser(description="为本地 skill 生成 agents/openai.yaml。")
    parser.add_argument("skill_dir", help="目标 skill 目录")
    parser.add_argument("--name", help="覆盖 SKILL.md frontmatter 里的 name")
    parser.add_argument(
        "--interface",
        action="append",
        default=[],
        help="以 key=value 形式传入展示层覆盖项，可重复传入",
    )
    args = parser.parse_args()

    skill_dir = Path(args.skill_dir).resolve()
    if not skill_dir.is_dir():
        print(f"目录不存在：{skill_dir}", file=sys.stderr)
        return 1

    skill_name = args.name or read_frontmatter_name(skill_dir)
    if not skill_name:
        print("无法从 SKILL.md frontmatter 读取 name，请显式传 --name。", file=sys.stderr)
        return 1

    try:
        output_path = write_openai_yaml(skill_dir, skill_name, args.interface)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"written={output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
