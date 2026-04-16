"""
PortOrange — Alert Dispatcher

Routes state-change events to configured notification channels
with suppression, cooldown, and maintenance window support.
"""

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

from backend.config import get_config
from backend.models import StateChange
from backend import database as db
from backend.alerting.console_notifier import console_notifier
from backend.alerting.email_notifier import email_notifier
from backend.alerting.webhook_notifier import webhook_notifier


class AlertDispatcher:
    """
    Alert routing engine with suppression logic.

    Checks cooldown windows, maintenance windows, and flapping status
    before dispatching to active notification channels. Logs all
    dispatch attempts.
    """

    def __init__(self):
        # Cooldown tracker: port_id → last alert timestamp
        self._cooldowns: dict[str, datetime] = {}
        self._lock = asyncio.Lock()

    async def dispatch(self, change: StateChange, event_id: int,
                       device_name: str,
                       criticality: str = "standard"):
        """
        Route a state-change alert to all enabled channels,
        applying suppression rules first.
        """
        config = get_config()

        # Check suppression rules
        suppressed, reason = await self._should_suppress(
            change, criticality
        )

        if suppressed:
            # Log suppressed alert
            await db.log_alert(
                event_id=event_id,
                channel="all",
                status="suppressed",
                message=reason
            )
            return

        # Update cooldown tracker
        async with self._lock:
            self._cooldowns[change.port_id] = datetime.now(timezone.utc)

        # Dispatch to all enabled channels
        channels = config.alerting.channels

        # Console (always fast, fire-and-forget)
        if channels.console.enabled:
            try:
                success = await console_notifier.send(
                    change, device_name, criticality
                )
                await db.log_alert(
                    event_id=event_id,
                    channel="console",
                    status="sent" if success else "failed"
                )
            except Exception as e:
                await db.log_alert(
                    event_id=event_id,
                    channel="console",
                    status="failed",
                    message=str(e)
                )

        # Email (async, non-blocking)
        if channels.email.enabled:
            try:
                success = await email_notifier.send(
                    change, device_name, criticality
                )
                await db.log_alert(
                    event_id=event_id,
                    channel="email",
                    status="sent" if success else "failed"
                )
            except Exception as e:
                await db.log_alert(
                    event_id=event_id,
                    channel="email",
                    status="failed",
                    message=str(e)
                )

        # Webhook (async, non-blocking)
        if channels.webhook.enabled:
            try:
                success = await webhook_notifier.send(
                    change, device_name, criticality
                )
                await db.log_alert(
                    event_id=event_id,
                    channel="webhook",
                    status="sent" if success else "failed"
                )
            except Exception as e:
                await db.log_alert(
                    event_id=event_id,
                    channel="webhook",
                    status="failed",
                    message=str(e)
                )

    async def _should_suppress(self, change: StateChange,
                                criticality: str) -> tuple[bool, str]:
        """
        Check if an alert should be suppressed.
        Returns (should_suppress, reason).
        """
        config = get_config()

        # Rule 1: Monitor-only ports never alert
        if criticality == "monitor-only":
            return True, "monitor-only port"

        # Rule 2: Check cooldown window
        async with self._lock:
            last_alert = self._cooldowns.get(change.port_id)
            if last_alert:
                cooldown = timedelta(
                    seconds=config.alerting.cooldown_seconds
                )
                if datetime.now(timezone.utc) - last_alert < cooldown:
                    return True, f"cooldown active ({config.alerting.cooldown_seconds}s)"

        # Rule 3: Check maintenance windows
        # Check port-level maintenance
        if await db.is_in_maintenance("port", change.port_id):
            return True, "port in maintenance window"

        # Check device-level maintenance
        if await db.is_in_maintenance("device", change.device_id):
            return True, "device in maintenance window"

        # Rule 4: Suppress individual flap alerts (flap detector
        # sends its own consolidated alert)
        if change.is_flapping:
            return True, "flapping — consolidated alert sent"

        return False, ""


# Global singleton
alert_dispatcher = AlertDispatcher()
