"""macOS-native window chrome helpers for the Orchestrator GUI."""

from __future__ import annotations

import sys
import tkinter as tk


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
