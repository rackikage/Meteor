"""Clipboard Integration — system clipboard read/write."""

from __future__ import annotations

import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


class ClipboardError(Exception):
    pass


class ClipboardManager:
    def __init__(self) -> None:
        import platform
        self._platform = {"Darwin": "macos", "Linux": "linux", "Windows": "windows"}.get(platform.system(), "unknown")
        self._history: list[str] = []
        self._max_history = 50

    def copy(self, text: str) -> bool:
        try:
            if self._platform == "macos":
                proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
                proc.communicate(text.encode("utf-8"), timeout=5)
            elif self._platform == "linux":
                try:
                    proc = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
                    proc.communicate(text.encode("utf-8"), timeout=5)
                except FileNotFoundError:
                    proc = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
                    proc.communicate(text.encode("utf-8"), timeout=5)
            else:
                raise ClipboardError(f"Unsupported platform: {self._platform}")
            self._history.append(text)
            if len(self._history) > self._max_history:
                self._history.pop(0)
            return True
        except Exception as e:
            raise ClipboardError(f"Failed to copy: {e}") from e

    def paste(self) -> str:
        try:
            if self._platform == "macos":
                result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
            elif self._platform == "linux":
                try:
                    result = subprocess.run(["wl-paste"], capture_output=True, text=True, timeout=5)
                except FileNotFoundError:
                    result = subprocess.run(["xclip", "-selection", "clipboard", "-o"], capture_output=True, text=True, timeout=5)
            else:
                return ""
            return result.stdout if result.returncode == 0 else ""
        except Exception as e:
            raise ClipboardError(f"Failed to paste: {e}") from e

    def append(self, text: str, separator: str = "\n") -> bool:
        current = self.paste()
        return self.copy(current + separator + text)

    def clear(self) -> bool:
        return self.copy("")

    def has_content(self) -> bool:
        return bool(self.paste().strip())
