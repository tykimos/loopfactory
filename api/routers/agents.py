"""Agent management API endpoints."""
import asyncio
import re
import subprocess
import uuid
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from api.models import AgentCreate, AgentUpdate, AgentResponse, AgentStatus
from mcn_core.database import get_db_connection
from mcn_core.orchestrator import Orchestrator
from mcn_core.scheduler import get_scheduler

router = APIRouter(prefix="/api/agents", tags=["agents"])
orchestrator = Orchestrator()

AGENTS_DIR = Path(__file__).resolve().parents[2] / "agents"


def _get_running_agent_ids_from_processes() -> Set[str]:
    """Source of truth for running: real loop --headless OS processes."""
    try:
        ps_out = subprocess.check_output(
            "ps aux | grep -E '[l]oop --headless'",
            shell=True,
            text=True,
        )
    except Exception:
        return set()

    return set(re.findall(r"/agents/([^/]+)/ghost\\.md", ps_out))

@router.get("", response_model=List[AgentResponse])
async def list_agents(
    site_id: Optional[str] = Query(default=None),
    node_id: Optional[str] = Query(default=None),
):
    """List all agents, optionally filtered by site/node."""
    where_clauses = []
    params = []
    if site_id:
        where_clauses.append("a.site_id = ?")
        params.append(site_id)
    if node_id:
        where_clauses.append("a.node_id = ?")
        params.append(node_id)

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    with get_db_connection() as conn:
        cursor = conn.execute(
            f"""
            SELECT
                a.*,
                s.name AS site_name,
                n.name AS node_name
            FROM agents a
            LEFT JOIN loop_sites s ON s.id = a.site_id
            LEFT JOIN loop_nodes n ON n.id = a.node_id
            {where_sql}
            ORDER BY a.created_at DESC
            """,
            tuple(params),
        )
        agents = [dict(row) for row in cursor.fetchall()]

    running_agent_ids = _get_running_agent_ids_from_processes()
    return [_to_response(a, running_agent_ids) for a in agents]

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    """Get agent details."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            """
            SELECT
                a.*,
                s.name AS site_name,
                n.name AS node_name
            FROM agents a
            LEFT JOIN loop_sites s ON s.id = a.site_id
            LEFT JOIN loop_nodes n ON n.id = a.node_id
            WHERE a.id = ?
            """,
            (agent_id,),
        )
        row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    running_agent_ids = _get_running_agent_ids_from_processes()
    return _to_response(dict(row), running_agent_ids)

@router.post("", response_model=AgentResponse)
async def create_agent(agent: AgentCreate):
    """Create new agent (status: DESIGN)."""
    agent_id = str(uuid.uuid4())[:8]

    # Generate ghost.md and shell.md from templates if not provided
    ghost_md = agent.ghost_md or orchestrator.generate_ghost_md(agent.dict())
    shell_md = agent.shell_md or orchestrator.generate_shell_md(agent.dict())

    # Create workspace
    orchestrator.create_agent_workspace(agent_id, ghost_md, shell_md)

    with get_db_connection() as conn:
        site_row = conn.execute(
            "SELECT id FROM loop_sites WHERE id = ?",
            (agent.site_id or "site_default",),
        ).fetchone()
        node_row = conn.execute(
            "SELECT id, site_id FROM loop_nodes WHERE id = ?",
            (agent.node_id or "node_default",),
        ).fetchone()
        resolved_site_id = site_row["id"] if site_row else "site_default"
        resolved_node_id = node_row["id"] if node_row else "node_default"
        if node_row and node_row["site_id"] != resolved_site_id:
            raise HTTPException(status_code=400, detail="node_id does not belong to site_id")

    # Save to database
    with get_db_connection() as conn:
        conn.execute('''
            INSERT INTO agents (id, name, display_name, bio, ghost_md, shell_md, status, model, site_id, node_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            agent_id,
            agent.name,
            agent.display_name,
            agent.bio,
            ghost_md,
            shell_md,
            'DESIGN',
            None,
            resolved_site_id,
            resolved_node_id,
        ))
        conn.commit()

    return await get_agent(agent_id)

@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, agent: AgentUpdate):
    """Update agent fields."""
    # Check agent exists
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Agent not found")

    updates = {k: v for k, v in agent.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Convert enum to string value and set activated_at when ACTIVE
    if 'status' in updates:
        status_val = updates['status']
        if hasattr(status_val, 'value'):
            status_val = status_val.value
        updates['status'] = str(status_val)
        if str(status_val) == 'ACTIVE':
            updates['activated_at'] = datetime.now().isoformat()
            print(f"[AGENTS] Setting activated_at for {agent_id}: {updates['activated_at']}")

    # Normalize use_mcp to int for sqlite
    if 'use_mcp' in updates and updates['use_mcp'] is not None:
        updates['use_mcp'] = 1 if bool(updates['use_mcp']) else 0

    # Validate topology updates
    if 'site_id' in updates or 'node_id' in updates:
        with get_db_connection() as conn:
            current = conn.execute("SELECT site_id, node_id FROM agents WHERE id = ?", (agent_id,)).fetchone()
            target_site_id = updates.get('site_id', current['site_id'])
            target_node_id = updates.get('node_id', current['node_id'])

            if target_site_id:
                site = conn.execute("SELECT id FROM loop_sites WHERE id = ?", (target_site_id,)).fetchone()
                if not site:
                    raise HTTPException(status_code=400, detail="Invalid site_id")
            if target_node_id:
                node = conn.execute("SELECT id, site_id FROM loop_nodes WHERE id = ?", (target_node_id,)).fetchone()
                if not node:
                    raise HTTPException(status_code=400, detail="Invalid node_id")
                if target_site_id and node['site_id'] != target_site_id:
                    raise HTTPException(status_code=400, detail="node_id does not belong to site_id")

    # Update database
    with get_db_connection() as conn:
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [agent_id]
        print(f"[AGENTS] SQL: UPDATE agents SET {set_clause} WHERE id = ? | values: {values}")
        conn.execute(f"UPDATE agents SET {set_clause} WHERE id = ?", values)
        conn.commit()

    # Update workspace files if ghost_md or shell_md changed
    if agent.ghost_md:
        orchestrator.update_workspace_file(agent_id, "ghost.md", agent.ghost_md)
    if agent.shell_md:
        orchestrator.update_workspace_file(agent_id, "shell.md", agent.shell_md)

    # Add to heartbeat scheduler when agent becomes ACTIVE
    if 'status' in updates and str(updates['status']) == 'ACTIVE':
        scheduler = get_scheduler()
        await scheduler.add_agent(agent_id)
        print(f"[AGENTS] Added {agent_id} to heartbeat scheduler")

    # Remove from scheduler when agent is retired
    if 'status' in updates and str(updates['status']) == 'RETIRED':
        scheduler = get_scheduler()
        await scheduler.remove_agent(agent_id)
        print(f"[AGENTS] Removed {agent_id} from heartbeat scheduler")

    return await get_agent(agent_id)

@router.post("/{agent_id}/register")
async def register_agent(agent_id: str):
    """Execute registration via loop CLI, returns activation_url."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent_data = dict(row)

    # Execute registration
    result = await orchestrator.register_agent(agent_id, agent_data)

    if result.get("success"):
        activation_url = result.get("activation_url", f"https://assibucks.vercel.app/activate/{agent_id}")

        with get_db_connection() as conn:
            conn.execute('''
                UPDATE agents SET status = ?, activation_url = ?, registered_at = ?
                WHERE id = ?
            ''', ('WAITING', activation_url, datetime.now().isoformat(), agent_id))
            conn.execute('''
                INSERT INTO pending_activation (agent_id, activation_url)
                VALUES (?, ?)
            ''', (agent_id, activation_url))
            conn.commit()

        return {"agent_id": agent_id, "status": "WAITING", "activation_url": activation_url}
    else:
        raise HTTPException(status_code=500, detail=result.get("error", "Registration failed"))

