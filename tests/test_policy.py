from __future__ import annotations

from pathlib import Path

from app.config import MeteorConfig
from app.policy.contract import PolicyAction, PolicyRequest, PolicySubject
from app.policy.engine import build_policy_engine

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"


def _engine():
    config = MeteorConfig.load(CONFIG_PATH)
    return build_policy_engine(config)


def test_policy_allows_runtime_invoke() -> None:
    engine = _engine()
    decision = engine.evaluate(
        PolicyRequest(subject=PolicySubject.RUNTIME, action="invoke", context={})
    )
    assert decision.action == PolicyAction.ALLOW


def test_policy_denies_unknown_subject() -> None:
    engine = _engine()
    decision = engine.evaluate(
        PolicyRequest(subject=PolicySubject.NETWORK, action="connect", context={})
    )
    assert decision.action == PolicyAction.DENY


def test_policy_denies_by_default() -> None:
    engine = _engine()
    decision = engine.evaluate(
        PolicyRequest(subject=PolicySubject.MODEL, action="execute", context={})
    )
    assert decision.action == PolicyAction.DENY


def test_policy_allows_filesystem_read_on_allowed_path() -> None:
    engine = _engine()
    decision = engine.evaluate(
        PolicyRequest(
            subject=PolicySubject.FILESYSTEM,
            action="read",
            context={"path": "./config/meteor.yaml"},
        )
    )
    assert decision.action == PolicyAction.ALLOW


def test_policy_denies_filesystem_read_on_disallowed_path() -> None:
    engine = _engine()
    decision = engine.evaluate(
        PolicyRequest(
            subject=PolicySubject.FILESYSTEM,
            action="read",
            context={"path": "/etc/passwd"},
        )
    )
    assert decision.action == PolicyAction.DENY


def test_policy_decision_is_audited() -> None:
    engine = _engine()
    decision = engine.evaluate(
        PolicyRequest(subject=PolicySubject.RUNTIME, action="invoke", context={})
    )
    assert decision.audited is True
