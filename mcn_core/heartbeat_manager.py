"""Heartbeat execution manager."""
import asyncio
import json
import re
from dataclasses import dataclass
from typing import Optional

from mcn_core.agent_runner import MCNAgentRunner


@dataclass
class HeartbeatResult:
    """Represents the outcome of a heartbeat execution."""

    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    log_file: Optional[str] = None
    skills_used: str = "unknown"


class HeartbeatManager:
    """Runs blocking heartbeat routines without freezing the event loop."""

    def __init__(self):
        self._lock = asyncio.Lock()

    async def execute_heartbeat(self, agent_id: str) -> HeartbeatResult:
        """Run the blocking heartbeat call on a worker thread."""
        runner = MCNAgentRunner(agent_id)
        async with self._lock:
            result = await asyncio.to_thread(runner.run_heartbeat)

        skills_used = self._extract_skills(result.get("output"))
        return HeartbeatResult(
            success=result.get("success", False),
            output=result.get("output"),
            error=result.get("error"),
            log_file=result.get("log_file"),
            skills_used=skills_used,
        )

    def _extract_skills(self, output: Optional[str]) -> str:
        """Best-effort extraction of skills used from loop output."""
        if not output:
            return "unknown"

        # Try JSON payloads first
        try:
            data = json.loads(output)
            if isinstance(data, dict):
                skills = data.get("skills_used") or data.get("skills")
                if isinstance(skills, (list, tuple)):
                    return ", ".join(str(s) for s in skills)
                if isinstance(skills, str):
                    return skills
        except json.JSONDecodeError:
            pass

        # Fallback: search for "Skills: a, b" style lines
        match = re.search(r"skills?\s*[:\-]\s*(.+)", output, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        return "unknown"


_manager: Optional[HeartbeatManager] = None


def get_heartbeat_manager() -> HeartbeatManager:
    """Return singleton heartbeat manager."""
    global _manager
    if _manager is None:
        _manager = HeartbeatManager()
    return _manager
