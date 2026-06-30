"""Start Ollama when installed but not already serving on localhost:11434."""

from __future__ import annotations

import http.client
import logging
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

OLLAMA_HOST = "localhost"
OLLAMA_PORT = 11434
DEFAULT_WAIT_SECONDS = 20.0

_started_proc: Optional[subprocess.Popen] = None
_we_started = False
_launched_mac_app = False


def _ollama_binaries() -> list[str]:
    """Candidate ollama paths — PATH first, then common install locations."""
    seen: set[str] = set()
    candidates: list[str] = []

    def add(path: Optional[str]) -> None:
        if path and path not in seen and os.path.isfile(path) and os.access(path, os.X_OK):
            seen.add(path)
            candidates.append(path)

    add(shutil.which("ollama"))
    add("/opt/homebrew/bin/ollama")
    add("/usr/local/bin/ollama")
    add(str(Path.home() / ".ollama" / "bin" / "ollama"))
    return candidates


def is_ollama_running(timeout: float = 2.0) -> bool:
    """Return True if Ollama responds on the default local port."""
    try:
        conn = http.client.HTTPConnection(OLLAMA_HOST, OLLAMA_PORT, timeout=timeout)
        conn.request("GET", "/api/tags")
        resp = conn.getresponse()
        conn.close()
        return resp.status == 200
    except (ConnectionRefusedError, OSError, TimeoutError, http.client.HTTPException):
        return False


def _wait_until_ready(wait_seconds: float) -> bool:
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if is_ollama_running(timeout=1.0):
            return True
        time.sleep(0.4)
    return False


def _try_macos_app() -> bool:
    """Launch Ollama.app (menu-bar daemon) on macOS."""
    global _launched_mac_app
    if platform.system() != "darwin":
        return False

    app_paths = [
        Path("/Applications/Ollama.app"),
        Path.home() / "Applications" / "Ollama.app",
    ]
    if not any(p.exists() for p in app_paths):
        return False

    try:
        subprocess.run(["open", "-a", "Ollama"], check=False, capture_output=True)
        _launched_mac_app = True
        print("Meteor: Launched Ollama.app — waiting for API...")
        return True
    except OSError:
        return False


def _start_ollama_serve() -> bool:
    """Start `ollama serve` as a background subprocess."""
    global _started_proc, _we_started

    binaries = _ollama_binaries()
    if not binaries:
        return False

    popen_kwargs: dict = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
    }
    if platform.system() != "Windows":
        popen_kwargs["start_new_session"] = True

    for ollama_bin in binaries:
        try:
            _started_proc = subprocess.Popen([ollama_bin, "serve"], **popen_kwargs)
            _we_started = True
            print(f"Meteor: Starting Ollama ({ollama_bin})...")
            return True
        except OSError as exc:
            logger.debug("Failed to start %s: %s", ollama_bin, exc)
    return False


def ensure_ollama_running(*, wait_seconds: float = DEFAULT_WAIT_SECONDS) -> bool:
    """Ensure Ollama is reachable; start the app or serve if needed."""
    global _started_proc, _we_started

    if is_ollama_running():
        logger.info("Ollama already running on %s:%s", OLLAMA_HOST, OLLAMA_PORT)
        return True

    if not _ollama_binaries() and platform.system() != "darwin":
        print(
            "Meteor: Ollama not found. Install: curl -fsSL https://ollama.com/install.sh | sh",
            file=sys.stderr,
        )
        return False

    # macOS: prefer the official app (registers launch agent, keeps server up)
    if _try_macos_app() and _wait_until_ready(wait_seconds):
        print("Meteor: Ollama ready.")
        return True

    if _start_ollama_serve():
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            if is_ollama_running(timeout=1.0):
                print("Meteor: Ollama ready.")
                return True
            if _started_proc and _started_proc.poll() is not None:
                print("Meteor: ollama serve exited — try: open -a Ollama", file=sys.stderr)
                _we_started = False
                _started_proc = None
                break
            time.sleep(0.4)

    print(
        "Meteor: Ollama not responding. On macOS run: open -a Ollama\n"
        "       Or in a terminal: ollama serve",
        file=sys.stderr,
    )
    return False


def shutdown_ollama_if_started() -> None:
    """Stop Ollama only if this process started `ollama serve` (not the Mac app)."""
    global _started_proc, _we_started

    if not _we_started or _started_proc is None:
        return

    proc = _started_proc
    _started_proc = None
    _we_started = False

    try:
        if platform.system() == "Windows":
            proc.terminate()
            proc.wait(timeout=5)
        else:
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=5)
        print("Meteor: Stopped Ollama.")
    except (ProcessLookupError, subprocess.TimeoutExpired, OSError):
        try:
            if platform.system() != "Windows":
                os.killpg(proc.pid, signal.SIGKILL)
            else:
                proc.kill()
        except (ProcessLookupError, OSError):
            pass
