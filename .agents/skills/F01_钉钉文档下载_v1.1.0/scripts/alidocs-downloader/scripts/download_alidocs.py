#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import pathlib
import posixpath
import random
import re
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from typing import Any, Callable


SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "docs.json"
CDP_TIMEOUT = 60.0


class WebSocketError(RuntimeError):
    pass


class TimeoutError(RuntimeError):
    pass


class MinimalWebSocket:
    """Small ws:// client for Chrome DevTools Protocol on localhost."""

    GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

    def __init__(self, url: str, timeout: float = 10.0) -> None:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme != "ws":
            raise WebSocketError(f"Only ws:// URLs are supported: {url}")

        self.url = url
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 80
        self.path = parsed.path or "/"
        if parsed.query:
            self.path += f"?{parsed.query}"

        self.sock = socket.create_connection((self.host, self.port), timeout=timeout)
        self.sock.settimeout(None)
        self._send_lock = threading.Lock()
        self._closed = False
        self._handshake()

    def _handshake(self) -> None:
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        host_header = f"{self.host}:{self.port}"
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {host_header}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            "Sec-WebSocket-Version: 13\r\n"
            "\r\n"
        ).encode("ascii")
        self.sock.sendall(request)

        response = bytearray()
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise WebSocketError("WebSocket handshake closed early.")
            response.extend(chunk)

        header_text = response.split(b"\r\n\r\n", 1)[0].decode("iso-8859-1")
        lines = header_text.split("\r\n")
        if not lines or " 101 " not in lines[0]:
            raise WebSocketError(f"WebSocket upgrade failed: {lines[0] if lines else header_text}")

        headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                headers[name.strip().lower()] = value.strip()
        expected = base64.b64encode(hashlib.sha1((key + self.GUID).encode("ascii")).digest()).decode("ascii")
        actual = headers.get("sec-websocket-accept")
        if actual != expected:
            raise WebSocketError("WebSocket accept key did not match.")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            self._send_frame(b"", opcode=0x8)
        except Exception:
            pass
        try:
            self.sock.close()
        except Exception:
            pass

    def send_text(self, text: str) -> None:
        self._send_frame(text.encode("utf-8"), opcode=0x1)

    def _send_frame(self, payload: bytes, opcode: int) -> None:
        with self._send_lock:
            if self._closed and opcode != 0x8:
                raise WebSocketError("WebSocket is closed.")

            first = 0x80 | opcode
            length = len(payload)
            if length < 126:
                header = struct.pack("!BB", first, 0x80 | length)
            elif length <= 0xFFFF:
                header = struct.pack("!BBH", first, 0x80 | 126, length)
            else:
                header = struct.pack("!BBQ", first, 0x80 | 127, length)

            mask = os.urandom(4)
            masked = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
            self.sock.sendall(header + mask + masked)

    def recv_text(self) -> str:
        parts: list[bytes] = []
        message_opcode: int | None = None

        while True:
            opcode, fin, payload = self._recv_frame()

            if opcode == 0x8:
                raise WebSocketError("WebSocket closed by peer.")
            if opcode == 0x9:
                self._send_frame(payload, opcode=0xA)
                continue
            if opcode == 0xA:
                continue

            if opcode in (0x1, 0x2):
                message_opcode = opcode
                parts = [payload]
            elif opcode == 0x0 and message_opcode is not None:
                parts.append(payload)
            else:
                continue

            if fin:
                data = b"".join(parts)
                if message_opcode == 0x1:
                    return data.decode("utf-8")
                return data.decode("utf-8", errors="replace")

    def _recv_frame(self) -> tuple[int, bool, bytes]:
        header = self._recv_exact(2)
        first, second = header[0], header[1]
        fin = bool(first & 0x80)
        opcode = first & 0x0F
        masked = bool(second & 0x80)
        length = second & 0x7F

        if length == 126:
            length = struct.unpack("!H", self._recv_exact(2))[0]
        elif length == 127:
            length = struct.unpack("!Q", self._recv_exact(8))[0]

        mask = self._recv_exact(4) if masked else b""
        payload = self._recv_exact(length) if length else b""
        if masked:
            payload = bytes(byte ^ mask[index % 4] for index, byte in enumerate(payload))
        return opcode, fin, payload

    def _recv_exact(self, length: int) -> bytes:
        data = bytearray()
        while len(data) < length:
            chunk = self.sock.recv(length - len(data))
            if not chunk:
                raise WebSocketError("WebSocket connection closed.")
            data.extend(chunk)
        return bytes(data)


