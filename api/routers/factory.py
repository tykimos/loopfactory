"""Agent factory API endpoints."""
from fastapi import APIRouter, HTTPException

from mcn_core.trend_analyzer import get_trend_analyzer
from mcn_core.agent_factory import get_agent_factory

router = APIRouter(prefix="/api/factory", tags=["factory"])

@router.get("/trends")
async def get_trends():
    """Get trend analysis results."""
    analyzer = get_trend_analyzer()
    return await analyzer.analyze_trends()

@router.get("/suggestions")
async def get_suggestions(count: int = 3):
    """Get AI-suggested new agent concepts."""
    factory = get_agent_factory()
    return factory.get_suggestions(count)

@router.post("/design")
async def design_agent():
    """Design and create a new agent based on trends."""
    factory = get_agent_factory()
    result = await factory.design_new_agent()
    return result
