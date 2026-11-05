from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

from .paths import config_dir


@dataclass
class Config:
    db: str = ""
    ntfy_server: str = "https://ntfy.sh"
    ntfy_topic: str = ""
    ntfy_token: str = ""
    ntfy_enabled: bool = True
    calls_enabled: bool = False
    cloud_enabled: bool = False
    quiet_enabled: bool = True
    quiet_start: str = "22:00"
    quiet_end: str = "07:00"
    debounce_seconds: float = 2
    max_wait_seconds: float = 8
    long_task_minutes: float = 10
    urgent_cooldown_minutes: float = 15
    retention_days: int = 7
    nvidia_api_key: str = ""
    nvidia_base_url: str = ""
    nvidia_model: str = ""
    openrouter_api_key: str = ""
    openrouter_model: str = ""
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_from: str = ""
    to_number: str = ""
    twilio_region: str = ""
    calls_on_failure: bool = True
    calls_on_permission: bool = True
    calls_on_long_task: bool = False
    max_retry_attempts: int = 5


def load_config(path: Path | None = None) -> Config:
    data: dict = {}
    p = path or (config_dir() / "jesko.toml")
    try:
        if p.exists():
            with p.open("rb") as f:
                data = tomllib.load(f)
    except OSError:
        data = {}

    def get(section: str, key: str, default):
        return data.get(section, {}).get(key, default)

    c = Config(
        ntfy_server=get("ntfy", "server", "https://ntfy.sh"),
        ntfy_topic=get("ntfy", "topic", ""),
        ntfy_token=get("ntfy", "token", ""),
        ntfy_enabled=get("ntfy", "enabled", True),
        calls_enabled=get("twilio", "enabled", False),
        cloud_enabled=get("summarization", "enabled", False),
        quiet_enabled=get("quiet_hours", "enabled", True),
        quiet_start=get("quiet_hours", "start", "22:00"),
        quiet_end=get("quiet_hours", "end", "07:00"),
        debounce_seconds=get("batching", "debounce_seconds", 2),
        max_wait_seconds=get("batching", "max_wait_seconds", 8),
        long_task_minutes=get("policy", "long_task_threshold_minutes", 10),
        urgent_cooldown_minutes=get("policy", "urgent_cooldown_minutes", 15),
        retention_days=get("app", "retention_days", 7),
    )
    env = {
        "ntfy_topic": "JESKO_NTFY_TOPIC",
        "ntfy_token": "JESKO_NTFY_TOKEN",
        "calls_enabled": "JESKO_CALLS_ENABLED",
        "cloud_enabled": "JESKO_CLOUD_SUMMARIZATION_ENABLED",
        "nvidia_api_key": "JESKO_NVIDIA_API_KEY",
        "nvidia_base_url": "JESKO_NVIDIA_BASE_URL",
        "nvidia_model": "JESKO_NVIDIA_MODEL",
        "openrouter_api_key": "JESKO_OPENROUTER_API_KEY",
        "openrouter_model": "JESKO_OPENROUTER_MODEL",
        "twilio_sid": "TWILIO_ACCOUNT_SID",
        "twilio_token": "TWILIO_AUTH_TOKEN",
        "twilio_from": "TWILIO_FROM_NUMBER",
        "to_number": "JESKO_TO_NUMBER",
        "twilio_region": "JESKO_TWILIO_REGION",
    }
    for field, name in env.items():
        if name in os.environ:
            v = os.environ[name]
            setattr(c, field, v.lower() == "true" if field.endswith("enabled") else v)
    return c
