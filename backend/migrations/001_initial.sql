-- ═══════════════════════════════════════════════════════════════
-- PortOrange — Initial Database Schema (Migration 001)
-- ═══════════════════════════════════════════════════════════════

-- Migration tracking table
CREATE TABLE IF NOT EXISTS schema_migrations (
    version     INTEGER PRIMARY KEY,
    applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Devices table
CREATE TABLE IF NOT EXISTS devices (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    host            TEXT NOT NULL,
    driver_type     TEXT NOT NULL DEFAULT 'snmp',
    snmp_community  TEXT,
    snmp_version    TEXT DEFAULT '2c',
    is_reachable    BOOLEAN DEFAULT 1,
    last_polled_at  TEXT,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Ports table
CREATE TABLE IF NOT EXISTS ports (
    id              TEXT PRIMARY KEY,
    device_id       TEXT NOT NULL REFERENCES devices(id),
    port_index      INTEGER NOT NULL,
    interface_name  TEXT,
    speed           TEXT,
    admin_status    TEXT DEFAULT 'up',
    oper_status     TEXT DEFAULT 'unknown',
    last_change_at  TEXT,
    is_flapping     BOOLEAN DEFAULT 0,
    criticality     TEXT DEFAULT 'standard',
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Events table (state transitions)
CREATE TABLE IF NOT EXISTS events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id           TEXT NOT NULL,
    port_id             TEXT NOT NULL,
    interface_name      TEXT,
    previous_state      TEXT NOT NULL,
    current_state       TEXT NOT NULL,
    timestamp           TEXT NOT NULL,
    polling_latency_ms  INTEGER,
    FOREIGN KEY (port_id) REFERENCES ports(id)
);

-- Alert log table
CREATE TABLE IF NOT EXISTS alert_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id    INTEGER REFERENCES events(id),
    channel     TEXT NOT NULL,
    status      TEXT NOT NULL,
    message     TEXT,
    timestamp   TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Maintenance windows table
CREATE TABLE IF NOT EXISTS maintenance_windows (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    target_type TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    start_time  TEXT NOT NULL,
    end_time    TEXT NOT NULL,
    reason      TEXT,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_ports_device_id ON ports(device_id);
CREATE INDEX IF NOT EXISTS idx_events_port_id ON events(port_id);
CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_device_id ON events(device_id);
CREATE INDEX IF NOT EXISTS idx_alert_log_event_id ON alert_log(event_id);
CREATE INDEX IF NOT EXISTS idx_maintenance_target ON maintenance_windows(target_type, target_id);

-- Mark migration as applied
INSERT OR IGNORE INTO schema_migrations (version) VALUES (1);
