#!/usr/bin/env python3
"""Database migration script for LoopFactory."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "mcn.db"

def run_migrations():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")  # Better concurrency
    cursor = conn.cursor()

    # Create agents table
    cursor.execute('''
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
    ''')

    # Create metrics table
    cursor.execute('''
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
    ''')

    # Create activity_log table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT REFERENCES agents(id),
            activity_type TEXT,
            details TEXT,
            success BOOLEAN,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Create pending_activation table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pending_activation (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT REFERENCES agents(id),
            activation_url TEXT NOT NULL,
            activation_code TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            last_checked DATETIME,
            check_count INTEGER DEFAULT 0
        )
    ''')

    conn.commit()
    conn.close()
    print(f"Database created at {DB_PATH}")

if __name__ == "__main__":
    run_migrations()
