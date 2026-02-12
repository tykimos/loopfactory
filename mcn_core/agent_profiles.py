"""Helpers for resolving agent profile environment and MCP configuration."""
import json
import sqlite3
from typing import Dict, List, Optional, Tuple

from mcn_core.database import get_db_connection


def _fetch_agent_profile(agent_id: str) -> Tuple[str, bool, Optional[str]]:
    """Return (profile_name, use_mcp_flag, agent_model) for an agent."""
    profile_name = "default"
    use_mcp = False
    model = None

    row = None
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT profile_name, use_mcp, model FROM agents WHERE id = ?",
                (agent_id,),
            )
            row = cursor.fetchone()
    except sqlite3.OperationalError:
        try:
            with get_db_connection() as conn:
                cursor = conn.execute(
                    "SELECT profile_name FROM agents WHERE id = ?",
                    (agent_id,),
                )
                row = cursor.fetchone()
        except sqlite3.OperationalError:
            row = None

    if row:
        profile_name = row["profile_name"] or "default"
        if "use_mcp" in row.keys():
            use_mcp = bool(row["use_mcp"])
        if "model" in row.keys():
            model = row["model"]

    return profile_name, use_mcp, model


def _load_profile(profile_name: str) -> Optional[dict]:
    """Load profile row from agent_profiles table."""
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(
                """
                SELECT name, env_ref, mcp_ref, use_mcp_default, system_prompt_mode, model
                FROM agent_profiles
                WHERE name = ?
                """,
                (profile_name,),
            )
            row = cursor.fetchone()
            return dict(row) if row else None
    except sqlite3.OperationalError:
        try:
            with get_db_connection() as conn:
                cursor = conn.execute(
                    """
                    SELECT name, env_ref, mcp_ref, use_mcp_default, model
                    FROM agent_profiles
                    WHERE name = ?
                    """,
                    (profile_name,),
                )
                row = cursor.fetchone()
                if row:
                    data = dict(row)
                    data.setdefault("system_prompt_mode", "default")
                    return data
        except sqlite3.OperationalError:
            return None
    return None


def _load_env(env_ref: Optional[str]) -> Dict[str, str]:
    if not env_ref:
        return {}
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT data FROM profile_envs WHERE name = ?",
                (env_ref,),
            )
            row = cursor.fetchone()
    except sqlite3.OperationalError:
        return {}

    if not row or not row["data"]:
        return {}

    try:
        data = json.loads(row["data"])
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except json.JSONDecodeError:
        pass
    return {}


def _load_mcp_servers(mcp_ref: Optional[str]) -> List[dict]:
    if not mcp_ref:
        return []
    try:
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT servers FROM profile_mcp_configs WHERE name = ?",
                (mcp_ref,),
            )
            row = cursor.fetchone()
    except sqlite3.OperationalError:
        return []

    if not row or not row["servers"]:
        return []

    try:
        data = json.loads(row["servers"])
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return []


def resolve_agent_profile(agent_id: str) -> Tuple[Dict[str, str], List[dict], str, Optional[str]]:
    """Return profile env, MCP servers, system prompt mode, and profile-level model."""
    profile_env: Dict[str, str] = {}
    mcp_servers: List[dict] = []
    system_prompt_mode = "default"
    profile_model: Optional[str] = None

    profile_name, use_mcp_flag, agent_model = _fetch_agent_profile(agent_id)
    profile_row = _load_profile(profile_name)

    if profile_row:
        profile_env = _load_env(profile_row.get("env_ref"))
        profile_model = profile_row.get("model") or agent_model
        system_prompt_mode = profile_row.get("system_prompt_mode") or "default"
        mcp_enabled = use_mcp_flag or bool(profile_row.get("use_mcp_default"))
        if mcp_enabled:
            mcp_servers = _load_mcp_servers(profile_row.get("mcp_ref"))
    else:
        profile_model = agent_model

    return profile_env, mcp_servers, system_prompt_mode, profile_model
