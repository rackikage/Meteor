"""Meteor MCP server — projects the shared tool core over stdio.

Any MCP-capable AI (Claude Code, Cursor, another agent) mounts this as a local
subprocess and drives Meteor's entire arsenal: filesystem, shell, nmap, the
pentest engine, web intel, and every wrapped weapon (sqlmap, nuclei, hydra, …).

Design: this is a *projection*, not a second tool definition. It reflects
`ToolExecutor.CAPABILITIES` into MCP tools — add a capability anywhere and it
shows up here automatically, identical to what the desktop app sees.

Safety: local stdio only (no network bind). Because there is no human on the
other end to answer a confirm, catastrophic actions flagged by the danger
classifier (rm -rf /, mkfs, fork bombs, power-off, …) are REFUSED by default.
Set METEOR_MCP_ALLOW_DANGER=1 to lift that and run fully unattended.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# MCP tool names allow [a-zA-Z0-9_-]; "." is not safe. Use "__" as the
# tool/operation separator — neither tool names nor operation names contain a
# double underscore, so the split back is unambiguous.
_SEP = "__"


def _mcp_name(tool_op: str) -> str:
    return tool_op.replace(".", _SEP)


def _split_name(name: str) -> tuple[str, str]:
    tool, _, operation = name.partition(_SEP)
    return tool, operation


def build_server():
    """Bootstrap the tools and return a configured MCP Server."""
    from mcp.server import Server
    import mcp.types as types

    from app.tools.bootstrap import bootstrap_tools
    from app.runtime.tool_executor import ToolExecutor
    from app.runtime.danger import classify_danger

    bootstrap_tools()  # register every tool (incl. arsenal) into the registry
    executor = ToolExecutor()
    allow_danger = os.environ.get("METEOR_MCP_ALLOW_DANGER", "").lower() in ("1", "true", "yes")

    server = Server("meteor")

    @server.list_tools()
    async def list_tools() -> list["types.Tool"]:
        tools = []
        for tool_op, (_, params, desc) in sorted(ToolExecutor.CAPABILITIES.items()):
            schema = {
                "type": "object",
                "properties": {p: {"type": "string"} for p in params},
                "required": list(params),
            }
            tools.append(types.Tool(name=_mcp_name(tool_op), description=desc, inputSchema=schema))
        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict | None) -> list["types.TextContent"]:
        import json
        import anyio

        tool, operation = _split_name(name)
        params = arguments or {}

        reason = classify_danger(tool, operation, params)
        if reason and not allow_danger:
            return [types.TextContent(
                type="text",
                text=(f"REFUSED: '{tool}.{operation}' is a guarded catastrophic action "
                      f"({reason}). There is no human on this MCP channel to confirm it. "
                      f"Set METEOR_MCP_ALLOW_DANGER=1 to permit unattended execution."),
            )]

        # ToolExecutor.execute is synchronous and some tools are slow — run off
        # the event loop so concurrent MCP calls don't block each other.
        result = await anyio.to_thread.run_sync(
            lambda: executor.execute(tool=tool, operation=operation, params=params, session_id="mcp")
        )
        payload = {
            "status": result.status.value,
            "tool": f"{tool}.{operation}",
            "duration_ms": round(result.duration_ms, 1),
            "result": result.result,
            "error": result.error,
        }
        return [types.TextContent(type="text", text=json.dumps(payload, default=str, indent=2)[:100_000])]

    return server


async def _run() -> None:
    from mcp.server.stdio import stdio_server
    server = build_server()
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def main() -> None:
    """Console-script entrypoint: `meteor-mcp`."""
    import anyio
    logging.basicConfig(level=os.environ.get("METEOR_LOG_LEVEL", "WARNING").upper())
    anyio.run(_run)


if __name__ == "__main__":
    main()
