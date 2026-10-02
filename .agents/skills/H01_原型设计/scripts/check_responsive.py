"""Serve a local prototype package and verify declared flows in real Chromium."""
import argparse
from datetime import datetime, timezone
import hashlib
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

from responsive_contract import REPORT, fingerprint, validate_config, engine_fingerprint

LAYOUT_CHECK = """viewport => {
 const {mobile,width,height}=viewport;
 const errors=[];
 const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
 if(document.documentElement.scrollWidth>width+1||innerWidth>width+1)errors.push('页面横向溢出或手机布局视口被扩张');
 const meta=document.querySelector('meta[name=viewport]')?.content||'';
 if(!meta.includes('width=device-width')||/user-scalable\\s*=\\s*no|maximum-scale\\s*=\\s*1(?:\\D|$)/i.test(meta))errors.push('viewport缺失或禁止缩放');
 for(const e of document.querySelectorAll('dialog[open],[role=dialog]')){
  if(!visible(e))continue;const r=e.getBoundingClientRect();
  if(r.left<-1||r.right>width+1||r.top<-1||r.bottom>height+1)errors.push('可见弹窗超出视口');
 }
 if(mobile){
  for(const e of document.querySelectorAll('button,a[href],input:not([type=hidden]),select,textarea,[role=button]')){
   if(!visible(e)||e.disabled||e.closest('[inert]'))continue;
   const dialog=document.querySelector('dialog[open]');if(dialog&&!e.closest('dialog[open]'))continue;
   let target=e;
   if(e.matches('input[type=checkbox],input[type=radio]'))target=e.labels?.[0]||e;
   const r=target.getBoundingClientRect();
   if(r.width<43.5||r.height<43.5)errors.push('触达区不足44px: '+(e.id||e.tagName));
   if(e.matches('input:not([type=checkbox]):not([type=radio]),select,textarea')&&parseFloat(getComputedStyle(e).fontSize)<16)errors.push('输入字号小于16px: '+(e.id||e.tagName));
  }
 }
 return [...new Set(errors)];
}"""


def run(root):
    config = json.loads((root / "ui.schema.json").read_text(encoding="utf-8")).get("responsive")
    errors = validate_config(config)
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "status": "failed", "passed": False,
              "prototype_sha256": hashlib.sha256((root / "prototype.html").read_bytes()).hexdigest(),
              "config_sha256": fingerprint(config), "results": [], "errors": errors,
              "engine_sha256": engine_fingerprint(),
              "scope": "本地自包含HTML、Chromium视口/触摸模拟；不代表iOS、软键盘或真机验收"}
    if errors:
        return report
    try:
        from playwright.sync_api import sync_playwright, expect
    except ImportError:
        report.update(status="not_run", errors=["缺少Playwright，响应式浏览器验收未执行"])
        return report
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def log_message(self, *args):
            pass
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    screenshots = root / "evaluation" / "responsive"
    screenshots.mkdir(parents=True, exist_ok=True)
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            report["browser_version"] = browser.version
            try:
                for port in config["viewports"]:
                    mobile = config["mode"] == "adaptive" and port["width"] <= config.get("mobile_breakpoint", 700)
                    context = browser.new_context(viewport=port, is_mobile=mobile, has_touch=mobile)
                    result = {**port, "passed": False, "scenarios": [], "errors": []}
                    report["results"].append(result)
                    try:
                        for index, scenario in enumerate(config["scenarios"]):
                            page = context.new_page()
                            page.set_default_timeout(5000)
                            js_errors = []
                            page.on("pageerror", lambda e: js_errors.append(str(e)))
                            try:
                                # No remote URLs, external APIs, fonts or CDN scripts in this isolated runner.
                                page.route("**/*", lambda route: route.continue_() if route.request.url.startswith(base + "/") else route.abort())
                                page.goto(base + "/prototype.html")
                                result["errors"].extend(page.evaluate(LAYOUT_CHECK, {**port, "mobile": mobile}))
                                page.screenshot(path=str(screenshots / f'{port["width"]}-{index}-initial.png'), full_page=True)
                                for step in scenario["steps"]:
                                    target = page.locator(step["selector"])
                                    action = step["action"]
                                    if action == "click":
                                        target.scroll_into_view_if_needed()
                                        unobscured = target.evaluate("e=>{const r=e.getBoundingClientRect(),hit=document.elementFromPoint(r.x+r.width/2,r.y+r.height/2);return hit===e||e.contains(hit)}")
                                        if not unobscured:
                                            raise AssertionError("关键操作被固定栏或弹层遮挡: " + step["selector"])
                                        target.click()
                                    elif action == "fill":
                                        target.fill(step["value"])
                                    elif action == "select":
                                        target.select_option(step["value"])
                                    elif action == "expect_visible":
                                        expect(target).to_be_visible()
                                    else:
                                        expect(target).to_contain_text(step["value"])
                                    result["errors"].extend(page.evaluate(LAYOUT_CHECK, {**port, "mobile": mobile}))
                                result["errors"].extend(js_errors)
                                result["scenarios"].append({"id": scenario["id"], "passed": not js_errors})
                                page.screenshot(path=str(screenshots / f'{port["width"]}-{index}-final.png'), full_page=True)
                            except Exception as exc:
                                result["errors"].append(str(exc))
                                result["scenarios"].append({"id": scenario["id"], "passed": False})
                            finally:
                                page.close()
                        result["errors"] = list(dict.fromkeys(result["errors"]))
                        result["passed"] = not result["errors"] and all(s["passed"] for s in result["scenarios"])
                    finally:
                        context.close()
            finally:
                browser.close()
    except Exception as exc:
        report["errors"].append(str(exc))
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
    report["passed"] = not report["errors"] and len(report["results"]) == len(config["viewports"]) and all(r["passed"] for r in report["results"])
    report["status"] = "passed" if report["passed"] else "failed"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package_dir")
    args = parser.parse_args()
    root = Path(args.package_dir).resolve()
    try:
        report = run(root)
    except (OSError, ValueError) as exc:
        report = {"status": "failed", "passed": False, "errors": [str(exc)]}
    target = root / REPORT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "status": report["status"], "report": str(target)}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
