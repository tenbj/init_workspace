#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


# Resolve from the script location so project moves do not break the path.
PROJECT_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_REPO_RELATIVE = Path("input") / "data-assets"
CLONE_URL_ENV = "DATA_ASSETS_REPO_URL"
DEFAULT_CLONE_URL = "git@git.rabbitgoo.com:dw-dev/data-assets.git"


class CommandError(RuntimeError):
    pass


def relpath(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def run_command(
    args: list[str],
    cwd: Path,
    *,
    capture_output: bool = True,
) -> subprocess.CompletedProcess[str]:
    printable = " ".join(args)
    print(f"$ ({relpath(cwd)}) {printable}")
    result = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=capture_output,
    )
    if capture_output:
        if result.stdout:
            print(result.stdout.rstrip())
        if result.stderr:
            print(result.stderr.rstrip(), file=sys.stderr)
    if result.returncode != 0:
        raise CommandError(f"Command failed with exit code {result.returncode}: {printable}")
    return result


def git(repo_path: Path, *git_args: str, capture_output: bool = True) -> subprocess.CompletedProcess[str]:
    return run_command(["git", *git_args], cwd=repo_path, capture_output=capture_output)


def resolve_project_path(repo_relative: str) -> Path:
    repo_path = (PROJECT_ROOT / repo_relative).resolve()
    try:
        repo_path.relative_to(PROJECT_ROOT)
    except ValueError as exc:
        raise FileNotFoundError(f"Target escapes project root: {repo_relative}") from exc
    return repo_path


def resolve_existing_repo_path(repo_relative: str) -> Path:
    repo_path = resolve_project_path(repo_relative)
    git_dir = repo_path / ".git"
    if not repo_path.exists():
        raise FileNotFoundError(f"Repository path does not exist: {relpath(repo_path)}")
    if not git_dir.exists():
        raise FileNotFoundError(f"Git metadata not found: {relpath(git_dir)}")
    return repo_path


def is_empty_directory(path: Path) -> bool:
    return path.is_dir() and not any(path.iterdir())


def ensure_git_available() -> None:
    if shutil.which("git") is None:
        raise FileNotFoundError("`git` was not found in PATH.")


def ensure_pull_only(repo_path: Path, remote: str) -> None:
    git(repo_path, "remote", "set-url", "--push", remote, "DISABLED")


def clone_repo(repo_path: Path, remote: str, branch: str, clone_url: str) -> None:
    if not clone_url:
        raise FileNotFoundError(
            f"Missing clone URL. Set {CLONE_URL_ENV} or pass --clone-url when the repository is absent."
        )
    repo_path.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            "git",
            "clone",
            "--origin",
            remote,
            "--branch",
            branch,
            clone_url,
            relpath(repo_path),
        ],
        cwd=PROJECT_ROOT,
    )
    ensure_pull_only(repo_path, remote)


def ensure_repo_available(repo_relative: str, remote: str, branch: str, clone_url: str) -> Path:
    repo_path = resolve_project_path(repo_relative)
    git_dir = repo_path / ".git"

    if git_dir.exists():
        return repo_path

    if not repo_path.exists() or is_empty_directory(repo_path):
        print(f"Repository missing; cloning {clone_url} into {relpath(repo_path)}")
        clone_repo(repo_path, remote, branch, clone_url)
        return repo_path

    raise FileNotFoundError(
        f"Target exists but is not an empty Git repository: {relpath(repo_path)}"
    )


def print_summary(repo_path: Path) -> None:
    git(repo_path, "remote", "-v")
    git(repo_path, "status", "--short", "--branch")
    git(repo_path, "log", "-1", "--oneline")


def sync_repo(repo_path: Path, remote: str, branch: str) -> None:
    # Mirror the remote branch exactly and discard all local drift.
    ensure_pull_only(repo_path, remote)
    git(repo_path, "fetch", remote, branch)
    git(repo_path, "reset", "--hard")
    git(repo_path, "clean", "-fdx")
    git(repo_path, "checkout", "-B", branch, f"{remote}/{branch}")
    git(repo_path, "reset", "--hard", f"{remote}/{branch}")
    git(repo_path, "clean", "-fdx")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Force-sync ./input/data-assets to origin/master using project-relative paths.",
    )
    parser.add_argument(
        "--repo-relative",
        default=str(DEFAULT_REPO_RELATIVE),
        help="Repository path relative to the project root.",
    )
    parser.add_argument(
        "--remote",
        default="origin",
        help="Remote name to fetch from.",
    )
    parser.add_argument(
        "--branch",
        default="master",
        help="Remote branch to mirror locally.",
    )
    parser.add_argument(
        "--clone-url",
        default=os.getenv(CLONE_URL_ENV, DEFAULT_CLONE_URL),
        help=(
            "Remote URL used when the target repository is missing. "
            f"Defaults to ${CLONE_URL_ENV} or {DEFAULT_CLONE_URL}."
        ),
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Print current repo summary without fetching or resetting.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        ensure_git_available()
        if args.status_only:
            repo_path = resolve_existing_repo_path(args.repo_relative)
        else:
            repo_path = ensure_repo_available(
                args.repo_relative,
                args.remote,
                args.branch,
                args.clone_url,
            )
        print(f"Project root: {relpath(PROJECT_ROOT)}")
        print(f"Target repo:  {relpath(repo_path)}")
        if args.status_only:
            ensure_pull_only(repo_path, args.remote)
            print_summary(repo_path)
            return 0

        sync_repo(repo_path, args.remote, args.branch)
        print_summary(repo_path)
        return 0
    except (FileNotFoundError, CommandError) as exc:
        print(str(exc), file=sys.stderr)
        print(
            "If the fetch step is blocked by sandboxed SSH or network restrictions, rerun the same relative command with approval.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
