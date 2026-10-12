from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.engine import Connection

logger = logging.getLogger(__name__)

# Demo-only: create_all does not ALTER existing SQLite tables.
_SQLITE_COLUMN_PATCHES: dict[str, list[tuple[str, str]]] = {
    "confluence_connections": [
        ("credential_location", "VARCHAR(32) NOT NULL DEFAULT 'CLOUD'"),
        ("connector_agent_id", "CHAR(32)"),
    ],
    "ingestion_jobs": [
        ("progress_json", "TEXT"),
    ],
    "documents": [
        ("position", "INTEGER NOT NULL DEFAULT 0"),
        ("depth", "INTEGER NOT NULL DEFAULT 0"),
        ("origin", "VARCHAR(32) NOT NULL DEFAULT 'CONFLUENCE'"),
        ("created_by_user_id", "CHAR(32)"),
        ("archived_at", "DATETIME"),
        ("deleted_at", "DATETIME"),
    ],
    "sources": [
        ("sync_enabled", "BOOLEAN NOT NULL DEFAULT 0"),
        ("sync_interval", "VARCHAR(16) NOT NULL DEFAULT 'OFF'"),
        ("last_sync_at", "DATETIME"),
        ("last_sync_status", "VARCHAR(32)"),
        ("last_sync_summary", "TEXT"),
        ("next_sync_at", "DATETIME"),
        ("jira_connection_id", "CHAR(32)"),
        ("config_json", "TEXT"),
        ("metadata_json", "TEXT"),
        ("error_code", "VARCHAR(64)"),
        ("error_message", "TEXT"),
    ],
    "user_ai_credentials": [
        ("verified_model", "VARCHAR(128)"),
    ],
    "citations": [
        ("section_heading", "VARCHAR(500)"),
        ("source_url", "VARCHAR(1000)"),
    ],
}


def _sqlite_table_exists(connection: Connection, name: str) -> bool:
    row = connection.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": name},
    ).scalar()
    return row is not None


def ensure_sqlite_demo_schema(connection: Connection) -> None:
    """Add missing columns on existing demo SQLite tables (idempotent)."""
    dialect = connection.dialect.name
    if dialect != "sqlite":
        return
    for table, columns in _SQLITE_COLUMN_PATCHES.items():
        exists = connection.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
            {"n": table},
        ).scalar()
        if not exists:
            continue
        existing = {
            row[1]
            for row in connection.execute(text(f"PRAGMA table_info({table})")).fetchall()
        }
        for col_name, col_ddl in columns:
            if col_name in existing:
                continue
            connection.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_ddl}"))
            logger.warning("Demo SQLite: added %s.%s", table, col_name)

    # Starred / recent page tables (create_all may miss if Base wasn't imported early).
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS user_starred_pages (
                user_id CHAR(32) NOT NULL,
                page_id CHAR(32) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                PRIMARY KEY (user_id, page_id)
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS user_recent_pages (
                user_id CHAR(32) NOT NULL,
                page_id CHAR(32) NOT NULL,
                last_opened_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                PRIMARY KEY (user_id, page_id)
            )
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS document_view_events (
                id CHAR(32) NOT NULL PRIMARY KEY,
                document_id CHAR(32) NOT NULL,
                user_id CHAR(32),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
            )
            """
        )
    )
    if not _sqlite_table_exists(connection, "studio_artifacts"):
        try:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS studio_artifacts (
                        id CHAR(32) NOT NULL PRIMARY KEY,
                        user_id CHAR(32) NOT NULL,
                        workspace_id CHAR(32) NOT NULL,
                        artifact_type VARCHAR(32) NOT NULL,
                        title VARCHAR(255) NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        focus_prompt TEXT,
                        payload_json TEXT,
                        warning_json TEXT,
                        progress_percent REAL NOT NULL DEFAULT 0,
                        stage VARCHAR(32) NOT NULL,
                        error_message VARCHAR(1000),
                        model_provider VARCHAR(32),
                        model_name VARCHAR(128),
                        input_tokens INTEGER,
                        output_tokens INTEGER,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                        FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE,
                        FOREIGN KEY(workspace_id) REFERENCES workspaces (id) ON DELETE CASCADE
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS studio_artifact_sources (
                        artifact_id CHAR(32) NOT NULL,
                        space_id CHAR(32) NOT NULL,
                        document_id CHAR(32) NOT NULL,
                        PRIMARY KEY (artifact_id, space_id, document_id),
                        FOREIGN KEY(artifact_id) REFERENCES studio_artifacts (id) ON DELETE CASCADE,
                        FOREIGN KEY(space_id) REFERENCES spaces (id) ON DELETE CASCADE,
                        FOREIGN KEY(document_id) REFERENCES documents (id) ON DELETE CASCADE
                    )
                    """
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_studio_artifacts_user_id ON studio_artifacts (user_id)"
                )
            )
            connection.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_studio_artifacts_workspace_id ON studio_artifacts (workspace_id)"
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Demo SQLite: could not create studio tables (%s)", exc)
