"""
PortOrange — REST API Routes

Endpoints for devices, ports, events, stats, and maintenance windows.
"""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException

from backend import database as db
from backend.models import (
    DeviceResponse, PortResponse, EventResponse,
    StatsResponse, MaintenanceWindowRequest, MaintenanceWindowResponse
)
from backend.state.store import state_store

router = APIRouter(prefix="/api", tags=["api"])


# ── Devices ───────────────────────────────────────────────────

@router.get("/devices")
async def list_devices():
    """List all devices with summary port statistics."""
    devices = await db.get_all_devices()
    return {"devices": devices}


# ── Ports ─────────────────────────────────────────────────────

@router.get("/ports")
async def list_ports(
    device_id: Optional[str] = Query(None, description="Filter by device ID"),
    status: Optional[str] = Query(None, description="Filter by oper_status")
):
    """List all ports with optional filtering by device and status."""
    ports = await db.get_all_ports(device_id=device_id, status=status)

    # Enrich with uptime info from state store
    for port in ports:
        parts = port["id"].split(":")
        if len(parts) == 2:
            uptime = await state_store.get_uptime_since(
                parts[0], int(parts[1])
            )
            port["uptime_since"] = uptime

    return {"ports": ports}


@router.get("/ports/{port_id:path}/events")
async def get_port_events(
    port_id: str,
    limit: int = Query(20, ge=1, le=100)
):
    """Get recent state-change events for a specific port."""
    events = await db.get_events_for_port(port_id, limit=limit)
    return {"events": events, "port_id": port_id}


@router.get("/ports/{port_id:path}/events/24h")
async def get_port_events_24h(port_id: str):
    """Get all events for a port within the last 24 hours."""
    events = await db.get_events_24h(port_id)
    return {"events": events, "port_id": port_id}


@router.get("/ports/{port_id:path}")
async def get_port(port_id: str):
    """Get detailed information for a single port."""
    port = await db.get_port(port_id)
    if not port:
        raise HTTPException(status_code=404, detail="Port not found")

    # Add uptime info
    parts = port_id.split(":")
    if len(parts) == 2:
        uptime = await state_store.get_uptime_since(parts[0], int(parts[1]))
        port["uptime_since"] = uptime

    return port


# ── Events ────────────────────────────────────────────────────

@router.get("/events")
async def list_events(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0)
):
    """Get global event log with pagination."""
    events = await db.get_all_events(limit=limit, offset=offset)
    return {"events": events, "limit": limit, "offset": offset}


# ── Stats ─────────────────────────────────────────────────────

@router.get("/stats")
async def get_stats():
    """Get aggregate port statistics across all devices."""
    stats = await db.get_stats()
    devices = await db.get_all_devices()

    stats["total_devices"] = len(devices)
    stats["devices_reachable"] = sum(
        1 for d in devices if d.get("is_reachable")
    )

    return stats


# ── Maintenance Windows ──────────────────────────────────────

@router.post("/maintenance")
async def create_maintenance_window(request: MaintenanceWindowRequest):
    """Create a new maintenance window to suppress alerts."""
    await db.create_maintenance_window(
        target_type=request.target_type,
        target_id=request.target_id,
        start_time=request.start_time,
        end_time=request.end_time,
        reason=request.reason
    )
    return {"status": "created", "message": "Maintenance window created"}


@router.get("/maintenance")
async def list_maintenance_windows():
    """List active and upcoming maintenance windows."""
    windows = await db.get_active_maintenance_windows()
    return {"maintenance_windows": windows}
