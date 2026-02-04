"""Activation monitor for checking PENDING agent activation status."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from mcn_core.database import get_db_connection, log_activity
from mcn_core.agent_runner import MCNAgentRunner
from mcn_core.config import get_config

logger = logging.getLogger(__name__)

class ActivationMonitor:
    """Background service to monitor PENDING agent activation."""

    def __init__(self, scheduler=None):
        self.config = get_config()
        self.check_interval = self.config.activation.check_interval_seconds
        self.max_pending_hours = self.config.activation.max_pending_hours
        self.scheduler = scheduler
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        """Start the activation monitor."""
        if self._running:
            logger.warning("Activation monitor already running")
            return

        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Activation monitor started")

    async def stop(self):
        """Stop the activation monitor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Activation monitor stopped")

    async def _monitor_loop(self):
        """Main monitoring loop."""
        while self._running:
            try:
                await self._check_all_pending()
            except Exception as e:
                logger.exception(f"Error in activation monitor: {e}")

            await asyncio.sleep(self.check_interval)

    async def _check_all_pending(self):
        """Check all pending agents."""
        with get_db_connection() as conn:
            cursor = conn.execute('''
                SELECT a.id, a.display_name, p.created_at, p.check_count
                FROM agents a
                JOIN pending_activation p ON p.agent_id = a.id
                WHERE a.status = 'PENDING'
            ''')
            pending_agents = [dict(row) for row in cursor.fetchall()]

        for agent in pending_agents:
            try:
                await self._check_agent(agent)
            except Exception as e:
                logger.error(f"Error checking agent {agent['id']}: {e}")

    async def _check_agent(self, agent: dict):
        """Check single agent activation status."""
        agent_id = agent['id']
        created_at = datetime.fromisoformat(agent['created_at'])

        # Check if pending too long - auto cleanup
        if datetime.now() - created_at > timedelta(hours=self.max_pending_hours):
            logger.warning(f"Agent {agent_id} pending too long, cleaning up")
            await self._cleanup_stale_pending(agent_id)
            return

        # Check activation status
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

            # Check if response indicates active status
            if self._is_activated(output):
                await self._on_activated(agent_id)

    def _is_activated(self, output: str) -> bool:
        """Check if output indicates agent is activated."""
        if not output:
            return False

        output_lower = output.lower()

        # Look for activation indicators
        if '"status": "active"' in output_lower:
            return True
        if 'status: active' in output_lower:
            return True
        if 'activated successfully' in output_lower:
            return True

        return False

    async def _on_activated(self, agent_id: str):
        """Handle successful activation."""
        logger.info(f"Agent {agent_id} activated!")

        with get_db_connection() as conn:
            # Update agent status
            conn.execute('''
                UPDATE agents SET status = ?, activated_at = ?
                WHERE id = ?
            ''', ('ACTIVE', datetime.now().isoformat(), agent_id))

            # Remove from pending queue
            conn.execute(
                "DELETE FROM pending_activation WHERE agent_id = ?",
                (agent_id,)
            )
            conn.commit()

        # Log the activation
        log_activity(agent_id, 'activation', 'Agent activated by user', True)

        # Start heartbeat scheduling
        if self.scheduler:
            await self.scheduler.add_agent(agent_id)

    async def _cleanup_stale_pending(self, agent_id: str):
        """Cleanup stale pending agent."""
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE agents SET status = ? WHERE id = ?",
                ('DESIGN', agent_id)
            )
            conn.execute(
                "DELETE FROM pending_activation WHERE agent_id = ?",
                (agent_id,)
            )
            conn.commit()

        log_activity(agent_id, 'pending_timeout',
                    f'Pending activation expired after {self.max_pending_hours} hours',
                    False)


# Singleton instance
_activation_monitor: Optional[ActivationMonitor] = None

def get_activation_monitor(scheduler=None) -> ActivationMonitor:
    """Get or create activation monitor singleton."""
    global _activation_monitor
    if _activation_monitor is None:
        _activation_monitor = ActivationMonitor(scheduler)
    return _activation_monitor
