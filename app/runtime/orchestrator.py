from __future__ import annotations

from app.bootstrap import bootstrap
from app.policy.contract import PolicyAction, PolicyRequest, PolicySubject
from app.policy.engine import PolicyEngine, build_policy_engine
from app.runtime.contract import RuntimeRequest, RuntimeResponse, RuntimeStatus


class RuntimeOrchestrator:
    def __init__(self, policy_engine: PolicyEngine) -> None:
        self._policy = policy_engine

    def handle(self, request: RuntimeRequest) -> RuntimeResponse:
        policy_request = PolicyRequest(
            subject=PolicySubject.RUNTIME,
            action="invoke",
            context={"prompt_length": len(request.prompt)},
        )
        decision = self._policy.evaluate(policy_request)

        if decision.action == PolicyAction.DENY:
            return RuntimeResponse(
                response_text="Request denied by policy.",
                status=RuntimeStatus.POLICY_DENIED,
                metadata={
                    "policy_reason": decision.reason,
                    "policy_action": "runtime_denied",
                    "policy_subject": "runtime",
                },
            )

        return RuntimeResponse(
            response_text="Runtime is not wired yet. Model inference adapter is not connected.",
            status=RuntimeStatus.NOT_IMPLEMENTED,
            evidence=[],
            metadata={
                "policy_reason": decision.reason,
                "policy_action": "runtime_invoke",
                "policy_subject": "runtime",
                "model_wired": False,
                "retrieval_wired": False,
                "memory_wired": False,
            },
        )


def build_orchestrator() -> RuntimeOrchestrator:
    result = bootstrap()
    engine = build_policy_engine(result.config)
    return RuntimeOrchestrator(policy_engine=engine)
