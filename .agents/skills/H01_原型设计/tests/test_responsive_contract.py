import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from create_package import create_package
from responsive_contract import REPORT, fingerprint, validate_config, engine_fingerprint
from validate_package import validate_package


def evidence(root):
    """Synthetic evidence tests the gate only; browser truth is tested separately."""
    config = json.loads((root / "ui.schema.json").read_text(encoding="utf-8"))["responsive"]
    data = {"status": "passed", "passed": True,
            "prototype_sha256": hashlib.sha256((root / "prototype.html").read_bytes()).hexdigest(),
            "config_sha256": fingerprint(config), "errors": [],
            "engine_sha256": engine_fingerprint(),
            "results": [{**v, "passed": True, "errors": [], "scenarios": [{"id": s["id"], "passed": True} for s in config["scenarios"]]} for v in config["viewports"]]}
    (root / REPORT).parent.mkdir(parents=True, exist_ok=True)
    (root / REPORT).write_text(json.dumps(data), encoding="utf-8")


class ResponsiveTests(unittest.TestCase):
    def test_new_package_requires_actual_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = create_package(Path(tmp) / "new", "新Web原型")
            self.assertTrue(any(REPORT in e for e in validate_package(root)))

    def test_default_and_explicit_desktop(self):
        with tempfile.TemporaryDirectory() as tmp:
            web = create_package(Path(tmp) / "web", "默认Web")
            config = json.loads((web / "ui.schema.json").read_text(encoding="utf-8"))["responsive"]
            self.assertEqual([], validate_config(config))
            self.assertEqual({360, 390, 430, 1440}, {v["width"] for v in config["viewports"]})
            desktop = create_package(Path(tmp) / "desktop", "", {"intent": "桌面明确限定", "target_platform": "desktop"})
            desktop_config = json.loads((desktop / "ui.schema.json").read_text(encoding="utf-8"))["responsive"]
            self.assertEqual([], validate_config(desktop_config))
            self.assertEqual("desktop-only", desktop_config["mode"])

    def test_stale_html_and_config_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = create_package(Path(tmp) / "new", "验证证据绑定")
            evidence(root)
            self.assertEqual([], validate_package(root))
            html = root / "prototype.html"
            html.write_text(html.read_text(encoding="utf-8") + "<!-- changed -->", encoding="utf-8")
            self.assertTrue(any("过期" in e for e in validate_package(root)))
            evidence(root)
            ui = root / "ui.schema.json"
            payload = json.loads(ui.read_text(encoding="utf-8"))
            payload["responsive"]["scenarios"][0]["steps"][1]["value"] = "other"
            ui.write_text(json.dumps(payload), encoding="utf-8")
            self.assertTrue(any("过期" in e for e in validate_package(root)))

    def test_missing_viewport_and_unexecuted_flow_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = create_package(Path(tmp) / "new", "完整证据")
            evidence(root)
            p = root / REPORT
            report = json.loads(p.read_text(encoding="utf-8"))
            report["results"].pop()
            p.write_text(json.dumps(report), encoding="utf-8")
            self.assertTrue(any("视口" in e for e in validate_package(root)))
            evidence(root)
            report = json.loads(p.read_text(encoding="utf-8"))
            report["results"][0]["scenarios"] = []
            p.write_text(json.dumps(report), encoding="utf-8")
            self.assertTrue(any("场景" in e for e in validate_package(root)))

    def test_exclusion_and_inert_scenarios_are_rejected(self):
        config = json.loads((ROOT / "assets/prototype-package/ui.schema.json").read_text(encoding="utf-8"))["responsive"]
        invalid = copy.deepcopy(config)
        invalid["mode"] = "desktop-only"
        self.assertTrue(any("用户约束" in e for e in validate_config(invalid)))
        invalid = copy.deepcopy(config)
        invalid["scenarios"][0]["steps"] = [{"action": "expect_visible", "selector": "main"}]
        self.assertTrue(any("操作" in e for e in validate_config(invalid)))

    def test_old_engine_evidence_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = create_package(Path(tmp) / "new", "验收方法也须一致")
            evidence(root)
            p = root / REPORT
            report = json.loads(p.read_text(encoding="utf-8"))
            report["engine_sha256"] = "old-engine"
            p.write_text(json.dumps(report), encoding="utf-8")
            self.assertTrue(any("验收脚本" in e for e in validate_package(root)))


if __name__ == "__main__":
    unittest.main()
