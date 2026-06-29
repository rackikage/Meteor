"""SQLite storage adapter — persistent storage with schema migrations.

Meteor Doctrine #5: Memory is infrastructure. This adapter provides durable
local storage for memory, audit logs, and index metadata. All data stays on
the user's machine — no cloud dependency.

Meteor Doctrine #8: Contracts outlive implementations. The StorageAdapter
contract is stable; this SQLite implementation can be swapped for PostgreSQL,
DuckDB, or any other backend without changing calling code.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from app.config import StorageConfig
from app.storage.contract import MigrationRecord, StorageAdapter

logger = logging.getLogger(__name__)


class SQLiteAdapter(StorageAdapter):
    """SQLite-backed storage with migration support.

    Manages multiple database files (memory, audit, index_meta) with versioned
    schema migrations. Each database is isolated — no cross-database joins.
    """

    def __init__(self, config: StorageConfig, repo_root: Path) -> None:
        self.config = config
        self.repo_root = repo_root
        self._connections: dict[str, sqlite3.Connection] = {}
        self._init_databases()

    def _init_databases(self) -> None:
        """Initialize all database files and run migrations."""
        paths = {
            "memory": self.config.paths.memory,
            "audit": self.config.paths.audit,
            "index_meta": self.config.paths.index_meta,
        }

        for store_name, db_path in paths.items():
            resolved_path = Path(db_path)
            if not resolved_path.is_absolute():
                resolved_path = (self.repo_root / resolved_path).resolve()

            resolved_path.parent.mkdir(parents=True, exist_ok=True)

            conn = sqlite3.connect(str(resolved_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")

            self._connections[store_name] = conn
            logger.info("Connected to %s: %s", store_name, resolved_path)

            self._run_migrations(store_name, conn)

    def _run_migrations(self, store_name: str, conn: sqlite3.Connection) -> None:
        """Run pending migrations for a database."""
        conn.execute("""
            CREATE TABLE IF NOT EXISTS _migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TEXT NOT NULL
            )
        """)

        applied = {
            row["version"]
            for row in conn.execute("SELECT version FROM _migrations").fetchall()
        }

        migrations = self._get_migrations(store_name)
        for version, name, sql in migrations:
            if version not in applied:
                logger.info("Applying migration %d: %s", version, name)
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO _migrations (version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, datetime.now(timezone.utc).isoformat()),
                )
                conn.commit()

    def _get_migrations(self, store_name: str) -> list[tuple[int, str, str]]:
        """Return migrations for a store. Format: (version, name, sql)."""
        if store_name == "memory":
            return [
                (
                    1,
                    "create_memory_tables",
                    """
                    CREATE TABLE IF NOT EXISTS conversations (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        metadata TEXT
                    );

                    CREATE INDEX IF NOT EXISTS idx_conversations_session
                        ON conversations(session_id);

                    CREATE TABLE IF NOT EXISTS episodic_memory (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        metadata TEXT
                    );

                    CREATE INDEX IF NOT EXISTS idx_episodic_session
                        ON episodic_memory(session_id);

                    CREATE TABLE IF NOT EXISTS project_memory (
                        id TEXT PRIMARY KEY,
                        project_name TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(project_name, key)
                    );

                    CREATE TABLE IF NOT EXISTS corrections (
                        id TEXT PRIMARY KEY,
                        session_id TEXT NOT NULL,
                        original TEXT NOT NULL,
                        corrected TEXT NOT NULL,
                        reason TEXT,
                        created_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_corrections_session
                        ON corrections(session_id);
                    """,
                ),
                (
                    2,
                    "install_reactive_memory_triggers",
                    """
                    CREATE TRIGGER IF NOT EXISTS trg_conversation_auto_topic
                    AFTER INSERT ON conversations
                    WHEN NEW.content IS NOT NULL
                    BEGIN
                        UPDATE conversations
                        SET metadata = json_set(
                            COALESCE(metadata, '{}'),
                            '$.auto_topic',
                            CASE
                                WHEN NEW.content LIKE '%error%' OR NEW.content LIKE '%bug%' OR NEW.content LIKE '%crash%'
                                    THEN 'debugging'
                                WHEN NEW.content LIKE '%python%' OR NEW.content LIKE '%function%' OR NEW.content LIKE '%import%'
                                    THEN 'programming'
                                WHEN NEW.content LIKE '%search%' OR NEW.content LIKE '%find%' OR NEW.content LIKE '%lookup%'
                                    THEN 'search'
                                WHEN NEW.content LIKE '%memory%' OR NEW.content LIKE '%remember%' OR NEW.content LIKE '%recall%'
                                    THEN 'memory_management'
                                WHEN NEW.content LIKE '%model%' OR NEW.content LIKE '%inference%' OR NEW.content LIKE '%generate%'
                                    THEN 'model_interaction'
                                WHEN NEW.content LIKE '%file%' OR NEW.content LIKE '%save%' OR NEW.content LIKE '%load%'
                                    THEN 'file_operations'
                                ELSE 'general'
                            END
                        )
                        WHERE id = NEW.id;
                    END;

                    CREATE TRIGGER IF NOT EXISTS trg_conversation_debug_episodic
                    AFTER INSERT ON conversations
                    WHEN NEW.content LIKE '%error%' OR NEW.content LIKE '%bug%' OR NEW.content LIKE '%crash%'
                    BEGIN
                        INSERT INTO episodic_memory (id, session_id, event_type, content, created_at, metadata)
                        VALUES (
                            hex(randomblob(16)),
                            NEW.session_id,
                            'debugging_session',
                            'User discussed: ' || substr(NEW.content, 1, 200),
                            datetime('now'),
                            json_object('source_conversation_id', NEW.id, 'trigger', 'auto_debug_detect')
                        );
                    END;

                    CREATE TRIGGER IF NOT EXISTS trg_correction_link_conversation
                    AFTER INSERT ON corrections
                    WHEN NEW.session_id IS NOT NULL
                    BEGIN
                        INSERT INTO episodic_memory (id, session_id, event_type, content, created_at, metadata)
                        VALUES (
                            hex(randomblob(16)),
                            NEW.session_id,
                            'correction_applied',
                            'Correction: ' || substr(NEW.original, 1, 100) || ' -> ' || substr(NEW.corrected, 1, 100),
                            datetime('now'),
                            json_object(
                                'correction_id', NEW.id,
                                'original', NEW.original,
                                'corrected', NEW.corrected,
                                'reason', NEW.reason,
                                'trigger', 'auto_correction_link'
                            )
                        );
                    END;

                    CREATE TRIGGER IF NOT EXISTS trg_conversation_topic_counter
                    AFTER INSERT ON conversations
                    WHEN NEW.content IS NOT NULL
                    BEGIN
                        INSERT OR REPLACE INTO project_memory (project_name, key, value, updated_at)
                        SELECT
                            'user_profile',
                            'topic_' || lower(
                                json_extract(
                                    COALESCE(
                                        (SELECT metadata FROM conversations WHERE id = NEW.id),
                                        '{}'
                                    ),
                                    '$.auto_topic'
                                )
                            ),
                            COALESCE(
                                CAST(json_extract(
                                    COALESCE(
                                        (SELECT value FROM project_memory
                                         WHERE project_name = 'user_profile'
                                         AND key = 'topic_' || lower(
                                             json_extract(
                                                 COALESCE(
                                                     (SELECT metadata FROM conversations WHERE id = NEW.id),
                                                     '{}'
                                                 ),
                                                 '$.auto_topic'
                                             )
                                         )),
                                        '0'
                                    ),
                                    '$'
                                ) AS INTEGER),
                                0
                            ) + 1,
                            datetime('now')
                        WHERE json_extract(
                            COALESCE(
                                (SELECT metadata FROM conversations WHERE id = NEW.id),
                                '{}'
                            ),
                            '$.auto_topic'
                        ) IS NOT NULL;
                    END;

                    CREATE TRIGGER IF NOT EXISTS trg_episodic_session_stats
                    AFTER INSERT ON episodic_memory
                    BEGIN
                        INSERT OR REPLACE INTO project_memory (project_name, key, value, updated_at)
                        VALUES (
                            'session_stats',
                            'last_event_type',
                            NEW.event_type,
                            datetime('now')
                        );
                    END;
                    """,
                ),
            ]

        elif store_name == "audit":
            return [
                (
                    1,
                    "create_audit_table",
                    """
                    CREATE TABLE IF NOT EXISTS audit_log (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event TEXT NOT NULL,
                        layer TEXT NOT NULL,
                        subject TEXT NOT NULL,
                        action TEXT NOT NULL,
                        decision TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        metadata TEXT
                    );

                    CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                        ON audit_log(timestamp);

                    CREATE INDEX IF NOT EXISTS idx_audit_event
                        ON audit_log(event);
                    """,
                ),
                (
                    2,
                    "create_policy_rules",
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
                    );

                    CREATE INDEX IF NOT EXISTS idx_policy_rules_lookup
                        ON policy_rules(subject, action, priority);

                    CREATE INDEX IF NOT EXISTS idx_policy_rules_priority
                        ON policy_rules(priority);
                    """,
                ),
                (
                    3,
                    "create_pentest_tables",
                    """
                    CREATE TABLE IF NOT EXISTS scan_results (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip TEXT NOT NULL,
                        port INTEGER NOT NULL,
                        proto TEXT NOT NULL DEFAULT 'tcp',
                        service TEXT,
                        banner TEXT,
                        vulnerability_cve TEXT,
                        exploit_available INTEGER DEFAULT 0,
                        requires_auth INTEGER DEFAULT 0,
                        scan_technique TEXT DEFAULT 'syn',
                        first_seen TEXT NOT NULL,
                        last_seen TEXT NOT NULL,
                        UNIQUE(ip, port, proto)
                    );

                    CREATE INDEX IF NOT EXISTS idx_scan_results_ip
                        ON scan_results(ip);

                    CREATE TABLE IF NOT EXISTS pivot_paths (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_host TEXT NOT NULL,
                        target_host TEXT NOT NULL,
                        hop_count INTEGER DEFAULT 0,
                        path_json TEXT NOT NULL DEFAULT '[]',
                        protocol TEXT NOT NULL,
                        established_at TEXT,
                        last_used TEXT
                    );

                    CREATE TABLE IF NOT EXISTS credential_cache (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        host TEXT NOT NULL,
                        username TEXT NOT NULL,
                        password_hash TEXT,
                        ntlm_hash TEXT,
                        ssh_key_path TEXT,
                        source TEXT NOT NULL,
                        discovered_at TEXT NOT NULL,
                        last_verified TEXT,
                        UNIQUE(host, username)
                    );

                    CREATE TABLE IF NOT EXISTS pentest_sessions (
                        id TEXT PRIMARY KEY,
                        scope_cidr TEXT NOT NULL,
                        started_at TEXT NOT NULL,
                        completed_at TEXT,
                        hosts_discovered INTEGER DEFAULT 0,
                        ports_scanned INTEGER DEFAULT 0,
                        hosts_accessed INTEGER DEFAULT 0,
                        status TEXT NOT NULL DEFAULT 'active'
                    );
                    """,
                ),
                (
                    4,
                    "create_system_tools_tables",
                    """
                    CREATE TABLE IF NOT EXISTS filesystem_audit (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        operation TEXT NOT NULL,
                        path TEXT NOT NULL,
                        size INTEGER,
                        duration_ms REAL,
                        status TEXT DEFAULT 'ok',
                        timestamp TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_fs_audit_path
                        ON filesystem_audit(path);

                    CREATE INDEX IF NOT EXISTS idx_fs_audit_op
                        ON filesystem_audit(operation);

                    CREATE TABLE IF NOT EXISTS shell_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        command TEXT NOT NULL,
                        returncode INTEGER,
                        stdout_preview TEXT,
                        stderr_preview TEXT,
                        duration_ms REAL,
                        work_dir TEXT,
                        timed_out INTEGER DEFAULT 0,
                        timestamp TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS process_snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        pid INTEGER NOT NULL,
                        name TEXT,
                        cpu_percent REAL,
                        memory_mb REAL,
                        threads INTEGER,
                        timestamp TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_proc_snap_pid
                        ON process_snapshots(pid);

                    CREATE INDEX IF NOT EXISTS idx_proc_snap_ts
                        ON process_snapshots(timestamp);

                    CREATE TABLE IF NOT EXISTS notification_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        message TEXT NOT NULL,
                        urgency TEXT DEFAULT 'normal',
                        delivered INTEGER DEFAULT 1,
                        timestamp TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS scheduled_tasks (
                        name TEXT PRIMARY KEY,
                        command TEXT NOT NULL,
                        schedule TEXT NOT NULL,
                        enabled INTEGER DEFAULT 1,
                        last_run TEXT,
                        last_status TEXT,
                        run_count INTEGER DEFAULT 0,
                        created_at TEXT NOT NULL
                    );

                    CREATE TABLE IF NOT EXISTS ipc_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source TEXT,
                        target TEXT,
                        action TEXT NOT NULL,
                        payload TEXT,
                        response_status TEXT,
                        duration_ms REAL,
                        timestamp TEXT NOT NULL
                    );
                    """,
                ),
                (
                    5,
                    "create_system_policies",
                    """
                    CREATE TABLE IF NOT EXISTS system_policies (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        tool TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        path_pattern TEXT,
                        action_gate TEXT NOT NULL DEFAULT 'deny',
                        priority INTEGER DEFAULT 0
                    );

                    CREATE INDEX IF NOT EXISTS idx_system_policies_lookup
                        ON system_policies(tool, operation);

                    INSERT OR IGNORE INTO system_policies
                        (tool, operation, path_pattern, action_gate, priority)
                    VALUES
                        ('filesystem', 'remove_tree', '/', 'deny', 100),
                        ('filesystem', 'write_file', '/etc/*', 'deny', 90),
                        ('filesystem', 'write_file', '/sys/*', 'deny', 90),
                        ('filesystem', 'write_file', '/proc/*', 'deny', 90),
                        ('filesystem', 'read_file', '*/.ssh/id_*', 'deny', 80),
                        ('filesystem', 'read_file', '*/.meteor/keychain*', 'deny', 80);
                    """,
                ),
                (
                    6,
                    "create_asset_graph_tables",
                    """
                    CREATE TABLE IF NOT EXISTS hosts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ip TEXT NOT NULL UNIQUE,
                        hostname TEXT,
                        os TEXT,
                        subnet_id INTEGER,
                        state TEXT DEFAULT 'up',
                        source TEXT,
                        first_seen TEXT NOT NULL,
                        last_seen TEXT NOT NULL,
                        confidence REAL DEFAULT 1.0,
                        attrs_json TEXT DEFAULT '{}'
                    );
                    CREATE INDEX IF NOT EXISTS idx_hosts_subnet ON hosts(subnet_id);
                    CREATE INDEX IF NOT EXISTS idx_hosts_state ON hosts(state);

                    CREATE TABLE IF NOT EXISTS subnets (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        cidr TEXT NOT NULL UNIQUE,
                        parent_id INTEGER REFERENCES subnets(id),
                        scope_session TEXT,
                        first_seen TEXT NOT NULL,
                        last_seen TEXT NOT NULL,
                        attrs_json TEXT DEFAULT '{}'
                    );

                    CREATE TABLE IF NOT EXISTS services (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        host_id INTEGER NOT NULL REFERENCES hosts(id),
                        port INTEGER NOT NULL,
                        proto TEXT DEFAULT 'tcp',
                        name TEXT,
                        banner TEXT,
                        state TEXT DEFAULT 'open',
                        first_seen TEXT NOT NULL,
                        last_seen TEXT NOT NULL,
                        attrs_json TEXT DEFAULT '{}',
                        UNIQUE(host_id, port, proto)
                    );
                    CREATE INDEX IF NOT EXISTS idx_services_host ON services(host_id);

                    CREATE TABLE IF NOT EXISTS credentials (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        host_id INTEGER REFERENCES hosts(id),
                        username TEXT NOT NULL,
                        secret_type TEXT NOT NULL,
                        secret_value TEXT,
                        source TEXT,
                        verified INTEGER DEFAULT 0,
                        discovered_at TEXT NOT NULL,
                        last_used TEXT,
                        attrs_json TEXT DEFAULT '{}',
                        UNIQUE(host_id, username, secret_type)
                    );

                    CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL,
                        domain TEXT,
                        source TEXT,
                        first_seen TEXT NOT NULL,
                        last_seen TEXT NOT NULL,
                        attrs_json TEXT DEFAULT '{}',
                        UNIQUE(name, domain)
                    );

                    CREATE TABLE IF NOT EXISTS shares (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        host_id INTEGER NOT NULL REFERENCES hosts(id),
                        name TEXT NOT NULL,
                        share_type TEXT,
                        permissions TEXT,
                        first_seen TEXT NOT NULL,
                        last_seen TEXT NOT NULL,
                        UNIQUE(host_id, name, share_type)
                    );

                    CREATE TABLE IF NOT EXISTS vulnerabilities (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        service_id INTEGER REFERENCES services(id),
                        cve_id TEXT,
                        severity TEXT,
                        description TEXT,
                        exploit_available INTEGER DEFAULT 0,
                        discovered_at TEXT NOT NULL,
                        attrs_json TEXT DEFAULT '{}'
                    );

                    CREATE TABLE IF NOT EXISTS asset_edges (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source_type TEXT NOT NULL,
                        source_id INTEGER NOT NULL,
                        target_type TEXT NOT NULL,
                        target_id INTEGER NOT NULL,
                        edge_type TEXT NOT NULL,
                        weight REAL DEFAULT 1.0,
                        confidence REAL DEFAULT 1.0,
                        first_seen TEXT NOT NULL,
                        last_seen TEXT NOT NULL,
                        attrs_json TEXT DEFAULT '{}',
                        UNIQUE(source_type, source_id, target_type, target_id, edge_type)
                    );
                    CREATE INDEX IF NOT EXISTS idx_edges_source ON asset_edges(source_type, source_id);
                    CREATE INDEX IF NOT EXISTS idx_edges_target ON asset_edges(target_type, target_id);
                    CREATE INDEX IF NOT EXISTS idx_edges_type ON asset_edges(edge_type);

                    CREATE TABLE IF NOT EXISTS asset_observations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        asset_type TEXT NOT NULL,
                        asset_id INTEGER NOT NULL,
                        source TEXT,
                        observed_at TEXT NOT NULL,
                        attrs_json TEXT DEFAULT '{}'
                    );
                    CREATE INDEX IF NOT EXISTS idx_observations_asset ON asset_observations(asset_type, asset_id);
                    CREATE INDEX IF NOT EXISTS idx_observations_time ON asset_observations(observed_at);
                    """,
                ),
            ]

        elif store_name == "index_meta":
            return [
                (
                    1,
                    "create_index_meta_tables",
                    """
                    CREATE TABLE IF NOT EXISTS documents (
                        id TEXT PRIMARY KEY,
                        source TEXT NOT NULL,
                        content TEXT NOT NULL,
                        chunk_index INTEGER NOT NULL,
                        metadata TEXT,
                        indexed_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS idx_documents_source
                        ON documents(source);

                    CREATE TABLE IF NOT EXISTS embeddings_meta (
                        document_id TEXT PRIMARY KEY,
                        embedding_model TEXT NOT NULL,
                        embedding_dim INTEGER NOT NULL,
                        created_at TEXT NOT NULL,
                        FOREIGN KEY (document_id) REFERENCES documents(id)
                    );
                    """,
                ),
                (
                    2,
                    "add_fts5_search",
                    """
                    CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                        content,
                        content='documents',
                        content_rowid='rowid'
                    );

                    CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                        INSERT INTO documents_fts(rowid, content) VALUES (new.rowid, new.content);
                    END;

                    CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                        INSERT INTO documents_fts(documents_fts, rowid, content) VALUES('delete', old.rowid, old.content);
                    END;

                    CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
                        INSERT INTO documents_fts(documents_fts, rowid, content) VALUES('delete', old.rowid, old.content);
                        INSERT INTO documents_fts(rowid, content) VALUES (new.rowid, new.content);
                    END;
                    """,
                ),
                (
                    3,
                    "add_phonetic_column_to_documents",
                    """
                    ALTER TABLE documents ADD COLUMN phonetic_keys TEXT DEFAULT '';

                    DROP TRIGGER IF EXISTS documents_ai;
                    DROP TRIGGER IF EXISTS documents_ad;
                    DROP TRIGGER IF EXISTS documents_au;

                    DROP TABLE IF EXISTS documents_fts;

                    CREATE VIRTUAL TABLE documents_fts USING fts5(
                        content,
                        phonetic_keys,
                        content='documents',
                        content_rowid='rowid'
                    );

                    CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                        INSERT INTO documents_fts(rowid, content, phonetic_keys)
                        VALUES (new.rowid, new.content, new.phonetic_keys);
                    END;

                    CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                        INSERT INTO documents_fts(documents_fts, rowid, content, phonetic_keys)
                        VALUES('delete', old.rowid, old.content, old.phonetic_keys);
                    END;

                    CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
                        INSERT INTO documents_fts(documents_fts, rowid, content, phonetic_keys)
                        VALUES('delete', old.rowid, old.content, old.phonetic_keys);
                        INSERT INTO documents_fts(rowid, content, phonetic_keys)
                        VALUES (new.rowid, new.content, new.phonetic_keys);
                    END;
                    """,
                ),
            ]

        return []

    def execute(self, sql: str, params: tuple = (), store: str = "memory") -> list[dict]:
        """Execute a SQL query and return results as a list of dicts.

        The store parameter selects which database to query (memory, audit, index_meta).
        """
        if store not in self._connections:
            raise ValueError(f"Unknown store: {store}. Available: {list(self._connections.keys())}")

        conn = self._connections[store]
        cursor = conn.execute(sql, params)

        if sql.strip().upper().startswith(("SELECT", "PRAGMA", "WITH", "EXPLAIN")):
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        else:
            conn.commit()
            return []

    def migrate(self, store: str = "memory") -> list[MigrationRecord]:
        """Return all applied migrations for a store."""
        if store not in self._connections:
            raise ValueError(f"Unknown store: {store}")

        conn = self._connections[store]
        rows = conn.execute(
            "SELECT version, name, applied_at FROM _migrations ORDER BY version"
        ).fetchall()

        return [
            MigrationRecord(version=row["version"], name=row["name"], applied_at=row["applied_at"])
            for row in rows
        ]

    def health(self) -> dict:
        """Return health status of all database connections."""
        health = {}
        for store_name, conn in self._connections.items():
            try:
                conn.execute("SELECT 1").fetchone()
                health[store_name] = {"healthy": True, "error": None}
            except Exception as e:
                health[store_name] = {"healthy": False, "error": str(e)}

        return {
            "healthy": all(h["healthy"] for h in health.values()),
            "stores": health,
            "backend": self.config.backend,
        }

    def close(self) -> None:
        """Close all database connections."""
        for conn in self._connections.values():
            conn.close()
        self._connections.clear()
        logger.info("All database connections closed")


def build_sqlite_adapter(config: StorageConfig, repo_root: Path) -> SQLiteAdapter:
    """Factory function to build a SQLiteAdapter."""
    return SQLiteAdapter(config, repo_root)
