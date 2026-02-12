"""Heuristics for scheduling heartbeats."""
import random
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Optional

from mcn_core.config import get_config


@dataclass
class ScheduleDecision:
    """Represents the next scheduled heartbeat."""

    next_run_at: datetime
    interval_minutes: int
    policy: str
    reason: str
    priority: int = 0


def _base_interval(agent: Optional[dict], throttled: bool) -> int:
    config = get_config()
    interval = int(config.scheduling.base_interval_minutes)
    status = (agent or {}).get("status", "ACTIVE")
    activity_status = (agent or {}).get("activity_status")

    if status in ("PROBATION", "PENDING"):
        interval = max(5, interval // 2)
    elif status == "DESIGN":
        interval = max(interval, 2 * interval)

    if activity_status in ("WARNING", "CRITICAL"):
        interval = max(5, interval // 2)
    elif activity_status == "IDLE":
        interval = max(5, int(interval * 0.75))

    if throttled:
        interval = int(interval * 1.5)

    jitter = int(config.scheduling.jitter_minutes or 0)
    if jitter > 0:
        interval += random.randint(0, jitter)

    return max(5, interval)


def decide_next_run(agent: Optional[dict], throttled: bool = False) -> Optional[ScheduleDecision]:
    """Decide when the next heartbeat should run."""
    interval = _base_interval(agent, throttled)
    next_run = datetime.now() + timedelta(minutes=interval)
    reason = "throttled" if throttled else "scheduled"
    priority = -1 if agent and agent.get("status") == "ACTIVE" else 0
    return ScheduleDecision(
        next_run_at=next_run,
        interval_minutes=interval,
        policy="heartbeat",
        reason=reason,
        priority=priority,
    )


def decide_backoff(agent: Optional[dict], minutes: int = 5) -> Optional[ScheduleDecision]:
    """Return a short backoff schedule decision."""
    interval = max(1, int(minutes))
    next_run = datetime.now() + timedelta(minutes=interval)
    return ScheduleDecision(
        next_run_at=next_run,
        interval_minutes=interval,
        policy="backoff",
        reason="resource_backoff",
        priority=5,
    )
