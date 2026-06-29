"""End-to-End Orchestrator — the full pipeline in a single flow.

Meteor Doctrine #4: Runtime is the product. This is the canonical execution
path — user input flows through every layer, each gated by policy:

  User → Policy Gate → Context Builder → Model → Tool Loop → Evidence → Response

Every request passes through:
1. Policy gate: is this operation allowed? (SQL policy engine)
2. Context assembly: memory + retrieval + evidence → structured prompt
3. Model inference: prompt → response (with streaming)
4. Tool loop: model requests tools → executor validates → results fed back
5. Evidence annotation: response scored against retrieved sources
6. Memory persistence: conversation stored for future context

This replaces the old skeleton orchestrator in orchestrator.py.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator, Optional

from app.evidence.contract import ConfidenceLevel, EvidenceRecord
from app.evidence.tracker import EvidenceTracker
from app.memory.contract import MemoryAdapter, MemoryEntry, MemoryType
from app.models.contract import ModelAdapter, ModelInput
from app.observability.contract import AuditEntry
from app.policy.sql_engine import SqlPolicyEngine
from app.retrieval.contract import RetrievalAdapter
from app.runtime.context_builder import BuiltContext, ContextBuilder
from app.runtime.tool_executor import ToolExecutor, ToolRequest, ToolResult, ToolResultStatus

logger = logging.getLogger(__name__)


@dataclass
class OrchestratorRequest:
    prompt: str
    session_id: str = ""
    max_tokens: int = 512
    temperature: float = 0.7
    max_tool_iterations: int = 5
    streaming: bool = False
    metadata: dict = field(default_factory=dict)


@dataclass
class OrchestratorResponse:
    session_id: str
    response_text: str
    finish_reason: str
    token_usage: dict = field(default_factory=dict)
    tool_results: list[ToolResult] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)
    context: Optional[BuiltContext] = None
    duration_ms: float = 0.0
    policy_checked: bool = True
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "response_text": self.response_text,
            "finish_reason": self.finish_reason,
            "token_usage": self.token_usage,
            "tool_results": len(self.tool_results),
            "evidence_count": len(self.evidence),
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
        }


class MeteorOrchestrator:
    """The canonical execution path for every user interaction.

    Wires together: Policy → Context → Model → Tools → Evidence → Memory.

    Usage:
        orch = MeteorOrchestrator(
            policy=sql_policy_engine,
            context=context_builder,
            model=model_adapter,
            tools=tool_executor,
            memory=memory_adapter,
            evidence=evidence_tracker,
            observability=observability_adapter,
        )
        response = orch.handle(OrchestratorRequest(prompt="What is on my system?"))
    """

    def __init__(
        self,
        policy: SqlPolicyEngine,
        context: ContextBuilder,
        model: ModelAdapter,
        tools: ToolExecutor,
        memory: MemoryAdapter,
        evidence: EvidenceTracker,
        observability=None,
    ) -> None:
        self.policy = policy
        self.context = context
        self.model = model
        self.tools = tools
        self.memory = memory
        self.evidence = evidence
        self.observability = observability

    def handle(self, request: OrchestratorRequest) -> OrchestratorResponse:
        """Execute the full pipeline synchronously."""
        import time
        start = time.monotonic()

        session_id = request.session_id or str(uuid.uuid4())

        # 1. Policy Gate
        from app.policy.contract import PolicyRequest, PolicySubject
        pol_req = PolicyRequest(
            subject=PolicySubject.RUNTIME,
            action="invoke",
            context={"session_id": session_id, "prompt": request.prompt[:100]},
        )
        pol_decision = self.policy.evaluate(pol_req)
        from app.policy.contract import PolicyAction
        if pol_decision.action == PolicyAction.DENY:
            return OrchestratorResponse(
                session_id=session_id,
                response_text="Policy denied this request.",
                finish_reason="policy_denied",
                duration_ms=(time.monotonic() - start) * 1000,
                policy_checked=True,
            )

        # 2. Context Assembly
        ctx = self.context.build(session_id, request.prompt)

        # 3. Model Inference
        model_input = ModelInput(
            prompt=ctx.final_prompt,
            context=ctx.conversation_history,
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            metadata=request.metadata,
        )
        model_output = self.model.complete(model_input)

        response_text = model_output.response_text

        # 4. Tool Loop (if model asks for tools)
        tool_results: list[ToolResult] = []
        iterations = 0
        while iterations < request.max_tool_iterations:
            tool_request = self._parse_tool_request(response_text)
            if not tool_request:
                break

            tool_result = self.tools.execute(
                tool=tool_request.tool,
                operation=tool_request.operation,
                params=tool_request.params,
                session_id=session_id,
            )
            tool_results.append(tool_result)

            if tool_result.status != ToolResultStatus.OK:
                break

            # Feed tool result back to model for continued reasoning
            follow_up = ModelInput(
                prompt=f"Previous response:\n{response_text}\n\n"
                       f"Tool result [{tool_result.tool}.{tool_result.operation}]:\n"
                       f"{tool_result.result}\n\n"
                       f"Continue reasoning. What do you conclude?",
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )
            follow_output = self.model.complete(follow_up)
            response_text = follow_output.response_text
            iterations += 1

        # 5. Evidence Annotation
        evidence_records = []
        if ctx.retrieved_documents:
            claim = self.evidence.annotate_response_with_evidence(
                response_text=response_text,
                retrieved_documents=ctx.retrieved_documents,
            )
            evidence_records = [
                {
                    "source": e.source,
                    "confidence": e.confidence.value,
                    "trace": e.trace,
                }
                for e in claim.evidence[:5]
            ]

        # 6. Memory Persistence
        self._persist_conversation(session_id, request.prompt, response_text, ctx)

        # 7. Audit
        if self.observability:
            self.observability.audit(AuditEntry(
                event="orchestration",
                layer="runtime",
                subject="orchestrator",
                action="handle",
                decision="allow",
                timestamp=datetime.now(timezone.utc).isoformat(),
                metadata={
                    "session_id": session_id,
                    "tool_operations": len(tool_results),
                    "evidence_count": len(evidence_records),
                },
            ))

        elapsed = (time.monotonic() - start) * 1000

        return OrchestratorResponse(
            session_id=session_id,
            response_text=response_text,
            finish_reason=model_output.finish_reason,
            token_usage=model_output.token_usage,
            tool_results=tool_results,
            evidence=evidence_records,
            context=ctx,
            duration_ms=elapsed,
            policy_checked=True,
            metadata={
                "tool_iterations": len(tool_results),
                "retrieved_docs": len(ctx.retrieved_documents),
                "corrections_applied": len(ctx.corrections),
            },
        )

    def handle_stream(self, request: OrchestratorRequest) -> Iterator[str]:
        """Execute the pipeline with streaming output."""
        session_id = request.session_id or str(uuid.uuid4())

        ctx = self.context.build(session_id, request.prompt)
        model_input = ctx.to_model_input(
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )

        for token in self.model.stream(model_input):
            yield token

        # Persist in background
        self._persist_conversation(session_id, request.prompt, "[streamed]", ctx)

    def _parse_tool_request(self, response_text: str) -> Optional[ToolRequest]:
        """Parse a tool invocation from model output.

        Looks for patterns like:
        TOOL: filesystem.read(path="/tmp/log.txt")
        or
        ```
        {"tool": "shell", "operation": "run", "params": {"command": "ls"}}
        ```
        """
        import json

        # JSON block pattern
        if "```json" in response_text:
            parts = response_text.split("```json", 1)
            if len(parts) > 1:
                json_part = parts[1].split("```", 1)[0].strip()
                try:
                    data = json.loads(json_part)
                    if "tool" in data and "operation" in data:
                        return ToolRequest(
                            tool=data["tool"],
                            operation=data["operation"],
                            params=data.get("params", {}),
                        )
                except json.JSONDecodeError:
                    pass

        # TOOL: pattern
        import re
        match = re.search(r"TOOL:\s*(\w+)\.(\w+)\(([^)]*)\)", response_text)
        if match:
            tool, operation, args_str = match.groups()
            params = {}
            for arg in args_str.split(","):
                arg = arg.strip()
                if "=" in arg:
                    k, v = arg.split("=", 1)
                    params[k.strip()] = v.strip().strip("'\"")
            return ToolRequest(tool=tool, operation=operation, params=params)

        return None

    def _persist_conversation(self, session_id: str, user_prompt: str, response: str, ctx: BuiltContext) -> None:
        """Persist the conversation exchange to memory."""
        now = datetime.now(timezone.utc).isoformat()

        user_entry = MemoryEntry(
            memory_type=MemoryType.CONVERSATION,
            content=user_prompt,
            session_id=session_id,
            timestamp=now,
            metadata={"role": "user"},
        )
        self.memory.write(user_entry)

        assistant_entry = MemoryEntry(
            memory_type=MemoryType.CONVERSATION,
            content=response,
            session_id=session_id,
            timestamp=now,
            metadata={
                "role": "assistant",
                "evidence_count": len(ctx.evidence),
                "retrieved_count": len(ctx.retrieved_documents),
            },
        )
        self.memory.write(assistant_entry)

    def health(self) -> dict:
        return {
            "healthy": True,
            "context_builder": self.context.health(),
            "budget_state": self.tools.get_budget_state(),
        }
