"""Read local Git facts for a target path without changing refs or contacting remotes."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


def inspect_repo(target: str | Path) -> dict:
    requested = Path(target).expanduser().resolve()
    probe = requested
    while not probe.exists():
        if probe.parent == probe:
            raise ValueError("No existing ancestor for target")
        probe = probe.parent
    if probe.is_file():
        probe = probe.parent
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_INDEX_FILE"):
        env.pop(key, None)

    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(probe), *args], capture_output=True,
            text=True, encoding="utf-8", errors="replace", env=env,
        )

    def required(*args: str) -> str:
        result = git(*args)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Git command failed")
        return result.stdout.strip()

    top = git("rev-parse", "--show-toplevel")
    facts = {"target": str(requested), "probe": str(probe)}
    if top.returncode:
        if "not a git repository" in top.stderr.lower():
            return {**facts, "is_repository": False, "reason": "no_git_repository"}
        raise RuntimeError(top.stderr.strip() or "Cannot inspect Git work tree")
    branch = git("symbolic-ref", "--quiet", "--short", "HEAD")
    if branch.returncode not in (0, 1):
        raise RuntimeError(branch.stderr.strip() or "Cannot inspect HEAD")
    head = git("rev-parse", "--verify", "HEAD")
    upstream = git("rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}")
    remotes = required("remote").splitlines()
    defaults = {}
    for remote in remotes:
        result = git("symbolic-ref", "--quiet", "--short", f"refs/remotes/{remote}/HEAD")
        if result.returncode == 0:
            defaults[remote] = result.stdout.strip()
    return {
        **facts, "is_repository": True,
        "repository": str(Path(top.stdout.strip()).resolve()),
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "head_commit": head.stdout.strip() if head.returncode == 0 else None,
        "head_state": "unborn" if head.returncode else ("branch" if branch.returncode == 0 else "detached"),
        "dirty": bool(required("status", "--porcelain=v1", "-z", "--untracked-files=normal")),
        "upstream": upstream.stdout.strip() if upstream.returncode == 0 else None,
        "remote_names": remotes,
        "local_default_branch_candidates": defaults,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=".", help="Target file or directory; may not exist yet")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        result = inspect_repo(args.target)
    except (OSError, RuntimeError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
