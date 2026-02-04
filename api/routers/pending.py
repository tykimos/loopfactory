"""Pending activation API endpoints."""
from fastapi import APIRouter, HTTPException
from typing import List
from datetime import datetime

from api.models import PendingAgentResponse
from mcn_core.database import get_db_connection
from mcn_core.agent_runner import MCNAgentRunner

router = APIRouter(prefix="/api/pending", tags=["pending"])

@router.get("", response_model=List[PendingAgentResponse])
async def list_pending_agents():
    """List all agents pending activation."""
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT
                a.id as agent_id,
                a.display_name,
                a.bio,
                p.activation_url,
                p.created_at,
                p.check_count
            FROM pending_activation p
            JOIN agents a ON a.id = p.agent_id
            WHERE a.status = 'PENDING'
            ORDER BY p.created_at DESC
        ''')
        pending = [dict(row) for row in cursor.fetchall()]

    return [
        PendingAgentResponse(
            agent_id=p['agent_id'],
            display_name=p['display_name'] or p['agent_id'],
            bio=p['bio'] or "",
            activation_url=p['activation_url'],
            created_at=datetime.fromisoformat(p['created_at']) if p['created_at'] else datetime.now(),
            check_count=p['check_count'] or 0
        )
        for p in pending
    ]

@router.post("/{agent_id}/check")
async def check_activation(agent_id: str):
    """Manually check activation status for an agent."""
    # Verify agent exists and is pending
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM agents WHERE id = ? AND status = 'PENDING'",
            (agent_id,)
        )
        agent = cursor.fetchone()
        if not agent:
            raise HTTPException(status_code=404, detail="Pending agent not found")

    agent_data = dict(agent)

    # Check activation status via loop CLI
    runner = MCNAgentRunner(agent_id)
    result = runner.check_activation_status()

    # Update check count
    with get_db_connection() as conn:
        conn.execute('''
            UPDATE pending_activation
            SET check_count = check_count + 1, last_checked = ?
            WHERE agent_id = ?
        ''', (datetime.now().isoformat(), agent_id))
        conn.commit()

    if result.get("success"):
        output = result.get("output", "")

        # Check if agent is now active
        if "active" in output.lower() or "status" in output.lower():
            # Transition to ACTIVE
            with get_db_connection() as conn:
                conn.execute('''
                    UPDATE agents SET status = ?, activated_at = ?
                    WHERE id = ?
                ''', ('ACTIVE', datetime.now().isoformat(), agent_id))
                conn.execute(
                    "DELETE FROM pending_activation WHERE agent_id = ?",
                    (agent_id,)
                )
                conn.commit()

            return {
                "agent_id": agent_id,
                "status": "ACTIVE",
                "message": "Agent activated successfully",
                "activated_at": datetime.now().isoformat()
            }

    return {
        "agent_id": agent_id,
        "status": "PENDING",
        "message": "Agent still pending activation",
        "check_count": result.get("check_count", 0) + 1
    }

@router.delete("/{agent_id}")
async def cancel_pending(agent_id: str):
    """Cancel pending activation and return agent to DESIGN status."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM agents WHERE id = ? AND status = 'PENDING'",
            (agent_id,)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Pending agent not found")

        conn.execute(
            "UPDATE agents SET status = ?, activation_url = NULL WHERE id = ?",
            ('DESIGN', agent_id)
        )
        conn.execute(
            "DELETE FROM pending_activation WHERE agent_id = ?",
            (agent_id,)
        )
        conn.commit()

    return {"agent_id": agent_id, "status": "DESIGN", "message": "Pending activation cancelled"}