class CdpSession:
    def __init__(self, ws: MinimalWebSocket) -> None:
        self.ws = ws
        self.next_id = 1
        self.pending: dict[int, dict[str, Any]] = {}
        self.events: list[dict[str, Any]] = []
        self.closed = False
        self.close_error: Exception | None = None
        self.condition = threading.Condition()
        self.reader = threading.Thread(target=self._read_loop, daemon=True)
        self.reader.start()

    @classmethod
    def connect(cls, ws_url: str) -> "CdpSession":
        return cls(MinimalWebSocket(ws_url))

    def _read_loop(self) -> None:
        try:
            while True:
                raw = self.ws.recv_text()
                message = json.loads(raw)
                with self.condition:
                    message_id = message.get("id")
                    if message_id in self.pending:
                        pending = self.pending.pop(message_id)
                        pending["message"] = message
                        pending["done"] = True
                    elif "method" in message:
                        self.events.append(message)
                    self.condition.notify_all()
        except Exception as error:
            with self.condition:
                self.closed = True
                self.close_error = error
                for pending in self.pending.values():
                    pending["done"] = True
                    pending["error"] = error
                self.pending.clear()
                self.condition.notify_all()

    def send(self, method: str, params: dict[str, Any] | None = None, timeout: float = CDP_TIMEOUT) -> dict[str, Any]:
        message_id = self.next_id
        self.next_id += 1
        payload = {"id": message_id, "method": method, "params": params or {}}
        pending: dict[str, Any] = {"done": False}
        with self.condition:
            self.pending[message_id] = pending

        try:
            self.ws.send_text(json.dumps(payload, separators=(",", ":")))
        except Exception:
            with self.condition:
                self.pending.pop(message_id, None)
            raise

        deadline = time.monotonic() + timeout
        with self.condition:
            while not pending["done"]:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self.pending.pop(message_id, None)
                    raise TimeoutError(f"Timed out waiting for CDP response: {method}")
                self.condition.wait(remaining)

        if "error" in pending:
            raise RuntimeError(str(pending["error"]))
        message = pending["message"]
        if "error" in message:
            raise RuntimeError(json.dumps(message["error"], ensure_ascii=False))
        return message.get("result", {})

    def wait_for_event(
        self,
        method: str,
        predicate: Callable[[dict[str, Any]], bool] | None = None,
        timeout: float = 30.0,
    ) -> dict[str, Any]:
        predicate = predicate or (lambda _event: True)
        deadline = time.monotonic() + timeout
        checked = 0

        with self.condition:
            while True:
                for event in self.events[checked:]:
                    if event.get("method") == method and safe_predicate(predicate, event):
                        return event
                checked = len(self.events)

                if self.closed:
                    raise RuntimeError(f"CDP session closed while waiting for {method}: {self.close_error}")

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError(f"Timed out waiting for {method}")
                self.condition.wait(remaining)

    def close(self) -> None:
        self.ws.close()
        with self.condition:
            self.closed = True
            self.condition.notify_all()


def safe_predicate(predicate: Callable[[dict[str, Any]], bool], event: dict[str, Any]) -> bool:
    try:
        return bool(predicate(event))
    except Exception:
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download an Alidocs/DingTalk spreadsheet through a logged-in Chrome session.",
    )
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to docs.json.")
    parser.add_argument("--doc", default="", help="Document key in the config file.")
    parser.add_argument("--output", default="", help="Output filename or absolute path.")
    parser.add_argument("--profile-dir", default="", help="Chrome profile directory. Overrides chromeProfileDir in config.")
    parser.add_argument("--download-dir", default="", help="Directory for relative --output paths. Overrides downloadDir in config.")
    parser.add_argument("--port", type=int, default=0, help="Chrome remote debugging port.")
    parser.add_argument("--no-launch", action="store_true", help="Use an already-running Chrome CDP instance.")
    parser.add_argument("--ready-timeout", type=int, default=30, help="Seconds to wait for the page before prompting.")
    parser.add_argument("--login-timeout", type=int, default=120, help="Seconds to wait after manual login.")
    parser.add_argument("--validate-only", action="store_true", help="Only validate the target xlsx file.")
    return parser.parse_args()


