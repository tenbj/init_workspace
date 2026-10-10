#!/usr/bin/env python3
"""Install/check repository-wide B11 hooks without changing Git configuration."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import subprocess
import sys

HOOKS = ("pre-commit", "prepare-commit-msg", "pre-merge-commit", "pre-push")
MARKER = "# B11 managed branch guard v1\n"
TEMPLATE = Path(__file__).resolve().parent.parent / "hooks" / "branch-guard"


def git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True,
        text=True, encoding="utf-8", errors="replace", check=False,
    )


def hook_directory(repo: Path) -> Path:
    result = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if result.returncode:
        raise ValueError("目标不是可用的 Git 仓库：" + result.stderr.strip())
    worktrees = git(repo, "worktree", "list", "--porcelain", "-z")
    if worktrees.returncode:
        raise ValueError("无法核对共享 Git 目录的 worktree 配置。")
    paths = {repo, *(Path(item.removeprefix("worktree "))
                     for item in worktrees.stdout.split("\0") if item.startswith("worktree "))}
    for path in paths:
        config = git(path, "config", "--get-all", "core.hooksPath")
        if config.returncode == 0:
            raise ValueError(f"{path} 检测到自定义 core.hooksPath；拒绝覆盖配置或在无效位置安装。")
        if config.returncode != 1:
            raise ValueError(f"无法检查 {path} 的 core.hooksPath 配置。")
    hooks = Path(result.stdout.strip()) / "hooks"
    if hooks.is_symlink() or (hooks.exists() and not hooks.is_dir()):
        raise ValueError("hooks 路径不是普通目录，拒绝安装或校验。")
    return hooks


def expected_hooks() -> dict[str, bytes]:
    source = TEMPLATE.read_text(encoding="utf-8")
    if not source.startswith("#!/bin/sh\n"):
        raise ValueError("branch-guard 模板必须以 POSIX shell shebang 开头。")
    body = source.split("\n", 1)[1]
    return {
        name: ("#!/bin/sh\n" + MARKER + f"B11_GUARD_HOOK='{name}'\n" + body).encode("utf-8")
        for name in HOOKS
    }


def verify_existing(path: Path, expected: bytes) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"{path.name} 不是普通文件，拒绝覆盖。")
    if path.read_bytes() != expected:
        raise ValueError(f"{path.name} 已存在且内容不匹配；拒绝覆盖已有或被修改的钩子。")
    if os.name != "nt" and not os.access(path, os.X_OK):
        raise ValueError(f"{path.name} 不可执行，保护无效。")


def run(repo: Path, install: bool) -> Path:
    directory = hook_directory(repo)
    expected = expected_hooks()
    # Preflight every existing hook before creating any missing hook.
    for name, content in expected.items():
        target = directory / name
        if target.exists() or target.is_symlink():
            verify_existing(target, content)
        elif not install:
            raise ValueError(f"缺少 {name} 钩子，分支保护未完整安装。")
    if install:
        directory.mkdir(parents=True, exist_ok=True)
        for name, content in expected.items():
            target = directory / name
            if not target.exists():
                with target.open("xb") as stream:
                    stream.write(content)
                target.chmod(0o755)
    for name, content in expected.items():
        verify_existing(directory / name, content)
    return directory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--install", action="store_true")
    mode.add_argument("--check", action="store_true", help="只读校验（默认）")
    args = parser.parse_args()
    try:
        directory = run(args.repo, args.install)
    except (OSError, ValueError) as exc:
        print(f"B11 分支保护失败：{exc}", file=sys.stderr)
        return 1
    print(f"B11 分支保护完整：4 个钩子；覆盖共享该 Git 目录的所有 worktree：{directory}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
