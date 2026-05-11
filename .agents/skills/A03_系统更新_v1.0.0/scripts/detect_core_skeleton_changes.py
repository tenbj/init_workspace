#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


CORE_PATHS = [
    "AGENTS.md",
    "CLAUDE.md",
    ".agents/rules",
    ".agents/skills",
    ".claude/commands",
    ".system/standards",
]


def find_workspace_root(start: Path) -> Path:
    current = start.resolve()
    for candidate in [current, *current.parents]:
        if (candidate / ".system" / "standards" / "workspace-spec.json").exists():
            return candidate
    raise SystemExit("workspace root not found")


def load_spec(root: Path) -> dict:
    spec_path = root / ".system" / "standards" / "workspace-spec.json"
    return json.loads(spec_path.read_text(encoding="utf-8"))


def list_dirs(path: Path) -> list[str]:
    if not path.exists():
        return []
    return sorted(item.name for item in path.iterdir() if item.is_dir())


def list_files(path: Path, suffix: str | None = None) -> list[str]:
    if not path.exists():
        return []
    files = [item.name for item in path.iterdir() if item.is_file()]
    if suffix:
        files = [name for name in files if name.endswith(suffix)]
    return sorted(files)


def run_git_status(root: Path) -> list[str]:
    try:
        completed = subprocess.run(
            ["git", "status", "--short", "--", *CORE_PATHS],
            cwd=root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except FileNotFoundError:
        return ["git unavailable"]
    if completed.returncode != 0:
        return [completed.stderr.strip() or "git status failed"]
    return [line for line in completed.stdout.splitlines() if line.strip()]


def build_report(root: Path) -> dict:
    spec = load_spec(root)
    registered = sorted(spec.get("skillsManagement", {}).get("registeredSkills", []))
    skill_dirs = list_dirs(root / ".agents" / "skills")
    command_files = list_files(root / ".claude" / "commands", ".md")
    expected_commands = sorted(f"{name}.md" for name in registered)
    overwrite_rules = sorted(spec.get("overwriteLayer", {}).get("rules", []))
    rule_files = list_files(root / ".agents" / "rules", ".md")
    standards = sorted(spec.get("overwriteLayer", {}).get("standards", []))
    standard_files = list_files(root / ".system" / "standards")
    bom_files = sorted(spec.get("bomCheck", {}).get("files", []))
    existing_bom_files = sorted(
        str(path.relative_to(root)).replace("\\", "/")
        for path in (root / ".agents" / "skills").rglob("*.ps1")
    )

    return {
        "workspace": str(root),
        "git_status": run_git_status(root),
        "skills": {
            "unregistered_dirs": sorted(set(skill_dirs) - set(registered)),
            "registered_missing_dirs": sorted(set(registered) - set(skill_dirs)),
        },
        "claude_commands": {
            "missing": sorted(set(expected_commands) - set(command_files)),
            "extra": sorted(set(command_files) - set(expected_commands)),
        },
        "rules": {
            "listed_missing": sorted(set(overwrite_rules) - set(rule_files)),
            "unlisted_files": sorted(set(rule_files) - set(overwrite_rules)),
        },
        "standards": {
            "listed_missing": sorted(set(standards) - set(standard_files)),
            "unlisted_files": sorted(set(standard_files) - set(standards)),
        },
        "bom_check": {
            "listed_missing": sorted(path for path in bom_files if not (root / path).exists()),
            "ps1_not_listed": sorted(set(existing_bom_files) - set(bom_files)),
        },
    }


def print_text(report: dict) -> None:
    print(f"workspace: {report['workspace']}")
    print("\n[git_status]")
    for line in report["git_status"] or ["clean"]:
        print(f"- {line}")
    for section in ["skills", "claude_commands", "rules", "standards", "bom_check"]:
        print(f"\n[{section}]")
        for key, values in report[section].items():
            print(f"{key}:")
            if values:
                for value in values:
                    print(f"- {value}")
            else:
                print("- none")


def main() -> int:
    parser = argparse.ArgumentParser(description="Detect core skeleton differences that may require .system updates.")
    parser.add_argument("--format", choices=["text", "json"], default="text")
    parser.add_argument("--root", default=".", help="workspace root or any path inside it")
    args = parser.parse_args()

    root = find_workspace_root(Path(args.root))
    report = build_report(root)
    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
