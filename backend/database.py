"""
PortOrange — Database Layer

Async SQLite connection management, migration runner,
and data access helper functions.
"""

import aiosqlite
import os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typing import Optional

from backend.config import get_config


# ── Database Connection ───────────────────────────────────────

_db: Optional[aiosqlite.Connection] = None


async def get_db() -> aiosqlite.Connection:
    """Get the active database connection."""
    global _db
    if _db is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _db


async def init_db():
    """Initialize database: create file, run migrations."""
    global _db
    config = get_config()
    db_path = Path(config.database.path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    _db = await aiosqlite.connect(str(db_path))
    _db.row_factory = aiosqlite.Row
    await _db.execute("PRAGMA journal_mode=WAL")
    await _db.execute("PRAGMA foreign_keys=ON")

    await _run_migrations(_db)


async def close_db():
    """Close the database connection."""
    global _db
    if _db:
        await _db.close()
        _db = None


# ── Migration Runner ──────────────────────────────────────────

async def _run_migrations(db: aiosqlite.Connection):
    """Run all pending SQL migration files."""
    migrations_dir = Path(__file__).parent / "migrations"
    if not migrations_dir.exists():
        return

    # Ensure schema_migrations table exists
    await db.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     INTEGER PRIMARY KEY,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    await db.commit()

    # Get applied versions
    cursor = await db.execute("SELECT version FROM schema_migrations")
    applied = {row[0] for row in await cursor.fetchall()}

    # Apply pending migrations in order
    migration_files = sorted(migrations_dir.glob("*.sql"))
    for mf in migration_files:
        version = int(mf.stem.split("_")[0])
        if version not in applied:
            sql = mf.read_text()
            await db.executescript(sql)
            await db.commit()
            print(f"  ✓ Applied migration {mf.name}")


# ── Device Operations ─────────────────────────────────────────

async def upsert_device(device_id: str, name: str, host: str,
                        driver_type: str, snmp_community: str = "",
                        snmp_version: str = "2c"):
    """Insert or update a device record."""
    db = await get_db()
    await db.execute("""
        INSERT INTO devices (id, name, host, driver_type, snmp_community, snmp_version)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=excluded.name, host=excluded.host,
            driver_type=excluded.driver_type,
            snmp_community=excluded.snmp_community,
            snmp_version=excluded.snmp_version,
            updated_at=datetime('now')
    """, (device_id, name, host, driver_type, snmp_community, snmp_version))
    await db.commit()


async def update_device_reachability(device_id: str, is_reachable: bool):
    """Update device reachability status after a poll attempt."""
    db = await get_db()
    await db.execute("""
        UPDATE devices SET is_reachable=?, last_polled_at=datetime('now'),
        updated_at=datetime('now') WHERE id=?
    """, (is_reachable, device_id))
    await db.commit()


async def get_all_devices():
    """Get all devices with summary statistics."""
    db = await get_db()
    cursor = await db.execute("""
        SELECT d.*,
            (SELECT COUNT(*) FROM ports WHERE device_id=d.id) as total_ports,
            (SELECT COUNT(*) FROM ports WHERE device_id=d.id AND oper_status='up') as ports_up,
            (SELECT COUNT(*) FROM ports WHERE device_id=d.id AND oper_status='down') as ports_down,
            (SELECT COUNT(*) FROM ports WHERE device_id=d.id AND is_flapping=1) as ports_flapping
        FROM devices d ORDER BY d.name
    """)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# ── Port Operations ───────────────────────────────────────────

async def upsert_port(port_id: str, device_id: str, port_index: int,
                      interface_name: str = "", speed: str = "",
                      oper_status: str = "unknown",
                      criticality: str = "standard"):
    """Insert or update a port record."""
    db = await get_db()
    await db.execute("""
        INSERT INTO ports (id, device_id, port_index, interface_name, speed,
                          oper_status, criticality)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            interface_name=excluded.interface_name,
            speed=excluded.speed,
            oper_status=excluded.oper_status,
            updated_at=datetime('now')
    """, (port_id, device_id, port_index, interface_name, speed,
          oper_status, criticality))
    await db.commit()


async def update_port_status(port_id: str, oper_status: str,
                             is_flapping: bool = False):
    """Update port operational status."""
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    await db.execute("""
        UPDATE ports SET oper_status=?, is_flapping=?, last_change_at=?,
        updated_at=datetime('now') WHERE id=?
    """, (oper_status, is_flapping, now, port_id))
    await db.commit()


async def get_all_ports(device_id: Optional[str] = None,
                        status: Optional[str] = None):
    """Get all ports with optional filtering."""
    db = await get_db()
    query = "SELECT * FROM ports WHERE 1=1"
    params = []

    if device_id:
        query += " AND device_id=?"
        params.append(device_id)
    if status:
        query += " AND oper_status=?"
        params.append(status)

    query += " ORDER BY device_id, port_index"
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_port(port_id: str):
    """Get a single port by ID."""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM ports WHERE id=?", (port_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


# ── Event Operations ──────────────────────────────────────────

async def insert_event(device_id: str, port_id: str, interface_name: str,
                       previous_state: str, current_state: str,
                       timestamp: str, polling_latency_ms: int = 0) -> int:
    """Insert a state change event and return its ID."""
    db = await get_db()
    cursor = await db.execute("""
        INSERT INTO events (device_id, port_id, interface_name,
                           previous_state, current_state, timestamp,
                           polling_latency_ms)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (device_id, port_id, interface_name, previous_state,
          current_state, timestamp, polling_latency_ms))
    await db.commit()
    return cursor.lastrowid


async def get_events_for_port(port_id: str, limit: int = 20):
    """Get recent events for a specific port."""
    db = await get_db()
    cursor = await db.execute("""
        SELECT * FROM events WHERE port_id=?
        ORDER BY timestamp DESC LIMIT ?
    """, (port_id, limit))
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_all_events(limit: int = 50, offset: int = 0):
    """Get global event log with pagination."""
    db = await get_db()
    cursor = await db.execute("""
        SELECT e.*, d.name as device_name
        FROM events e LEFT JOIN devices d ON e.device_id = d.id
        ORDER BY e.timestamp DESC LIMIT ? OFFSET ?
    """, (limit, offset))
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def get_events_24h(port_id: str):
    """Get all events for a port within the last 24 hours."""
    db = await get_db()
    since = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    cursor = await db.execute("""
        SELECT * FROM events WHERE port_id=? AND timestamp >= ?
        ORDER BY timestamp ASC
    """, (port_id, since))
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


# ── Alert Log Operations ─────────────────────────────────────

async def log_alert(event_id: int, channel: str, status: str,
                    message: str = ""):
    """Log an alert dispatch attempt."""
    db = await get_db()
    await db.execute("""
        INSERT INTO alert_log (event_id, channel, status, message)
        VALUES (?, ?, ?, ?)
    """, (event_id, channel, status, message))
    await db.commit()


# ── Stats ─────────────────────────────────────────────────────

async def get_stats():
    """Get aggregate port statistics."""
    db = await get_db()
    cursor = await db.execute("""
        SELECT
            COUNT(*) as total_ports,
            SUM(CASE WHEN oper_status='up' THEN 1 ELSE 0 END) as ports_up,
            SUM(CASE WHEN oper_status='down' THEN 1 ELSE 0 END) as ports_down,
            SUM(CASE WHEN oper_status='unknown' THEN 1 ELSE 0 END) as ports_unknown,
            SUM(CASE WHEN is_flapping=1 THEN 1 ELSE 0 END) as ports_flapping
        FROM ports
    """)
    row = await cursor.fetchone()
    return dict(row) if row else {}


# ── Maintenance Windows ──────────────────────────────────────

async def create_maintenance_window(target_type: str, target_id: str,
                                     start_time: str, end_time: str,
                                     reason: str = ""):
    """Create a maintenance window."""
    db = await get_db()
    await db.execute("""
        INSERT INTO maintenance_windows (target_type, target_id,
                                         start_time, end_time, reason)
        VALUES (?, ?, ?, ?, ?)
    """, (target_type, target_id, start_time, end_time, reason))
    await db.commit()


async def get_active_maintenance_windows():
    """Get currently active maintenance windows."""
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    cursor = await db.execute("""
        SELECT * FROM maintenance_windows
        WHERE start_time <= ? AND end_time >= ?
        ORDER BY start_time
    """, (now, now))
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def is_in_maintenance(target_type: str, target_id: str) -> bool:
    """Check if a device or port is currently in a maintenance window."""
    db = await get_db()
    now = datetime.now(timezone.utc).isoformat()
    cursor = await db.execute("""
        SELECT COUNT(*) FROM maintenance_windows
        WHERE target_type=? AND target_id=?
        AND start_time <= ? AND end_time >= ?
    """, (target_type, target_id, now, now))
    row = await cursor.fetchone()
    return row[0] > 0


# ── Retention Cleanup ─────────────────────────────────────────

async def cleanup_old_events():
    """Delete events older than the configured retention period."""
    config = get_config()
    db = await get_db()
    cutoff = (datetime.now(timezone.utc) -
              timedelta(days=config.database.retention_days)).isoformat()
    await db.execute("DELETE FROM events WHERE timestamp < ?", (cutoff,))
    await db.execute("DELETE FROM alert_log WHERE timestamp < ?", (cutoff,))
    await db.commit()
