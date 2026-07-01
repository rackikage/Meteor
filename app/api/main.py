"""Meteor API — FastAPI application.

This is the main entry point for the HTTP API. It wires together all v1
endpoints and provides dependency injection for the runtime.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.endpoints import agent, chat, health, hyper_search, memory, retrieval, nodes, pentest
from app.agent.loop import MeteorAgent
from app.agent.strategy import StrategyEngine
from app.node.controller import NodeController
from app.plugins.loader import PluginRegistry
from app.bootstrap import bootstrap
from app.dispatcher.grinder import InfiltrationGrinder
from app.dispatcher.noise import NoiseFloorSampler
from app.evidence.tracker import EvidenceTracker
from app.graph.event_bus import AssetEventBus
from app.graph.sqlite_graph import SQLiteAssetGraph
from app.graph.tools import GraphQueryTool
from app.memory.sqlite_adapter import build_sqlite_memory_adapter
from app.memory.triggers import install_memory_triggers
from app.models.registry import build_model_registry
from app.observability.sqlite_adapter import build_sqlite_observability_adapter
from app.policy.sql_engine import build_sql_policy_engine
from app.retrieval.sqlite_adapter import build_sqlite_retrieval_adapter
from app.runtime.context_builder import ContextBuilder
from app.runtime.orchestrator import MeteorOrchestrator, OrchestratorRequest
from app.runtime.tool_executor import ToolExecutor
from app.search.orchestrator import HyperSearchOrchestrator
from app.storage.sqlite_adapter import build_sqlite_adapter

logger = logging.getLogger(__name__)


class MeteorRuntime:
    """Runtime container — holds all initialized adapters."""

    def __init__(self) -> None:
        self.config = None
        self.repo_root = None
        self.storage = None
        self.model_registry = None
        self.memory = None
        self.retrieval = None
        self.observability = None
        self.policy = None
        self.graph = None
        self.event_bus = None
        self.noise = None
        self.grinder = None
        self.graph_tool = None
        self.agent = None
        self.strategy = None
        self.plugins = None
        self.node_controller = None
        self.evidence = None
        self.context_builder = None
        self.tool_executor = None
        self.orchestrator = None

    def initialize(self) -> None:
        """Initialize all runtime components."""
        result = bootstrap()
        self.config = result.config
        self.repo_root = result.repo_root

        self.storage = build_sqlite_adapter(self.config.storage, self.repo_root)
        self.model_registry = build_model_registry(self.config, self.repo_root)
        self.memory = build_sqlite_memory_adapter(self.storage)
        self.retrieval = build_sqlite_retrieval_adapter(self.storage)
        self.policy = build_sql_policy_engine(self.storage)
        self.observability = build_sqlite_observability_adapter(
            self.storage,
            log_level=self.config.observability.log_level,
            audit_enabled=self.config.observability.audit_enabled,
        )

        install_memory_triggers(self.storage)

        self.event_bus = AssetEventBus()
        self.graph = SQLiteAssetGraph(self.storage)

        self._wire_graph_subscribers()

        self.noise = NoiseFloorSampler(interval_s=2.0)
        self.grinder = InfiltrationGrinder(
            graph=self.graph, event_bus=self.event_bus,
            noise=self.noise,
        )

        self.graph_tool = GraphQueryTool(self.graph)

        # ── Strategy engine (Ollama meta-learning) ─────────────────
        self.strategy = StrategyEngine(
            model=self.config.models.profiles.get(
                self.config.models.default_profile
            ).model_path if self.config.models.profiles else "llama3.2",
            storage=self.storage,
        )
        self.strategy.ensure_table()

        # ── Plugin registry ────────────────────────────────────────
        self.plugins = PluginRegistry()
        n_plugins = self.plugins.load_all()
        logger.info("Loaded %d plugin(s)", n_plugins)

        # ── Node controller (distributed orchestration) ────────────
        self.node_controller = NodeController()
        nodes.init_node_controller(self.node_controller)

        self.agent = MeteorAgent(
            graph=self.graph,
            event_bus=self.event_bus,
            grinder=self.grinder,
            strategy=self.strategy,
            plugins=self.plugins,
        )

        self.evidence = EvidenceTracker()
        self.context_builder = ContextBuilder(
            memory=self.memory,
            retrieval=self.retrieval,
            evidence_tracker=self.evidence,
        )
        # Register every system tool with permissive local ownership
        # (nmap, full shell, full filesystem, pentest, network scope) and seed
        # allow-* SQL policy rules so the orchestrator's tool loop can execute.
        from app.tools.bootstrap import bootstrap_tools
        bootstrap_tools(storage=self.storage)
        self.tool_executor = ToolExecutor()
        self.orchestrator = MeteorOrchestrator(
            policy=self.policy,
            context=self.context_builder,
            model=self.model_registry.get_adapter(),
            tools=self.tool_executor,
            memory=self.memory,
            evidence=self.evidence,
            observability=self.observability,
            model_registry=self.model_registry,
        )

        self.observability.register_health_check("model", self.model_registry.health)
        self.observability.register_health_check("memory", self.memory.health)
        self.observability.register_health_check("retrieval", self.retrieval.health)
        self.observability.register_health_check("storage", self.storage.health)
        self.observability.register_health_check("orchestrator", self.orchestrator.health)

        hyper_orchestrator = HyperSearchOrchestrator(retrieval_adapter=self.retrieval)
        hyper_search.init_hyper_search(hyper_orchestrator)
        pentest.init_pentest_runtime(get_runtime)

        logger.info("Meteor runtime initialized")

    def _wire_graph_subscribers(self) -> None:
        """Wire event bus topics to auto-persist into the asset graph."""

        def _on_host(payload: dict) -> None:
            subnet_id = payload.get("subnet_id")
            self.graph.upsert_host(
                ip=payload["ip"],
                hostname=payload.get("hostname"),
                os=payload.get("os"),
                subnet_id=subnet_id,
                source=payload.get("source", "discovery"),
            )

        def _on_service(payload: dict) -> None:
            host_id = payload.get("host_id")
            if not host_id:
                host_id = self.graph.upsert_host(ip=payload["ip"])
            svc_id = self.graph.upsert_service(
                host_id=host_id,
                port=payload["port"],
                name=payload.get("name", "unknown"),
                banner=payload.get("banner", ""),
            )
            self.graph.add_edge("host", host_id, "service", svc_id, "RUNS_SERVICE")

        def _on_vuln(payload: dict) -> None:
            svc_id = payload["service_id"]
            self.graph.upsert_vulnerability(
                service_id=svc_id,
                cve_id=payload["cve_id"],
                severity=payload.get("severity"),
                exploit_available=payload.get("exploit_available", False),
            )
            self.graph.add_edge("service", svc_id, "vulnerability", 0,
                                "HAS_VULNERABILITY")

        def _on_cred(payload: dict) -> None:
            host_id = payload.get("host_id")
            cred_id = self.graph.upsert_credential(
                host_id=host_id,
                username=payload["username"],
                secret_type=payload["secret_type"],
                secret_value=payload.get("secret_value", ""),
                source=payload.get("source", "discovery"),
            )
            if host_id:
                self.graph.add_edge("host", host_id, "credential", cred_id,
                                    "CONTAINS_CREDENTIAL")

        self.event_bus.subscribe("host.discovered", _on_host)
        self.event_bus.subscribe("service.discovered", _on_service)
        self.event_bus.subscribe("vulnerability.matched", _on_vuln)
        self.event_bus.subscribe("credential.found", _on_cred)

    def handle_chat(
        self,
        prompt: str,
        session_id: str,
        max_tokens: int,
        temperature: float,
        metadata: dict,
    ) -> dict:
        """Handle a chat completion request via the canonical orchestrator pipeline."""
        response = self.orchestrator.handle(
            OrchestratorRequest(
                prompt=prompt,
                session_id=session_id,
                max_tokens=max_tokens,
                temperature=temperature,
                metadata=metadata,
            )
        )

        return {
            "response_text": response.response_text,
            "finish_reason": response.finish_reason,
            "token_usage": response.token_usage,
            "metadata": {
                **metadata,
                **response.metadata,
                "policy_checked": response.policy_checked,
                "duration_ms": response.duration_ms,
                "tool_results": len(response.tool_results),
                "evidence_count": len(response.evidence),
            },
        }

    def handle_chat_stream(
        self,
        prompt: str,
        session_id: str,
        max_tokens: int,
        temperature: float,
        metadata: dict,
    ):
        """Handle a streaming chat completion request via the orchestrator."""
        yield from self.orchestrator.handle_stream(
            OrchestratorRequest(
                prompt=prompt,
                session_id=session_id,
                max_tokens=max_tokens,
                temperature=temperature,
                metadata=metadata,
                streaming=True,
            )
        )

    def shutdown(self) -> None:
        """Shutdown all runtime components."""
        if self.storage:
            self.storage.close()
        logger.info("Meteor runtime shut down")


_runtime: Optional[MeteorRuntime] = None


def get_runtime() -> MeteorRuntime:
    """Get the global runtime instance."""
    global _runtime
    if _runtime is None:
        _runtime = MeteorRuntime()
        _runtime.initialize()
    return _runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan — initialize on startup, shutdown on exit."""
    get_runtime()
    yield
    if _runtime:
        _runtime.shutdown()


app = FastAPI(
    title="Meteor API",
    description="Local-first AI runtime — the runtime is the product",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(memory.router, prefix="/api/v1")
app.include_router(retrieval.router, prefix="/api/v1")
app.include_router(hyper_search.router, prefix="/api/v1")
app.include_router(nodes.router, prefix="/api/v1")
app.include_router(pentest.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")

# ── Web chat UI ─────────────────────────────────────────────────────
# Serve the OLED-black + silver ChatGPT-style single-page app.
_WEB_DIR = Path(__file__).resolve().parent.parent / "web" / "static"
if _WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_WEB_DIR)), name="static")

    @app.get("/")
    async def root():
        """Serve the chat UI."""
        return FileResponse(str(_WEB_DIR / "index.html"))

    @app.get("/api")
    async def api_info():
        return {
            "name": "Meteor API",
            "version": "1.0.0",
            "description": "Local-first AI runtime",
            "docs": "/docs",
            "chat": "/",
            "health": "/api/v1/health",
        }
else:
    @app.get("/")
    async def root():
        """Root endpoint — API info."""
        return {
            "name": "Meteor API",
            "version": "1.0.0",
            "description": "Local-first AI runtime",
            "docs": "/docs",
            "health": "/api/v1/health",
        }
