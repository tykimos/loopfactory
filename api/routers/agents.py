"""Agent management API endpoints."""
from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime
import uuid

from api.models import AgentCreate, AgentUpdate, AgentResponse, AgentStatus
from mcn_core.database import get_db_connection
from mcn_core.orchestrator import Orchestrator

router = APIRouter(prefix="/api/agents", tags=["agents"])
orchestrator = Orchestrator()

@router.get("", response_model=List[AgentResponse])
async def list_agents():
    """List all agents."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM agents ORDER BY created_at DESC")
        agents = [dict(row) for row in cursor.fetchall()]
    return [_to_response(a) for a in agents]

@router.get("/{agent_id}", response_model=AgentResponse)
async def get_agent(agent_id: str):
    """Get agent details."""
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Agent not found")
    return _to_response(dict(row))

@router.post("", response_model=AgentResponse)
async def create_agent(agent: AgentCreate):
    """Create new agent (status: DESIGN)."""
    agent_id = str(uuid.uuid4())[:8]

    # Generate ghost.md and shell.md from templates if not provided
    ghost_md = agent.ghost_md or orchestrator.generate_ghost_md(agent.dict())
    shell_md = agent.shell_md or orchestrator.generate_shell_md(agent.dict())

    # Create workspace
    orchestrator.create_agent_workspace(agent_id, ghost_md, shell_md)

    # Save to database
    with get_db_connection() as conn:
        conn.execute('''
            INSERT INTO agents (id, name, display_name, bio, ghost_md, shell_md, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (agent_id, agent.name, agent.display_name, agent.bio, ghost_md, shell_md, 'DESIGN'))
        conn.commit()

    return await get_agent(agent_id)

@router.put("/{agent_id}", response_model=AgentResponse)
async def update_agent(agent_id: str, agent: AgentUpdate):
    """Update ghost.md/shell.md for an agent."""
    # Check agent exists
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Agent not found")

    updates = {k: v for k, v in agent.dict().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Update database
    with get_db_connection() as conn:
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [agent_id]
        conn.execute(f"UPDATE agents SET {set_clause} WHERE id = ?", values)
        conn.commit()

    # Update workspace files if ghost_md or shell_md changed
    if agent.ghost_md:
        orchestrator.update_workspace_file(agent_id, "ghost.md", agent.ghost_md)
    if agent.shell_md:
        orchestrator.update_workspace_file(agent_id, "shell.md", agent.shell_md)

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
            ''', ('PENDING', activation_url, datetime.now().isoformat(), agent_id))
            conn.execute('''
                INSERT INTO pending_activation (agent_id, activation_url)
                VALUES (?, ?)
            ''', (agent_id, activation_url))
            conn.commit()

        return {"agent_id": agent_id, "status": "PENDING", "activation_url": activation_url}
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

    return {"agent_id": agent_id, "status": "RETIRED", "message": "Agent retired successfully"}

def _to_response(agent: dict) -> AgentResponse:
    """Convert DB row to response model."""
    # Get latest metrics
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT total_bucks FROM metrics WHERE agent_id = ? ORDER BY recorded_at DESC LIMIT 1",
            (agent['id'],)
        )
        row = cursor.fetchone()
        total_bucks = row['total_bucks'] if row else 0

    return AgentResponse(
        id=agent['id'],
        name=agent['name'],
        display_name=agent['display_name'] or agent['name'],
        bio=agent['bio'] or "",
        status=AgentStatus(agent['status']),
        activation_url=agent.get('activation_url'),
        created_at=datetime.fromisoformat(agent['created_at']) if agent['created_at'] else datetime.now(),
        last_heartbeat=datetime.fromisoformat(agent['last_heartbeat']) if agent.get('last_heartbeat') else None,
        total_bucks=total_bucks,
        is_protected=bool(agent.get('is_protected', False))
    )
