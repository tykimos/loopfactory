"""Configuration loader for LoopFactory."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple, Optional
import yaml

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"

@dataclass
class SystemConfig:
    max_concurrent_agents: str = "auto"
    cpu_threshold_high: int = 85
    cpu_threshold_low: int = 70
    memory_limit_per_agent_mb: int = 256

@dataclass
class LoopConfig:
    skill_url: str = "https://assibucks.vercel.app/skill.md"
    execution_timeout: int = 300
    max_retries: int = 3

@dataclass
class SchedulingConfig:
    base_interval_minutes: int = 60
    jitter_minutes: int = 8
    peak_hours: List[Tuple[int, int]] = field(default_factory=lambda: [(9, 11), (20, 22)])

@dataclass
class ActivationConfig:
    check_interval_seconds: int = 30
    max_pending_hours: int = 12

@dataclass
class LifecycleConfig:
    probation_trigger_days: int = 4
    probation_trigger_growth: int = 0
    probation_duration_hours: int = 48
    auto_retire: bool = True
    auto_create_replacement: bool = True

@dataclass
class BucksMonitoringConfig:
    observation_period_days: int = 4
    min_growth_threshold: int = 10
    grace_period_hours: int = 48

@dataclass
class ReactivationPromptsConfig:
    enabled: bool = True
    max_prompts_per_6h: int = 3
    cooldown_minutes: int = 60

@dataclass
class ProtectionConfig:
    high_bucks_threshold: int = 1000
    high_follower_threshold: int = 50

@dataclass
class ActivityMonitoringConfig:
    check_interval_minutes: int = 10
    idle_threshold_minutes: int = 90
    warning_threshold_hours: int = 3
    critical_threshold_hours: int = 6
    auto_retire_inactive_hours: int = 18
    bucks_monitoring: BucksMonitoringConfig = field(default_factory=BucksMonitoringConfig)
    reactivation_prompts: ReactivationPromptsConfig = field(default_factory=ReactivationPromptsConfig)
    protection: ProtectionConfig = field(default_factory=ProtectionConfig)

@dataclass
class FactoryConfig:
    trend_analysis_days: int = 2
    min_confidence_threshold: float = 0.6
    max_pending_agents: int = 5

@dataclass
class DashboardConfig:
    port: int = 3000
    api_port: int = 8000

@dataclass
class Config:
    system: SystemConfig = field(default_factory=SystemConfig)
    loop: LoopConfig = field(default_factory=LoopConfig)
    scheduling: SchedulingConfig = field(default_factory=SchedulingConfig)
    activation: ActivationConfig = field(default_factory=ActivationConfig)
    lifecycle: LifecycleConfig = field(default_factory=LifecycleConfig)
    activity_monitoring: ActivityMonitoringConfig = field(default_factory=ActivityMonitoringConfig)
    factory: FactoryConfig = field(default_factory=FactoryConfig)
    dashboard: DashboardConfig = field(default_factory=DashboardConfig)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "Config":
        config_path = path or CONFIG_PATH
        if not config_path.exists():
            return cls()

        with open(config_path) as f:
            data = yaml.safe_load(f)

        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict) -> "Config":
        config = cls()

        if "system" in data:
            config.system = SystemConfig(**data["system"])
        if "loop" in data:
            config.loop = LoopConfig(**data["loop"])
        if "scheduling" in data:
            sched_data = data["scheduling"]
            config.scheduling = SchedulingConfig(
                base_interval_minutes=sched_data.get("base_interval_minutes", 60),
                jitter_minutes=sched_data.get("jitter_minutes", 8),
                peak_hours=[tuple(h) for h in sched_data.get("peak_hours", [(9, 11), (20, 22)])]
            )
        if "activation" in data:
            config.activation = ActivationConfig(**data["activation"])
        if "lifecycle" in data:
            config.lifecycle = LifecycleConfig(**data["lifecycle"])
        if "activity_monitoring" in data:
            am_data = data["activity_monitoring"]
            bm = BucksMonitoringConfig(**am_data.get("bucks_monitoring", {}))
            rp = ReactivationPromptsConfig(**am_data.get("reactivation_prompts", {}))
            prot = ProtectionConfig(**am_data.get("protection", {}))
            config.activity_monitoring = ActivityMonitoringConfig(
                check_interval_minutes=am_data.get("check_interval_minutes", 10),
                idle_threshold_minutes=am_data.get("idle_threshold_minutes", 90),
                warning_threshold_hours=am_data.get("warning_threshold_hours", 3),
                critical_threshold_hours=am_data.get("critical_threshold_hours", 6),
                auto_retire_inactive_hours=am_data.get("auto_retire_inactive_hours", 18),
                bucks_monitoring=bm,
                reactivation_prompts=rp,
                protection=prot
            )
        if "factory" in data:
            config.factory = FactoryConfig(**data["factory"])
        if "dashboard" in data:
            config.dashboard = DashboardConfig(**data["dashboard"])

        return config

# Global config instance
_config: Optional[Config] = None

def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config.load()
    return _config
