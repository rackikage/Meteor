"""Tests for context builder, tool executor, and end-to-end orchestrator."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.config import MeteorConfig
from app.evidence.tracker import EvidenceTracker
from app.memory.contract import MemoryAdapter, MemoryEntry, MemoryType
from app.memory.sqlite_adapter import build_sqlite_memory_adapter
from app.models.contract import ModelAdapter, ModelInput, ModelOutput
from app.policy.sql_engine import SqlPolicyEngine
from app.retrieval.contract import RetrievedDocument, RetrievalAdapter, RetrievalQuery, RetrievalResult
from app.retrieval.sqlite_adapter import build_sqlite_retrieval_adapter
from app.runtime.context_builder import BuiltContext, ContextBuilder
from app.runtime.orchestrator import MeteorOrchestrator, OrchestratorRequest, OrchestratorResponse
from app.runtime.tool_executor import ToolExecutor, ToolRequest, ToolResult, ToolResultStatus
from app.storage.sqlite_adapter import build_sqlite_adapter
from app.tools.system.filesystem import FilesystemAgent
from app.tools.system.registry import get_registry
from app.tools.system.signal_budget import SignalBudget

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"


# ============================================================
# Mock Adapters
# ============================================================

class MockModelAdapter(ModelAdapter):
    def __init__(self, response: str = "Mock response"):
        self._response = response
        self.calls: list[ModelInput] = []

    def complete(self, input: ModelInput) -> ModelOutput:
        self.calls.append(input)
        return ModelOutput(
            response_text=self._response,
            finish_reason="stop",
            token_usage={"prompt_tokens": len(input.prompt.split()), "completion_tokens": 3, "total_tokens": len(input.prompt.split()) + 3},
        )

    def stream(self, input: ModelInput):
        for token in self._response.split():
            yield token + " "

    def health(self) -> dict:
        return {"healthy": True}


class MockPolicyEngine:
    def __init__(self, allow: bool = True):
        self.allow = allow

    def evaluate(self, request) -> object:
        from app.policy.contract import PolicyAction, PolicyDecision
        return PolicyDecision(
            action=PolicyAction.ALLOW if self.allow else PolicyAction.DENY,
            subject=request.subject,
            reason="mock",
        )


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def memory_and_retrieval(tmp_path):
    config = MeteorConfig.load(CONFIG_PATH)
    config.storage.paths.memory = str(tmp_path / "t_memory.db")
    config.storage.paths.audit = str(tmp_path / "t_audit.db")
    config.storage.paths.index_meta = str(tmp_path / "t_index.db")
    storage = build_sqlite_adapter(config.storage, tmp_path)
    mem = build_sqlite_memory_adapter(storage)
    ret = build_sqlite_retrieval_adapter(storage)
    yield mem, ret
    storage.close()


@pytest.fixture
def context_builder(memory_and_retrieval):
    mem, ret = memory_and_retrieval
    return ContextBuilder(memory=mem, retrieval=ret, max_history_messages=10, max_retrieved_docs=3)


@pytest.fixture
def budget():
    return SignalBudget(max_budget=1000.0, replenish_per_minute=200.0)


@pytest.fixture
def tool_executor(budget):
    registry = get_registry()
    registry.register("filesystem", FilesystemAgent(allowed_dirs=["/tmp"]), "FS", "1.0.0")
    return ToolExecutor(budget=budget)


@pytest.fixture
def orchestrator(memory_and_retrieval):
    mem, ret = memory_and_retrieval
    ctx = ContextBuilder(memory=mem, retrieval=ret)
    model = MockModelAdapter("The answer is 42.")
    tools = ToolExecutor()
    evidence = EvidenceTracker()
    policy = MockPolicyEngine(allow=True)

    registry = get_registry()
    registry.register("filesystem", FilesystemAgent(allowed_dirs=["/tmp"]), "FS")
    registry.register("shell", object(), "Shell")

    return MeteorOrchestrator(
        policy=policy, context=ctx, model=model,
        tools=tools, memory=mem, evidence=evidence,
    )


# ============================================================
# Context Builder Tests
# ============================================================

class TestContextBuilder:

    def test_build_basic_context(self, context_builder):
        ctx = context_builder.build("s1", "What is ML?")
        assert ctx.session_id == "s1"
        assert ctx.user_prompt == "What is ML?"
        assert ctx.system_prompt
        assert ctx.final_prompt
        assert "System:" in ctx.final_prompt
        assert "User:" in ctx.final_prompt

    def test_build_with_memory(self, context_builder, memory_and_retrieval):
        mem, _ = memory_and_retrieval
        mem.write(MemoryEntry(
            memory_type=MemoryType.CONVERSATION,
            content="Hello",
            session_id="s2",
            timestamp="2024-01-01T00:00:00",
            metadata={"role": "user"},
        ))
        mem.write(MemoryEntry(
            memory_type=MemoryType.CONVERSATION,
            content="Hi there!",
            session_id="s2",
            timestamp="2024-01-01T00:00:01",
            metadata={"role": "assistant"},
        ))

        ctx = context_builder.build("s2", "What now?")
        assert len(ctx.conversation_history) >= 2

    def test_build_with_retrieval(self, context_builder, memory_and_retrieval):
        _, ret = memory_and_retrieval
        ret.index([{"source": "doc1", "content": "Machine learning is a subset of AI"}])

        ctx = context_builder.build("s3", "machine learning")
        assert len(ctx.retrieved_documents) >= 0

    def test_build_with_corrections(self, context_builder, memory_and_retrieval):
        mem, _ = memory_and_retrieval
        mem.write(MemoryEntry(
            memory_type=MemoryType.CORRECTION,
            content="Use Hello instead of Hi",
            session_id="s4",
            timestamp="2024-01-01T00:00:00",
            metadata={"original": "Hi there", "reason": "Formal tone"},
        ))

        ctx = context_builder.build("s4", "Greet me")
        assert len(ctx.corrections) >= 1
        assert "corrections" in ctx.final_prompt.lower()

    def test_build_quick(self, context_builder):
        prompt = context_builder.build_quick("s5", "Quick question")
        assert "Quick question" in prompt

    def test_final_prompt_structure(self, context_builder):
        ctx = context_builder.build("s6", "Test prompt")
        assert "System:" in ctx.final_prompt
        assert "User:" in ctx.final_prompt
        assert "Assistant:" in ctx.final_prompt

    def test_to_model_input(self, context_builder):
        ctx = context_builder.build("s7", "test")
        mi = ctx.to_model_input(max_tokens=256, temperature=0.5)
        assert mi.prompt == ctx.final_prompt

    def test_health(self, context_builder):
        health = context_builder.health()
        assert health["healthy"] is True
        assert health["has_retrieval"] is True


# ============================================================
# Tool Executor Tests
# ============================================================

class TestToolExecutor:

    def test_get_capabilities(self, tool_executor):
        caps = tool_executor.get_capabilities()
        assert len(caps) > 0
        assert any("filesystem.read" in c["tool"] for c in caps)

    def test_get_capabilities_prompt(self, tool_executor):
        prompt = tool_executor.get_capabilities_prompt()
        assert "filesystem.read" in prompt

    def test_execute_filesystem_read(self, tool_executor):
        result = tool_executor.execute("filesystem", "read", {"path": "/tmp"}, session_id="s1")
        assert result.tool == "filesystem"
        assert result.operation == "read"

    def test_execute_unknown_tool(self, tool_executor):
        result = tool_executor.execute("nonexistent", "op")
        assert result.status == ToolResultStatus.ERROR

    def test_execute_missing_params(self, tool_executor):
        result = tool_executor.execute("filesystem", "read", {}, session_id="s2")
        assert result.status == ToolResultStatus.ERROR
        assert "Missing" in result.error

    def test_execute_disabled_tool(self):
        registry = get_registry()
        registry.disable("filesystem")
        executor = ToolExecutor()
        result = executor.execute("filesystem", "read", {"path": "/tmp"})
        assert result.status in (ToolResultStatus.DENIED, ToolResultStatus.ERROR)

    def test_result_to_prompt_context(self, tool_executor):
        result = tool_executor.execute("filesystem", "list", {"path": "/tmp"}, session_id="s3")
        prompt_ctx = result.to_prompt_context()
        assert "Tool result" in prompt_ctx or "Tool error" in prompt_ctx

    def test_get_history(self, tool_executor):
        tool_executor.execute("filesystem", "list", {"path": "/tmp"}, session_id="s4")
        history = tool_executor.get_history()
        assert len(history) >= 1

    def test_budget_state(self, tool_executor):
        state = tool_executor.get_budget_state()
        assert "current_budget" in state


# ============================================================
# Orchestrator Tests
# ============================================================

class TestMeteorOrchestrator:

    def test_handle_basic(self, orchestrator):
        request = OrchestratorRequest(prompt="What is 2+2?", session_id="orch-1")
        response = orchestrator.handle(request)
        assert response.session_id == "orch-1"
        assert response.response_text
        assert response.finish_reason == "stop"
        assert response.policy_checked

    def test_handle_memory_persistence(self, orchestrator, memory_and_retrieval):
        mem, _ = memory_and_retrieval
        request = OrchestratorRequest(prompt="Save this in memory", session_id="persist-1")
        orchestrator.handle(request)

        history = mem.read("persist-1", MemoryType.CONVERSATION)
        assert len(history) >= 1

    def test_handle_tool_loop(self, orchestrator):
        model = orchestrator.model
        model._response = '''Let me check the filesystem.
```json
{"tool": "filesystem", "operation": "list", "params": {"path": "/tmp"}}
```'''
        request = OrchestratorRequest(prompt="List /tmp", session_id="tool-1")
        response = orchestrator.handle(request)
        assert response.tool_results is not None

    def test_handle_evidence(self, orchestrator, memory_and_retrieval):
        _, ret = memory_and_retrieval
        ret.index([{"source": "doc1", "content": "Python is a programming language created by Guido van Rossum"}])

        request = OrchestratorRequest(prompt="What is Python?", session_id="ev-1")
        response = orchestrator.handle(request)
        assert response.evidence is not None

    def test_root_response_fields(self, orchestrator):
        request = OrchestratorRequest(prompt="Root test", session_id="root-1")
        response = orchestrator.handle(request)
        d = response.to_dict()
        assert "session_id" in d
        assert "response_text" in d
        assert "duration_ms" in d

    def test_health(self, orchestrator):
        health = orchestrator.health()
        assert health["healthy"] is True
        assert "context_builder" in health
        assert "budget_state" in health
