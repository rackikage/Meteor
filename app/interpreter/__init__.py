"""Local code interpreter — Open Interpreter-style execution on your machine.

Runs Python (and optional bash snippets) with session state across calls.
NOT reverse/bind shells — network callback payloads are out of scope.
"""

from app.interpreter.local import LocalInterpreter

__all__ = ["LocalInterpreter"]