def read_json(path: pathlib.Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_from_project(value: str | None) -> pathlib.Path | None:
    if not value:
        return None
    path = pathlib.Path(value)
    if path.is_absolute():
        return path
    return (PROJECT_ROOT / path).resolve()


def http_get_json(url: str, timeout: float = 5.0) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "alidocs-python-downloader"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def chrome_candidates() -> list[pathlib.Path]:
    candidates = [
        os.environ.get("CHROME_PATH"),
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        str(pathlib.Path(os.environ.get("LOCALAPPDATA", "")) / r"Google\Chrome\Application\chrome.exe"),
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    ]
    return [pathlib.Path(candidate) for candidate in candidates if candidate and pathlib.Path(candidate).exists()]


def wait_for_chrome(port: int, timeout: float = 20.0) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return http_get_json(f"http://127.0.0.1:{port}/json/version", timeout=2.0)
        except Exception as error:
            last_error = error
            time.sleep(0.5)
    raise RuntimeError(f"Chrome CDP did not become ready on port {port}: {last_error}")


def ensure_chrome(port: int, profile_dir: pathlib.Path, initial_url: str, no_launch: bool) -> dict[str, Any]:
    try:
        return http_get_json(f"http://127.0.0.1:{port}/json/version", timeout=1.5)
    except Exception:
        if no_launch:
            raise RuntimeError(f"No Chrome CDP instance found on port {port}.")

    chrome_exe = chrome_candidates()[0] if chrome_candidates() else None
    if not chrome_exe:
        raise RuntimeError("Chrome or Edge executable was not found. Set CHROME_PATH if needed.")

    profile_dir.mkdir(parents=True, exist_ok=True)
    args = [
        str(chrome_exe),
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-first-run",
        "--disable-features=Translate",
        "--new-window",
        initial_url,
    ]

    creationflags = 0
    if os.name == "nt":
        creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    subprocess.Popen(
        args,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
    )
    print(f"Started Chrome with profile: {profile_dir}")
    return wait_for_chrome(port)


def list_targets(port: int) -> list[dict[str, Any]]:
    return http_get_json(f"http://127.0.0.1:{port}/json/list", timeout=5.0)


def get_or_create_page(browser: CdpSession, port: int, url: str) -> dict[str, Any]:
    targets = list_targets(port)
    existing = next(
        (target for target in targets if target.get("type") == "page" and "alidocs.dingtalk.com" in target.get("url", "")),
        None,
    )
    if existing:
        return existing

    result = browser.send("Target.createTarget", {"url": url})
    target_id = result["targetId"]
    for _attempt in range(30):
        targets = list_targets(port)
        target = next((item for item in targets if item.get("id") == target_id), None)
        if target:
            return target
        time.sleep(0.3)
    raise RuntimeError("Created a Chrome target, but could not resolve its page WebSocket URL.")


def evaluate(page: CdpSession, expression: str, timeout: float = CDP_TIMEOUT) -> Any:
    result = page.send(
        "Runtime.evaluate",
        {"expression": expression, "returnByValue": True, "awaitPromise": True},
        timeout=timeout,
    )
    if "exceptionDetails" in result:
        raise RuntimeError(result["exceptionDetails"].get("text", "Runtime.evaluate failed"))
    return result.get("result", {}).get("value")


def page_snapshot(page: CdpSession) -> dict[str, Any]:
    return evaluate(
        page,
        """(() => ({
          title: document.title,
          url: location.href,
          text: document.body ? document.body.innerText.slice(0, 5000) : ''
        }))()""",
    )


def wait_for_document_ready(page: CdpSession, doc_name: str, timeout: float) -> dict[str, Any] | None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        snapshot = page_snapshot(page)
        text = snapshot.get("text") or ""
        title = snapshot.get("title") or ""
        url = snapshot.get("url") or ""
        has_toolbar = "菜单" in text or "Menu" in text
        has_doc_hint = doc_name in text or doc_name in title or "spreadsheet" in url
        if has_toolbar and has_doc_hint:
            return snapshot
        time.sleep(1.0)
    return None


def prompt_for_login_if_possible() -> None:
    if not sys.stdin.isatty():
        return
    input("If the page needs login, complete it in Chrome, then press Enter here to continue...")


def js_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def element_box(page: CdpSession, needle: str, constraints: dict[str, Any] | None = None) -> dict[str, Any]:
    constraints = constraints or {}
    expression = f"""(() => {{
      const needle = {js_json(needle)};
      const constraints = {js_json(constraints)};
      const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
      const interactiveSelector = [
        'button',
        'a',
        '[role="button"]',
        '.wd3-toolbar-item',
        '.wd3-listitem',
        '.wd3-button',
        '.wd3-icon-button'
      ].join(',');
      const clickableAncestor = (element) => {{
        let current = element;
        for (let depth = 0; current && depth < 6; depth += 1) {{
          if (current.matches && current.matches(interactiveSelector)) return current;
          current = current.parentElement;
        }}
        return element;
      }};
      const visible = (rect, style) =>
        rect.width > 0 && rect.height > 0 &&
        style.display !== 'none' && style.visibility !== 'hidden' &&
        rect.x >= (constraints.minX ?? -Infinity) &&
        rect.y >= (constraints.minY ?? -Infinity) &&
        rect.x <= (constraints.maxX ?? Infinity) &&
        rect.y <= (constraints.maxY ?? Infinity);

      const candidates = [];
      for (const element of document.querySelectorAll('*')) {{
        const text = normalize(element.innerText || element.textContent);
        const aria = normalize(element.getAttribute('aria-label'));
        const title = normalize(element.getAttribute('title'));
        const haystack = text || aria || title;
        if (!haystack) continue;

        const exact = haystack === needle;
        const starts = haystack.startsWith(needle);
        const includes = haystack.includes(needle);
        if (!exact && !starts && !includes) continue;

        const target = clickableAncestor(element);
        const rect = target.getBoundingClientRect();
        const style = getComputedStyle(target);
        if (!visible(rect, style)) continue;

        const lengthScore = haystack.length;
        const matchScore = exact ? 0 : starts ? 10 : 20;
        const areaScore = rect.width * rect.height / 10000;
        candidates.push({{
          text: haystack.slice(0, 120),
          x: rect.x,
          y: rect.y,
          w: rect.width,
          h: rect.height,
          cx: rect.x + rect.width / 2,
          cy: rect.y + rect.height / 2,
          score: matchScore + lengthScore / 100 + areaScore
        }});
      }}
      candidates.sort((a, b) => a.score - b.score);
      return candidates[0] || null;
    }})()"""

    box = evaluate(page, expression)
    if not box:
        raise RuntimeError(f'Could not find visible element containing "{needle}".')
    return box


def move_mouse(page: CdpSession, x: float, y: float) -> None:
    page.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y, "button": "none"})


