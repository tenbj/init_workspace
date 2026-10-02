"""Real-browser positive/negative cases; all fixtures and evidence go to caller output."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from check_responsive import run
from create_package import create_package
from responsive_contract import REPORT
from validate_package import validate_package


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    output = Path(parser.parse_args().output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for name in ["adaptive", "desktop-only", "wide-layout", "small-target", "covered-action", "broken-flow"]:
        payload = {"intent": "验证用户明确的桌面原型", "target_platform": "desktop"} if name == "desktop-only" else None
        package = create_package(output / name, "响应式回归合成原型", payload)
        html = package / "prototype.html"
        text = html.read_text(encoding="utf-8")
        if name == "wide-layout":
            text = text.replace("</style>", "main{min-width:1200px}</style>")
        elif name == "small-target":
            text = text.replace("</style>", "button{min-width:0;min-height:0;width:20px;height:20px;padding:0}</style>")
        elif name == "covered-action":
            text = text.replace("</body>", '<div style="position:fixed;inset:0;z-index:999;background:#fff"></div></body>')
        elif name == "broken-flow":
            text = text.replace("= 'completed'", "= 'unchanged'")
        html.write_text(text, encoding="utf-8")
        report = run(package)
        p = package / REPORT
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        expected = name in {"adaptive", "desktop-only"}
        assert report["passed"] is expected, (name, report)
        errors = validate_package(package, require_responsive=True)
        assert bool(errors) is (not expected), (name, errors)
        results.append({"case": name, "expected_browser_pass": expected, "browser_pass": report["passed"], "gate_rejected": bool(errors), "correct": True})
        print("PASS: " + name, flush=True)
        if name == "adaptive":
            html.write_text(text + "<!-- changed after validation -->", encoding="utf-8")
            assert any("过期" in e for e in validate_package(package, require_responsive=True))
            html.write_text(text, encoding="utf-8")
            results.append({"case": "stale-evidence", "gate_rejected": True, "correct": True})
    summary = {"passed": True, "kind": "real-local-chromium-positive-negative", "cases": results}
    (output / "regression-report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("responsive_regression=ok")


if __name__ == "__main__":
    main()
