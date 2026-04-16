"""
PortOrange — Async Polling Engine

Orchestrates device polling by spawning one asyncio task per device.
Each task runs a poll loop at the configured interval, detects state
transitions via the state store, and dispatches alerts + DB writes.
"""

import asyncio
import traceback
from datetime import datetime, timezone
from typing import Optional

from backend.config import get_config, DeviceConfig
from backend.models import PortPollResult, StateChange
from backend.state.store import state_store
from backend.state.flap_detector import flap_detector
from backend import database as db
from backend.alerting.dispatcher import alert_dispatcher
from backend.api.websocket import ws_manager


class PollingEngine:
    """
    Async polling orchestrator.

    Spawns one asyncio.Task per device in the config. Each task
    independently polls its device, detects transitions, persists
    events, and dispatches alerts.
    """

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}
        self._running = False

    async def start(self):
        """Start polling all configured devices."""
        config = get_config()
        self._running = True

        print("\n🔄 Starting polling engine...")
        print(f"   Polling interval: {config.polling.interval_seconds}s")
        print(f"   Devices: {len(config.devices)}\n")

        for device_cfg in config.devices:
            # Register device in database
            await db.upsert_device(
                device_id=device_cfg.id,
                name=device_cfg.name,
                host=device_cfg.host,
                driver_type=device_cfg.driver,
                snmp_community=device_cfg.snmp_community,
                snmp_version=device_cfg.snmp_version
            )

            # Spawn polling task
            task = asyncio.create_task(
                self._poll_device_loop(device_cfg),
                name=f"poll-{device_cfg.id}"
            )
            self._tasks[device_cfg.id] = task
            print(f"   ✓ Started polling: {device_cfg.name} "
                  f"({device_cfg.host}) [{device_cfg.driver}]")

    async def stop(self):
        """Stop all polling tasks gracefully."""
        self._running = False
        for device_id, task in self._tasks.items():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        print("\n⏹ Polling engine stopped.")

    def _create_driver(self, device_cfg: DeviceConfig):
        """Create the appropriate driver for a device."""
        if device_cfg.driver == "simulated":
            from backend.polling.simulated_driver import SimulatedDriver
            return SimulatedDriver(
                device_id=device_cfg.id,
                port_count=device_cfg.port_count
            )
        else:
            from backend.polling.snmp_driver import SNMPDriver
            return SNMPDriver(
                device_id=device_cfg.id,
                host=device_cfg.host,
                community=device_cfg.snmp_community,
                version=device_cfg.snmp_version,
                timeout=get_config().polling.timeout_seconds,
                retries=get_config().polling.retries
            )

    async def _poll_device_loop(self, device_cfg: DeviceConfig):
        """
        Main polling loop for a single device.
        Runs until cancelled or self._running is False.
        """
        config = get_config()
        driver = self._create_driver(device_cfg)
        interval = config.polling.interval_seconds

        while self._running:
            try:
                # Poll the device
                results = await driver.poll()

                if results:
                    await db.update_device_reachability(device_cfg.id, True)
                    await self._process_poll_results(device_cfg, results)
                else:
                    await db.update_device_reachability(device_cfg.id, False)

                # Check flap stability for all ports
                for result in results:
                    await flap_detector.check_stability(
                        device_cfg.id, result.port_index
                    )

            except asyncio.CancelledError:
                raise
            except Exception as e:
                print(f"  ⚠ Poll error ({device_cfg.id}): {e}")
                traceback.print_exc()
                await db.update_device_reachability(device_cfg.id, False)

            # Wait for next poll cycle
            try:
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                raise

    async def _process_poll_results(self, device_cfg: DeviceConfig,
                                     results: list[PortPollResult]):
        """Process poll results: detect transitions, persist, alert."""
        config = get_config()

        for result in results:
            port_id = f"{device_cfg.id}:{result.port_index}"

            # Determine port criticality
            criticality = device_cfg.port_criticality.get(
                result.port_index, "standard"
            )

            # Upsert port in database
            await db.upsert_port(
                port_id=port_id,
                device_id=device_cfg.id,
                port_index=result.port_index,
                interface_name=result.interface_name,
                speed=result.speed,
                oper_status=result.oper_status,
                criticality=criticality
            )

            # Check for state change
            change = await state_store.update_and_detect(
                device_id=device_cfg.id,
                port_index=result.port_index,
                new_status=result.oper_status,
                interface_name=result.interface_name,
                speed=result.speed,
                polling_latency_ms=result.polling_latency_ms
            )

            if change:
                # Record transition for flap detection
                is_flapping = await flap_detector.record_transition(
                    device_cfg.id, result.port_index
                )
                change.is_flapping = is_flapping

                # Update port flapping status in DB
                await db.update_port_status(
                    port_id=port_id,
                    oper_status=result.oper_status,
                    is_flapping=is_flapping
                )

                # Persist event to database
                event_id = await db.insert_event(
                    device_id=device_cfg.id,
                    port_id=port_id,
                    interface_name=result.interface_name,
                    previous_state=change.previous_state,
                    current_state=change.current_state,
                    timestamp=change.timestamp,
                    polling_latency_ms=result.polling_latency_ms
                )

                # Broadcast to WebSocket clients
                await ws_manager.broadcast({
                    "type": "state_change",
                    "data": {
                        "device_id": device_cfg.id,
                        "device_name": device_cfg.name,
                        "port_id": port_id,
                        "port_index": result.port_index,
                        "interface_name": result.interface_name,
                        "previous_state": change.previous_state,
                        "current_state": change.current_state,
                        "timestamp": change.timestamp,
                        "is_flapping": is_flapping,
                        "criticality": criticality
                    }
                })

                # Dispatch alert
                await alert_dispatcher.dispatch(
                    change=change,
                    event_id=event_id,
                    device_name=device_cfg.name,
                    criticality=criticality
                )

        # Broadcast stats update
        stats = await db.get_stats()
        await ws_manager.broadcast({
            "type": "stats_update",
            "data": stats
        })


# Global singleton
polling_engine = PollingEngine()
