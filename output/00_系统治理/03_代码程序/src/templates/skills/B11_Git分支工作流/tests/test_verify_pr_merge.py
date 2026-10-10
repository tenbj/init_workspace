"""Real isolated Git histories; GitHub responses are mocked, never networked."""

import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verify_pr_merge.py"
SPEC = importlib.util.spec_from_file_location("verify_pr_merge", SCRIPT)
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class MergeGateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="pr-merge-check-")
        self.addCleanup(self.temp.cleanup)
        self.cwd = self.temp.name
        self.git("init", "-q", "--initial-branch=main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("config", "core.hooksPath", str(Path(self.cwd) / "no-hooks"))
        self.git("commit", "--allow-empty", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD")
        self.git("switch", "-qc", "feature")
        self.git("commit", "--allow-empty", "-qm", "skills")
        self.skills = self.git("rev-parse", "HEAD")
        self.git("commit", "--allow-empty", "-qm", "governance")
        self.head = self.git("rev-parse", "HEAD")
        self.git("switch", "-q", "main")
        self.git("merge", "--no-ff", "--no-gpg-sign", "-qm", "PR merge", "feature")
        self.merge = self.git("rev-parse", "HEAD")
        self.remote = self.merge
        self.calls = []
        self.pr = {"number": 9, "state": "closed", "merged": True,
                   "merge_commit_sha": self.merge, "html_url": "https://github.com/example/repo/pull/9",
                   "base": {"ref": "main", "repo": {"full_name": "example/repo"}},
                   "head": {"sha": self.head}}
        self.associated = [[{"number": 9, "merge_commit_sha": self.merge}]]

    def git(self, *args):
        result = subprocess.run(["git", *args], cwd=self.cwd, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", check=False)
        if result.returncode:
            raise gate.CheckError(f"Git failed ({result.returncode})")
        return result.stdout.strip()

    def runner(self, args):
        self.calls.append(args)
        if args[0] == "git":
            return self.git(*args[1:])
        self.assertEqual(args[:4], ["gh", "api", "--method", "GET"])
        path = args[4]
        if "/git/ref/heads/" in path:
            return json.dumps({"object": {"sha": self.remote}})
        if "/commits/" in path:
            self.assertEqual(args[5:], ["--paginate", "--slurp"])
            return json.dumps(self.associated)
        self.assertEqual(path, "repos/example/repo/pulls/9")
        return json.dumps(self.pr)

    def check(self, commit=None, expected=None):
        return gate.verify("example/repo", commit or self.merge, "main",
                           expected if expected is not None else [self.skills, self.head], self.runner)

    def test_real_merge_preserves_both_classified_commits(self):
        before = self.git("status", "--porcelain")
        result = self.check()
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["pr"]["head"], self.head)
        self.assertEqual(len(result["classified_commit_checks"]), 2)
        self.assertEqual(self.git("status", "--porcelain"), before)

    def test_direct_or_squash_commit_rejected_before_network(self):
        result = self.check(commit=self.head)
        self.assertFalse(result["ok"])
        self.assertIn("two-parent", result["error"])
        self.assertFalse(any(args[0] == "gh" for args in self.calls))

    def test_root_commit_rejected(self):
        self.assertFalse(self.check(commit=self.base)["ok"])

    def test_missing_classified_commit_rejected_before_network(self):
        self.git("switch", "-qc", "unrelated", self.base)
        self.git("commit", "--allow-empty", "-qm", "lost commit")
        missing = self.git("rev-parse", "HEAD")
        result = self.check(expected=[self.skills, missing])
        self.assertFalse(result["ok"])
        self.assertIn("missing from PR head", result["error"])
        self.assertFalse(any(args[0] == "gh" for args in self.calls))

    def test_already_merged_expected_commit_rejected(self):
        result = self.check(expected=[self.base])
        self.assertFalse(result["ok"])
        self.assertIn("already in base", result["error"])

    def test_empty_expected_commits_rejected(self):
        self.assertFalse(self.check(expected=[])["ok"])
        self.assertEqual(self.calls, [])

    def test_unmerged_pr_rejected(self):
        self.pr.update(merged=False, state="open")
        self.assertFalse(self.check()["ok"])

    def test_closed_unmerged_pr_rejected(self):
        self.pr["merged"] = False
        self.assertFalse(self.check()["ok"])

    def test_wrong_base_head_merge_or_repository_rejected(self):
        original = copy.deepcopy(self.pr)
        for field in ("base", "head", "merge", "repo"):
            with self.subTest(field=field):
                self.pr = copy.deepcopy(original)
                if field == "base":
                    self.pr["base"]["ref"] = "release"
                elif field == "head":
                    self.pr["head"]["sha"] = self.skills
                elif field == "merge":
                    self.pr["merge_commit_sha"] = self.head
                else:
                    self.pr["base"]["repo"]["full_name"] = "other/repo"
                self.assertFalse(self.check()["ok"])

    def test_no_associated_pr_rejected(self):
        self.associated = [[]]
        self.assertFalse(self.check()["ok"])

    def test_merge_not_in_remote_base_rejected(self):
        self.remote = self.base
        result = self.check()
        self.assertFalse(result["ok"])
        self.assertIn("remote base branch history", result["error"])

    def test_remote_base_can_advance_after_merge(self):
        self.git("commit", "--allow-empty", "-qm", "later")
        self.remote = self.git("rev-parse", "HEAD")
        self.assertTrue(self.check()["ok"])

    def test_remote_object_missing_fails_closed(self):
        self.remote = "a" * 40
        self.assertFalse(self.check()["ok"])

    def test_github_failure_is_non_success_evidence(self):
        def unavailable(args):
            if args[0] == "gh":
                raise gate.CheckError("GitHub unavailable")
            return self.runner(args)
        result = gate.verify("example/repo", self.merge, "main", [self.skills], unavailable)
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], "GitHub unavailable")

    def test_invalid_sha_cannot_be_an_option(self):
        self.assertFalse(self.check(commit="--help")["ok"])
        self.assertEqual(self.calls, [])

    def test_malformed_pr_evidence_fails_closed(self):
        self.pr["head"] = "invalid"
        result = self.check()
        self.assertFalse(result["ok"])
        self.assertIn("Invalid PR base/head", result["error"])

    def test_cli_missing_expected_is_json_and_nonzero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", "example/repo", "--commit", self.merge],
            cwd=self.cwd, capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)["ok"])

    def test_cli_direct_commit_is_json_and_nonzero(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", "example/repo", "--commit", self.head,
             "--expected-commit", self.skills],
            cwd=self.cwd, capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("two-parent", json.loads(result.stdout)["error"])


if __name__ == "__main__":
    unittest.main()
