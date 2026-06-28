"""Tests for the SQL-based policy engine.

Verifies: rule loading, condition evaluation, CRUD operations, default deny.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.config import MeteorConfig
from app.policy.contract import PolicyAction, PolicyRequest, PolicySubject
from app.policy.sql_engine import SqlPolicyEngine, build_sql_policy_engine
from app.storage.sqlite_adapter import build_sqlite_adapter


CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "meteor.yaml"


@pytest.fixture
def sql_policy_engine(tmp_path):
    config = MeteorConfig.load(CONFIG_PATH)
    config.storage.paths.memory = str(tmp_path / "test_memory.db")
    config.storage.paths.audit = str(tmp_path / "test_audit.db")
    config.storage.paths.index_meta = str(tmp_path / "test_index_meta.db")
    storage = build_sqlite_adapter(config.storage, tmp_path)
    engine = build_sql_policy_engine(storage)
    yield engine
    storage.close()


class TestSqlPolicyEngineDefaults:

    def test_default_rules_are_seeded(self, sql_policy_engine):
        rules = sql_policy_engine.list_rules()
        assert len(rules) >= 3

    def test_runtime_invoke_is_allowed(self, sql_policy_engine):
        request = PolicyRequest(
            subject=PolicySubject.RUNTIME,
            action="invoke",
            context={},
        )
        decision = sql_policy_engine.evaluate(request)
        assert decision.action == PolicyAction.ALLOW

    def test_unknown_subject_is_denied(self, sql_policy_engine):
        request = PolicyRequest(
            subject=PolicySubject.NETWORK,
            action="connect",
            context={"url": "https://doubleclick.net/ad"},
        )
        decision = sql_policy_engine.evaluate(request)
        assert decision.action == PolicyAction.DENY

    def test_network_allowed_for_safe_url(self, sql_policy_engine):
        request = PolicyRequest(
            subject=PolicySubject.NETWORK,
            action="connect",
            context={"url": "https://example.com"},
        )
        decision = sql_policy_engine.evaluate(request)
        assert decision.action == PolicyAction.ALLOW

    def test_filesystem_safe_path_allowed(self, sql_policy_engine):
        request = PolicyRequest(
            subject=PolicySubject.FILESYSTEM,
            action="read",
            context={"path": "./data/file.txt"},
        )
        decision = sql_policy_engine.evaluate(request)
        assert decision.action == PolicyAction.ALLOW

    def test_filesystem_dangerous_path_denied(self, sql_policy_engine):
        request = PolicyRequest(
            subject=PolicySubject.FILESYSTEM,
            action="read",
            context={"path": "../etc/passwd"},
        )
        decision = sql_policy_engine.evaluate(request)
        assert decision.action == PolicyAction.DENY

    def test_model_inference_allowed(self, sql_policy_engine):
        request = PolicyRequest(
            subject=PolicySubject.MODEL,
            action="inference",
            context={},
        )
        decision = sql_policy_engine.evaluate(request)
        assert decision.action == PolicyAction.ALLOW

    def test_memory_write_allowed(self, sql_policy_engine):
        request = PolicyRequest(
            subject=PolicySubject.MEMORY,
            action="write",
            context={},
        )
        decision = sql_policy_engine.evaluate(request)
        assert decision.action == PolicyAction.ALLOW


class TestSqlPolicyEngineCrud:

    def test_add_rule(self, sql_policy_engine):
        before_count = len(sql_policy_engine.list_rules())
        rule_id = sql_policy_engine.add_rule(
            priority=10,
            subject="tool",
            action="execute",
            condition_sql="tool_name != 'rm'",
            decision="allow",
            reason="Allow safe tools",
        )
        assert rule_id > 0
        assert len(sql_policy_engine.list_rules()) == before_count + 1

    def test_remove_rule(self, sql_policy_engine):
        rule_id = sql_policy_engine.add_rule(
            priority=50,
            subject="test",
            action="test",
            condition_sql="1=1",
            decision="allow",
            reason="test rule",
        )
        assert sql_policy_engine.remove_rule(rule_id) is True
        assert sql_policy_engine.remove_rule(rule_id) is False

    def test_update_rule(self, sql_policy_engine):
        rule_id = sql_policy_engine.add_rule(
            priority=50,
            subject="test",
            action="test",
            condition_sql="1=1",
            decision="allow",
            reason="original",
        )
        updated = sql_policy_engine.update_rule(rule_id, reason="updated", priority=25)
        assert updated is True

        rules = sql_policy_engine.list_rules()
        rule = next(r for r in rules if r["id"] == rule_id)
        assert rule["reason"] == "updated"
        assert rule["priority"] == 25

    def test_update_rule_invalid_field(self, sql_policy_engine):
        rule_id = sql_policy_engine.add_rule(
            priority=50,
            subject="test",
            action="test",
            condition_sql="1=1",
            decision="allow",
            reason="test",
        )
        updated = sql_policy_engine.update_rule(rule_id, invalid_field="value")
        assert updated is False

    def test_added_rule_is_evaluated(self, sql_policy_engine):
        sql_policy_engine.add_rule(
            priority=1,
            subject="tool",
            action="run",
            condition_sql="tool_name = 'safe_tool'",
            decision="allow",
            reason="Allow safe_tool specifically",
        )
        request = PolicyRequest(
            subject=PolicySubject.TOOL,
            action="run",
            context={"tool_name": "safe_tool"},
        )
        decision = sql_policy_engine.evaluate(request)
        assert decision.action == PolicyAction.ALLOW


class TestSqlPolicyEngineConditionEvaluation:

    def test_always_true_condition(self, sql_policy_engine):
        assert sql_policy_engine._evaluate_condition("1=1", {}) is True

    def test_always_false_condition(self, sql_policy_engine):
        assert sql_policy_engine._evaluate_condition("1=0", {}) is False

    def test_string_equality_condition(self, sql_policy_engine):
        assert sql_policy_engine._evaluate_condition(
            "url = 'https://example.com'",
            {"url": "https://example.com"},
        ) is True

    def test_string_not_equal_condition(self, sql_policy_engine):
        assert sql_policy_engine._evaluate_condition(
            "url != 'https://bad.com'",
            {"url": "https://good.com"},
        ) is True

    def test_like_condition(self, sql_policy_engine):
        assert sql_policy_engine._evaluate_condition(
            "url LIKE '%tracker%'",
            {"url": "https://tracker.example.com"},
        ) is True

    def test_not_like_condition(self, sql_policy_engine):
        assert sql_policy_engine._evaluate_condition(
            "url NOT LIKE '%tracker%'",
            {"url": "https://safe.com"},
        ) is True

    def test_numeric_condition(self, sql_policy_engine):
        assert sql_policy_engine._evaluate_condition(
            "depth < 5",
            {"depth": 3},
        ) is True

    def test_compound_and_condition(self, sql_policy_engine):
        assert sql_policy_engine._evaluate_condition(
            "url NOT LIKE '%tracker%' AND depth < 5",
            {"url": "https://safe.com", "depth": 3},
        ) is True

    def test_compound_or_condition(self, sql_policy_engine):
        assert sql_policy_engine._evaluate_condition(
            "url LIKE '%tracker%' OR url LIKE '%ads%'",
            {"url": "https://ads.example.com"},
        ) is True


class TestSqlPolicyEnginePriority:

    def test_higher_priority_rule_wins(self, sql_policy_engine):
        sql_policy_engine.add_rule(
            priority=1,
            subject="test_priority",
            action="check",
            condition_sql="1=1",
            decision="deny",
            reason="Highest priority deny",
        )
        sql_policy_engine.add_rule(
            priority=10,
            subject="test_priority",
            action="check",
            condition_sql="1=1",
            decision="allow",
            reason="Lower priority allow",
        )
        request = PolicyRequest(
            subject=PolicySubject.RUNTIME,
            action="check",
            context={},
        )
        decision = sql_policy_engine.evaluate(request)
        assert decision.action == PolicyAction.DENY
        assert "test_priority" in str(sql_policy_engine.list_rules())

    def test_wildcard_subject_catches_all(self, sql_policy_engine):
        """The default deny rule with subject='*' catches unmatched requests."""
        request = PolicyRequest(
            subject=PolicySubject.RUNTIME,
            action="nonexistent_action",
            context={},
        )
        decision = sql_policy_engine.evaluate(request)
        assert decision.action == PolicyAction.DENY
