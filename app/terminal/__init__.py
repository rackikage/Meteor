"""Terminal bridge — interactive REPL + live renderer for Meteor's agent loop.

Runs KITT (or Loop Freak) entirely in the terminal without the web GUI or
Cursor.  The bridge builds a lightweight runtime (config + storage + model
registry + tool executor — no FastAPI), wires the ``AgentChatLoop`` events to a
``rich``-based renderer, and drives the conversation through a ``prompt_toolkit``
REPL.

Entry point: ``meteor-chat`` console script → :func:`app.terminal.main.main`.
"""

from __future__ import annotations

from app.terminal.bridge import TerminalBridge, TerminalConfig
from app.terminal.renderer import TerminalRenderer

__all__ = ["TerminalBridge", "TerminalConfig", "TerminalRenderer"]
