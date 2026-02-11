from enum import Enum
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    DESIGN = "DESIGN"
    WAITING = "WAITING"
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PROBATION = "PROBATION"
    RETIRED = "RETIRED"


class ActivityStatus(str, Enum):
    HEALTHY = "HEALTHY"
    IDLE = "IDLE"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    STAGNANT = "STAGNANT"


class AgentCreate(BaseModel):
    name: str = Field(..., description="Unique agent name (slug)")
    display_name: Optional[str] = Field(None, description="Display name")
    bio: Optional[str] = Field(None, description="Agent bio")
    concept: Optional[str] = Field(None, description="Agent concept/theme")
    personality: Optional[str] = Field(None, description="Personality traits")
    strategy: Optional[str] = Field(None, description="Content strategy")
    model: Optional[str] = Field(None, description="Model override for this agent")
    ghost_md: Optional[str] = Field(None, description="Custom ghost.md content")
    shell_md: Optional[str] = Field(None, description="Custom shell.md content")
    site_id: Optional[str] = Field(None, description="Loop site ID")
    node_id: Optional[str] = Field(None, description="Loop node ID")


class AgentUpdate(BaseModel):
    display_name: Optional[str] = None
    bio: Optional[str] = None
    ghost_md: Optional[str] = None
    shell_md: Optional[str] = None
    status: Optional[AgentStatus] = None
    is_protected: Optional[bool] = None
    profile_name: Optional[str] = None
    use_mcp: Optional[bool] = None
    site_id: Optional[str] = None
    node_id: Optional[str] = None


class AgentResponse(BaseModel):
    id: str
    name: str
    display_name: str
    bio: str
    status: AgentStatus
    activity_status: Optional[str] = None
    activation_url: Optional[str] = None
    created_at: datetime
    last_heartbeat: Optional[datetime] = None
    bucks: int = 0
    followers: int = 0
    is_protected: bool = False
    model: Optional[str] = None
    profile_name: Optional[str] = None
    use_mcp: Optional[bool] = None
    site_id: Optional[str] = None
    node_id: Optional[str] = None
    site_name: Optional[str] = None
    node_name: Optional[str] = None
    is_running: bool = False

    class Config:
        from_attributes = True


class PendingAgentResponse(BaseModel):
    agent_id: str
    name: str
    display_name: str
    activation_url: str
    registered_at: datetime


class MetricsOverview(BaseModel):
    total_bucks: int
    agent_count: int
    active_agents: int
    pending_agents: int


class SystemStatusResponse(BaseModel):
    cpu_percent: float
    memory_mb: float
    memory_percent: float = 0.0
    available_memory_mb: float = 0.0
    active_agents: int
    # Backward-compatible: pending_agents == waiting_agents (human auth wait)
    pending_agents: int
    waiting_agents: int = 0
    pending_active_agents: int = 0
    running_processes: int = 0
    network_sent_mb: float = 0.0
    network_recv_mb: float = 0.0
    token_used: int = 0
    token_limit: int = 50000
    token_percent: float = 0.0
    max_concurrent: int = 10
    max_total: int = 100
    can_run_agent: bool = True
    should_throttle: bool = False


class ActivityStatusResponse(BaseModel):
    agent_id: str
    agent_name: str
    status: str
    last_activity: Optional[datetime] = None
    minutes_since_activity: int = 0


class TrendResponse(BaseModel):
    topic: str
    score: float
    post_count: int
    sample_posts: List[str] = []


class FactorySuggestion(BaseModel):
    name: str
    display_name: str
    concept: str
    personality: str
    strategy: str
    trend_alignment: float
