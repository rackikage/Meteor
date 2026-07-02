"""Console-script entry point: ``meteor-chat``.

Parses CLI args, builds a :class:`TerminalConfig`, and hands off to the REPL.
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="meteor-chat",
        description="Meteor terminal — interactive KITT / Loop Freak REPL",
    )
    parser.add_argument(
        "--persona", "-p",
        choices=("kitt", "loop_freak"),
        default="kitt",
        help="Agent persona (default: kitt)",
    )
    parser.add_argument(
        "--model", "-m",
        default=None,
        help="Model profile name (default: auto-select)",
    )
    parser.add_argument(
        "--session", "-s",
        default="terminal",
        help="Session ID for history isolation",
    )
    parser.add_argument(
        "--max-iterations", "-i",
        type=int, default=12,
        help="Max agent loop iterations per turn (default: 12, 25 for loop_freak)",
    )
    parser.add_argument(
        "--max-tokens", "-t",
        type=int, default=2048,
        help="Max tokens per model call (default: 2048)",
    )
    parser.add_argument(
        "--plain",
        action="store_true",
        help="Disable rich formatting (plain text output)",
    )
    parser.add_argument(
        "--one-shot",
        default=None,
        metavar="PROMPT",
        help="Run a single prompt and exit (no REPL)",
    )

    args = parser.parse_args()

    from app.terminal.bridge import TerminalConfig
    config = TerminalConfig(
        persona=args.persona,
        session_id=args.session,
        max_iterations=args.max_iterations,
        max_tokens=args.max_tokens,
        plain=args.plain,
        model_profile=args.model,
    )

    if args.one_shot:
        from app.terminal.bridge import TerminalBridge
        bridge = TerminalBridge(config)
        bridge.initialize()
        bridge.run_turn(args.one_shot)
        return

    from app.terminal.repl import run_repl
    run_repl(config)


if __name__ == "__main__":
    main()
