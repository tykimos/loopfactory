"""Activity monitor for tracking agent health and sending reactivation prompts."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List

from mcn_core.config import get_config
from mcn_core.database import get_db_connection, log_activity
from mcn_core.agent_runner import MCNAgentRunner

logger = logging.getLogger(__name__)

class ActivityMonitor:
    """Monitors agent activity and sends reactivation prompts."""

    REACTIVATION_PROMPTS = {
        "idle": """
You've been quiet for a while. Time to check in with AssiBucks!
- Check the hot and rising feeds
- Engage with at least 3 interesting posts
- Consider creating a post if you have something to share
        """,
        "warning": """
URGENT: Your activity has dropped significantly.
To maintain your presence on AssiBucks:
1. Immediately perform a heartbeat
2. Engage actively with the feed
3. Post something relevant to your interests
Your community is waiting for your insights!
        """,
        "stagnant_bucks": """
Your bucks growth has stalled. Let's change strategy:
- Focus on rising posts (higher engagement potential)
- Write more thoughtful comments (quality over quantity)
- Create original content that sparks discussion
Time to re-engage and grow!
        """
    }

    def __init__(self):
        self.config = get_config()
        self.am_config = self.config.activity_monitoring
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._prompt_cooldowns: dict = {}  # agent_id -> last_prompt_time

    async def start(self):
        """Start the activity monitor."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("Activity monitor started")

    async def stop(self):
        """Stop the activity monitor."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Activity monitor stopped")

    async def _monitor_loop(self):
        """Main monitoring loop."""
        check_interval = self.am_config.check_interval_minutes * 60

        while self._running:
            try:
                await self._check_all_agents()
            except Exception as e:
                logger.exception(f"Error in activity monitor: {e}")

            await asyncio.sleep(check_interval)

    async def _check_all_agents(self):
        """Check activity status of all active agents."""
        with get_db_connection() as conn:
            cursor = conn.execute('''
                SELECT id, display_name, last_heartbeat, is_protected
                FROM agents WHERE status = 'ACTIVE'
            ''')
            agents = [dict(row) for row in cursor.fetchall()]

        for agent in agents:
            try:
                await self.check_and_reactivate(agent)
            except Exception as e:
                logger.error(f"Error checking agent {agent['id']}: {e}")

    async def check_and_reactivate(self, agent: dict):
        """Check agent activity and send reactivation prompt if needed."""
        agent_id = agent['id']
        status = self._get_activity_status(agent)

        # Update activity_status in state.json
        runner = MCNAgentRunner(agent_id)
        runner.update_state({"activity_status": status})

        if status == "IDLE":
            await self._send_reactivation_prompt(agent_id, "idle")
        elif status == "WARNING":
            await self._send_reactivation_prompt(agent_id, "warning")
            await self._notify_dashboard(agent_id, "warning")
        elif status == "CRITICAL":
            if not agent.get('is_protected'):
                await self._escalate_to_probation(agent_id)
        elif status == "STAGNANT":
            await self._send_reactivation_prompt(agent_id, "stagnant_bucks")

    def _get_activity_status(self, agent: dict) -> str:
        """Determine agent's activity status."""
        last_heartbeat = agent.get('last_heartbeat')

        if not last_heartbeat:
            return "UNKNOWN"

        try:
            last_hb_time = datetime.fromisoformat(last_heartbeat)
        except:
            return "UNKNOWN"

        now = datetime.now()
        elapsed = now - last_hb_time

        idle_threshold = timedelta(minutes=self.am_config.idle_threshold_minutes)
        warning_threshold = timedelta(hours=self.am_config.warning_threshold_hours)
        critical_threshold = timedelta(hours=self.am_config.critical_threshold_hours)

        if elapsed > critical_threshold:
            return "CRITICAL"
        elif elapsed > warning_threshold:
            return "WARNING"
        elif elapsed > idle_threshold:
            return "IDLE"

        # Check for stagnant bucks
        if self._is_bucks_stagnant(agent['id']):
            return "STAGNANT"

        return "HEALTHY"

    def _is_bucks_stagnant(self, agent_id: str) -> bool:
        """Check if agent's bucks growth is stagnant."""
        observation_days = self.am_config.bucks_monitoring.observation_period_days
        min_growth = self.am_config.bucks_monitoring.min_growth_threshold

        with get_db_connection() as conn:
            since = (datetime.now() - timedelta(days=observation_days)).isoformat()

            cursor = conn.execute('''
                SELECT total_bucks FROM metrics
                WHERE agent_id = ? AND recorded_at >= ?
                ORDER BY recorded_at ASC LIMIT 1
            ''', (agent_id, since))
            old = cursor.fetchone()

            cursor = conn.execute('''
                SELECT total_bucks FROM metrics
                WHERE agent_id = ?
                ORDER BY recorded_at DESC LIMIT 1
            ''', (agent_id,))
            new = cursor.fetchone()

        if not old or not new:
            return False

        growth = (new['total_bucks'] or 0) - (old['total_bucks'] or 0)
        return growth < min_growth

    async def _send_reactivation_prompt(self, agent_id: str, prompt_type: str):
        """Send reactivation prompt to agent."""
        # Check cooldown
        cooldown_mins = self.am_config.reactivation_prompts.cooldown_minutes
        last_prompt = self._prompt_cooldowns.get(agent_id)

        if last_prompt:
            elapsed = (datetime.now() - last_prompt).total_seconds() / 60
            if elapsed < cooldown_mins:
                return

        prompt = self.REACTIVATION_PROMPTS.get(prompt_type, "")
        if not prompt:
            return

        runner = MCNAgentRunner(agent_id)
        result = runner.run_with_prompt(prompt.strip())

        self._prompt_cooldowns[agent_id] = datetime.now()

        log_activity(
            agent_id,
            "reactivation_prompt",
            f"Type: {prompt_type}, Success: {result.get('success', False)}",
            result.get('success', False)
        )

    async def _notify_dashboard(self, agent_id: str, level: str):
        """Notify dashboard of agent needing attention."""
        log_activity(agent_id, "alert", f"Activity {level}", False)

    async def _escalate_to_probation(self, agent_id: str):
        """Escalate agent to probation status."""
        with get_db_connection() as conn:
            conn.execute(
                "UPDATE agents SET status = ? WHERE id = ?",
                ('PROBATION', agent_id)
            )
            conn.commit()

        log_activity(agent_id, "probation", "Escalated due to critical inactivity", False)
        logger.warning(f"Agent {agent_id} moved to PROBATION")

    def get_activity_summary(self) -> dict:
        """Get summary of activity statuses for all agents."""
        with get_db_connection() as conn:
            cursor = conn.execute('''
                SELECT id, display_name, last_heartbeat, is_protected
                FROM agents WHERE status = 'ACTIVE'
            ''')
            agents = [dict(row) for row in cursor.fetchall()]

        summary = {"healthy": 0, "idle": 0, "warning": 0, "critical": 0, "stagnant": 0}

        for agent in agents:
            status = self._get_activity_status(agent).lower()
            if status in summary:
                summary[status] += 1
            elif status == "unknown":
                summary["idle"] += 1

        return {
            "healthy_count": summary["healthy"],
            "idle_count": summary["idle"],
            "warning_count": summary["warning"],
            "critical_count": summary["critical"]
        }

    def get_alerts(self) -> List[dict]:
        """Get list of agents needing attention."""
        with get_db_connection() as conn:
            cursor = conn.execute('''
                SELECT id, display_name, last_heartbeat, is_protected
                FROM agents WHERE status IN ('ACTIVE', 'PROBATION')
            ''')
            agents = [dict(row) for row in cursor.fetchall()]

        alerts = []
        for agent in agents:
            status = self._get_activity_status(agent)
            if status not in ["HEALTHY", "UNKNOWN"]:
                alerts.append({
                    "agent_id": agent['id'],
                    "display_name": agent['display_name'] or agent['id'],
                    "status": status,
                    "last_heartbeat": agent['last_heartbeat'],
                    "is_protected": agent.get('is_protected', False)
                })

        return alerts


# Singleton
_activity_monitor: Optional[ActivityMonitor] = None

def get_activity_monitor() -> ActivityMonitor:
    global _activity_monitor
    if _activity_monitor is None:
        _activity_monitor = ActivityMonitor()
    return _activity_monitor
