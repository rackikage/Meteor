"""UI Automation — AppleScript, Accessibility API, GUI interaction."""

from __future__ import annotations

import base64
import logging
import os
import re
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class Platform(Enum):
    MACOS = "macos"
    LINUX = "linux"
    UNKNOWN = "unknown"


class UIAutomation:
    def __init__(self) -> None:
        self._platform = self._detect_platform()

    def _detect_platform(self) -> Platform:
        if os.uname().sysname == "Darwin":
            return Platform.MACOS
        elif os.uname().sysname == "Linux":
            return Platform.LINUX
        return Platform.UNKNOWN

    def osascript(self, script: str) -> str:
        if self._platform != Platform.MACOS:
            raise RuntimeError("osascript only available on macOS")
        result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"osascript failed: {result.stderr}")
        return result.stdout.strip()

    def tell_app(self, app_name: str, command: str) -> str:
        return self.osascript(f'tell application "{app_name}"\n{command}\nend tell')

    def open_app(self, app_name_or_path: str) -> bool:
        if self._platform == Platform.MACOS:
            self.tell_app(app_name_or_path, "activate")
            return True
        try:
            subprocess.run(["open", "-a", app_name_or_path], capture_output=True, timeout=10)
            return True
        except Exception:
            return False

    def quit_app(self, app_name: str) -> bool:
        if self._platform == Platform.MACOS:
            self.tell_app(app_name, "quit")
            return True
        return False

    def get_running_apps(self) -> list[str]:
        if self._platform == Platform.MACOS:
            output = self.osascript('tell application "System Events" to get name of every process whose background only is false')
            return [a.strip() for a in output.split(",")]
        return []

    def get_frontmost_app(self) -> Optional[str]:
        if self._platform == Platform.MACOS:
            return self.osascript('tell application "System Events" to get name of first process whose frontmost is true')
        return None

    def click(self, x: int, y: int) -> bool:
        if self._platform == Platform.MACOS:
            self.osascript(f'tell application "System Events" to click at {{{x}, {y}}}')
            return True
        elif self._platform == Platform.LINUX:
            subprocess.run(["xdotool", "mousemove", str(x), str(y), "click", "1"], capture_output=True, timeout=5)
            return True
        return False

    def type_text(self, text: str) -> bool:
        escaped = text.replace('"', '\\"')
        if self._platform == Platform.MACOS:
            self.osascript(f'tell application "System Events" to keystroke "{escaped}"')
            return True
        elif self._platform == Platform.LINUX:
            subprocess.run(["xdotool", "type", "--", text], capture_output=True, timeout=10)
            return True
        return False

    def press_key(self, key: str, modifiers: Optional[list[str]] = None) -> bool:
        key_map = {"return": "return", "tab": "tab", "escape": "escape", "up": "up-arrow", "down": "down-arrow", "left": "left-arrow", "right": "right-arrow", "delete": "delete", "backspace": "delete", "enter": "return"}
        mapped = key_map.get(key, key)
        if self._platform == Platform.MACOS:
            mod_clause = f" using {{{', '.join(modifiers or [])}}}" if modifiers else ""
            self.osascript(f'tell application "System Events" to keystroke "{mapped}"{mod_clause}')
            return True
        elif self._platform == Platform.LINUX:
            mod_map = {"command": "super", "option": "alt", "shift": "shift", "control": "ctrl"}
            mods = "+".join(mod_map.get(m, m) for m in (modifiers or []))
            key_spec = f"{mods}+{key}" if mods else key
            subprocess.run(["xdotool", "key", key_spec], capture_output=True, timeout=5)
            return True
        return False

    def get_selected_text(self) -> str:
        if self._platform == Platform.MACOS:
            return self.osascript('tell application "System Events" to get selection')
        return ""

    def paste_text(self, text: str) -> bool:
        import json
        subprocess.run("pbcopy" if self._platform == Platform.MACOS else "xclip -selection clipboard", shell=True, input=text.encode(), capture_output=True, timeout=5)
        time.sleep(0.1)
        return self.press_key("v", modifiers=["command" if self._platform == Platform.MACOS else "control"])

    def screenshot(self, path: Optional[str] = None) -> str:
        if not path:
            fd, path = tempfile.mkstemp(suffix=".png")
            os.close(fd)
        if self._platform == Platform.MACOS:
            subprocess.run(["screencapture", "-x", path], capture_output=True, timeout=10)
        elif self._platform == Platform.LINUX:
            subprocess.run(["gnome-screenshot", "-f", path], capture_output=True, timeout=10)
        return path

    def screenshot_base64(self) -> str:
        path = self.screenshot()
        with open(path, "rb") as f:
            data = f.read()
        os.unlink(path)
        return base64.b64encode(data).decode()
