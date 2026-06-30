"""macOS-native window chrome helpers for the Orchestrator GUI."""

from __future__ import annotations

import sys
import tkinter as tk

# Left inset so unified-title-bar content clears traffic-light controls.
MACOS_TITLE_INSET = 78


def macos_content_padx(default: int = 14) -> tuple[int, int]:
    """Return (left, right) horizontal padding for in-window chrome."""
    if sys.platform == "darwin":
        return MACOS_TITLE_INSET, default
    return default, default


def configure_macos_window(root: tk.Tk, *, dark: bool = True) -> None:
    """Unified title/toolbar strip with standard traffic-light controls."""
    if sys.platform != "darwin":
        return

    try:
        root.tk.call(
            "::tk::unsupported::MacWindowStyle",
            "style",
            root._w,
            "document",
            "closeBox collapseBox resizable unifiedTitleAndToolbar",
        )
    except tk.TclError:
        pass

    if dark:
        try:
            root.attributes("-appearance", "dark")
        except tk.TclError:
            pass
