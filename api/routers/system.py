"""System status and configuration API endpoints."""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import yaml
from pathlib import Path

from mcn_core.resource_monitor import get_resource_monitor
from mcn_core.config import get_config, CONFIG_PATH
from mcn_core.database import get_db_connection
from api.models import SystemStatusResponse

router = APIRouter(prefix="/api/system", tags=["system"])

@router.get("/status", response_model=SystemStatusResponse)
async def get_system_status():
    """Get current system status (CPU, memory, running processes)."""
    monitor = get_resource_monitor()
    status = monitor.get_system_status()

    # Add agent counts
    with get_db_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM agents WHERE status = 'ACTIVE'")
        active_count = cursor.fetchone()[0]

        cursor = conn.execute("SELECT COUNT(*) FROM agents WHERE status = 'PENDING'")
        pending_count = cursor.fetchone()[0]

    return SystemStatusResponse(
        cpu_percent=status["cpu_percent"],
        memory_mb=status["memory_mb"],
        active_agents=active_count,
        pending_agents=pending_count,
        running_processes=status["running_processes"]
    )

@router.get("/config")
async def get_current_config():
    """Get current configuration."""
    config = get_config()

    # Convert config to dict
    return {
        "system": {
            "max_concurrent_agents": config.system.max_concurrent_agents,
            "cpu_threshold_high": config.system.cpu_threshold_high,
            "cpu_threshold_low": config.system.cpu_threshold_low,
            "memory_limit_per_agent_mb": config.system.memory_limit_per_agent_mb
        },
        "scheduling": {
            "base_interval_minutes": config.scheduling.base_interval_minutes,
            "jitter_minutes": config.scheduling.jitter_minutes,
            "peak_hours": config.scheduling.peak_hours
        },
        "activation": {
            "check_interval_seconds": config.activation.check_interval_seconds,
            "max_pending_hours": config.activation.max_pending_hours
        },
        "lifecycle": {
            "probation_trigger_days": config.lifecycle.probation_trigger_days,
            "probation_duration_hours": config.lifecycle.probation_duration_hours,
            "auto_retire": config.lifecycle.auto_retire,
            "auto_create_replacement": config.lifecycle.auto_create_replacement
        },
        "activity_monitoring": {
            "check_interval_minutes": config.activity_monitoring.check_interval_minutes,
            "idle_threshold_minutes": config.activity_monitoring.idle_threshold_minutes,
            "warning_threshold_hours": config.activity_monitoring.warning_threshold_hours,
            "critical_threshold_hours": config.activity_monitoring.critical_threshold_hours,
            "auto_retire_inactive_hours": config.activity_monitoring.auto_retire_inactive_hours
        },
        "factory": {
            "trend_analysis_days": config.factory.trend_analysis_days,
            "min_confidence_threshold": config.factory.min_confidence_threshold,
            "max_pending_agents": config.factory.max_pending_agents
        }
    }

@router.put("/config")
async def update_config(updates: Dict[str, Any]):
    """Update configuration values."""
    config_path = CONFIG_PATH

    if not config_path.exists():
        raise HTTPException(status_code=404, detail="Config file not found")

    try:
        # Load current config
        with open(config_path) as f:
            current = yaml.safe_load(f) or {}

        # Merge updates
        def deep_merge(base: dict, updates: dict) -> dict:
            for key, value in updates.items():
                if isinstance(value, dict) and key in base and isinstance(base[key], dict):
                    base[key] = deep_merge(base[key], value)
                else:
                    base[key] = value
            return base

        new_config = deep_merge(current, updates)

        # Save updated config
        with open(config_path, 'w') as f:
            yaml.dump(new_config, f, default_flow_style=False, allow_unicode=True)

        # Reload config (invalidate cache)
        from mcn_core import config as config_module
        config_module._config = None

        return {"success": True, "message": "Configuration updated"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
