from __future__ import annotations

from dataclasses import dataclass

from app.bootstrap import bootstrap, resolve_repo_path
from app.context.builder import ContextBuilder
from app.evidence.builder import evidence_from_model, evidence_from_policy, evidence_from_retrieval, utc_now
from app.memory.contract import MemoryEntry, MemoryType
from app.memory.sqlite_adapter import SQLiteMemoryAdapter
from app.models.contract import ModelInput
from app.models.null_adapter import DisabledModelAdapter
from app.observability.contract import AuditEntry
from app.observability.memory_adapter import InMemoryObservabilityAdapter
from app.policy.contract import PolicyAction, PolicyDecision, PolicyRequest, PolicySubject
from app.policy.engine import PolicyEngine, build_policy_engine
from app.retrieval.contract import RetrievalQuery
from app.retrieval.null_adapter import NullRetrievalAdapter
from app.runtime.contract import RuntimeRequest, RuntimeResponse, RuntimeStatus


@dataclass
class RuntimeAdapters:
    model: DisabledModelAdapter
    retrieval: NullRetrievalAdapter
    memory: SQLiteMemoryAdapter
    observability: InMemoryObservabilityAdapter
    context_builder: ContextBuilder


class RuntimeOrchestrator:
    def __init__(self, policy_engine: PolicyEngine, adapters: RuntimeAdapters) -> None:
        self._policy = policy_engine
        self._adapters = adapters

    def handle(self, request: RuntimeRequest) -> RuntimeResponse:
        policy_trace: list[dict] = []
        evidence = []

        runtime_decision = self._evaluate_policy(
            PolicyRequest(
                subject=PolicySubject.RUNTIME,
                action="invoke",
                context={
                    "prompt_length": len(request.prompt),
                    "session_id": request.session_id,
                },
            ),
            policy_trace,
        )
        evidence.append(evidence_from_policy(runtime_decision, "policy.runtime.invoke"))
        if runtime_decision.action == PolicyAction.DENY:
            return RuntimeResponse(
                response_text="Request denied by policy.",
                status=RuntimeStatus.POLICY_DENIED,
                evidence=evidence,
                metadata={
                    "policy_reason": runtime_decision.reason,
                    "policy_action": "runtime_denied",
                    "policy_subject": "runtime",
                    "runtime_wired": True,
                },
            )

        memories = self._read_memory(request, policy_trace, evidence)
        retrieval_result = self._retrieve(request, policy_trace, evidence)
        context = self._adapters.context_builder.build(
            request=request,
            memory=memories,
            documents=retrieval_result.documents,
            policy_trace=policy_trace,
        )

        model_decision = self._evaluate_policy(
            PolicyRequest(
                subject=PolicySubject.MODEL,
                action="execute",
                context={"session_id": request.session_id, "context_items": len(context.to_model_context())},
            ),
            policy_trace,
        )
        evidence.append(evidence_from_policy(model_decision, "policy.model.execute"))
        if model_decision.action == PolicyAction.DENY:
            return RuntimeResponse(
                response_text="Model execution denied by policy.",
                status=RuntimeStatus.POLICY_DENIED,
                evidence=evidence,
                metadata={
                    "policy_reason": model_decision.reason,
                    "policy_action": "model_denied",
                    "policy_subject": "model",
                    "runtime_wired": True,
                },
            )

        model_output = self._adapters.model.complete(
            ModelInput(
                prompt=request.prompt,
                context=context.to_model_context(),
                metadata={
                    "session_id": request.session_id,
                    "request_metadata": request.metadata,
                    "context_metadata": context.metadata,
                },
            )
        )
        evidence.append(evidence_from_model(model_output))

        if request.store_in_memory:
            self._write_memory(request, model_output.response_text, policy_trace, evidence)

        model_wired = bool(model_output.metadata.get("wired"))
        status = RuntimeStatus.OK if model_wired else RuntimeStatus.DEGRADED

        return RuntimeResponse(
            response_text=model_output.response_text,
            status=status,
            evidence=evidence,
            metadata={
                "runtime_wired": True,
                "model_wired": model_wired,
                "retrieval_wired": bool(retrieval_result.metadata.get("wired")),
                "memory_wired": bool(self._adapters.memory.health().get("wired")),
                "context_item_count": len(context.to_model_context()),
                "policy_trace": policy_trace,
                "model_finish_reason": model_output.finish_reason,
            },
        )

    def health(self) -> dict:
        model = self._adapters.model.health()
        retrieval = self._adapters.retrieval.health()
        memory = self._adapters.memory.health()
        observability = self._adapters.observability.health()
        return {
            "runtime_wired": True,
            "model": model,
            "retrieval": retrieval,
            "memory": memory,
            "observability": {
                "component": observability.component,
                "healthy": observability.healthy,
                "detail": observability.detail,
                **observability.metadata,
            },
        }

    def _read_memory(self, request: RuntimeRequest, policy_trace: list[dict], evidence: list) -> list[MemoryEntry]:
        decision = self._evaluate_policy(
            PolicyRequest(
                subject=PolicySubject.MEMORY,
                action="read",
                context={"session_id": request.session_id, "memory_type": MemoryType.CONVERSATION.value},
            ),
            policy_trace,
        )
        evidence.append(evidence_from_policy(decision, "policy.memory.read"))
        if decision.action == PolicyAction.DENY:
            return []
        return self._adapters.memory.read(request.session_id, MemoryType.CONVERSATION, limit=10)

    def _write_memory(
        self,
        request: RuntimeRequest,
        response_text: str,
        policy_trace: list[dict],
        evidence: list,
    ) -> None:
        decision = self._evaluate_policy(
            PolicyRequest(
                subject=PolicySubject.MEMORY,
                action="write",
                context={"session_id": request.session_id, "memory_type": MemoryType.CONVERSATION.value},
            ),
            policy_trace,
        )
        evidence.append(evidence_from_policy(decision, "policy.memory.write"))
        if decision.action == PolicyAction.DENY:
            return
        self._adapters.memory.write(
            MemoryEntry(
                memory_type=MemoryType.CONVERSATION,
                content=f"user: {request.prompt}\nassistant: {response_text}",
                session_id=request.session_id,
                timestamp=utc_now(),
                metadata={"source": "runtime"},
            )
        )

    def _retrieve(self, request: RuntimeRequest, policy_trace: list[dict], evidence: list):
        decision = self._evaluate_policy(
            PolicyRequest(
                subject=PolicySubject.INDEX,
                action="read",
                context={"session_id": request.session_id, "top_k": request.top_k},
            ),
            policy_trace,
        )
        evidence.append(evidence_from_policy(decision, "policy.index.read"))
        if decision.action == PolicyAction.DENY:
            query = RetrievalQuery(query_text=request.prompt, top_k=request.top_k)
            return self._adapters.retrieval.query(query)
        result = self._adapters.retrieval.query(RetrievalQuery(query_text=request.prompt, top_k=request.top_k))
        evidence.extend(evidence_from_retrieval(result))
        return result

    def _evaluate_policy(self, request: PolicyRequest, policy_trace: list[dict]) -> PolicyDecision:
        decision = self._policy.evaluate(request)
        policy_trace.append(
            {
                "subject": request.subject.value,
                "action": request.action,
                "decision": decision.action.value,
                "reason": decision.reason,
            }
        )
        self._adapters.observability.audit(
            AuditEntry(
                event="policy_decision",
                layer="runtime",
                subject=request.subject.value,
                action=request.action,
                decision=decision.action.value,
                timestamp=utc_now(),
                metadata={"reason": decision.reason},
            )
        )
        return decision


def build_orchestrator() -> RuntimeOrchestrator:
    result = bootstrap()
    config = result.config
    engine = build_policy_engine(config, repo_root=result.repo_root)
    profile_name = config.models.default_profile
    profile = config.models.profiles[profile_name]
    memory_path = resolve_repo_path(result.repo_root, config.memory.path)
    adapters = RuntimeAdapters(
        model=DisabledModelAdapter(profile_name, profile, str(result.default_model_path)),
        retrieval=NullRetrievalAdapter(),
        memory=SQLiteMemoryAdapter(memory_path),
        observability=InMemoryObservabilityAdapter(),
        context_builder=ContextBuilder(),
    )
    return RuntimeOrchestrator(policy_engine=engine, adapters=adapters)
