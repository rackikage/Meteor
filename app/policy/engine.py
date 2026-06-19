from __future__ import annotations

from pathlib import Path

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
            requested_path = request.context.get("path")
            if not requested_path:
                return False

            resolved_request_path = Path(requested_path).resolve(strict=False)
            for allowed_root in rule.paths:
                resolved_root = Path(allowed_root).resolve(strict=False)
                if resolved_request_path == resolved_root or resolved_request_path.is_relative_to(resolved_root):
                    return True
            return False

        return True


def build_policy_engine(config: MeteorConfig) -> PolicyEngine:
    return PolicyEngine(config)
