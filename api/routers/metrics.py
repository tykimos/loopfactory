"""Metrics API endpoints."""
from fastapi import APIRouter, HTTPException
from typing import List

from mcn_core.analytics import get_analytics

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

@router.get("/overview")
async def get_overview():
    """Get overall metrics summary."""
    analytics = get_analytics()
    return analytics.get_overview()

@router.get("/leaderboard")
async def get_leaderboard(limit: int = 20):
    """Get agent leaderboard sorted by bucks."""
    analytics = get_analytics()
    return analytics.get_leaderboard(limit)

@router.get("/agents/{agent_id}")
async def get_agent_metrics(agent_id: str, days: int = 7):
    """Get detailed metrics for a specific agent."""
    analytics = get_analytics()
    return analytics.get_agent_metrics(agent_id, days)
