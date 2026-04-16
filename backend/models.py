"""
PortOrange — Pydantic Models

Request/response models for the REST API and internal data transfer.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ── Internal Data Transfer ────────────────────────────────────

class PortPollResult(BaseModel):
    """Result from polling a single port."""
    port_index: int
    interface_name: str = ""
    speed: str = ""
    oper_status: str = "unknown"  # up | down | unknown
    polling_latency_ms: int = 0


class StateChange(BaseModel):
    """Detected state transition for a port."""
    device_id: str
    port_id: str
    port_index: int
    interface_name: str
    previous_state: str
    current_state: str
    timestamp: str
    polling_latency_ms: int = 0
    is_flapping: bool = False


# ── API Response Models ───────────────────────────────────────

class DeviceResponse(BaseModel):
    id: str
    name: str
    host: str
    driver_type: str
    is_reachable: Optional[bool] = True
    last_polled_at: Optional[str] = None
    total_ports: int = 0
    ports_up: int = 0
    ports_down: int = 0
    ports_flapping: int = 0


class PortResponse(BaseModel):
    id: str
    device_id: str
    port_index: int
    interface_name: Optional[str] = ""
    speed: Optional[str] = ""
    admin_status: Optional[str] = "up"
    oper_status: str = "unknown"
    last_change_at: Optional[str] = None
    is_flapping: bool = False
    criticality: str = "standard"


class EventResponse(BaseModel):
    id: int
    device_id: str
    port_id: str
    interface_name: Optional[str] = ""
    previous_state: str
    current_state: str
    timestamp: str
    polling_latency_ms: Optional[int] = 0
    device_name: Optional[str] = None


class StatsResponse(BaseModel):
    total_ports: int = 0
    ports_up: int = 0
    ports_down: int = 0
    ports_unknown: int = 0
    ports_flapping: int = 0
    total_devices: int = 0
    devices_reachable: int = 0


class MaintenanceWindowRequest(BaseModel):
    target_type: str  # device | port
    target_id: str
    start_time: str   # ISO 8601
    end_time: str     # ISO 8601
    reason: str = ""


class MaintenanceWindowResponse(BaseModel):
    id: int
    target_type: str
    target_id: str
    start_time: str
    end_time: str
    reason: str = ""
    created_at: str


# ── WebSocket Message Models ─────────────────────────────────

class WSMessage(BaseModel):
    type: str  # state_change | stats_update | device_status
    data: dict = Field(default_factory=dict)
