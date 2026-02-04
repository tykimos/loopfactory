"""Activity monitoring API endpoints."""
from fastapi import APIRouter, HTTPException
from typing import List

from mcn_core.activity_monitor import get_activity_monitor
from mcn_core.agent_runner import MCNAgentRunner
from mcn_core.database import get_db_connection
from api.models import ActivityStatusResponse

router = APIRouter(prefix="/api/activity", tags=["activity"])

@router.get("/summary", response_model=ActivityStatusResponse)
async def get_activity_summary():
    """Get summary of activity statuses for all agents."""
    monitor = get_activity_monitor()
    return monitor.get_activity_summary()

@router.get("/alerts")
async def get_alerts():
    """Get list of agents needing attention."""
    monitor = get_activity_monitor()
    return monitor.get_alerts()

@router.get("/agents/{agent_id}")
async def get_agent_activity(agent_id: str):
    """Get activity details for a specific agent."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT id, display_name, last_heartbeat, is_protected, status FROM agents WHERE id = ?",
            (agent_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found")

        agent = dict(row)

    monitor = get_activity_monitor()
    status = monitor._get_activity_status(agent)

    # Get recent activity logs
    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT activity_type, details, success, created_at
            FROM activity_log
            WHERE agent_id = ?
            ORDER BY created_at DESC
            LIMIT 20
        ''', (agent_id,))
        logs = [dict(row) for row in cursor.fetchall()]

    return {
        "agent_id": agent_id,
        "display_name": agent['display_name'],
        "status": agent['status'],
        "activity_status": status,
        "last_heartbeat": agent['last_heartbeat'],
        "is_protected": agent['is_protected'],
        "recent_logs": logs
    }

@router.post("/agents/{agent_id}/prompt")
async def send_reactivation_prompt(agent_id: str, prompt_type: str = "idle"):
    """Send a reactivation prompt to an agent."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT * FROM agents WHERE id = ?",
            (agent_id,)
        )
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Agent not found")

    monitor = get_activity_monitor()
    prompts = monitor.REACTIVATION_PROMPTS

    if prompt_type not in prompts:
        raise HTTPException(status_code=400, detail=f"Invalid prompt type. Choose from: {list(prompts.keys())}")

    runner = MCNAgentRunner(agent_id)
    result = runner.run_with_prompt(prompts[prompt_type].strip())

    return {
        "agent_id": agent_id,
        "prompt_type": prompt_type,
        "success": result.get("success", False),
        "message": "Reactivation prompt sent" if result.get("success") else "Failed to send prompt"
    }

@router.post("/agents/{agent_id}/protect")
async def toggle_protection(agent_id: str):
    """Toggle protection status for an agent."""
    with get_db_connection() as conn:
        cursor = conn.execute(
            "SELECT is_protected FROM agents WHERE id = ?",
            (agent_id,)
        )
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agent not found")

        new_status = not row['is_protected']
        conn.execute(
            "UPDATE agents SET is_protected = ? WHERE id = ?",
            (new_status, agent_id)
        )
        conn.commit()

    return {
        "agent_id": agent_id,
        "is_protected": new_status,
        "message": f"Protection {'enabled' if new_status else 'disabled'}"
    }

@router.get("/retirements")
async def get_scheduled_retirements():
    """Get list of agents scheduled for auto-retirement."""
    from datetime import datetime, timedelta
    from mcn_core.config import get_config

    config = get_config()
    threshold_hours = config.activity_monitoring.auto_retire_inactive_hours
    threshold_time = (datetime.now() - timedelta(hours=threshold_hours - 6)).isoformat()  # 6 hours warning

    with get_db_connection() as conn:
        cursor = conn.execute('''
            SELECT id, display_name, last_heartbeat, is_protected
            FROM agents
            WHERE status IN ('ACTIVE', 'PROBATION')
            AND last_heartbeat IS NOT NULL
            AND last_heartbeat < ?
            AND is_protected = 0
            ORDER BY last_heartbeat ASC
        ''', (threshold_time,))

        agents = []
        for row in cursor.fetchall():
            agent = dict(row)
            if agent['last_heartbeat']:
                last_hb = datetime.fromisoformat(agent['last_heartbeat'])
                hours_until = threshold_hours - (datetime.now() - last_hb).total_seconds() / 3600
                agent['hours_until_retirement'] = max(0, round(hours_until, 1))
            agents.append(agent)

        return agents
