from __future__ import annotations

from app.config import MeteorConfig, PolicyAllowRule
from app.policy.contract import PolicyAction, PolicyDecision, PolicyRequest, PolicySubject


class PolicyEngine:
    def __init__(self, config: MeteorConfig) -> None:
        self._config = config

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        for rule in self._config.policy.allow_rules:
            if self._rule_matches(rule, request):
                return PolicyDecision(
                    action=PolicyAction.ALLOW,
                    subject=request.subject,
                    reason=f"Matched allow rule: subject={rule.subject} action={rule.action}",
                )

        return PolicyDecision(
            action=PolicyAction.DENY,
            subject=request.subject,
            reason="Default deny: no matching allow rule.",
        )

    def _rule_matches(self, rule: PolicyAllowRule, request: PolicyRequest) -> bool:
        subject_match = rule.subject == request.subject.value
        action_match = rule.action == request.action

        if not (subject_match and action_match):
            return False

        if rule.paths:
            path = request.context.get("path", "")
            return any(path.startswith(p) for p in rule.paths)

        return True


def build_policy_engine(config: MeteorConfig) -> PolicyEngine:
    return PolicyEngine(config)
