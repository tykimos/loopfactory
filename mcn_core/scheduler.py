"""Heartbeat scheduler for agent execution."""
import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from typing import Dict, Optional
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.date import DateTrigger

from mcn_core.config import get_config
from mcn_core.agent_runner import MCNAgentRunner
from mcn_core.database import get_db_connection, log_activity
from mcn_core.resource_monitor import get_resource_monitor
from mcn_core.heartbeat_manager import get_heartbeat_manager
from mcn_core.scheduling_policy import decide_next_run, decide_backoff, ScheduleDecision
from mcn_core.concurrency_controller import get_concurrency_controller

logger = logging.getLogger(__name__)


class HeartbeatScheduler:
    """Schedules and executes agent heartbeats using BackgroundScheduler."""

    # Auto-sync interval (seconds)
    # Keep within 10s per operational requirement.
    SYNC_INTERVAL = 5
    # First sync should be gentle: only schedule jobs.
    # Do not burst-kickstart hundreds of immediate heartbeats.
    FIRST_SYNC_KICKSTART_MAX = 0
    FIRST_SYNC_BATCH_SIZE = 1
    FIRST_SYNC_BATCH_DELAY_SEC = 1

    def __init__(self):
        self.config = get_config()

        # Use BackgroundScheduler (runs in separate thread, doesn't block event loop)
        self.scheduler = BackgroundScheduler()
        self._active_jobs: Dict[str, str] = {}  # agent_id -> job_id
        self._sync_task: Optional[asyncio.Task] = None
        self._running = False
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None
        self._semaphore: Optional[asyncio.Semaphore] = None
        self._concurrency_controller = None
        self._inflight_heartbeats = 0
        self._inflight_lock = asyncio.Lock()
        self._admission_lock = asyncio.Lock()
        self._default_executor: Optional[ThreadPoolExecutor] = None

    async def start(self):
        """Start the scheduler and auto-sync loop."""
        # Store reference to event loop for running coroutines from threads
        try:
            self._event_loop = asyncio.get_running_loop()
        except RuntimeError:
            self._event_loop = asyncio.get_event_loop()

        # Increase asyncio.to_thread() parallelism.
        # Many heartbeats call subprocess.run() via asyncio.to_thread; the default executor
        # size can be small (~os.cpu_count()+4), which often looks like a hard cap (e.g. 15).
        if self._event_loop and self._default_executor is None:
            cpu = os.cpu_count() or 4
            # Allow override via env; keep a sane cap to avoid spawning thousands of processes.
            env_workers = os.getenv("LOOPFACTORY_TO_THREAD_WORKERS")
            max_cap = 1024
            if env_workers:
                try:
                    requested = int(env_workers)
                    if requested <= 0:
                        raise ValueError("must be > 0")
                    max_workers = min(max_cap, requested)
                    if requested != max_workers:
                        logger.warning(
                            f"LOOPFACTORY_TO_THREAD_WORKERS={requested} clipped to {max_workers} (cap={max_cap})"
                        )
                except Exception as e:
                    logger.warning(
                        f"Invalid LOOPFACTORY_TO_THREAD_WORKERS={env_workers!r} ({e}); "
                        f"falling back to auto sizing"
                    )
                    max_workers = min(max_cap, max(64, cpu * 16))
            else:
                max_workers = min(max_cap, max(64, cpu * 16))
            self._default_executor = ThreadPoolExecutor(max_workers=max_workers)
            try:
                self._event_loop.set_default_executor(self._default_executor)
                logger.info(f"Set default executor max_workers={max_workers}")
            except Exception as e:
                logger.warning(f"Failed to set default executor: {e}")

        # Initialize concurrency controller
        self._concurrency_controller = get_concurrency_controller()

        # No fixed upper cap here. Admission is controlled by live resource checks.
        self._semaphore = None

        logger.info("Resource-gated heartbeat admission enabled (no fixed max cap)")

        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Heartbeat scheduler started (BackgroundScheduler)")

        # Start auto-sync background task
        if not self._running:
            self._running = True
            self._sync_task = asyncio.create_task(self._auto_sync_loop())
            logger.info("Auto-sync loop started")

    def stop(self):
        """Stop the scheduler and auto-sync loop."""
        self._running = False
        if self._sync_task:
            self._sync_task.cancel()
            self._sync_task = None

        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Heartbeat scheduler stopped")

        if self._default_executor:
            try:
                self._default_executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                try:
                    self._default_executor.shutdown(wait=False)
                except Exception:
                    pass
            self._default_executor = None

    async def _auto_sync_loop(self):
        """Background loop that syncs scheduler with DB every SYNC_INTERVAL seconds."""
        print(f"[SCHEDULER] Auto-sync loop starting (interval: {self.SYNC_INTERVAL}s)", flush=True)
        first_sync = True

        while self._running:
            try:
                await self._sync_with_db(first_sync=first_sync)
                first_sync = False
            except Exception as e:
                print(f"[SCHEDULER] Auto-sync error: {e}", flush=True)

            await asyncio.sleep(self.SYNC_INTERVAL)

    async def _sync_with_db(self, first_sync: bool = False):
        """Sync scheduler state with database - add missing, remove retired."""
        # Get all ACTIVE agents from DB
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT id FROM agents WHERE status = 'ACTIVE'"
            )
            db_active_agents = {row['id'] for row in cursor.fetchall()}

        # Currently scheduled agents
        scheduled_agents = set(self._active_jobs.keys())

        # Add missing agents (in DB but not scheduled)
        to_add = db_active_agents - scheduled_agents

        if first_sync and to_add:
            # First sync: schedule only (no immediate mass kickstart).
            print(f"[SCHEDULER] First sync: scheduling {len(to_add)} agents (no burst start)", flush=True)
            for agent_id in to_add:
                await self.add_agent(agent_id, run_immediately=False)
        else:
            for agent_id in to_add:
                logger.info(f"Auto-sync: Adding new ACTIVE agent {agent_id}")
                await self.add_agent(agent_id, run_immediately=True)

        # Remove retired agents (scheduled but not in DB as ACTIVE)
        to_remove = scheduled_agents - db_active_agents
        for agent_id in to_remove:
            logger.info(f"Auto-sync: Removing non-ACTIVE agent {agent_id}")
            await self.remove_agent(agent_id)

    async def _delayed_heartbeat(self, agent_id: str, delay: float):
        """Execute heartbeat after a delay."""
        await asyncio.sleep(delay)
        print(f"[SCHEDULER] Delayed heartbeat starting for {agent_id}", flush=True)
        await self._execute_heartbeat(agent_id)

    async def add_agent(self, agent_id: str, run_immediately: bool = True):
        """Add an agent to the heartbeat schedule."""
        if agent_id in self._active_jobs:
            job_id = self._active_jobs.get(agent_id)
            if job_id and self.scheduler.get_job(job_id):
                logger.warning(f"Agent {agent_id} already scheduled")
                return

        agent = self._load_agent(agent_id)
        decision = decide_next_run(agent)
        if decision:
            self._schedule_job(agent_id, decision)
        else:
            logger.info(f"Agent {agent_id} is not schedulable (status not ACTIVE)")
            return

        # Run first heartbeat immediately in background if requested
        if run_immediately:
            asyncio.create_task(self._execute_heartbeat(agent_id))

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
        self._delete_schedule(agent_id)

    def _execute_heartbeat_sync(self, agent_id: str):
        """Synchronous wrapper for heartbeat execution (called by BackgroundScheduler)."""
        if self._event_loop and self._running:
            # Schedule coroutine on the main event loop from background thread
            asyncio.run_coroutine_threadsafe(
                self._execute_heartbeat(agent_id),
                self._event_loop
            )

    def _get_agent_profile(self, agent_id: str) -> str:
        """Get the profile name for an agent."""
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT profile_name FROM agents WHERE id = ?",
                (agent_id,)
            )
            row = cursor.fetchone()
            return row['profile_name'] if row and row['profile_name'] else 'default'

    async def _acquire_execution_slot(self, profile_name: str):
        """Acquire an execution slot with serialized admission and live resource checks.

        - No hard max cap is enforced here.
        - Admission decisions are made one-by-one to avoid burst launching.
        """
        if self._concurrency_controller:
            live_max = self._concurrency_controller.get_max_concurrent(force_recalc=True)
        else:
            live_max = 1

        resource_monitor = get_resource_monitor()

        # Serialize admission checks so launches happen one-by-one.
        async with self._admission_lock:
            while not resource_monitor.can_run_agent():
                await asyncio.sleep(1)

            async with self._inflight_lock:
                self._inflight_heartbeats += 1

        return live_max

    async def _release_execution_slot(self):
        """Release a previously acquired execution slot."""
        async with self._inflight_lock:
            if self._inflight_heartbeats > 0:
                self._inflight_heartbeats -= 1

    async def _execute_heartbeat(self, agent_id: str):
        """Execute a single heartbeat for an agent using HeartbeatManager."""
        # Get agent's profile
        profile_name = self._get_agent_profile(agent_id)
        resource_monitor = get_resource_monitor()
        live_max = await self._acquire_execution_slot(profile_name)
        try:
            print(
                f"[HEARTBEAT] Executing for {agent_id} [profile={profile_name}, "
                f"inflight={self._inflight_heartbeats}, live_max={live_max}]...",
                flush=True,
            )

            # Check resource availability
            if not resource_monitor.can_run_agent():
                print(f"[HEARTBEAT] Resources unavailable, skipping {agent_id}", flush=True)
                agent = self._load_agent(agent_id)
                decision = decide_backoff(agent, minutes=5)
                if decision:
                    self._schedule_job(agent_id, decision)
                return

            # Use HeartbeatManager for execution
            heartbeat_manager = get_heartbeat_manager()
            result = await heartbeat_manager.execute_heartbeat(agent_id)
        finally:
            await self._release_execution_slot()

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
            f"Success: {result.success}, Skills: {result.skills_used}",
            result.success
        )

        self._update_last_run(agent_id, datetime.now())

        # Update state.json via runner
        runner = MCNAgentRunner(agent_id)
        runner.update_state({
            "last_heartbeat": datetime.now().isoformat(),
            "heartbeat_count": runner.get_state().get("heartbeat_count", 0) + 1,
            "last_skills_used": result.skills_used
        })

        if not result.success:
            state = runner.get_state()
            failures = state.get("consecutive_failures", 0) + 1
            runner.update_state({"consecutive_failures": failures, "activity_status": "IDLE"})

            # Persist activity_status in DB so UI reflects immediate idle on failure
            with get_db_connection() as conn:
                conn.execute(
                    "UPDATE agents SET activity_status = ? WHERE id = ?",
                    ("IDLE", agent_id)
                )
                conn.commit()

            if failures >= 5:
                logger.error(f"Agent {agent_id} has {failures} consecutive failures")
        else:
            runner.update_state({"consecutive_failures": 0})

        # Reschedule next run based on policy
        agent = self._load_agent(agent_id)
        throttled = resource_monitor.should_throttle() if resource_monitor else False
        decision = decide_next_run(agent, throttled=throttled)
        if decision:
            self._schedule_job(agent_id, decision)

    def get_jobs(self):
        """Get all scheduled jobs."""
        return self.scheduler.get_jobs()

    def get_active_agents(self) -> list:
        """Get list of agents with active schedules."""
        return list(self._active_jobs.keys())

    def get_runtime_status(self) -> dict:
        """Get lightweight runtime execution status."""
        return {
            "inflight_heartbeats": self._inflight_heartbeats,
            "scheduled_jobs": len(self._active_jobs),
        }

    def _load_agent(self, agent_id: str) -> Optional[dict]:
        """Load agent record from database."""
        with get_db_connection() as conn:
            cursor = conn.execute(
                "SELECT id, status, activity_status, last_heartbeat FROM agents WHERE id = ?",
                (agent_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None

    def _schedule_job(self, agent_id: str, decision: ScheduleDecision):
        """Schedule next heartbeat run using a one-shot job."""
        if not decision:
            return

        run_at = decision.next_run_at
        if run_at <= datetime.now():
            run_at = datetime.now() + timedelta(seconds=10)

        job = self.scheduler.add_job(
            self._execute_heartbeat_sync,
            trigger=DateTrigger(run_date=run_at),
            args=[agent_id],
            id=f"heartbeat_{agent_id}",
            replace_existing=True
        )

        self._active_jobs[agent_id] = job.id
        self._upsert_schedule(agent_id, decision)
        logger.info(
            f"Scheduled heartbeat for {agent_id} at {run_at.isoformat()} "
            f"(interval={decision.interval_minutes}m, reason={decision.reason})"
        )

    def _upsert_schedule(self, agent_id: str, decision: ScheduleDecision):
        """Upsert schedule decision into agent_schedule table."""
        with get_db_connection() as conn:
            conn.execute('''
                INSERT INTO agent_schedule (
                    agent_id, next_run_at, policy, reason, priority, interval_minutes, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(agent_id) DO UPDATE SET
                    next_run_at = excluded.next_run_at,
                    policy = excluded.policy,
                    reason = excluded.reason,
                    priority = excluded.priority,
                    interval_minutes = excluded.interval_minutes,
                    updated_at = excluded.updated_at
            ''', (
                agent_id,
                decision.next_run_at.isoformat(),
                decision.policy,
                decision.reason,
                decision.priority,
                decision.interval_minutes,
                datetime.now().isoformat()
            ))
            conn.commit()

    def _update_last_run(self, agent_id: str, run_at: datetime):
        """Update last_run_at for agent in schedule table."""
        with get_db_connection() as conn:
            conn.execute('''
                UPDATE agent_schedule
                SET last_run_at = ?, updated_at = ?
                WHERE agent_id = ?
            ''', (run_at.isoformat(), datetime.now().isoformat(), agent_id))
            conn.commit()

    def _delete_schedule(self, agent_id: str):
        """Remove schedule entry for agent."""
        with get_db_connection() as conn:
            conn.execute("DELETE FROM agent_schedule WHERE agent_id = ?", (agent_id,))
            conn.commit()


# Singleton
_scheduler: Optional[HeartbeatScheduler] = None

def get_scheduler() -> HeartbeatScheduler:
    """Get or create scheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = HeartbeatScheduler()
    return _scheduler
