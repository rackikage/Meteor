"""Asset context provider — resolves the graph / event-bus / grinder / graph_tool
bundle without importing the FastAPI app.

The full desktop runtime registers itself as the provider during init
(`set_asset_context`). Headless consumers — chiefly the `meteor-mcp` server —
fall back to a lightweight self-built context so grinder runs and graph queries
work without uvicorn, the model stack, or plugins.

This is the seam that lets `PentestTool`, `GrinderTool`, and `GraphTool` stay
free of `app.api.main.get_runtime()`, which would otherwise boot the whole app.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Protocol

if TYPE_CHECKING:
    from app.dispatcher.grinder import InfiltrationGrinder
    from app.graph.event_bus import AssetEventBus
    from app.graph.sqlite_graph import SQLiteAssetGraph
    from app.graph.tools import GraphQueryTool


class AssetContext(Protocol):
    """The subset of the runtime that graph/grinder/pentest tools depend on."""

    graph: "SQLiteAssetGraph"
    event_bus: "AssetEventBus"
    grinder: "InfiltrationGrinder"
    graph_tool: "GraphQueryTool"


_provider: Optional[AssetContext] = None


def set_asset_context(ctx: AssetContext) -> None:
    """Register the process-wide asset context (called by MeteorRuntime)."""
    global _provider
    _provider = ctx


def get_asset_context() -> AssetContext:
    """Return the asset context, building a headless one on first use if the
    full runtime has not registered itself."""
    global _provider
    if _provider is None:
        from app.mcp.context import build_headless_context
        _provider = build_headless_context()
    return _provider
