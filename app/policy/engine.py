from __future__ import annotations

from pathlib import Path

from app.config import MeteorConfig, PolicyAllowRule
from app.policy.contract import PolicyAction, PolicyDecision, PolicyRequest


class PolicyEngine:
    def __init__(self, config: MeteorConfig, repo_root: Path | None = None) -> None:
        self._config = config
        self._repo_root = repo_root.resolve(strict=False) if repo_root else Path.cwd().resolve(strict=False)

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

            resolved_request_path = self._resolve_policy_path(str(requested_path))
            for allowed_root in rule.paths:
                resolved_root = self._resolve_policy_path(allowed_root)
                if resolved_request_path == resolved_root or resolved_request_path.is_relative_to(resolved_root):
                    return True
            return False

        return True

    def _resolve_policy_path(self, path_value: str) -> Path:
        path = Path(path_value)
        if path.is_absolute():
            return path.resolve(strict=False)
        return (self._repo_root / path).resolve(strict=False)


def build_policy_engine(config: MeteorConfig, repo_root: Path | None = None) -> PolicyEngine:
    return PolicyEngine(config, repo_root=repo_root)