def dispatch_text_mouse(
    page: CdpSession,
    needle: str,
    constraints: dict[str, Any] | None = None,
    action: str = "click",
) -> dict[str, Any]:
    constraints = constraints or {}
    events = (
        ["pointerover", "mouseover", "pointerenter", "mouseenter", "mousemove"]
        if action == "hover"
        else ["pointerover", "mouseover", "mousemove", "pointerdown", "mousedown", "pointerup", "mouseup", "click"]
    )
    expression = f"""(() => {{
      const needle = {js_json(needle)};
      const constraints = {js_json(constraints)};
      const events = {js_json(events)};
      const action = {js_json(action)};
      const normalize = (value) => String(value || '').replace(/\\s+/g, ' ').trim();
      const interactiveSelector = [
        'button',
        'a',
        '[role="button"]',
        '.wd3-toolbar-item',
        '.wd3-listitem',
        '.wd3-button',
        '.wd3-icon-button'
      ].join(',');
      const clickableAncestor = (element) => {{
        let current = element;
        for (let depth = 0; current && depth < 6; depth += 1) {{
          if (current.matches && current.matches(interactiveSelector)) return current;
          current = current.parentElement;
        }}
        return element;
      }};
      const visible = (rect, style) =>
        rect.width > 0 && rect.height > 0 &&
        style.display !== 'none' && style.visibility !== 'hidden' &&
        rect.x >= (constraints.minX ?? -Infinity) &&
        rect.y >= (constraints.minY ?? -Infinity) &&
        rect.x <= (constraints.maxX ?? Infinity) &&
        rect.y <= (constraints.maxY ?? Infinity);

      const candidates = [];
      for (const element of document.querySelectorAll('*')) {{
        const text = normalize(element.innerText || element.textContent);
        const aria = normalize(element.getAttribute('aria-label'));
        const title = normalize(element.getAttribute('title'));
        const haystack = text || aria || title;
        if (!haystack) continue;

        const exact = haystack === needle;
        const starts = haystack.startsWith(needle);
        const includes = haystack.includes(needle);
        if (!exact && !starts && !includes) continue;

        const target = clickableAncestor(element);
        const rect = target.getBoundingClientRect();
        const style = getComputedStyle(target);
        if (!visible(rect, style)) continue;

        const lengthScore = haystack.length;
        const matchScore = exact ? 0 : starts ? 10 : 20;
        const areaScore = rect.width * rect.height / 10000;
        candidates.push({{
          target,
          text: haystack.slice(0, 120),
          x: rect.x,
          y: rect.y,
          w: rect.width,
          h: rect.height,
          cx: rect.x + rect.width / 2,
          cy: rect.y + rect.height / 2,
          score: matchScore + lengthScore / 100 + areaScore
        }});
      }}

      candidates.sort((a, b) => a.score - b.score);
      const chosen = candidates[0];
      if (!chosen) return null;

      const eventInit = (type) => ({{
        bubbles: !['mouseenter', 'pointerenter'].includes(type),
        cancelable: true,
        composed: true,
        view: window,
        clientX: chosen.cx,
        clientY: chosen.cy,
        screenX: chosen.cx,
        screenY: chosen.cy,
        button: 0,
        buttons: ['pointerdown', 'mousedown'].includes(type) ? 1 : 0,
        pointerId: 1,
        pointerType: 'mouse',
        isPrimary: true
      }});

      const pointTarget = (
        chosen.cx >= 0 && chosen.cy >= 0 &&
        chosen.cx <= window.innerWidth && chosen.cy <= window.innerHeight
      ) ? document.elementFromPoint(chosen.cx, chosen.cy) : null;
      const dispatchRoot = pointTarget || chosen.target;

      const targets = [dispatchRoot];
      if (action === 'hover') {{
        let current = dispatchRoot.parentElement;
        for (let depth = 0; current && depth < 5; depth += 1) {{
          targets.push(current);
          current = current.parentElement;
        }}
      }}

      for (const eventTarget of targets) {{
        for (const type of events) {{
          const Ctor = type.startsWith('pointer') && window.PointerEvent ? window.PointerEvent : window.MouseEvent;
          eventTarget.dispatchEvent(new Ctor(type, eventInit(type)));
        }}
      }}

      return {{
        text: chosen.text,
        x: chosen.x,
        y: chosen.y,
        w: chosen.w,
        h: chosen.h,
        cx: chosen.cx,
        cy: chosen.cy
      }};
    }})()"""

    box = evaluate(page, expression)
    if not box:
        raise RuntimeError(f'Could not find element containing "{needle}".')
    if box.get("cx", -1) >= 0 and box.get("cy", -1) >= 0:
        try:
            move_mouse(page, box["cx"], box["cy"])
        except Exception:
            pass
    return box


