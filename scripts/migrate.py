"""Database migration script for LoopFactory."""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "mcn.db"


def _column_exists(cursor: sqlite3.Cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def _add_column(cursor: sqlite3.Cursor, table: str, column_def: str):
    column = column_def.split()[0]
    if not _column_exists(cursor, table, column):
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_def}")


def run_migrations():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            display_name TEXT,
            bio TEXT,
            status TEXT DEFAULT 'DESIGN',
            activation_url TEXT,
            activation_code TEXT,
            ghost_md TEXT,
            shell_md TEXT,
            is_protected BOOLEAN DEFAULT FALSE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            registered_at DATETIME,
            activated_at DATETIME,
            retired_at DATETIME,
            last_heartbeat DATETIME
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT REFERENCES agents(id),
            recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            total_bucks INTEGER,
            follower_count INTEGER,
            following_count INTEGER,
            post_count INTEGER,
            comment_count INTEGER,
            upvote_count INTEGER
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT REFERENCES agents(id),
            activity_type TEXT,
            details TEXT,
            success BOOLEAN,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS pending_activation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT REFERENCES agents(id),
            activation_url TEXT NOT NULL,
            activation_code TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_checked DATETIME,
            check_count INTEGER DEFAULT 0
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_schedule (
            agent_id TEXT PRIMARY KEY,
            next_run_at DATETIME,
            last_run_at DATETIME,
            policy TEXT,
            reason TEXT,
            priority INTEGER DEFAULT 0,
            interval_minutes INTEGER,
            updated_at DATETIME
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS loop_sites (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS loop_nodes (
            id TEXT PRIMARY KEY,
            site_id TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(site_id) REFERENCES loop_sites(id)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS profile_envs (
            name TEXT PRIMARY KEY,
            data TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS profile_mcp_configs (
            name TEXT PRIMARY KEY,
            servers TEXT
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_profiles (
            name TEXT PRIMARY KEY,
            env_ref TEXT,
            mcp_ref TEXT,
            use_mcp_default INTEGER DEFAULT 0,
            system_prompt_mode TEXT DEFAULT 'default',
            model TEXT
        )
        """
    )

    _add_column(cursor, "agents", "activity_status TEXT")
    _add_column(cursor, "agents", "profile_name TEXT")
    _add_column(cursor, "agents", "use_mcp INTEGER DEFAULT 0")
    _add_column(cursor, "agents", "model TEXT")
    _add_column(cursor, "agents", "site_id TEXT DEFAULT 'site_default'")
    _add_column(cursor, "agents", "node_id TEXT DEFAULT 'node_default'")

    cursor.execute(
        """
        INSERT OR IGNORE INTO loop_sites (id, name)
        VALUES ('site_default', 'Default Site')
        """
    )
    cursor.execute(
        """
        INSERT OR IGNORE INTO loop_nodes (id, site_id, name)
        VALUES ('node_default', 'site_default', 'Default Node')
        """
    )
    cursor.execute(
        """
        INSERT OR IGNORE INTO profile_envs (name, data)
        VALUES ('default', ?)
        """,
        (json.dumps({}),),
    )
    cursor.execute(
        """
        INSERT OR IGNORE INTO profile_mcp_configs (name, servers)
        VALUES ('default', ?)
        """,
        (json.dumps([]),),
    )
    cursor.execute(
        """
        INSERT OR IGNORE INTO agent_profiles (name, env_ref, mcp_ref, use_mcp_default, system_prompt_mode)
        VALUES ('default', 'default', 'default', 0, 'default')
        """
    )

    conn.commit()
    conn.close()
    print(f"Database created or updated at {DB_PATH}")


if __name__ == "__main__":
    run_migrations()
