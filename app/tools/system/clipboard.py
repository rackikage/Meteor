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
                ok = self._wayland_copy(text)
                if not ok:
                    ok = self._x11_copy(text)
                if not ok:
                    raise ClipboardError("No clipboard tool available (install wl-clipboard or xclip)")
            else:
                raise ClipboardError(f"Unsupported platform: {self._platform}")
            self._history.append(text)
            if len(self._history) > self._max_history:
                self._history.pop(0)
            return True
        except Exception as e:
            raise ClipboardError(f"Failed to copy: {e}") from e

    def _wayland_copy(self, text: str) -> bool:
        try:
            proc = subprocess.Popen(
                ["wl-copy", "--foreground"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            proc.communicate(text.encode("utf-8"), timeout=3)
            return proc.returncode == 0
        except Exception:
            return False

    def _x11_copy(self, text: str) -> bool:
        try:
            proc = subprocess.Popen(
                ["xclip", "-selection", "clipboard", "-f"],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            proc.communicate(text.encode("utf-8"), timeout=3)
            return proc.returncode == 0
        except Exception:
            return False

    def paste(self) -> str:
        try:
            if self._platform == "macos":
                result = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=5)
            elif self._platform == "linux":
                out = self._wayland_paste()
                if out is None:
                    out = self._x11_paste()
                if out is None:
                    return ""
                return out
            else:
                return ""
            return result.stdout if result.returncode == 0 else ""
        except Exception as e:
            raise ClipboardError(f"Failed to paste: {e}") from e

    def _wayland_paste(self) -> str | None:
        try:
            result = subprocess.run(
                ["wl-paste", "--no-newline"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                return result.stdout
        except Exception:
            pass
        return None

    def _x11_paste(self) -> str | None:
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                return result.stdout
        except Exception:
            pass
        return None

    def append(self, text: str, separator: str = "\n") -> bool:
        current = self.paste()
        return self.copy(current + separator + text)

    def clear(self) -> bool:
        return self.copy("")

    def has_content(self) -> bool:
        return bool(self.paste().strip())
