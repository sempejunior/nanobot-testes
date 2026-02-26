"""SQLite schema migrations.

Each migration is a (version, sql) tuple.  ``apply_migrations`` runs them
inside a transaction so the database is always in a consistent state.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import aiosqlite

_MIGRATIONS: list[tuple[int, str]] = [
    (1, """
-- ===================== v1: initial schema =====================

CREATE TABLE IF NOT EXISTS users (
    user_id        TEXT PRIMARY KEY,
    display_name   TEXT NOT NULL,
    email          TEXT UNIQUE,
    api_key_hash   TEXT UNIQUE,
    role           TEXT NOT NULL DEFAULT 'user',

    agent_config   TEXT NOT NULL DEFAULT '{}',
    bootstrap      TEXT NOT NULL DEFAULT '{}',
    limits         TEXT NOT NULL DEFAULT '{}',
    tools_enabled  TEXT NOT NULL DEFAULT '[]',

    tokens_today      INTEGER NOT NULL DEFAULT 0,
    tokens_total      INTEGER NOT NULL DEFAULT 0,
    requests_today    INTEGER NOT NULL DEFAULT 0,
    last_request_at   TEXT,
    usage_reset_date  TEXT,

    status     TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_users_status ON users(status);
CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key_hash);

-- -----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS sessions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    session_key       TEXT NOT NULL,
    last_consolidated INTEGER NOT NULL DEFAULT 0,
    message_count     INTEGER NOT NULL DEFAULT 0,
    status            TEXT NOT NULL DEFAULT 'active',
    metadata          TEXT NOT NULL DEFAULT '{}',
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(user_id, session_key)
);

CREATE INDEX IF NOT EXISTS idx_sessions_user_status ON sessions(user_id, status);
CREATE INDEX IF NOT EXISTS idx_sessions_user_updated ON sessions(user_id, updated_at DESC);

-- -----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id      TEXT NOT NULL,
    role         TEXT NOT NULL,
    content      TEXT,
    tool_calls   TEXT,
    tool_call_id TEXT,
    name         TEXT,
    timestamp    TEXT NOT NULL DEFAULT (datetime('now')),
    seq          INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session_seq ON messages(session_id, seq);

-- -----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memories (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    type       TEXT NOT NULL,
    content    TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_memories_user_type ON memories(user_id, type);
CREATE INDEX IF NOT EXISTS idx_memories_user_type_updated ON memories(user_id, type, updated_at DESC);

-- -----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS skills (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id       TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    content       TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    always_active INTEGER NOT NULL DEFAULT 0,
    enabled       INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_skills_user_enabled ON skills(user_id, enabled);

-- -----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS cron_jobs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    job_id           TEXT NOT NULL,
    name             TEXT NOT NULL,
    enabled          INTEGER NOT NULL DEFAULT 1,
    schedule         TEXT NOT NULL,
    payload          TEXT NOT NULL,
    next_run_at_ms   INTEGER,
    last_run_at_ms   INTEGER,
    last_status      TEXT,
    last_error       TEXT,
    delete_after_run INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(user_id, job_id)
);

CREATE INDEX IF NOT EXISTS idx_cron_enabled_next ON cron_jobs(enabled, next_run_at_ms);
CREATE INDEX IF NOT EXISTS idx_cron_user ON cron_jobs(user_id, enabled);

-- -----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS channel_bindings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    channel    TEXT NOT NULL,
    sender_id  TEXT NOT NULL,
    verified   INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),

    UNIQUE(channel, sender_id)
);

CREATE INDEX IF NOT EXISTS idx_bindings_user ON channel_bindings(user_id);

-- -----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    TEXT NOT NULL,
    event      TEXT NOT NULL,
    detail     TEXT NOT NULL DEFAULT '{}',
    ip_address TEXT,
    user_agent TEXT,
    timestamp  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_audit_user_ts ON audit_log(user_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_event_ts ON audit_log(event, timestamp DESC);

-- -----------------------------------------------------------------
-- Schema version tracker
-- -----------------------------------------------------------------

CREATE TABLE IF NOT EXISTS _schema_version (
    version INTEGER NOT NULL
);

INSERT INTO _schema_version (version) VALUES (1);
"""),

    (2, """
-- ===================== v2: FTS5 full-text search on memories =====================

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content,
    content='memories',
    content_rowid='id'
);

-- Populate index with existing history entries
INSERT INTO memories_fts(rowid, content)
    SELECT id, content FROM memories WHERE type = 'history';

-- Triggers to keep FTS index in sync
CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories
WHEN NEW.type = 'history'
BEGIN
    INSERT INTO memories_fts(rowid, content) VALUES (NEW.id, NEW.content);
END;

CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories
WHEN OLD.type = 'history'
BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', OLD.id, OLD.content);
END;

CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE OF content ON memories
WHEN NEW.type = 'history'
BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content) VALUES('delete', OLD.id, OLD.content);
    INSERT INTO memories_fts(rowid, content) VALUES (NEW.id, NEW.content);
END;
"""),
]


async def apply_migrations(db: "aiosqlite.Connection") -> None:
    """Apply any outstanding migrations."""
    cursor = await db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='_schema_version'"
    )
    exists = await cursor.fetchone()

    current_version = 0
    if exists:
        cursor = await db.execute("SELECT MAX(version) FROM _schema_version")
        row = await cursor.fetchone()
        current_version = row[0] if row and row[0] else 0

    for version, sql in _MIGRATIONS:
        if version > current_version:
            await db.executescript(sql)
            if current_version > 0:
                await db.execute("INSERT INTO _schema_version (version) VALUES (?)", (version,))
            current_version = version
            await db.commit()
