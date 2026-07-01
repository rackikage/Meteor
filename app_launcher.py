"""Meteor native app — starts the FastAPI backend in a background thread and
opens a real desktop window (WebKit2GTK / QtWebEngine / Edge WebView2).

Not a browser tab. No taskbar delegation to Firefox/Chromium. The window that
appears in your task manager IS Meteor.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _pick_port(default: int = 8765) -> int:
    requested = int(os.environ.get("METEOR_PORT", default))
    for port in (requested, requested + 1, requested + 2, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    return requested


def _serve(port: int) -> None:
    """Run uvicorn in-process. Kept in its own function so it runs cleanly on
    a background thread."""
    import uvicorn
    uvicorn.run(
        "app.api.main:app",
        host="127.0.0.1",
        port=port,
        log_level=os.environ.get("METEOR_LOG_LEVEL", "warning"),
        access_log=False,
    )


def _wait_for_health(url: str, timeout_s: float = 25.0) -> bool:
    import urllib.error
    import urllib.request
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/v1/health", timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, ConnectionRefusedError, TimeoutError, OSError):
            time.sleep(0.3)
    return False


def _ensure_optional_backends() -> None:
    """Kick Ollama over if it's already installed. Never downloads anything."""
    try:
        from app.runtime.ollama_launcher import ensure_ollama_running, is_ollama_running
        if not is_ollama_running():
            ensure_ollama_running()
    except Exception:
        pass


def main() -> None:
    port = _pick_port()
    url = f"http://127.0.0.1:{port}"

    _ensure_optional_backends()

    server_thread = threading.Thread(target=_serve, args=(port,), daemon=True)
    server_thread.start()

    if not _wait_for_health(url, timeout_s=25.0):
        print(f"Meteor: backend did not come up on {url} within 25s — opening window anyway",
              file=sys.stderr)

    os.environ.setdefault("QT_API", "pyqt6")
    import webview  # native window

    icon = HERE / "assets" / "meteor_icon_256.png"
    webview.create_window(
        title="Meteor",
        url=url,
        width=1280,
        height=860,
        min_size=(760, 540),
        background_color="#0d0d0d",
        resizable=True,
        text_select=True,
        zoomable=True,
    )

    # Linux picks GTK (WebKit2GTK 4.1) if the typelib is actually available,
    # otherwise Qt (PyQt6 WebEngine, bundled via pip). Windows uses EdgeChromium,
    # macOS uses Cocoa — both handled by pywebview's own default detection.
    gui = os.environ.get("METEOR_WEBVIEW_GUI")  # "gtk" | "qt" | None
    if not gui and sys.platform.startswith("linux"):
        try:
            import gi
            gi.require_version("WebKit2", "4.1")
            gui = "gtk"
        except Exception:
            gui = "qt"
    webview.start(
        gui=gui,
        icon=str(icon) if icon.exists() else None,
        debug=os.environ.get("METEOR_DEBUG", "").lower() in ("1", "true", "yes"),
    )


if __name__ == "__main__":
    main()
