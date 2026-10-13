import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "scan_release_history.py"
SPEC = importlib.util.spec_from_file_location("release_scanner", SCRIPT)
SCANNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCANNER)


class HistoryScanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.name", "Scanner Test")
        self.git("config", "user.email", "scanner@example.invalid")
        self.git("config", "core.hooksPath", str(self.root / "no-hooks"))
        (self.repo / "README.md").write_text("base\n", encoding="utf-8")
        self.commit()
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], stderr=subprocess.DEVNULL, text=True)

    def commit(self):
        self.git("add", "--all")
        self.git("commit", "-qm", "test change")

    def scan(self, *extra, base=None):
        process = subprocess.run([sys.executable, str(SCRIPT), "--repo-dir", str(self.repo), "--base", base or self.base, "--head", "HEAD", *extra], capture_output=True, text=True)
        self.assertEqual(process.stderr, "")
        return process.returncode, json.loads(process.stdout), process.stdout

    def test_deleted_intermediate_secret_is_detected(self):
        secret = "".join(("K9rT7vQ2", "mP8zN4sW"))
        (self.repo / "config.env").write_text("DATABASE_PASSWORD=" + secret)
        self.commit()
        (self.repo / "config.env").unlink()
        self.commit()
        code, report, output = self.scan()
        self.assertEqual(code, 1)
        self.assertTrue(any(row["path"] == "config.env" for row in report["git"]["findings"]))
        self.assertNotIn(secret, output)

    def test_clean_placeholders_and_code(self):
        (self.repo / "sample.env").write_text('API_TOKEN="your_token_here"\nPASSWORD=${DB_PASSWORD}\nsecret = os.getenv("API_SECRET")\npassword="synthetic_test_1234"\n', encoding="utf-8")
        self.commit()
        code, report, _ = self.scan()
        self.assertEqual(code, 0)
        self.assertEqual(report["status"], "clean")

    def test_runtime_crypto_and_compose_references_are_not_literals(self):
        source = b'''const token = crypto.randomBytes(32).toString('hex');
const token = crypto.randomBytes(64);
MYSQL_PASSWORD: "$$MYSQL_PASSWORD"
API_TOKEN=replace-with-32-character-random-token
password: ''
'''
        self.assertEqual(SCANNER.rules(source, []), [])

    def test_quoted_crypto_lookalike_still_scans_as_literal(self):
        source = b"token" + b" = " + b'''"crypto.randomBytes(32).toString('hex')"'''
        self.assertIn("R003_CREDENTIAL_LITERAL", SCANNER.rules(source, []))

    def test_synthetic_password_literal_in_test_remains_reviewable(self):
        value = "".join(("long-password-", "7319"))
        source = ('test("hash", () => { const password="' + value + '"; });').encode()
        self.assertIn("R003_CREDENTIAL_LITERAL", SCANNER.rules(source, []))

    def test_explicit_private_value_overrides_instructional_shape(self):
        value = "".join(("replace-with-", "32-character-value"))
        self.assertTrue(SCANNER.private_value(value))
        self.assertIn("R005_PRIVATE_VALUE_MATCH", SCANNER.rules(value.encode(), [value]))

    def test_invalid_base_is_incomplete(self):
        code, report, _ = self.scan(base="missing-ref-do-not-print")
        self.assertEqual(code, 2)
        self.assertFalse(report["git"]["complete"])

    def test_zip_content_match(self):
        asset = self.root / "release.zip"
        secret = "".join(("p7Z2c5N8", "r4T9v6Q3"))
        with zipfile.ZipFile(asset, "w") as archive:
            archive.writestr("settings.env", "PASSWORD=" + secret)
        code, report, output = self.scan("--asset", str(asset))
        self.assertEqual(code, 1)
        self.assertTrue(report["assets"]["findings"])
        self.assertNotIn(secret, output)
        self.assertNotIn(str(asset), output)

    def test_private_value_exact_match_and_output_redaction(self):
        secret = "".join(("v6P3s9W4", "z7C2n8M5"))
        private = self.root / "private.env"
        private.write_text("API_TOKEN=" + secret)
        (self.repo / "notes.txt").write_text("unlabelled value " + secret)
        self.commit()
        code, report, output = self.scan("--secret-file", str(private))
        self.assertEqual(code, 1)
        self.assertIn("R005_PRIVATE_VALUE_MATCH", [row["rule"] for row in report["git"]["findings"]])
        self.assertNotIn(secret, output)
        self.assertNotIn(str(private), output)

    def test_unreadable_private_input_has_no_path(self):
        missing = self.root / "private-sensitive-name.env"
        code, report, output = self.scan("--secret-file", str(missing))
        self.assertEqual(code, 2)
        self.assertEqual(report["status"], "incomplete")
        self.assertNotIn(missing.name, output)

    def test_clean_nested_zip_is_scanned(self):
        import io
        nested = io.BytesIO()
        with zipfile.ZipFile(nested, "w") as archive:
            archive.writestr("a.txt", "hello")
        asset = self.root / "outer.zip"
        with zipfile.ZipFile(asset, "w") as archive:
            archive.writestr("inner.zip", nested.getvalue())
        code, report, _ = self.scan("--asset", str(asset))
        self.assertEqual(code, 0)
        self.assertEqual(report["assets"]["archive_members"], 2)
        self.assertEqual(report["assets"]["scanned_files"], 3)

    def test_nested_zip_in_git_and_asset_detects_secret(self):
        import io
        secret = "".join(("K9rT7vQ2", "mP8zN4sW"))
        nested = io.BytesIO()
        with zipfile.ZipFile(nested, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("config.env", "PASSWORD=" + secret)
        asset = self.repo / "outer.zip"
        with zipfile.ZipFile(asset, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("downloads/skill.zip", nested.getvalue())
        self.commit()
        code, report, output = self.scan("--asset", str(asset))
        self.assertEqual(code, 1)
        self.assertTrue(any(row["path"].endswith("skill.zip/config.env") for row in report["git"]["findings"]))
        self.assertTrue(any(row["path"].endswith("skill.zip/config.env") for row in report["assets"]["findings"]))
        self.assertNotIn(secret, output)

    def test_explicit_private_value_with_test_substring(self):
        secret = "".join(("v6P3test_", "z7C2sampleN5"))
        private = self.root / "private.env"
        private.write_text("API_TOKEN=" + secret)
        (self.repo / "notes.txt").write_text("unlabelled value " + secret)
        self.commit()
        code, report, output = self.scan("--secret-file", str(private))
        self.assertEqual(code, 1)
        self.assertIn("R005_PRIVATE_VALUE_MATCH", [row["rule"] for row in report["git"]["findings"]])
        self.assertNotIn(secret, output)

    def test_zip_depth_limit_is_incomplete(self):
        import io
        data = b"clean"
        for index in range(4):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w") as archive:
                archive.writestr("inner.zip" if index else "clean.txt", data)
            data = stream.getvalue()
        result = SCANNER.section()
        with self.assertRaisesRegex(SCANNER.ScanError, "ZIP_DEPTH_LIMIT"):
            SCANNER.scan_content(result, data, "outer.zip", None, [])

    def test_nested_zip_uses_shared_member_budget(self):
        import io
        nested = io.BytesIO()
        with zipfile.ZipFile(nested, "w") as archive:
            archive.writestr("one.txt", "clean")
            archive.writestr("two.txt", "clean")
        asset = self.root / "outer.zip"
        with zipfile.ZipFile(asset, "w") as archive:
            archive.writestr("inner.zip", nested.getvalue())
        with patch.object(SCANNER, "MAX_ZIP_MEMBERS", 2):
            result = SCANNER.scan_assets([str(asset)], [])
        self.assertFalse(result["complete"])
        self.assertIn("ZIP_MEMBER_LIMIT", result["errors"])

    def test_oversized_plain_asset_is_incomplete(self):
        asset = self.root / "large.txt"
        asset.write_bytes(b"a" * 33)
        with patch.object(SCANNER, "MAX_FILE", 32):
            result = SCANNER.scan_assets([str(asset)], [])
        self.assertFalse(result["complete"])
        self.assertIn("CONTENT_SIZE_LIMIT", result["errors"])

    def test_corrupt_zip_is_incomplete(self):
        asset = self.root / "broken.zip"
        asset.write_bytes(b"not a zip")
        code, report, output = self.scan("--asset", str(asset))
        self.assertEqual(code, 2)
        self.assertFalse(report["assets"]["complete"])
        self.assertNotIn(str(asset), output)

    def test_secret_in_zip_filename_is_redacted(self):
        secret = "".join(("z8C4q1T7", "v6J3r9N2"))
        private = self.root / "private.env"
        private.write_text("API_TOKEN=" + secret)
        asset = self.root / "release.zip"
        with zipfile.ZipFile(asset, "w") as archive:
            archive.writestr(secret + ".txt", secret)
        code, report, output = self.scan("--asset", str(asset), "--secret-file", str(private))
        self.assertEqual(code, 1)
        self.assertNotIn(secret, output)
        self.assertTrue(any("[REDACTED]" in row["path"] for row in report["assets"]["findings"]))

    def test_zip_member_limit_is_incomplete(self):
        asset = self.root / "many.zip"
        with zipfile.ZipFile(asset, "w") as archive:
            archive.writestr("one", "clean")
            archive.writestr("two", "clean")
        with patch.object(SCANNER, "MAX_ZIP_MEMBERS", 1):
            result = SCANNER.scan_assets([str(asset)], [])
        self.assertFalse(result["complete"])
        self.assertIn("ZIP_MEMBER_LIMIT", result["errors"])

    def test_nested_zip_uses_shared_byte_budget(self):
        import io
        nested = io.BytesIO()
        with zipfile.ZipFile(nested, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("one.txt", "clean" * 100)
        asset = self.root / "outer.zip"
        with zipfile.ZipFile(asset, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("inner.zip", nested.getvalue())
        budget = asset.stat().st_size + len(nested.getvalue()) + 10
        with patch.object(SCANNER, "MAX_TOTAL", budget):
            result = SCANNER.scan_assets([str(asset)], [])
        self.assertFalse(result["complete"])
        self.assertIn("ZIP_CONTENT_LIMIT", result["errors"])


if __name__ == "__main__":
    unittest.main()
