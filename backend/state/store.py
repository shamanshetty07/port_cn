"""
PortOrange — In-Memory State Store

Thread-safe state store tracking last known port states.
Detects transitions by comparing new poll results with stored state.
"""

import asyncio
from datetime import datetime, timezone
from typing import Optional
from backend.models import StateChange


class PortState:
    """Stored state for a single port."""
    __slots__ = ('oper_status', 'last_poll_time', 'uptime_since',
                 'interface_name', 'speed')

    def __init__(self, oper_status: str = "unknown",
                 interface_name: str = "", speed: str = ""):
        self.oper_status = oper_status
        self.last_poll_time: Optional[str] = None
        self.uptime_since: Optional[str] = None
        self.interface_name = interface_name
        self.speed = speed


class StateStore:
    """
    In-memory state store keyed by 'device_id:port_index'.

    Compares incoming poll results with stored state to detect
    UP→DOWN, DOWN→UP, and unknown→* transitions.
    """

    def __init__(self):
        self._states: dict[str, PortState] = {}
        self._lock = asyncio.Lock()

    def _key(self, device_id: str, port_index: int) -> str:
        return f"{device_id}:{port_index}"

    async def update_and_detect(
        self,
        device_id: str,
        port_index: int,
        new_status: str,
        interface_name: str = "",
        speed: str = "",
        polling_latency_ms: int = 0
    ) -> Optional[StateChange]:
        """
        Update the stored state for a port and return a StateChange
        if the operational status has changed, or None if unchanged.
        """
        key = self._key(device_id, port_index)
        now = datetime.now(timezone.utc).isoformat()

        async with self._lock:
            if key not in self._states:
                # First time seeing this port — store initial state
                state = PortState(
                    oper_status=new_status,
                    interface_name=interface_name,
                    speed=speed
                )
                state.last_poll_time = now
                if new_status == "up":
                    state.uptime_since = now
                self._states[key] = state

                # Emit an initial "discovery" event if port is not unknown
                if new_status != "unknown":
                    return StateChange(
                        device_id=device_id,
                        port_id=key,
                        port_index=port_index,
                        interface_name=interface_name,
                        previous_state="unknown",
                        current_state=new_status,
                        timestamp=now,
                        polling_latency_ms=polling_latency_ms
                    )
                return None

            state = self._states[key]
            previous = state.oper_status

            # Update metadata
            state.last_poll_time = now
            state.interface_name = interface_name or state.interface_name
            state.speed = speed or state.speed

            if previous == new_status:
                # No change
                return None

            # State has changed!
            state.oper_status = new_status

            if new_status == "up":
                state.uptime_since = now
            elif new_status == "down":
                state.uptime_since = None

            return StateChange(
                device_id=device_id,
                port_id=key,
                port_index=port_index,
                interface_name=interface_name,
                previous_state=previous,
                current_state=new_status,
                timestamp=now,
                polling_latency_ms=polling_latency_ms
            )

    async def get_state(self, device_id: str,
                        port_index: int) -> Optional[PortState]:
        """Get the current stored state for a port."""
        key = self._key(device_id, port_index)
        return self._states.get(key)

    async def get_all_states(self) -> dict[str, PortState]:
        """Get all stored port states."""
        return dict(self._states)

    async def get_uptime_since(self, device_id: str,
                               port_index: int) -> Optional[str]:
        """Get the timestamp since the port was last UP."""
        state = await self.get_state(device_id, port_index)
        if state and state.oper_status == "up":
            return state.uptime_since
        return None


# Global singleton
state_store = StateStore()
