from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    IDLE = "idle"
    ACTIVE = "active"
    PAUSED = "paused"
    ERROR = "error"


class AgentCreate(BaseModel):
    name: str = Field(..., description="Name of the agent")
    type: str = Field(..., description="Type of agent (e.g., 'monitor', 'processor', 'analyzer')")
    config: Dict[str, Any] = Field(default_factory=dict, description="Agent configuration parameters")
    schedule: Optional[str] = Field(None, description="Cron-style schedule expression")


class AgentUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Name of the agent")
    type: Optional[str] = Field(None, description="Type of agent")
    config: Optional[Dict[str, Any]] = Field(None, description="Agent configuration parameters")
    schedule: Optional[str] = Field(None, description="Cron-style schedule expression")
    status: Optional[AgentStatus] = Field(None, description="Agent status")


class AgentResponse(BaseModel):
    id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Name of the agent")
    type: str = Field(..., description="Type of agent")
    status: AgentStatus = Field(..., description="Current agent status")
    config: Dict[str, Any] = Field(default_factory=dict, description="Agent configuration")
    schedule: Optional[str] = Field(None, description="Schedule expression")
    created_at: datetime = Field(..., description="Agent creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_run: Optional[datetime] = Field(None, description="Last execution timestamp")
    next_run: Optional[datetime] = Field(None, description="Next scheduled execution timestamp")
    run_count: int = Field(0, description="Total number of executions")
    error_count: int = Field(0, description="Total number of errors")
    last_error: Optional[str] = Field(None, description="Last error message")

    class Config:
        from_attributes = True


class PendingAgentResponse(BaseModel):
    id: str = Field(..., description="Unique agent identifier")
    name: str = Field(..., description="Name of the agent")
    status: AgentStatus = Field(..., description="Current agent status")
    next_run: Optional[datetime] = Field(None, description="Next scheduled execution")


class MetricsResponse(BaseModel):
    total_agents: int = Field(..., description="Total number of agents")
    active_agents: int = Field(..., description="Number of active agents")
    idle_agents: int = Field(..., description="Number of idle agents")
    error_agents: int = Field(..., description="Number of agents in error state")
    total_executions: int = Field(..., description="Total execution count across all agents")
    total_errors: int = Field(..., description="Total error count across all agents")
    system_uptime: float = Field(..., description="System uptime in seconds")
    cpu_usage: float = Field(..., description="Current CPU usage percentage")
    memory_usage: float = Field(..., description="Current memory usage percentage")


class ActivityStatusResponse(BaseModel):
    timestamp: datetime = Field(..., description="Activity timestamp")
    agent_id: str = Field(..., description="Agent identifier")
    agent_name: str = Field(..., description="Agent name")
    status: AgentStatus = Field(..., description="Agent status at this time")
    event: str = Field(..., description="Event type (e.g., 'started', 'completed', 'failed')")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional event details")


class TrendResponse(BaseModel):
    timestamp: datetime = Field(..., description="Data point timestamp")
    active_agents: int = Field(..., description="Number of active agents at this time")
    total_executions: int = Field(..., description="Cumulative executions at this time")
    error_rate: float = Field(..., description="Error rate percentage at this time")
    cpu_usage: float = Field(..., description="CPU usage at this time")
    memory_usage: float = Field(..., description="Memory usage at this time")


class SystemStatusResponse(BaseModel):
    status: str = Field(..., description="Overall system status")
    metrics: MetricsResponse = Field(..., description="Current system metrics")
    recent_activity: List[ActivityStatusResponse] = Field(default_factory=list, description="Recent activity events")
    pending_agents: List[PendingAgentResponse] = Field(default_factory=list, description="Agents pending execution")
