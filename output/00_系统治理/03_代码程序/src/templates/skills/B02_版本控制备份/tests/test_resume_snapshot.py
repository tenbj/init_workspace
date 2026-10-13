"""Synthetic isolated workspaces; never operates on an actual project backup."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
VERSION_FILE = "\u7248\u672c\u8bb0\u5f55.md"
PWSH = shutil.which("pwsh")


def native(path):
    value = str(Path(path).resolve())
    return "\\\\?\\" + value if os.name == "nt" and not value.startswith("\\\\?\\") else value


def write(path, data=b"fixture"):
    os.makedirs(native(Path(path).parent), exist_ok=True)
    with open(native(path), "wb") as stream:
        stream.write(data)


@unittest.skipUnless(PWSH, "PowerShell 7 required")
class ResumeSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="b02-resume-test-"))
        self.addCleanup(lambda: shutil.rmtree(native(self.root)))
        script_dir = self.root / ".agents" / "skills" / "B02_fixture" / "scripts"
        script_dir.mkdir(parents=True)
        for name in ("backup.ps1", "content_snapshot.ps1"):
            shutil.copyfile(SCRIPTS / name, script_dir / name)
        self.script = script_dir / "backup.ps1"
        self.source = self.root / "output" / "11_fixture"
        self.record = self.source / VERSION_FILE
        self.original_record = b"# fixture\n\n## v1.0.0\n"
        write(self.record, self.original_record)
        write(self.source / "file.txt", b"unchanged")
        (self.source / "empty").mkdir()
        write(self.source / ".git" / "excluded", b"not snapshot payload")
        self.final = self.root / ".history" / "output" / "11_fixture_v1.0.0_20261013010101"
        self.pending = Path(str(self.final) + ".incomplete-" + "a" * 32)
        self.clone_pending()

    def clone_pending(self):
        if os.path.exists(native(self.pending)):
            shutil.rmtree(native(self.pending))
        shutil.copytree(native(self.source), native(self.pending), ignore=shutil.ignore_patterns(".git"))

    def resume(self, pending=None, mode="PROJECT"):
        return subprocess.run([
            PWSH, "-NoProfile", "-File", str(self.script), "-TargetPath", "output/11_fixture",
            "-Mode", mode, "-ChangeType", "PATCH", "-ResumeSnapshotPath", str(pending or self.pending),
        ], cwd=self.root, capture_output=True, text=True, encoding="utf-8", timeout=90)

    def assert_rejected(self, result):
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.record.read_bytes(), self.original_record)
        self.assertTrue(os.path.isdir(native(self.pending)))

    def test_success_preserves_snapshot_and_advances_version(self):
        result = self.resume()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.pending.exists())
        self.assertEqual((self.final / VERSION_FILE).read_bytes(), self.original_record)
        self.assertTrue((self.final / "empty").is_dir())
        self.assertFalse((self.final / ".git").exists())
        self.assertIn("## v1.0.1", self.record.read_text(encoding="utf-8"))

    def test_missing_file_rejected(self):
        (self.pending / "file.txt").unlink()
        self.assert_rejected(self.resume())

    def test_extra_file_rejected(self):
        write(self.pending / "extra.txt")
        self.assert_rejected(self.resume())

    def test_changed_file_same_length_rejected(self):
        write(self.pending / "file.txt", b"different")
        self.assert_rejected(self.resume())

    def test_missing_empty_directory_rejected(self):
        (self.pending / "empty").rmdir()
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
        write(self.pending / ".git" / "unexpected")
        self.assert_rejected(self.resume())

    def test_non_project_mode_rejected(self):
        self.assert_rejected(self.resume(mode="FOLDER"))

    def test_long_paths_success(self):
        deep = self.source
        for index in range(7):
            deep /= "segment-" + str(index) + "-" + "a" * 30
        write(deep / "long-file.txt", b"long path payload")
        os.makedirs(native(deep / "empty-long"))
        self.clone_pending()
        self.assertGreater(len(str(deep / "long-file.txt")), 260)
        result = self.resume()
        self.assertEqual(result.returncode, 0, result.stderr)
        destination = self.final / (deep / "long-file.txt").relative_to(self.source)
        with open(native(destination), "rb") as stream:
            self.assertEqual(stream.read(), b"long path payload")
        self.assertIn("## v1.0.1", self.record.read_text(encoding="utf-8"))

    @unittest.skipUnless(os.name == "nt", "Windows junction test")
    def test_junction_rejected(self):
        outside = self.root / "outside"
        outside.mkdir()
        junction = self.pending / "linked"
        command = "$ErrorActionPreference='Stop'; $null = New-Item -ItemType Junction -Path $env:B02_TEST_LINK -Target $env:B02_TEST_TARGET"
        creation = subprocess.run([PWSH, "-NoProfile", "-Command", command], capture_output=True, text=True, encoding="utf-8",
                                  env={**os.environ, "B02_TEST_LINK": str(junction), "B02_TEST_TARGET": str(outside)})
        self.assertEqual(creation.returncode, 0, creation.stderr)
        try:
            self.assert_rejected(self.resume())
        finally:
            os.rmdir(native(junction))


if __name__ == "__main__":
    unittest.main()
