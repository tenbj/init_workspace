#!/usr/bin/env python3
"""Read-only, explicitly invoked PR release check; not server-side protection.

Run from the repository with the required Git objects already available. This
script never fetches, pushes, creates tags, or changes GitHub/local Git state.
"""

import argparse
import json
import re
import subprocess
import sys
from urllib.parse import quote


class CheckError(Exception):
    """A failed check or unavailable evidence."""


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        print(json.dumps({"ok": False, "error": message}, ensure_ascii=False))
        self.exit(2)


def run_command(args):
    try:
        result = subprocess.run(
            args, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=60, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise CheckError(f"Cannot execute {args[0]}: {exc}") from exc
    if result.returncode:
        # Do not print arbitrary remote output that could expose credentials.
        raise CheckError(
            f"{args[0]} {args[1]} failed (exit {result.returncode}); "
            "check authentication, repository access and local Git objects"
        )
    return result.stdout.strip()


def require(condition, message):
    if not condition:
        raise CheckError(message)


def checked_sha(value):
    require(
        isinstance(value, str) and bool(re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", value)),
        "A full 40/64-character commit SHA is required",
    )
    return value.lower()


def verify(repo, commit, base, expected_commits, runner=run_command):
    evidence = {
        "ok": False, "repo": repo, "commit": commit, "base": base,
        "expected_commits": list(expected_commits),
        "scope": "Explicit read-only check; not server-side branch protection",
    }
    try:
        require(bool(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo)),
                "Repository must be owner/repo")
        commit = checked_sha(commit)
        expected = list(dict.fromkeys(checked_sha(sha) for sha in expected_commits))
        require(bool(expected), "At least one --expected-commit is required")
        require(bool(base) and not base.startswith("-"), "Invalid base branch")
        runner(["git", "check-ref-format", "refs/heads/" + base])

        def resolve(sha):
            resolved = runner(["git", "rev-parse", "--verify", "--end-of-options", sha + "^{commit}"])
            require(checked_sha(resolved) == sha, "Commit object does not match requested SHA")
            return resolved

        resolve(commit)
        parents = runner(["git", "rev-list", "--parents", "-n", "1", commit]).split()
        require(len(parents) == 3 and parents[0] == commit,
                "Release commit must be a two-parent merge; direct/squash/rebase commits are rejected")
        first, second = parents[1:]
        evidence["parents"] = [first, second]

        def ancestor(older, newer):
            # rev-list produces an empty range iff older is an ancestor of newer.
            # Unlike --is-ancestor, an unavailable object cannot look like 'false'.
            return runner(["git", "rev-list", "--max-count=1", older, "--not", newer]) == ""

        checks = []
        evidence["classified_commit_checks"] = checks
        for sha in expected:
            resolve(sha)
            item = {"commit": sha, "in_pr_head": ancestor(sha, second),
                    "already_in_base": ancestor(sha, first)}
            checks.append(item)
            require(item["in_pr_head"], f"Expected classified commit is missing from PR head: {sha}")
            require(not item["already_in_base"], f"Expected commit was already in base, not introduced by this PR: {sha}")

        def api(path, paginate=False):
            args = ["gh", "api", "--method", "GET", path]
            if paginate:
                args += ["--paginate", "--slurp"]
            try:
                return json.loads(runner(args))
            except json.JSONDecodeError as exc:
                raise CheckError("GitHub returned invalid JSON") from exc

        ref = api(f"repos/{repo}/git/ref/heads/{quote(base, safe='')}")
        require(isinstance(ref, dict) and isinstance(ref.get("object"), dict),
                "Remote base reference is unavailable")
        remote_sha = checked_sha(ref["object"].get("sha"))
        evidence["remote_base_commit"] = remote_sha
        resolve(remote_sha)
        require(ancestor(commit, remote_sha), "Release commit is not in the remote base branch history")

        pages = api(f"repos/{repo}/commits/{commit}/pulls", paginate=True)
        require(isinstance(pages, list) and all(isinstance(page, list) for page in pages),
                "Invalid associated-PR response")
        candidates = [item for page in pages for item in page
                      if isinstance(item, dict) and item.get("merge_commit_sha") == commit]
        require(bool(candidates), "No associated PR has this merge commit")
        rejections = []
        for candidate in candidates:
            number = candidate.get("number")
            require(type(number) is int and number > 0, "Invalid associated PR number")
            pr = api(f"repos/{repo}/pulls/{number}")
            require(isinstance(pr, dict), "Invalid PR detail response")
            pr_base, pr_head = pr.get("base") or {}, pr.get("head") or {}
            require(isinstance(pr_base, dict) and isinstance(pr_head, dict),
                    "Invalid PR base/head evidence")
            base_repo = pr_base.get("repo") or {}
            require(isinstance(base_repo, dict) and isinstance(base_repo.get("full_name", ""), str),
                    "Invalid PR base repository evidence")
            matches = (
                pr.get("merged") is True and pr.get("state") == "closed"
                and pr.get("merge_commit_sha") == commit
                and pr_base.get("ref") == base and pr_head.get("sha") == second
                and base_repo.get("full_name", "").lower() == repo.lower()
            )
            if matches:
                evidence["pr"] = {
                    "number": number, "url": pr.get("html_url"), "state": "MERGED",
                    "base": pr_base["ref"], "head": pr_head["sha"], "merge_commit": commit,
                }
                evidence["ok"] = True
                return evidence
            rejections.append({"number": number, "merged": pr.get("merged"),
                               "state": pr.get("state"), "base": pr_base.get("ref"),
                               "head": pr_head.get("sha"), "merge_commit": pr.get("merge_commit_sha")})
        evidence["rejected_prs"] = rejections
        raise CheckError("Associated PR is not MERGED or its base/head/merge commit/repository does not match")
    except CheckError as exc:
        evidence["error"] = str(exc)
        return evidence


def main(argv=None):
    parser = JsonArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="GitHub owner/repo")
    parser.add_argument("--commit", required=True, help="Full release merge commit SHA")
    parser.add_argument("--base", default="main")
    parser.add_argument("--expected-commit", required=True, action="append",
                        help="Full classified commit SHA; repeat for every required commit")
    args = parser.parse_args(argv)
    evidence = verify(args.repo, args.commit, args.base, args.expected_commit)
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if evidence["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
