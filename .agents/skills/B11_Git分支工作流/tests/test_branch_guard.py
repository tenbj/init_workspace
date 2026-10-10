"""Behavioral tests using isolated real repositories; never touch project refs."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parent.parent
INSTALLER = SKILL / "scripts" / "install_branch_guard.py"
WORKSPACE = SKILL.parents[2]


class BranchGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp_root = (WORKSPACE / ".temp").resolve()
        self.temp_root.mkdir(exist_ok=True)
        self.base = Path(tempfile.mkdtemp(prefix="b11-guard-test-", dir=self.temp_root)).resolve()
        self.repo = self.base / "repo"
        self.repo.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "B11 Test")
        self.git("config", "user.email", "b11-test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.autocrlf", "false")
        self.git("commit", "--allow-empty", "-m", "seed")
        self.seed = self.git("rev-parse", "HEAD").stdout.strip()

    def tearDown(self):
        if not self.base.is_relative_to(self.temp_root) or self.base == self.temp_root:
            raise RuntimeError("Unsafe test cleanup path")
        shutil.rmtree(self.base, onexc=lambda func, path, exc: (os.chmod(path, 0o700), func(path)))

    def command(self, args, cwd=None, success=True):
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_EDITOR"] = "true"
        result = subprocess.run(args, cwd=cwd or self.repo, env=env,
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        if success:
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        return result

    def git(self, *args, cwd=None, success=True):
        return self.command(["git", *args], cwd=cwd, success=success)

    def guard(self, *args, cwd=None, success=True):
        return self.command([sys.executable, str(INSTALLER), "--repo", str(cwd or self.repo), *args],
                            success=success)

    def blocked_commit(self, *args, cwd=None):
        before = self.git("rev-parse", "HEAD", cwd=cwd).stdout
        result = self.git("commit", "--allow-empty", "-m", "blocked", *args, cwd=cwd, success=False)
        self.assertIn("B11 分支保护", result.stderr)
        self.assertEqual(before, self.git("rev-parse", "HEAD", cwd=cwd).stdout)

    def test_main_commit_amend_and_no_verify_blocked(self):
        self.guard("--install")
        for args in ((), ("--amend",), ("--no-verify",), ("--amend", "--no-verify")):
            with self.subTest(args=args):
                self.blocked_commit(*args)

    def test_master_and_detached_blocked(self):
        self.guard("--install")
        self.git("checkout", "-b", "master")
        self.blocked_commit()
        self.git("checkout", "--detach")
        self.blocked_commit("--no-verify")

    def test_remote_symbolic_default_branch_blocked(self):
        self.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
        self.git("update-ref", "refs/remotes/origin/trunk", "HEAD")
        self.git("checkout", "-b", "trunk")
        self.guard("--install")
        self.blocked_commit()

    def test_feature_commit_and_no_verify_allowed(self):
        self.guard("--install")
        self.git("checkout", "-b", "codex/test")
        self.git("commit", "--allow-empty", "-m", "feature")
        self.git("commit", "--allow-empty", "--no-verify", "-m", "feature2")
        self.assertNotEqual(self.seed, self.git("rev-parse", "HEAD").stdout.strip())

    def test_main_merge_commit_blocked(self):
        self.guard("--install")
        self.git("checkout", "-b", "codex/test")
        self.git("commit", "--allow-empty", "-m", "feature")
        self.git("checkout", "main")
        result = self.git("merge", "--no-ff", "codex/test", "-m", "merge", success=False)
        self.assertIn("B11 分支保护", result.stderr)
        self.assertEqual(self.seed, self.git("rev-parse", "HEAD").stdout.strip())
        self.git("merge", "--abort")
        result = self.git("merge", "--no-ff", "--no-verify", "codex/test", "-m", "merge", success=False)
        self.assertIn("B11 分支保护", result.stderr)
        self.assertEqual(self.seed, self.git("rev-parse", "HEAD").stdout.strip())

    def test_push_destination_and_delete_main_blocked_feature_allowed(self):
        remote = self.base / "remote.git"
        self.git("init", "--bare", str(remote))
        self.git("remote", "add", "origin", str(remote))
        self.git("push", "origin", "main")
        self.guard("--install")
        self.git("checkout", "-b", "codex/test")
        self.git("commit", "--allow-empty", "-m", "feature")
        self.git("symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/trunk")
        self.git("update-ref", "refs/remotes/origin/trunk", self.seed)
        for target in ("HEAD:main", ":main", "HEAD:master", "HEAD:trunk"):
            result = self.git("push", "origin", target, success=False)
            self.assertIn("B11 分支保护", result.stderr)
        self.assertEqual(self.seed, self.git("--git-dir", str(remote), "rev-parse", "main").stdout.strip())
        self.git("push", "origin", "HEAD:refs/heads/codex/test")

    def test_linked_worktree_shares_guard(self):
        self.git("checkout", "-b", "codex/test")
        linked = self.base / "linked"
        self.git("worktree", "add", str(linked), "main")
        self.guard("--install", cwd=linked)
        self.guard("--check")
        self.blocked_commit("--no-verify", cwd=linked)
        self.git("commit", "--allow-empty", "-m", "feature")

    def test_install_idempotent_and_tamper_detected(self):
        self.guard("--check", success=False)
        self.guard("--install")
        hooks = self.repo / ".git" / "hooks"
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in hooks.iterdir()}
        self.guard("--install")
        self.guard()
        self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in hooks.iterdir()})
        (hooks / "prepare-commit-msg").write_bytes(b"#!/bin/sh\nexit 0\n")
        self.guard("--check", success=False)
        self.guard("--install", success=False)
        self.assertEqual((hooks / "prepare-commit-msg").read_bytes(), b"#!/bin/sh\nexit 0\n")

    def test_existing_hook_refuses_before_partial_install(self):
        hooks = self.repo / ".git" / "hooks"
        original = b"#!/bin/sh\necho custom\n"
        (hooks / "pre-push").write_bytes(original)
        self.guard("--install", success=False)
        self.assertEqual((hooks / "pre-push").read_bytes(), original)
        self.assertFalse((hooks / "pre-commit").exists())

    def test_custom_hooks_path_refuses_without_config_changes(self):
        self.git("config", "core.hooksPath", "custom-hooks")
        before = (self.repo / ".git" / "config").read_bytes()
        self.guard("--install", success=False)
        self.guard("--check", success=False)
        self.assertEqual((self.repo / ".git" / "config").read_bytes(), before)
        self.assertFalse((self.repo / "custom-hooks").exists())

    def test_sibling_worktree_hooks_path_detected(self):
        self.git("checkout", "-b", "codex/test")
        linked = self.base / "linked"
        self.git("worktree", "add", str(linked), "main")
        self.git("config", "extensions.worktreeConfig", "true")
        self.git("config", "--worktree", "core.hooksPath", "custom-hooks", cwd=linked)
        self.guard("--install", success=False)
        self.assertFalse((self.repo / ".git" / "hooks" / "pre-commit").exists())

    @unittest.skipIf(os.name == "nt", "POSIX executable mode only")
    def test_non_executable_hook_detected(self):
        self.guard("--install")
        (self.repo / ".git" / "hooks" / "pre-commit").chmod(0o644)
        self.guard("--check", success=False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