def hover_text(page: CdpSession, text: str, constraints: dict[str, Any] | None = None) -> dict[str, Any]:
    return dispatch_text_mouse(page, text, constraints, action="hover")


def click_text(page: CdpSession, text: str, constraints: dict[str, Any] | None = None) -> dict[str, Any]:
    return dispatch_text_mouse(page, text, constraints, action="click")


def has_element(page: CdpSession, text: str, constraints: dict[str, Any] | None = None) -> bool:
    try:
        element_box(page, text, constraints)
        return True
    except Exception:
        return False


def trigger_excel_download(page: CdpSession) -> None:
    top_menu_constraints = {"minX": 0, "maxX": 250, "minY": 100, "maxY": 190}
    menu_open = has_element(page, "表格", top_menu_constraints)
    if not menu_open:
        menu_box = click_text(page, "菜单", {"minX": 0, "maxX": 130, "minY": 45, "maxY": 130})
        print(f"Clicked menu at ({round(menu_box['cx'])}, {round(menu_box['cy'])})")
        time.sleep(0.7)
        menu_open = has_element(page, "表格", top_menu_constraints)
    if not menu_open:
        menu_box = click_text(page, "菜单", {"minX": 0, "maxX": 130, "minY": 45, "maxY": 130})
        print(f"Clicked menu retry at ({round(menu_box['cx'])}, {round(menu_box['cy'])})")
        time.sleep(0.7)

    table_box = hover_text(page, "表格", top_menu_constraints)
    print(f"Hovered table menu at ({round(table_box['cx'])}, {round(table_box['cy'])})")
    time.sleep(0.5)

    download_as_box = hover_text(page, "下载为")
    print(f"Hovered download-as at ({round(download_as_box['cx'])}, {round(download_as_box['cy'])})")
    time.sleep(0.5)

    excel_box = click_text(page, "Excel")
    print(f"Clicked Excel export at ({round(excel_box['cx'])}, {round(excel_box['cy'])})")


