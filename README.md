# PortOrange — Port Status Monitoring Tool v2.0

🍊 A lightweight, self-hosted network port monitoring tool providing real-time visibility into switch port states, structured event logging, and multi-channel alerting.

![Version](https://img.shields.io/badge/version-2.0-orange)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Features

- **Real-Time Port Polling** — Configurable async polling engine (default 15s)
- **State-Change Detection** — Efficient diff-based transition detection
- **Flap Detection** — Sliding-window algorithm catches port flapping
- **Live Dashboard** — Dark glassmorphism SPA with WebSocket updates
- **Port Detail View** — Click any port for history, timeline chart, and metadata
- **Multi-Channel Alerts** — Console (color-coded), Email (SMTP), Webhooks (Slack/Teams/PagerDuty)
- **Alert Suppression** — Cooldown windows, maintenance scheduling, flap throttling
- **Simulated Mode** — Demo without real hardware using realistic simulated switches

## Quick Start

### Prerequisites

- Python 3.11+
- pip

### 1. Install Dependencies

```bash
cd portorange
pip install -r requirements.txt
```

### 2. Configure

Edit `config.yaml` to customize:
- **Device inventory** — Add your switches or use simulated devices
- **Polling interval** — Default 15 seconds
- **Alert channels** — Enable console, email, or webhooks
- **Flap detection** — Threshold and window settings

For simulated mode (no real hardware needed):
```yaml
devices:
  - id: "sw-core-01"
    name: "Core Switch 01"
    host: "192.168.1.1"
    driver: "simulated"    # ← Use simulated driver
    port_count: 24
```

### 3. Run

```bash
python -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. Open Dashboard

Navigate to **http://localhost:8000** in your browser.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  Layer 5: Frontend (Vanilla JS SPA)                 │
│  Port grid · Detail panel · Sparkline charts        │
├─────────────────────────────────────────────────────┤
│  Layer 4: API (FastAPI REST + WebSocket)             │
│  /api/ports · /api/events · /ws/live                │
├─────────────────────────────────────────────────────┤
│  Layer 3: Persistence (SQLite)                       │
│  devices · ports · events · alert_log               │
├─────────────────────────────────────────────────────┤
│  Layer 2: State Engine                               │
│  In-memory store · Flap detector                    │
├─────────────────────────────────────────────────────┤
│  Layer 1: Data Collection                            │
│  SNMP Driver · Simulated Driver · Async workers     │
└─────────────────────────────────────────────────────┘
```

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/devices` | List all devices with stats |
| GET | `/api/ports` | All ports (filter: `?device_id=&status=`) |
| GET | `/api/ports/{id}` | Single port detail |
| GET | `/api/ports/{id}/events` | Port event history |
| GET | `/api/ports/{id}/events/24h` | Last 24h events |
| GET | `/api/events` | Global event log |
| GET | `/api/stats` | Aggregate statistics |
| POST | `/api/maintenance` | Create maintenance window |
| GET | `/api/maintenance` | List maintenance windows |
| WS | `/ws/live` | Real-time WebSocket feed |

## Configuration Reference

All settings live in `config.yaml`. Secrets can reference environment variables:

```yaml
alerting:
  channels:
    email:
      smtp_password: "${SMTP_PASSWORD}"  # Reads from env
```

## Project Structure

```
portorange/
├── config.yaml              # Configuration
├── requirements.txt         # Python dependencies
├── backend/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Config loader
│   ├── database.py          # SQLite layer
│   ├── models.py            # Pydantic models
│   ├── polling/
│   │   ├── engine.py        # Async polling orchestrator
│   │   ├── snmp_driver.py   # Real SNMP driver
│   │   └── simulated_driver.py
│   ├── state/
│   │   ├── store.py         # In-memory state store
│   │   └── flap_detector.py
│   ├── alerting/
│   │   ├── dispatcher.py    # Alert routing
│   │   ├── console_notifier.py
│   │   ├── email_notifier.py
│   │   └── webhook_notifier.py
│   ├── api/
│   │   ├── routes.py        # REST endpoints
│   │   └── websocket.py     # WebSocket manager
│   └── migrations/
│       └── 001_initial.sql  # Database schema
└── frontend/
    ├── index.html           # Dashboard SPA
    ├── css/style.css        # Design system
    └── js/
        ├── app.js           # App controller
        ├── api.js           # API client
        ├── dashboard.js     # Port grid
        ├── detail.js        # Detail panel
        └── charts.js        # Sparkline charts
```

## License

MIT
