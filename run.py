#!/usr/bin/env python3
"""Meteor launcher — sets up the venv on first run, then opens the native
desktop window (WebKit2GTK on Linux, QtWebEngine as fallback, EdgeChromium on
Windows, Cocoa on macOS). No browser tab. No downloads unless the user asks.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE / ".venv"

if sys.version_info < (3, 11):
    sys.exit("Meteor requires Python 3.11 or newer.")

if sys.platform == "win32":
    PYTHON = VENV / "Scripts" / "python.exe"
    PIP = VENV / "Scripts" / "pip.exe"
else:
    PYTHON = VENV / "bin" / "python"
    PIP = VENV / "bin" / "pip"


def _run(*cmd: str) -> None:
    subprocess.check_call(list(cmd))


def _link_system_site_packages() -> None:
    """On Linux, expose the system dist-packages so the venv can import gi/
    PyGObject/PyQt6 without having to build them from source. Requires the OS
    packages: python3-gi, gir1.2-webkit2-4.1 (Debian/Ubuntu/Kali)."""
    if platform.system() != "Linux":
        return
    try:
        result = subprocess.run(
            [sys.executable, "-c",
             "import site; [print(p) for p in site.getsitepackages() if 'dist-packages' in p]"],
            capture_output=True, text=True, check=False,
        )
        # Pick the first candidate that actually contains PyGObject (gi/), since
        # Debian ships gi only in /usr/lib/python3/dist-packages regardless of
        # python minor version.
        target = ""
        for p in (result.stdout or "").splitlines():
            p = p.strip()
            if p and (Path(p) / "gi").is_dir():
                target = p
                break
        if not target:
            # Debian's canonical location for arch-independent Python packages.
            fallback = Path("/usr/lib/python3/dist-packages")
            if (fallback / "gi").is_dir():
                target = str(fallback)
        if target:
            for candidate in VENV.glob("lib/python*/site-packages"):
                (candidate / "system-dist.pth").write_text(target + "\n")
                break
    except Exception:
        pass


def _ensure_venv() -> None:
    first_run = not PYTHON.exists()
    if first_run:
        print("Meteor: first-run setup — this takes about a minute...")
        _run(sys.executable, "-m", "venv", str(VENV))
        _run(str(PIP), "install", "--quiet", "--upgrade", "pip", "setuptools")
        _run(str(PIP), "install", "--quiet", "-e", str(HERE))
        _run(str(PIP), "install", "--quiet", "pywebview", "pillow")

    _link_system_site_packages()

    if first_run:
        _print_linux_deps_hint()
        print("Meteor: setup complete.\n")


def _print_linux_deps_hint() -> None:
    """Native window needs a WebView backend. On Debian/Kali, one apt line
    covers it — print it if we detect the packages are missing."""
    if platform.system() != "Linux":
        return
    try:
        subprocess.run(["dpkg", "-s", "gir1.2-webkit2-4.1"],
                       capture_output=True, check=True)
        return
    except Exception:
        pass
    print(
        "Meteor: for the native window, install one of these once:\n"
        "  Debian/Ubuntu/Kali:  sudo apt install python3-gi gir1.2-webkit2-4.1 libwebkit2gtk-4.1-0\n"
        "  Fedora:              sudo dnf install python3-gobject webkit2gtk4.1\n"
        "  (or Qt: sudo apt install python3-pyqt6 python3-pyqt6.qtwebengine)"
    )


def _launch() -> None:
    """Run the native launcher inside the venv."""
    env = os.environ.copy()
    subprocess.check_call([str(PYTHON), str(HERE / "app_launcher.py")], env=env)


if __name__ == "__main__":
    _ensure_venv()
    _launch()