def download_file(url: str, output_path: pathlib.Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(output_path.name + ".part")
    if temp_path.exists():
        temp_path.unlink()

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 alidocs-python-downloader",
            "Accept": "*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response, temp_path.open("wb") as handle:
        shutil.copyfileobj(response, handle)

    if output_path.exists():
        output_path.unlink()
    temp_path.replace(output_path)


def column_number(column_letters: str) -> int:
    value = 0
    for letter in column_letters:
        value = value * 26 + ord(letter) - 64
    return value


def normalize_sheet_target(target: str) -> str:
    target = target.replace("\\", "/")
    if target.startswith("/"):
        return posixpath.normpath(target.lstrip("/"))
    if target.startswith("xl/"):
        return posixpath.normpath(target)
    return posixpath.normpath(posixpath.join("xl", target))


def validate_xlsx(xlsx_path: pathlib.Path, expected_sheets: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    expected_sheets = expected_sheets or []
    if not xlsx_path.exists() or xlsx_path.stat().st_size <= 0:
        raise RuntimeError(f"Output file does not exist or is empty: {xlsx_path}")

    with zipfile.ZipFile(xlsx_path) as archive:
        workbook_xml = archive.read("xl/workbook.xml")
        rels_xml = archive.read("xl/_rels/workbook.xml.rels")
        workbook = ET.fromstring(workbook_xml)
        rels = ET.fromstring(rels_xml)

        rel_map = {
            rel.attrib["Id"]: rel.attrib["Target"]
            for rel in rels
            if "Id" in rel.attrib and "Target" in rel.attrib
        }

        sheets: list[dict[str, Any]] = []
        rel_id_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        for sheet in workbook.findall(".//{http://schemas.openxmlformats.org/spreadsheetml/2006/main}sheet"):
            name = sheet.attrib.get("name", "")
            rel_id = sheet.attrib.get(rel_id_attr, "")
            target = normalize_sheet_target(rel_map.get(rel_id, ""))
            xml = archive.read(target).decode("utf-8", errors="replace")
            row_numbers = [int(match.group(1)) for match in re.finditer(r'<row\b[^>]*\br="(\d+)"', xml)]
            cell_refs = list(re.finditer(r'<c\b[^>]*\br="([A-Z]+)(\d+)"', xml))
            max_row = max([0, *row_numbers, *[int(match.group(2)) for match in cell_refs]])
            max_col = max([0, *[column_number(match.group(1)) for match in cell_refs]])
            sheets.append({"name": name, "rows": max_row, "cols": max_col})

    for expected in expected_sheets:
        expected_name = expected.get("name")
        sheet = next((item for item in sheets if item["name"] == expected_name), None)
        if not sheet:
            raise RuntimeError(f"Expected sheet was not found: {expected_name}")
        min_rows = int(expected.get("minRows") or 0)
        min_cols = int(expected.get("minCols") or 0)
        if min_rows and sheet["rows"] < min_rows:
            raise RuntimeError(f"Sheet {expected_name} has {sheet['rows']} rows, expected at least {min_rows}.")
        if min_cols and sheet["cols"] < min_cols:
            raise RuntimeError(f"Sheet {expected_name} has {sheet['cols']} cols, expected at least {min_cols}.")

    return sheets


def is_export_download(event: dict[str, Any]) -> bool:
    params = event.get("params") or {}
    url = params.get("url") or ""
    filename = (params.get("suggestedFilename") or "").lower()
    return "/export/tempres/" in url or filename.endswith((".xlsx", ".xls"))


def find_recent_xlsx(download_dir: pathlib.Path, started_at: float) -> pathlib.Path | None:
    if not download_dir.exists():
        return None
    candidates = [
        path
        for path in download_dir.glob("*.xlsx")
        if path.is_file() and path.stat().st_mtime >= started_at - 2 and not path.name.endswith(".crdownload")
    ]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def output_path_for(args: argparse.Namespace, config: dict[str, Any], doc_name: str, doc: dict[str, Any]) -> pathlib.Path:
    download_dir = resolve_from_project(args.download_dir or config.get("downloadDir") or "../outputs")
    assert download_dir is not None
    if args.output:
        output_arg = pathlib.Path(args.output)
        return output_arg if output_arg.is_absolute() else (download_dir / output_arg).resolve()
    return (download_dir / (doc.get("outputFile") or f"{doc_name}.xlsx")).resolve()


def run() -> int:
    args = parse_args()
    config_path = pathlib.Path(args.config).resolve()
    config = read_json(config_path)
    documents = config.get("documents") or {}
    doc_name = args.doc or config.get("defaultDocument") or next(iter(documents), "")
    doc = documents.get(doc_name)
    if not doc:
        raise RuntimeError(f'Document "{doc_name}" was not found in {config_path}.')

    output_path = output_path_for(args, config, doc_name, doc)
    if args.validate_only:
        sheets = validate_xlsx(output_path, doc.get("expectedSheets") or [])
        print(f"Validated: {output_path}")
        for sheet in sheets:
            print(f"- {sheet['name']}: {sheet['rows']} rows x {sheet['cols']} cols")
        return 0

    port = int(args.port or config.get("chromeDebugPort") or 9222)
    profile_dir = resolve_from_project(args.profile_dir or config.get("chromeProfileDir") or "../.tmp/alidocs-chrome-profile")
    download_dir = resolve_from_project(args.download_dir or config.get("downloadDir") or "../outputs")
    assert profile_dir is not None and download_dir is not None
    download_dir.mkdir(parents=True, exist_ok=True)

    print(f"Document: {doc_name}")
    print(f"Output: {output_path}")
    version = ensure_chrome(port, profile_dir, doc["url"], args.no_launch)
    browser = CdpSession.connect(version["webSocketDebuggerUrl"])

    try:
        browser.send(
            "Browser.setDownloadBehavior",
            {"behavior": "allow", "downloadPath": str(download_dir), "eventsEnabled": True},
        )
        target = get_or_create_page(browser, port, doc["url"])
        page = CdpSession.connect(target["webSocketDebuggerUrl"])

        try:
            page.send("Runtime.enable")
            page.send("Page.enable")
            page.send("Page.navigate", {"url": doc["url"]})
            time.sleep(2.0)

            ready = wait_for_document_ready(page, doc_name, args.ready_timeout)
            if not ready:
                print("The document is not ready yet. Login may be required in the Chrome window.")
                prompt_for_login_if_possible()
                ready = wait_for_document_ready(page, doc_name, args.login_timeout)
            if not ready:
                raise RuntimeError("Timed out waiting for the Alidocs spreadsheet page.")

            print(f"Page ready: {ready.get('title')}")
            started_at = time.time()
            trigger_excel_download(page)

            try:
                will_begin = browser.wait_for_event("Browser.downloadWillBegin", is_export_download, timeout=90.0)
            except TimeoutError:
                fallback = find_recent_xlsx(download_dir, started_at)
                if not fallback:
                    raise
                if fallback.resolve() != output_path:
                    shutil.copy2(fallback, output_path)
                print(f"Used Chrome-downloaded fallback: {fallback}")
            else:
                params = will_begin.get("params") or {}
                print(f"Export generated: {params.get('suggestedFilename')}")
                try:
                    browser.wait_for_event(
                        "Browser.downloadProgress",
                        lambda event: (event.get("params") or {}).get("guid") == params.get("guid")
                        and (event.get("params") or {}).get("state") in {"completed", "canceled"},
                        timeout=30.0,
                    )
                except TimeoutError:
                    pass
                download_file(params["url"], output_path)

            stats = output_path.stat()
            sheets = validate_xlsx(output_path, doc.get("expectedSheets") or [])
            print(f"Saved: {output_path}")
            print(f"Bytes: {stats.st_size}")
            print("Sheets:")
            for sheet in sheets:
                print(f"- {sheet['name']}: {sheet['rows']} rows x {sheet['cols']} cols")
        finally:
            page.close()
    finally:
        browser.close()

    return 0


def main() -> None:
    try:
        raise SystemExit(run())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
