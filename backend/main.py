"""
PortOrange — FastAPI Application Entry Point

Creates the FastAPI app, mounts static files, initializes DB,
starts the polling engine on startup, and shuts down gracefully.
"""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.config import load_config, get_config
from backend.database import init_db, close_db
from backend.polling.engine import polling_engine
from backend.api.routes import router as api_router
from backend.api.websocket import ws_manager


# ── Lifespan (startup / shutdown) ────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: init DB + start polling on startup."""
    print("\n" + "═" * 56)
    print("  🍊 PortOrange — Port Status Monitor v2.0")
    print("═" * 56)

    # Load configuration
    config = load_config("config.yaml")
    print(f"\n✓ Config loaded ({len(config.devices)} devices)")

    # Initialize database
    await init_db()
    print("✓ Database initialized")

    # Start polling engine
    await polling_engine.start()

    print(f"\n🌐 Dashboard: http://localhost:{config.server.port}")
    print(f"📡 API:       http://localhost:{config.server.port}/api")
    print(f"🔌 WebSocket: ws://localhost:{config.server.port}/ws/live")
    print("═" * 56 + "\n")

    yield

    # Shutdown
    print("\n🛑 Shutting down...")
    await polling_engine.stop()
    await close_db()
    print("✓ Cleanup complete\n")


# ── App Creation ──────────────────────────────────────────────

app = FastAPI(
    title="PortOrange",
    description="Port Status Monitoring Tool",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Include API routes
app.include_router(api_router)

# Mount static frontend files
frontend_dir = Path(__file__).parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)),
              name="static")


# ── WebSocket Endpoint ───────────────────────────────────────

@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time dashboard updates."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive, listen for client messages
            data = await websocket.receive_text()
            # Currently no client→server messages needed
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception:
        await ws_manager.disconnect(websocket)


# ── Dashboard Route ──────────────────────────────────────────

@app.get("/")
async def serve_dashboard():
    """Serve the main dashboard HTML page."""
    index_path = frontend_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return {"message": "PortOrange API v2.0 — Frontend not found"}
