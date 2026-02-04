"""Database connection manager for LoopFactory."""
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from typing import Optional

DB_PATH = Path(__file__).parent.parent / "data" / "mcn.db"

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def get_agent(agent_id: str) -> Optional[dict]:
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_agents_by_status(status: str) -> list:
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM agents WHERE status = ?", (status,))
        return [dict(row) for row in cursor.fetchall()]

def create_agent(agent_data: dict) -> str:
    with get_db_connection() as conn:
        conn.execute('''
            INSERT INTO agents (id, name, display_name, bio, ghost_md, shell_md, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (agent_data['id'], agent_data['name'], agent_data['display_name'],
              agent_data['bio'], agent_data.get('ghost_md'), agent_data.get('shell_md'), 'DESIGN'))
        conn.commit()
        return agent_data['id']

def update_agent(agent_id: str, updates: dict) -> bool:
    with get_db_connection() as conn:
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [agent_id]
        conn.execute(f"UPDATE agents SET {set_clause} WHERE id = ?", values)
        conn.commit()
        return True

def set_agent_protected(agent_id: str, protected: bool) -> bool:
    return update_agent(agent_id, {"is_protected": protected})

def get_latest_metrics(agent_id: str) -> Optional[dict]:
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM metrics WHERE agent_id = ? ORDER BY recorded_at DESC LIMIT 1",
            (agent_id,)
        )
        row = cursor.fetchone()
        return dict(row) if row else None

def log_activity(agent_id: str, activity_type: str, details: str, success: bool):
    with get_db_connection() as conn:
        conn.execute('''
            INSERT INTO activity_log (agent_id, activity_type, details, success)
            VALUES (?, ?, ?, ?)
        ''', (agent_id, activity_type, details, success))
        conn.commit()
