"""
PortOrange — Configuration Loader

Reads config.yaml, resolves environment variable references,
and validates all settings via Pydantic models.
"""

import os
import re
import yaml
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


# ── Config Models ─────────────────────────────────────────────

class PollingConfig(BaseModel):
    interval_seconds: int = 15
    timeout_seconds: int = 10
    retries: int = 2


class DatabaseConfig(BaseModel):
    path: str = "data/portorange.db"
    retention_days: int = 90


class FlapDetectionConfig(BaseModel):
    enabled: bool = True
    threshold: int = 5
    window_seconds: int = 60
    stability_multiplier: int = 2


class ConsoleChannelConfig(BaseModel):
    enabled: bool = True


class EmailChannelConfig(BaseModel):
    enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    from_address: str = ""
    to_addresses: list[str] = Field(default_factory=list)


class WebhookChannelConfig(BaseModel):
    enabled: bool = False
    url: str = ""
    type: str = "slack"  # slack | teams | pagerduty


class AlertChannelsConfig(BaseModel):
    console: ConsoleChannelConfig = Field(default_factory=ConsoleChannelConfig)
    email: EmailChannelConfig = Field(default_factory=EmailChannelConfig)
    webhook: WebhookChannelConfig = Field(default_factory=WebhookChannelConfig)


class AlertingConfig(BaseModel):
    cooldown_seconds: int = 300
    channels: AlertChannelsConfig = Field(default_factory=AlertChannelsConfig)


class DeviceConfig(BaseModel):
    id: str
    name: str
    host: str
    driver: str = "simulated"  # snmp | simulated
    snmp_community: str = "public"
    snmp_version: str = "2c"
    port_count: int = 24
    port_criticality: dict[int, str] = Field(default_factory=dict)


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    dashboard_url: str = "http://localhost:8000"


class AppConfig(BaseModel):
    polling: PollingConfig = Field(default_factory=PollingConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    flap_detection: FlapDetectionConfig = Field(default_factory=FlapDetectionConfig)
    alerting: AlertingConfig = Field(default_factory=AlertingConfig)
    devices: list[DeviceConfig] = Field(default_factory=list)
    server: ServerConfig = Field(default_factory=ServerConfig)


# ── Environment Variable Resolution ──────────────────────────

_ENV_PATTERN = re.compile(r'\$\{([^}]+)\}')


def _resolve_env_vars(value):
    """Recursively resolve ${ENV_VAR} references in config values."""
    if isinstance(value, str):
        def _replace(match):
            env_key = match.group(1)
            return os.environ.get(env_key, match.group(0))
        return _ENV_PATTERN.sub(_replace, value)
    elif isinstance(value, dict):
        return {k: _resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [_resolve_env_vars(item) for item in value]
    return value


# ── Config Singleton ──────────────────────────────────────────

_config: Optional[AppConfig] = None


def load_config(config_path: str = "config.yaml") -> AppConfig:
    """Load and validate configuration from YAML file."""
    global _config

    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path, "r") as f:
        raw = yaml.safe_load(f)

    resolved = _resolve_env_vars(raw)
    _config = AppConfig(**resolved)
    return _config


def get_config() -> AppConfig:
    """Get the loaded configuration. Call load_config() first."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
