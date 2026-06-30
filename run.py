#!/usr/bin/env python3
"""Meteor launcher — auto-installs dependencies on first run, then opens the GUI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV = HERE / ".venv"

if sys.version_info < (3, 11):
    sys.exit("Meteor requires Python 3.11 or newer.")

# ── Resolve venv python / pip paths ───────────────────────────────────
if sys.platform == "win32":
    PYTHON = VENV / "Scripts" / "python.exe"
    PIP = VENV / "Scripts" / "pip.exe"
else:
    PYTHON = VENV / "bin" / "python"
    PIP = VENV / "bin" / "pip"


def _run(*cmd: str) -> None:
    subprocess.check_call(list(cmd))


def _ensure_venv() -> None:
    if PYTHON.exists():
        return

    print("Meteor: first-run setup — this takes about a minute...")

    _run(sys.executable, "-m", "venv", str(VENV))
    _run(str(PIP), "install", "--quiet", "--upgrade", "pip", "setuptools")
    _run(str(PIP), "install", "--quiet", "-e", str(HERE))

    # Download playwright's bundled browser (chromium only, ~150 MB)
    print("Meteor: downloading browser for web scraping...")
    _run(str(PYTHON), "-m", "playwright", "install", "chromium")

    print("Meteor: setup complete.\n")


def _ensure_ollama() -> None:
    """Start Ollama in the background when installed but not already running."""
    sys.path.insert(0, str(HERE))
    from app.runtime.ollama_launcher import ensure_ollama_running

    ensure_ollama_running()


def _launch() -> None:
    gui = str(HERE / "meteor_gui.py")
    sys.path.insert(0, str(HERE))
    from app.runtime.ollama_launcher import shutdown_ollama_if_started

    try:
        subprocess.call([str(PYTHON), gui])
    finally:
        shutdown_ollama_if_started()


if __name__ == "__main__":
    _ensure_venv()
    _ensure_ollama()
    _launch()
