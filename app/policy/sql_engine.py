"""SQL-based policy engine — rules as SQL expressions, runtime-updatable.

Meteor Doctrine #1: Policy gates everything. This engine loads rules from SQLite,
evaluates them using SQL expressions against request context, and supports
live-updatable rules without code deploys.

Rules are stored as rows with priority, condition (SQL expression), and decision.
Evaluation queries the rules table with the request context bound as parameters.
"""

from __future__ import annotations

import logging
from typing import Optional

from app.policy.contract import PolicyAction, PolicyDecision, PolicyRequest, PolicySubject
from app.storage.sqlite_adapter import SQLiteAdapter

logger = logging.getLogger(__name__)


class SqlPolicyRule:
    """A single policy rule loaded from the database."""

    def __init__(
        self,
        rule_id: int,
        priority: int,
        subject: str,
        action: str,
        condition_sql: str,
        decision: str,
        reason: str,
    ) -> None:
        self.id = rule_id
        self.priority = priority
        self.subject = subject
        self.action = action
        self.condition_sql = condition_sql
        self.decision = decision
        self.reason = reason

    def matches(self, request: PolicyRequest) -> bool:
        """Check if this rule matches the request's subject and action."""
        return request.subject.value == self.subject and request.action == self.action


class SqlPolicyEngine:
    """Policy engine backed by SQLite.

    Rules are stored in the `policy_rules` table in the audit database.
    Evaluation queries rules by priority, checking SQL conditions against
    the request context.

    Migration 'create_policy_rules' must have been applied to the audit store.
    """

    DEFAULT_RULES = [
        ("""
            INSERT INTO policy_rules (priority, subject, action, condition_sql, decision, reason)
            VALUES (1, 'runtime', 'invoke', '1=1', 'allow', 'Runtime invocation is always allowed')
        """),
        ("""
            INSERT INTO policy_rules (priority, subject, action, condition_sql, decision, reason)
            VALUES (2, 'filesystem', 'read', 'path NOT LIKE ''%../%'' AND path NOT LIKE ''%/etc/%''', 'allow', 'Filesystem read allowed for safe paths')
        """),
        ("""
            INSERT INTO policy_rules (priority, subject, action, condition_sql, decision, reason)
            VALUES (3, 'network', 'connect', 'url NOT LIKE ''%doubleclick%'' AND url NOT LIKE ''%tracker%''', 'allow', 'Network allowed for non-tracking URLs')
        """),
        ("""
            INSERT INTO policy_rules (priority, subject, action, condition_sql, decision, reason)
            VALUES (4, 'memory', 'write', '1=1', 'allow', 'Memory writes are always allowed')
        """),
        ("""
            INSERT INTO policy_rules (priority, subject, action, condition_sql, decision, reason)
            VALUES (5, 'model', 'inference', '1=1', 'allow', 'Model inference is always allowed')
        """),
        ("""
            INSERT INTO policy_rules (priority, subject, action, condition_sql, decision, reason)
            VALUES (100, '*', '*', '1=1', 'deny', 'Default deny: no matching allow rule')
        """),
    ]

    def __init__(self, storage: SQLiteAdapter) -> None:
        self._storage = storage
        self._ensure_rules_table()
        self._seed_default_rules()

    def _ensure_rules_table(self) -> None:
        """Ensure the policy_rules table exists (idempotent)."""
        try:
            self._storage.execute("SELECT 1 FROM policy_rules LIMIT 1", store="audit")
        except Exception:
            logger.info("Creating policy_rules table in audit store")
            self._storage.execute(
                """
                CREATE TABLE IF NOT EXISTS policy_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    priority INTEGER NOT NULL DEFAULT 100,
                    subject TEXT NOT NULL,
                    action TEXT NOT NULL,
                    condition_sql TEXT NOT NULL DEFAULT '1=1',
                    decision TEXT NOT NULL DEFAULT 'deny',
                    reason TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """,
                store="audit",
            )
            self._storage.execute(
                "CREATE INDEX IF NOT EXISTS idx_policy_rules_lookup ON policy_rules(subject, action, priority)",
                store="audit",
            )

    def _seed_default_rules(self) -> None:
        """Seed default rules if the table is empty."""
        count = self._storage.execute(
            "SELECT COUNT(*) as cnt FROM policy_rules", store="audit"
        )
        if count[0]["cnt"] == 0:
            logger.info("Seeding default policy rules")
            for sql in self.DEFAULT_RULES:
                self._storage.execute(sql, store="audit")

    def evaluate(self, request: PolicyRequest) -> PolicyDecision:
        """Evaluate a policy request against SQL rules.

        Queries all matching rules by priority, evaluates their SQL condition
        against the request context, and returns the decision of the first
        matching rule.
        """
        rows = self._storage.execute(
            """
            SELECT id, priority, subject, action, condition_sql, decision, reason
            FROM policy_rules
            WHERE (subject = ?1 OR subject = '*')
              AND (action = ?2 OR action = '*')
            ORDER BY priority ASC
            """,
            (request.subject.value, request.action),
            store="audit",
        )

        for row in rows:
            rule = SqlPolicyRule(
                rule_id=row["id"],
                priority=row["priority"],
                subject=row["subject"],
                action=row["action"],
                condition_sql=row["condition_sql"],
                decision=row["decision"],
                reason=row["reason"],
            )

            if self._evaluate_condition(rule.condition_sql, request.context):
                decision_action = (
                    PolicyAction.ALLOW if rule.decision == "allow" else PolicyAction.DENY
                )
                logger.debug(
                    "Policy rule %d matched: %s:%s → %s (%s)",
                    rule.id,
                    rule.subject,
                    rule.action,
                    rule.decision,
                    rule.reason,
                )
                return PolicyDecision(
                    action=decision_action,
                    subject=request.subject,
                    reason=rule.reason,
                )

        return PolicyDecision(
            action=PolicyAction.DENY,
            subject=request.subject,
            reason="No matching policy rule found (default deny)",
        )

    def _evaluate_condition(self, condition_sql: str, context: dict) -> bool:
        """Evaluate a SQL condition against request context.

        Replaces placeholders in the condition_sql with values from the context
        dict, then evaluates using SQLite's expression evaluator.
        """
        if condition_sql == "1=1":
            return True

        if condition_sql == "1=0":
            return False

        try:
            resolved = condition_sql
            for key, value in context.items():
                if isinstance(value, str):
                    escaped = value.replace("'", "''")
                    resolved = resolved.replace(key, f"'{escaped}'")
                elif isinstance(value, (int, float)):
                    resolved = resolved.replace(key, str(value))
                elif isinstance(value, bool):
                    resolved = resolved.replace(key, "1" if value else "0")

            rows = self._storage.execute(
                f"SELECT ({resolved}) as result", store="audit"
            )
            return bool(rows[0]["result"]) if rows else False

        except Exception as e:
            logger.warning("Failed to evaluate condition '%s': %s", condition_sql, e)
            return False

    def add_rule(
        self,
        priority: int,
        subject: str,
        action: str,
        condition_sql: str,
        decision: str,
        reason: str,
    ) -> int:
        """Add a new policy rule. Returns the new rule's ID."""
        self._storage.execute(
            """
            INSERT INTO policy_rules (priority, subject, action, condition_sql, decision, reason)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (priority, subject, action, condition_sql, decision, reason),
            store="audit",
        )
        rows = self._storage.execute(
            "SELECT last_insert_rowid() as id", store="audit"
        )
        rule_id = rows[0]["id"]
        logger.info("Added policy rule %d: %s:%s → %s", rule_id, subject, action, decision)
        return rule_id

    def remove_rule(self, rule_id: int) -> bool:
        """Remove a policy rule by ID. Returns True if removed."""
        self._storage.execute(
            "DELETE FROM policy_rules WHERE id = ?", (rule_id,), store="audit"
        )
        rows = self._storage.execute(
            "SELECT changes() as cnt", store="audit"
        )
        removed = rows[0]["cnt"] > 0
        if removed:
            logger.info("Removed policy rule %d", rule_id)
        return removed

    def list_rules(self) -> list[dict]:
        """List all policy rules ordered by priority."""
        rows = self._storage.execute(
            """
            SELECT id, priority, subject, action, condition_sql, decision, reason, created_at
            FROM policy_rules
            ORDER BY priority ASC, id ASC
            """,
            store="audit",
        )
        return [dict(row) for row in rows]

    def update_rule(self, rule_id: int, **kwargs) -> bool:
        """Update fields of a policy rule. Returns True if updated."""
        allowed_fields = {"priority", "subject", "action", "condition_sql", "decision", "reason"}
        updates = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not updates:
            return False

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [rule_id]

        self._storage.execute(
            f"UPDATE policy_rules SET {set_clause}, updated_at = datetime('now') WHERE id = ?",
            tuple(values),
            store="audit",
        )
        rows = self._storage.execute(
            "SELECT changes() as cnt", store="audit"
        )
        updated = rows[0]["cnt"] > 0
        if updated:
            logger.info("Updated policy rule %d: %s", rule_id, list(updates.keys()))
        return updated


def build_sql_policy_engine(storage: SQLiteAdapter) -> SqlPolicyEngine:
    """Factory function to build a SqlPolicyEngine."""
    return SqlPolicyEngine(storage)
