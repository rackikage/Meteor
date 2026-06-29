"""Browser Bridge — live browser tab interaction via CDP."""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TabInfo:
    id: str
    title: str
    url: str
    active: bool
    loaded: bool


@dataclass
class BrowserConfig:
    browser_type: str = "chrome"
    cdp_port: int = 9222


class BrowserBridge:
    def __init__(self, config: Optional[BrowserConfig] = None) -> None:
        self.config = config or BrowserConfig()
        self._cdp_available: bool = False
        self._check_cdp()

    def _check_cdp(self) -> None:
        import urllib.request
        try:
            resp = urllib.request.urlopen(f"http://localhost:{self.config.cdp_port}/json/version", timeout=2)
            data = json.loads(resp.read())
            self._cdp_available = True
            logger.info("CDP available: %s", data.get("Browser", "unknown"))
        except Exception:
            self._cdp_available = False

    def list_tabs(self) -> list[TabInfo]:
        import urllib.request
        if not self._cdp_available:
            return []
        try:
            resp = urllib.request.urlopen(f"http://localhost:{self.config.cdp_port}/json", timeout=3)
            tabs = json.loads(resp.read())
            return [TabInfo(id=t.get("id", ""), title=t.get("title", ""), url=t.get("url", ""), active=True, loaded=True) for t in tabs]
        except Exception as e:
            logger.warning("Failed to list tabs: %s", e)
            return []

    def get_active_tab(self) -> Optional[TabInfo]:
        tabs = self.list_tabs()
        return tabs[0] if tabs else None

    def get_page_url(self) -> str:
        tab = self.get_active_tab()
        return tab.url if tab else ""

    def get_page_title(self) -> str:
        tab = self.get_active_tab()
        return tab.title if tab else ""

    def execute_js(self, script: str) -> Optional[str]:
        import urllib.request
        import websocket
        if not self._cdp_available:
            return None
        tabs = self.list_tabs()
        if not tabs:
            return None
        try:
            resp = urllib.request.urlopen(f"http://localhost:{self.config.cdp_port}/json/{tabs[0].id}", timeout=3)
            info = json.loads(resp.read())
            ws_url = info.get("webSocketDebuggerUrl", "")
            if not ws_url:
                return None
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
            ws.recv()
            ws.send(json.dumps({"id": 2, "method": "Runtime.evaluate", "params": {"expression": script, "returnByValue": True}}))
            result = json.loads(ws.recv())
            ws.close()
            if "result" in result and "result" in result["result"]:
                return result["result"]["result"].get("value")
            return None
        except Exception as e:
            logger.warning("CDP execute failed: %s", e)
            return None

    def get_page_text(self) -> str:
        return self.execute_js("document.body.innerText") or ""

    def get_page_html(self) -> str:
        return self.execute_js("document.documentElement.outerHTML") or ""

    def navigate(self, url: str) -> bool:
        self.execute_js(f"window.location.href = '{url}'")
        return True

    def fill_field(self, selector: str, value: str) -> bool:
        js = f"""document.querySelector('{selector}').value='{value}';document.querySelector('{selector}').dispatchEvent(new Event('input',{{bubbles:true}}));"""
        return self.execute_js(js) is not None

    def click_element(self, selector: str) -> bool:
        return self.execute_js(f"document.querySelector('{selector}').click()") is not None

    def launch_browser(self, headless: bool = False) -> bool:
        import shutil
        browser = shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("chrome")
        if not browser:
            logger.error("No Chrome/Chromium found")
            return False
        cmd = [browser, f"--remote-debugging-port={self.config.cdp_port}", "--no-first-run"]
        if headless:
            cmd.append("--headless")
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
        self._check_cdp()
        return self._cdp_available

    @property
    def connected(self) -> bool:
        return self._cdp_available
