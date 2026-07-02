"""Headless asset context for the MCP server.

Builds the minimal slice of the runtime that grinder / graph / pentest tools
need — storage, event bus, asset graph, noise sampler, grinder, and the graph
query tool — without FastAPI, the model registry, plugins, or the orchestrator.
This lets `meteor-mcp` run autonomous scans and graph queries with no uvicorn
process behind it.

The full desktop app never calls this: `MeteorRuntime` registers itself as the
asset context first (see `app/api/main.py`), so `get_asset_context()` returns
the live runtime there and this headless build only fires in standalone MCP.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class HeadlessAssetContext:
    """Minimal AssetContext — carries just the objects the tools resolve."""

    graph: Any
    event_bus: Any
    noise: Any
    grinder: Any
    graph_tool: Any


def build_headless_context() -> HeadlessAssetContext:
    """Construct graph + grinder + graph_tool from storage alone, then register
    the result as the process-wide asset context."""
    from app.bootstrap import bootstrap
    from app.dispatcher.grinder import InfiltrationGrinder
    from app.dispatcher.noise import NoiseFloorSampler
    from app.graph.event_bus import AssetEventBus
    from app.graph.sqlite_graph import SQLiteAssetGraph
    from app.graph.subscribers import wire_graph_subscribers
    from app.graph.tools import GraphQueryTool
    from app.runtime.asset_context import set_asset_context
    from app.storage.sqlite_adapter import build_sqlite_adapter

    result = bootstrap()
    storage = build_sqlite_adapter(result.config.storage, result.repo_root)

    event_bus = AssetEventBus()
    graph = SQLiteAssetGraph(storage)
    wire_graph_subscribers(graph, event_bus)

    noise = NoiseFloorSampler(interval_s=2.0)
    grinder = InfiltrationGrinder(graph=graph, event_bus=event_bus, noise=noise)
    graph_tool = GraphQueryTool(graph)

    ctx = HeadlessAssetContext(
        graph=graph,
        event_bus=event_bus,
        noise=noise,
        grinder=grinder,
        graph_tool=graph_tool,
    )
    set_asset_context(ctx)
    return ctx
