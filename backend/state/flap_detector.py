"""
PortOrange — Flap Detection Algorithm

Tracks transition counts per port in a sliding time window.
A port is marked as "flapping" when it exceeds the configured
threshold of transitions within the window.
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Optional
from backend.config import get_config


class FlapRecord:
    """Transition history for a single port."""
    __slots__ = ('transitions', 'is_flapping', 'flapping_since',
                 'last_stable_at')

    def __init__(self):
        self.transitions: list[datetime] = []
        self.is_flapping: bool = False
        self.flapping_since: Optional[datetime] = None
        self.last_stable_at: Optional[datetime] = None


class FlapDetector:
    """
    Sliding-window flap detector.

    Counts state transitions per port within a configurable time window.
    When the count exceeds the threshold, the port is flagged as flapping.
    The flag clears after a stability period (no transitions for
    stability_multiplier × window).
    """

    def __init__(self):
        self._records: dict[str, FlapRecord] = defaultdict(FlapRecord)
        self._lock = asyncio.Lock()

    def _key(self, device_id: str, port_index: int) -> str:
        return f"{device_id}:{port_index}"

    async def record_transition(self, device_id: str,
                                port_index: int) -> bool:
        """
        Record a state transition for a port.
        Returns True if the port is now flapping, False otherwise.
        """
        config = get_config()
        flap_cfg = config.flap_detection

        if not flap_cfg.enabled:
            return False

        key = self._key(device_id, port_index)
        now = datetime.now(timezone.utc)
        window = timedelta(seconds=flap_cfg.window_seconds)

        async with self._lock:
            record = self._records[key]

            # Add this transition
            record.transitions.append(now)

            # Prune transitions outside the sliding window
            cutoff = now - window
            record.transitions = [
                t for t in record.transitions if t >= cutoff
            ]

            # Check if we've exceeded the threshold
            if len(record.transitions) >= flap_cfg.threshold:
                if not record.is_flapping:
                    record.is_flapping = True
                    record.flapping_since = now
                    print(f"  ⚡ Flap detected: {key} "
                          f"({len(record.transitions)} transitions in "
                          f"{flap_cfg.window_seconds}s)")
                return True

            return record.is_flapping

    async def check_stability(self, device_id: str,
                              port_index: int) -> bool:
        """
        Check if a flapping port has stabilized.
        Returns True if the port WAS flapping but is now stable.
        """
        config = get_config()
        flap_cfg = config.flap_detection

        if not flap_cfg.enabled:
            return False

        key = self._key(device_id, port_index)
        now = datetime.now(timezone.utc)
        stability_window = timedelta(
            seconds=flap_cfg.window_seconds * flap_cfg.stability_multiplier
        )

        async with self._lock:
            record = self._records.get(key)
            if not record or not record.is_flapping:
                return False

            # Check if no recent transitions
            cutoff = now - stability_window
            recent = [t for t in record.transitions if t >= cutoff]

            if len(recent) < 2:  # Effectively stable
                record.is_flapping = False
                record.last_stable_at = now
                record.transitions.clear()
                print(f"  ✓ Flap resolved: {key}")
                return True

            return False

    async def is_flapping(self, device_id: str,
                          port_index: int) -> bool:
        """Check if a port is currently flagged as flapping."""
        key = self._key(device_id, port_index)
        record = self._records.get(key)
        return record.is_flapping if record else False


# Global singleton
flap_detector = FlapDetector()
