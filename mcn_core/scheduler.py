"""Heartbeat scheduler for agent execution."""
import asyncio
import random
import logging
from datetime import datetime
from typing import Dict, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from mcn_core.config import get_config
from mcn_core.agent_runner import MCNAgentRunner
from mcn_core.database import get_db_connection, log_activity
from mcn_core.resource_monitor import get_resource_monitor

logger = logging.getLogger(__name__)

class HeartbeatScheduler:
    """Schedules and executes agent heartbeats."""

    def __init__(self):
        self.config = get_config()
        self.base_interval = self.config.scheduling.base_interval_minutes
        self.jitter = self.config.scheduling.jitter_minutes
        self.peak_hours = self.config.scheduling.peak_hours

        self.scheduler = AsyncIOScheduler()
        self._active_jobs: Dict[str, str] = {}  # agent_id -> job_id

    def start(self):
        """Start the scheduler."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Heartbeat scheduler started")

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Heartbeat scheduler stopped")

    async def add_agent(self, agent_id: str):
        """Add an agent to the heartbeat schedule."""
        if agent_id in self._active_jobs:
            logger.warning(f"Agent {agent_id} already scheduled")
            return

        interval = self._calculate_interval()

        job = self.scheduler.add_job(
            self._execute_heartbeat,
            trigger=IntervalTrigger(minutes=interval),
            args=[agent_id],
            id=f"heartbeat_{agent_id}",
            replace_existing=True
        )

        self._active_jobs[agent_id] = job.id
        logger.info(f"Scheduled heartbeat for agent {agent_id} every {interval} minutes")

    async def remove_agent(self, agent_id: str):
        """Remove an agent from the heartbeat schedule."""
        job_id = self._active_jobs.get(agent_id)
        if job_id:
            try:
                self.scheduler.remove_job(job_id)
            except Exception:
                pass
            del self._active_jobs[agent_id]
            logger.info(f"Removed heartbeat schedule for agent {agent_id}")

    def _calculate_interval(self) -> int:
        """Calculate heartbeat interval with jitter."""
        base = self.base_interval
        jitter = random.randint(-self.jitter, self.jitter)

        # Reduce interval during peak hours
        current_hour = datetime.now().hour
        for start, end in self.peak_hours:
            if start <= current_hour < end:
                base = int(base * 0.75)  # 25% shorter interval during peak
                break

        return max(5, base + jitter)  # Minimum 5 minutes

    async def _execute_heartbeat(self, agent_id: str):
        """Execute a single heartbeat for an agent."""
        logger.info(f"Executing heartbeat for agent {agent_id}")

        # Check resource availability
        resource_monitor = get_resource_monitor()
        if not resource_monitor.can_run_agent():
            logger.warning(f"Resources unavailable, skipping heartbeat for {agent_id}")
            return

        runner = MCNAgentRunner(agent_id)
        result = runner.run_heartbeat()

        # Update last_heartbeat in database
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE agents SET last_heartbeat = ? WHERE id = ?",
                (datetime.now().isoformat(), agent_id)
            )
            conn.commit()

        # Log activity
        log_activity(
            agent_id,
            'heartbeat',
            f"Success: {result.get('success', False)}",
            result.get('success', False)
        )

        # Update state.json
        runner.update_state({
            "last_heartbeat": datetime.now().isoformat(),
            "heartbeat_count": runner.get_state().get("heartbeat_count", 0) + 1
        })

        if not result.get("success"):
            # Track consecutive failures
            state = runner.get_state()
            failures = state.get("consecutive_failures", 0) + 1
            runner.update_state({"consecutive_failures": failures})

            if failures >= 5:
                logger.error(f"Agent {agent_id} has {failures} consecutive failures")
        else:
            # Reset consecutive failures on success
            runner.update_state({"consecutive_failures": 0})

    def get_jobs(self):
        """Get all scheduled jobs."""
        return self.scheduler.get_jobs()

    def get_active_agents(self) -> list:
        """Get list of agents with active schedules."""
        return list(self._active_jobs.keys())


# Singleton
_scheduler: Optional[HeartbeatScheduler] = None

def get_scheduler() -> HeartbeatScheduler:
    """Get or create scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = HeartbeatScheduler()
    return _scheduler
