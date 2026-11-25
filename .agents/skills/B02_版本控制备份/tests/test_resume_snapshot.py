"""Synthetic isolated workspaces; never operates on an actual project backup."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
WORKSPACE_SPEC = Path(__file__).resolve().parents[4] / ".system" / "standards" / "workspace-spec.json"
VERSION_FILE = "\u7248\u672c\u8bb0\u5f55.md"
CATALOG_FILE = "\u76ee\u5f55.md"
DIR_01 = "01_\u95ee\u9898\u7b54\u7591"
DIR_02 = "02_\u8bfe\u9898\u7814\u7a76"
DIR_03 = "03_\u4ee3\u7801\u7a0b\u5e8f"
PWSH = shutil.which("pwsh")
POWERSHELL = PWSH or shutil.which("powershell")


def native(path):
    value = str(Path(path).resolve())
    return "\\\\?\\" + value if os.name == "nt" and not value.startswith("\\\\?\\") else value


def write(path, data=b"fixture"):
    os.makedirs(native(Path(path).parent), exist_ok=True)
    with open(native(path), "wb") as stream:
        stream.write(data)


def run_backup(root, script, *extra_args, shell=None):
    exe = shell or POWERSHELL
    cmd = [exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), *extra_args]
    return subprocess.run(cmd, cwd=root, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=90)


def setup_synthetic_workspace(include_spec=True):
    root = Path(tempfile.mkdtemp(prefix="b02-ssot-test-"))
    script_dir = root / ".agents" / "skills" / "B02_fixture" / "scripts"
    script_dir.mkdir(parents=True)
    for name in ("backup.ps1", "content_snapshot.ps1"):
        shutil.copyfile(SCRIPTS / name, script_dir / name)
    (root / ".history" / "output").mkdir(parents=True)
    if include_spec:
        spec_dest = root / ".system" / "standards" / "workspace-spec.json"
        spec_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE_SPEC, spec_dest)
    return root, script_dir / "backup.ps1"


@unittest.skipUnless(POWERSHELL, "PowerShell required")
class BackupPolicySSOTTests(unittest.TestCase):
    def setUp(self):
        self.root, self.script = setup_synthetic_workspace(include_spec=True)
        self.addCleanup(lambda: shutil.rmtree(native(self.root)))
        self.source = self.root / "output" / "11_fixture"
        self.record = self.source / VERSION_FILE
        self.original_record = "# \u7248\u672c\u8bb0\u5f55\n\n## v1.0.0\n".encode("utf-8")
        write(self.record, self.original_record)
        write(self.source / CATALOG_FILE, b"# catalog\n")
        write(self.source / "root-stray.txt", b"must not be copied")
        write(self.source / DIR_01 / "01_qa.md", b"qa content")
        write(self.source / DIR_02 / "01_study.md", b"study content")
        (self.source / DIR_02 / "empty-sub").mkdir(parents=True)
        write(self.source / DIR_01 / ".git" / "excluded", b"git metadata")
        # 03 contains code and even a .env secret that must never block 01/02 backup or be copied.
        write(self.source / DIR_03 / "app.py", b"print('code')")
        write(self.source / DIR_03 / ".env", b"SECRET=should-never-be-read")

    def test_project_backup_copies_only_01_and_02(self):
        result = run_backup(self.root, self.script, "-TargetPath", "output/11_fixture", "-ChangeType", "MINOR")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        snapshots = list((self.root / ".history" / "output").glob("11_fixture_v1.0.0_*"))
        self.assertEqual(len(snapshots), 1)
        snap = snapshots[0]
        self.assertEqual((snap / DIR_01 / "01_qa.md").read_bytes(), b"qa content")
        self.assertEqual((snap / DIR_02 / "01_study.md").read_bytes(), b"study content")
        self.assertTrue((snap / DIR_02 / "empty-sub").is_dir())
        self.assertFalse((snap / DIR_01 / ".git").exists())
        self.assertFalse((snap / DIR_03).exists())
        self.assertFalse((snap / VERSION_FILE).exists())
        self.assertFalse((snap / CATALOG_FILE).exists())
        self.assertFalse((snap / "root-stray.txt").exists())
        self.assertIn("## v1.1.0", self.record.read_text(encoding="utf-8"))

    def test_env_inside_01_still_rejected(self):
        write(self.source / DIR_01 / ".env", b"LEAK=1")
        result = run_backup(self.root, self.script, "-TargetPath", "output/11_fixture", "-ChangeType", "PATCH")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.record.read_bytes(), self.original_record)

    def test_exempt_paths_rejected_by_ssot(self):
        write(self.root / ".agents" / "rules" / "version-control-rules.md", b"rule")
        write(self.root / ".agents" / "skills" / "B02_fixture" / "SKILL.md", b"skill")
        write(self.root / ".memory" / "\u5bf9\u8bdd\u8bb0\u5f55" / "11_fixture.md", b"log")
        write(self.root / ".memory" / "\u7cfb\u7edf\u8bb0\u5f55" / "\u89c4\u5219\u53d8\u66f4\u8bb0\u5f55.md", b"sys")
        write(self.root / ".memory" / "\u4efb\u52a1\u8fdb\u5ea6" / "\u7d22\u5f15.md", b"task")

        cases = [
            (".agents/skills/B02_fixture", "-Mode", "FOLDER"),
            (".agents/rules/version-control-rules.md", "-Mode", "CONFIG"),
            (".system/standards", "-Mode", "FOLDER"),
            (".system/standards/workspace-spec.json", "-Mode", "CONFIG"),
            (f"output/11_fixture/{DIR_03}",),
            (f"output/11_fixture/{DIR_03}/app.py",),
            (f"output/11_fixture/{CATALOG_FILE}",),
            (".memory/\u5bf9\u8bdd\u8bb0\u5f55/11_fixture.md",),
            (".memory/\u7cfb\u7edf\u8bb0\u5f55/\u89c4\u5219\u53d8\u66f4\u8bb0\u5f55.md",),
            (".memory/\u4efb\u52a1\u8fdb\u5ea6/\u7d22\u5f15.md",),
        ]
        for args in cases:
            with self.subTest(target=args[0]):
                res = run_backup(self.root, self.script, "-TargetPath", *args)
                self.assertNotEqual(res.returncode, 0, f"Expected rejection for {args}: {res.stdout}")

    def test_memory_mode_preserved_for_versioned_files(self):
        distill = self.root / ".memory" / "\u77e5\u8bc6\u63d0\u70bc" / "\u6d4b\u8bd5\u8bdd\u9898.md"
        gmap = self.root / ".memory" / "\u5168\u5c40\u77e5\u8bc6\u5730\u56fe.md"
        write(distill, b"<!-- memory-version: 1.0.0 -->\n# distill\n")
        write(gmap, b"<!-- memory-version: 2.0.0 -->\n# map\n")

        res1 = run_backup(self.root, self.script, "-TargetPath", ".memory/\u77e5\u8bc6\u63d0\u70bc/\u6d4b\u8bd5\u8bdd\u9898.md", "-Mode", "MEMORY", "-ChangeType", "MINOR")
        self.assertEqual(res1.returncode, 0, res1.stderr + res1.stdout)
        self.assertTrue((self.root / ".history" / ".memory" / "\u77e5\u8bc6\u63d0\u70bc" / "\u6d4b\u8bd5\u8bdd\u9898_v1.0.0.md").is_file())
        self.assertIn("<!-- memory-version: 1.1.0 -->", distill.read_text(encoding="utf-8"))

        res2 = run_backup(self.root, self.script, "-TargetPath", ".memory/\u5168\u5c40\u77e5\u8bc6\u5730\u56fe.md", "-Mode", "MEMORY", "-ChangeType", "PATCH")
        self.assertEqual(res2.returncode, 0, res2.stderr + res2.stdout)
        self.assertTrue((self.root / ".history" / ".memory" / "\u5168\u5c40\u77e5\u8bc6\u5730\u56fe" / "\u5168\u5c40\u77e5\u8bc6\u5730\u56fe_v2.0.0.md").is_file())
        self.assertIn("<!-- memory-version: 2.0.1 -->", gmap.read_text(encoding="utf-8"))

    def test_ssot_dynamic_policy_override(self):
        spec_path = self.root / ".system" / "standards" / "workspace-spec.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["backupPolicy"]["project"]["includeSubfolders"] = [DIR_01]
        spec_path.write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")

        result = run_backup(self.root, self.script, "-TargetPath", "output/11_fixture", "-ChangeType", "PATCH")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        snap = list((self.root / ".history" / "output").glob("11_fixture_v1.0.0_*"))[0]
        self.assertTrue((snap / DIR_01 / "01_qa.md").is_file())
        self.assertFalse((snap / DIR_02).exists())


@unittest.skipUnless(POWERSHELL, "PowerShell required")
class ResumeSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.root, self.script = setup_synthetic_workspace(include_spec=True)
        self.addCleanup(lambda: shutil.rmtree(native(self.root)))
        self.source = self.root / "output" / "11_fixture"
        self.record = self.source / VERSION_FILE
        self.original_record = b"# fixture\n\n## v1.0.0\n"
        write(self.record, self.original_record)
        write(self.source / CATALOG_FILE, b"# catalog\n")
        write(self.source / DIR_01 / "file.txt", b"unchanged")
        (self.source / DIR_02 / "empty").mkdir(parents=True)
        write(self.source / DIR_01 / ".git" / "excluded", b"not snapshot payload")
        write(self.source / DIR_03 / "code.py", b"excluded code dir")
        write(self.source / DIR_03 / ".env", b"SECRET=ignored")
        self.final = self.root / ".history" / "output" / "11_fixture_v1.0.0_20261013010101"
        self.pending = Path(str(self.final) + ".incomplete-" + "a" * 32)
        self.clone_pending()

    def clone_pending(self):
        if os.path.exists(native(self.pending)):
            shutil.rmtree(native(self.pending))
        os.makedirs(native(self.pending), exist_ok=True)
        for sub in (DIR_01, DIR_02):
            src_sub = self.source / sub
            if src_sub.is_dir():
                shutil.copytree(native(src_sub), native(self.pending / sub), ignore=shutil.ignore_patterns(".git"))

    def resume(self, pending=None, mode="PROJECT"):
        return run_backup(
            self.root,
            self.script,
            "-TargetPath",
            "output/11_fixture",
            "-Mode",
            mode,
            "-ChangeType",
            "PATCH",
            "-ResumeSnapshotPath",
            str(pending or self.pending),
        )

    def assert_rejected(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.record.read_bytes(), self.original_record)
        self.assertTrue(os.path.isdir(native(self.pending)))

    def test_success_preserves_01_02_snapshot_and_advances_version(self):
        result = self.resume()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertFalse(self.pending.exists())
        self.assertEqual((self.final / DIR_01 / "file.txt").read_bytes(), b"unchanged")
        self.assertTrue((self.final / DIR_02 / "empty").is_dir())
        self.assertFalse((self.final / DIR_01 / ".git").exists())
        self.assertFalse((self.final / DIR_03).exists())
        self.assertFalse((self.final / VERSION_FILE).exists())
        self.assertIn("## v1.0.1", self.record.read_text(encoding="utf-8"))

    def test_missing_file_rejected(self):
        (self.pending / DIR_01 / "file.txt").unlink()
        self.assert_rejected(self.resume())

    def test_extra_file_or_03_in_pending_rejected(self):
        write(self.pending / DIR_03 / "code.py", b"excluded code dir")
        self.assert_rejected(self.resume())

    def test_root_file_in_pending_rejected(self):
        write(self.pending / CATALOG_FILE, b"# catalog\n")
        self.assert_rejected(self.resume())

    def test_changed_file_same_length_rejected(self):
        write(self.source / DIR_01 / "file.txt", b"different")
        self.assert_rejected(self.resume())

    def test_missing_empty_directory_rejected(self):
        (self.pending / DIR_02 / "empty").rmdir()
        self.assert_rejected(self.resume())

    def test_outside_workspace_rejected(self):
        self.assert_rejected(self.resume(self.root.parent / self.pending.name))

    def test_wrong_history_parent_rejected(self):
        self.assert_rejected(self.resume(self.root / ".history" / "other" / self.pending.name))

    def test_wrong_version_rejected(self):
        self.assert_rejected(self.resume(Path(str(self.pending).replace("_v1.0.0_", "_v9.0.0_"))))

    def test_existing_destination_rejected_without_changes(self):
        write(self.final / "preserve.txt", b"existing backup")
        self.assert_rejected(self.resume())
        self.assertEqual((self.final / "preserve.txt").read_bytes(), b"existing backup")

    def test_pending_git_metadata_rejected(self):
        write(self.pending / DIR_01 / ".git" / "unexpected")
        self.assert_rejected(self.resume())

    def test_non_project_mode_rejected(self):
        self.assert_rejected(self.resume(mode="FOLDER"))

    def test_long_paths_success(self):
        deep = self.source / DIR_01
        for index in range(7):
            deep /= "segment-" + str(index) + "-" + "a" * 30
        write(deep / "long-file.txt", b"long path payload")
        os.makedirs(native(deep / "empty-long"))
        self.clone_pending()
        self.assertGreater(len(str(deep / "long-file.txt")), 260)
        result = self.resume()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        destination = self.final / (deep / "long-file.txt").relative_to(self.source)
        with open(native(destination), "rb") as stream:
            self.assertEqual(stream.read(), b"long path payload")
        self.assertIn("## v1.0.1", self.record.read_text(encoding="utf-8"))

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_junction_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        junction = self.pending / DIR_01 / "linked"
        command = "$ErrorActionPreference='Stop'; $null = New-Item -ItemType Junction -Path $env:B02_TEST_LINK -Target $env:B02_TEST_TARGET"
        creation = subprocess.run([POWERSHELL, "-NoProfile", "-Command", command], capture_output=True, text=True, encoding="utf-8",
                                  env={**os.environ, "B02_TEST_LINK": str(junction), "B02_TEST_TARGET": str(outside)})
        self.assertEqual(creation.returncode, 0, creation.stderr)
        try:
            self.assert_rejected(self.resume())
        finally:
            junction.absolute().relative_to(self.root.absolute())
            os.rmdir(str(junction.absolute()))
            self.assertTrue(outside.is_dir(), "Junction cleanup must preserve its target")


if __name__ == "__main__":
    unittest.main()