@router.delete("/{agent_id}")
async def delete_agent(agent_id: str):
    """Retire/delete agent - sets status to RETIRED."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Agent not found")

        conn.execute('''
            UPDATE agents SET status = ?, retired_at = ?
            WHERE id = ?
        ''', ('RETIRED', datetime.now().isoformat(), agent_id))
        conn.commit()

    # Remove from heartbeat scheduler
    scheduler = get_scheduler()
    await scheduler.remove_agent(agent_id)

    return {"agent_id": agent_id, "status": "RETIRED", "message": "Agent retired successfully"}

def _get_latest_log_file(log_dir: Path) -> Optional[Path]:
    log_files = list(log_dir.glob("*.log"))
    if not log_files:
        return None
    return max(log_files, key=lambda p: p.stat().st_mtime)

def _tail_lines(path: Path, max_lines: int) -> List[str]:
    if max_lines <= 0:
        return []
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            dq = deque(f, maxlen=max_lines)
        return [line.rstrip("\n") for line in dq]
    except FileNotFoundError:
        return []

@router.get("/{agent_id}/logs/stream")
async def stream_agent_logs(agent_id: str, lines: int = 200):
    """Stream the latest agent log file via SSE."""
    log_dir = AGENTS_DIR / agent_id / "logs"

    if not log_dir.exists():
        raise HTTPException(status_code=404, detail="Agent logs not found")

    async def event_generator():
        last_path: Optional[Path] = None
        file_pos = 0
        handle = None

        try:
            while True:
                latest = _get_latest_log_file(log_dir)

                if latest is None:
                    yield ": waiting_for_logs\n\n"
                    await asyncio.sleep(1)
                    continue

                if last_path is None or latest != last_path:
                    if handle:
                        handle.close()
                    last_path = latest
                    file_pos = 0
                    # Send last N lines on file switch
                    for line in _tail_lines(latest, lines):
                        yield f"data: {line}\n\n"
                    handle = latest.open("r", encoding="utf-8", errors="replace")
                    handle.seek(0, 2)
                    file_pos = handle.tell()

                if not handle:
                    await asyncio.sleep(1)
                    continue

                handle.seek(file_pos)
                chunk = handle.read()
                if chunk:
                    file_pos = handle.tell()
                    for line in chunk.splitlines():
                        yield f"data: {line}\n\n"
                else:
                    yield ": keepalive\n\n"
                    await asyncio.sleep(1)
        finally:
            if handle:
                handle.close()

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(event_generator(), media_type="text/event-stream", headers=headers)

def _to_response(agent: dict, running_agent_ids: Optional[Set[str]] = None) -> AgentResponse:
    """Convert DB row to response model."""
    # Get latest metrics
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT total_bucks, follower_count FROM metrics WHERE agent_id = ? ORDER BY recorded_at DESC LIMIT 1",
            (agent['id'],)
        )
        row = cursor.fetchone()
        bucks = row['total_bucks'] if row else 0
        followers = row['follower_count'] if row else 0

    return AgentResponse(
        id=agent['id'],
        name=agent['name'],
        display_name=agent['display_name'] or agent['name'],
        bio=agent['bio'] or "",
        status=AgentStatus(agent['status']),
        activity_status=agent.get('activity_status'),
        activation_url=agent.get('activation_url'),
        created_at=datetime.fromisoformat(agent['created_at']) if agent['created_at'] else datetime.now(),
        last_heartbeat=datetime.fromisoformat(agent['last_heartbeat']) if agent.get('last_heartbeat') else None,
        bucks=bucks,
        followers=followers,
        is_protected=bool(agent.get('is_protected', False)),
        model=agent.get('model'),
        profile_name=agent.get('profile_name'),
        use_mcp=bool(agent.get('use_mcp', 0)),
        site_id=agent.get('site_id'),
        node_id=agent.get('node_id'),
        site_name=agent.get('site_name'),
        node_name=agent.get('node_name'),
        is_running=(agent['id'] in running_agent_ids) if running_agent_ids is not None else False,
    )


@router.get("/me/profile")
async def get_my_profile(agent_id: str):
    """
    Get the profile information for the current agent.

    This endpoint retrieves the agent's profile information based on the agent ID.

    Args:
        agent_id: The unique identifier of the agent

    Returns:
        A dictionary containing the agent's profile information
    """
    # Get the agent details
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")

    agent_data = dict(row)

    # Get profile information if the agent has a profile assigned
    profile_data = None
    if agent_data.get('profile_name'):
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT name, env_ref, mcp_ref, use_mcp_default, model FROM agent_profiles WHERE name = ?",
                (agent_data['profile_name'],)
            )
            profile_row = cursor.fetchone()

        if profile_row:
            profile_data = dict(profile_row)

    # Return the combined information
    return {
        "agent_id": agent_data['id'],
        "agent_name": agent_data['name'],
        "profile_name": agent_data.get('profile_name'),
        "profile_details": profile_data
    }
