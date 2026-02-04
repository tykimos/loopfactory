"""Resource monitor for system CPU and memory usage."""
import os
import psutil
import logging
from typing import Optional
from dataclasses import dataclass

from mcn_core.config import get_config

logger = logging.getLogger(__name__)

@dataclass
class ResourceUsage:
    """Current resource usage snapshot."""
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    available_memory_mb: float
    running_processes: int

class ResourceMonitor:
    """Monitors system resources for agent execution."""

    def __init__(self):
        self.config = get_config()
        self.cpu_high = self.config.system.cpu_threshold_high
        self.cpu_low = self.config.system.cpu_threshold_low
        self.memory_per_agent = self.config.system.memory_limit_per_agent_mb

    def get_current_usage(self) -> dict:
        """Get current system resource usage."""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()

        # Count loop processes (or python processes as proxy)
        running_processes = 0
        for proc in psutil.process_iter(['name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', []) or []
                if any('loop' in str(c).lower() for c in cmdline):
                    running_processes += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return {
            "cpu_percent": cpu_percent,
            "memory_mb": memory.used / (1024 * 1024),
            "memory_percent": memory.percent,
            "available_memory_mb": memory.available / (1024 * 1024),
            "running_processes": running_processes
        }

    def can_run_agent(self) -> bool:
        """Check if system has resources to run another agent."""
        usage = self.get_current_usage()

        # Check CPU
        if usage["cpu_percent"] >= self.cpu_high:
            logger.warning(f"CPU too high: {usage['cpu_percent']}%")
            return False

        # Check memory
        if usage["available_memory_mb"] < self.memory_per_agent:
            logger.warning(f"Memory too low: {usage['available_memory_mb']:.0f}MB available")
            return False

        return True

    def get_max_concurrent_agents(self) -> int:
        """Calculate maximum concurrent agents based on resources."""
        max_concurrent = self.config.system.max_concurrent_agents

        if max_concurrent == "auto":
            # Auto-calculate based on CPU cores and memory
            cpu_count = os.cpu_count() or 4
            memory = psutil.virtual_memory()
            available_mb = memory.available / (1024 * 1024)

            # Each agent needs ~256MB and we leave some headroom
            memory_based = int(available_mb / self.memory_per_agent * 0.7)

            # Don't exceed 2x CPU count
            cpu_based = cpu_count * 2

            return min(memory_based, cpu_based, 20)  # Cap at 20

        return int(max_concurrent)

    def should_throttle(self) -> bool:
        """Check if we should throttle agent execution."""
        usage = self.get_current_usage()
        return usage["cpu_percent"] >= self.cpu_low

    def get_system_status(self) -> dict:
        """Get full system status for dashboard."""
        usage = self.get_current_usage()

        return {
            "cpu_percent": usage["cpu_percent"],
            "memory_mb": usage["memory_mb"],
            "memory_percent": usage["memory_percent"],
            "available_memory_mb": usage["available_memory_mb"],
            "running_processes": usage["running_processes"],
            "max_concurrent": self.get_max_concurrent_agents(),
            "can_run_agent": self.can_run_agent(),
            "should_throttle": self.should_throttle()
        }


# Singleton
_monitor: Optional[ResourceMonitor] = None

def get_resource_monitor() -> ResourceMonitor:
    """Get or create resource monitor singleton."""
    global _monitor
    if _monitor is None:
        _monitor = ResourceMonitor()
    return _monitor
