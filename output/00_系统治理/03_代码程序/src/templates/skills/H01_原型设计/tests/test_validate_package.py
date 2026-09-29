import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from validate_package import validate_package


def write_text(root: Path, relative: str, content: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(root: Path, relative: str, payload: object) -> None:
    write_text(root, relative, json.dumps(payload, ensure_ascii=False, indent=2))


def build_valid_package(root: Path) -> None:
    write_json(
        root,
        "manifest.json",
        {
            "asoc_version": "1.0.0",
            "intent": "验证订单详情原型",
            "artifacts": [
                {"id": "prd", "path": "prd.md", "layer": "human"},
                {"id": "prototype", "path": "prototype.html", "layer": "human"},
                {"id": "ui", "path": "ui.schema.json", "layer": "machine"},
                {"id": "interaction", "path": "interaction.json", "layer": "machine"},
                {"id": "flow", "path": "user-flow.md", "layer": "human"},
                {"id": "api", "path": "api.yaml", "layer": "machine"},
                {"id": "database", "path": "database.sql", "layer": "machine"},
                {"id": "evaluation", "path": "evaluation/report.json", "layer": "evaluation"},
            ],
        },
    )
    write_text(root, "prd.md", "# PRD\n\n## REQ-001\n用户可取消待支付订单。\n")
    write_text(
        root,
        "prototype.html",
        '<!doctype html><button data-event-id="cancel_order">取消订单</button>'
        "<script>document.querySelector('[data-event-id=\"cancel_order\"]')"
        ".addEventListener('click', () => {});</script>",
    )
    write_json(
        root,
        "ui.schema.json",
        {
            "schema_version": "1.0.0",
            "page": {"id": "order_detail", "states": ["pending", "cancelled"]},
            "components": [
                {
                    "id": "cancel_button",
                    "type": "button",
                    "states": ["enabled", "disabled"],
                    "events": ["cancel_order"],
                }
            ],
        },
    )
    write_json(
        root,
        "interaction.json",
        {
            "schema_version": "1.0.0",
            "interactions": [
                {
                    "id": "cancel_order",
                    "component_id": "cancel_button",
                    "trigger": "click",
                    "from_state": "pending",
                    "to_state": "cancelled",
                    "action": "POST /orders/{id}/cancel",
                }
            ],
        },
    )
    write_text(root, "user-flow.md", "# User Flow\n\nSTART -> order_detail -> END\n")
    write_text(
        root,
        "api.yaml",
        "openapi: 3.0.3\npaths:\n  /orders/{id}/cancel:\n    post:\n"
        "      responses:\n        '200': {description: cancelled}\n"
        "        '409': {description: invalid state}\n",
    )
    write_text(root, "database.sql", "CREATE TABLE orders (id BIGINT, status VARCHAR(20));\n")


class ValidatePackageTests(unittest.TestCase):
    def test_valid_package_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_valid_package(root)
            self.assertEqual([], validate_package(root))

    def test_missing_required_artifact_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_valid_package(root)
            (root / "prd.md").unlink()
            errors = validate_package(root)
            self.assertTrue(any("prd.md" in error for error in errors))

    def test_undefined_interaction_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_valid_package(root)
            ui = json.loads((root / "ui.schema.json").read_text(encoding="utf-8"))
            ui["components"][0]["events"] = ["unknown_event"]
            write_json(root, "ui.schema.json", ui)
            errors = validate_package(root)
            self.assertTrue(any("unknown_event" in error for error in errors))

    def test_button_without_event_binding_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_valid_package(root)
            write_text(root, "prototype.html", "<!doctype html><button>取消订单</button>")
            errors = validate_package(root)
            self.assertTrue(any("button" in error.lower() for error in errors))

    def test_event_id_without_javascript_binding_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_valid_package(root)
            write_text(
                root,
                "prototype.html",
                '<!doctype html><button data-event-id="cancel_order">取消订单</button>',
            )
            errors = validate_package(root)
            self.assertTrue(any("JavaScript" in error for error in errors))

    def test_manifest_must_register_evaluation_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_valid_package(root)
            manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            manifest["artifacts"] = [
                item for item in manifest["artifacts"] if item["path"] != "evaluation/report.json"
            ]
            write_json(root, "manifest.json", manifest)
            errors = validate_package(root)
            self.assertTrue(any("evaluation/report.json" in error for error in errors))

    def test_fake_openapi_tokens_do_not_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            build_valid_package(root)
            write_text(
                root,
                "api.yaml",
                "note: 'openapi: paths: responses:'\nerror: '400:'\n",
            )
            errors = validate_package(root)
            self.assertTrue(any("api.yaml" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
