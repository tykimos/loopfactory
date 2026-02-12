"""Simple concurrency controller that derives capacity from resource usage."""
import time
from typing import Optional

from mcn_core.resource_monitor import get_resource_monitor


class ConcurrencyController:
    """Calculates and caches the recommended concurrent agent limit."""

    CACHE_TTL_SECONDS = 10

    def __init__(self):
        self._cached_max: Optional[int] = None
        self._last_refresh: float = 0.0

    def get_max_concurrent(self, force_recalc: bool = False) -> int:
        """Return the maximum concurrent agents suggested by the resource monitor."""
        now = time.time()
        if (
            force_recalc
            or self._cached_max is None
            or (now - self._last_refresh) >= self.CACHE_TTL_SECONDS
        ):
            monitor = get_resource_monitor()
            self._cached_max = max(1, monitor.get_max_concurrent_agents())
            self._last_refresh = now
        return self._cached_max


_controller: Optional[ConcurrencyController] = None


def get_concurrency_controller() -> ConcurrencyController:
    """Return singleton controller instance."""
    global _controller
    if _controller is None:
        _controller = ConcurrencyController()
    return _controller
