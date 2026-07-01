"""Reactive memory triggers — self-organizing memory via SQL triggers.

Meteor Doctrine #5: Memory is infrastructure. These triggers make memory
self-organizing: conversations auto-tag topics, corrections auto-cross-reference,
and episodic events auto-derive from conversation patterns.

Triggers run inside SQLite when data is written. The application code doesn't
need to know about tagging or cross-referencing — it just writes conversations
and the database handles the rest.
"""

from __future__ import annotations

import logging

from app.storage.sqlite_adapter import SQLiteAdapter

logger = logging.getLogger(__name__)

MEMORY_TRIGGERS_SQL = """
-- Trigger 1: Auto-tag conversation entries with topic detection
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

-- Trigger 2: Create episodic memory when debugging is detected
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

-- Trigger 3: Cross-reference corrections with their source conversations
CREATE TRIGGER IF NOT EXISTS trg_correction_link_conversation
AFTER INSERT ON corrections
WHEN NEW.session_id IS NOT NULL
BEGIN
    INSERT INTO episodic_memory (id, session_id, event_type, content, created_at, metadata)
    VALUES (
        hex(randomblob(16)),
        NEW.session_id,
        'correction_applied',
        'Correction: ' || substr(NEW.original, 1, 100) || ' → ' || substr(NEW.corrected, 1, 100),
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

-- Trigger 4: Track repeated topics for user preference detection
CREATE TRIGGER IF NOT EXISTS trg_conversation_topic_counter
AFTER INSERT ON conversations
WHEN NEW.content IS NOT NULL
BEGIN
    INSERT OR REPLACE INTO project_memory (project_name, key, value, updated_at)
    SELECT
        'user_profile',
        'topic_' || lower(json_extract(COALESCE(NEW.metadata, '{}'), '$.auto_topic')),
        COALESCE(
            CAST(json_extract(
                (SELECT value FROM project_memory WHERE project_name = 'user_profile' AND key = 'topic_' || lower(json_extract(COALESCE(NEW.metadata, '{}'), '$.auto_topic'))),
                '$'
            ) AS INTEGER),
            0
        ) + 1,
        datetime('now')
    WHERE json_extract(COALESCE(NEW.metadata, '{}'), '$.auto_topic') IS NOT NULL;
END;

-- Trigger 5: Auto-index new episodic memory into project state
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
"""


def install_memory_triggers(storage: SQLiteAdapter) -> None:
    """Install all reactive memory triggers on the memory database.

    Idempotent — each trigger uses CREATE TRIGGER IF NOT EXISTS.
    Call this once during runtime initialization.
    """
    try:
        storage.execute_script(MEMORY_TRIGGERS_SQL, store="memory")
        logger.info("Installed reactive memory triggers (5 triggers)")
    except Exception as e:
        logger.warning("Failed to install memory triggers: %s", e)


def uninstall_memory_triggers(storage: SQLiteAdapter) -> None:
    """Remove all reactive memory triggers (for testing/cleanup)."""
    trigger_names = [
        "trg_conversation_auto_topic",
        "trg_conversation_debug_episodic",
        "trg_correction_link_conversation",
        "trg_conversation_topic_counter",
        "trg_episodic_session_stats",
    ]
    for name in trigger_names:
        try:
            storage.execute(
                f"DROP TRIGGER IF EXISTS {name}", store="memory"
            )
        except Exception:
            pass
    logger.info("Uninstalled reactive memory triggers")
