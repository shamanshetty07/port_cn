"""
PortOrange — Simulated Device Driver

Generates realistic port state transitions for development and demo.
Produces random UP/DOWN flips with configurable probability,
simulates flapping on select ports, and adds realistic latency jitter.
"""

import asyncio
import random
from typing import Optional
from backend.models import PortPollResult


class SimulatedDriver:
    """
    Simulated SNMP-like driver for testing without real hardware.

    On first poll, initializes all ports to UP. Subsequent polls
    randomly transition ports with a configurable probability.
    One or two ports are designated as "flappers" with higher
    transition probability to test flap detection.
    """

    def __init__(self, device_id: str, port_count: int = 24):
        self.device_id = device_id
        self.port_count = port_count
        self._port_states: dict[int, str] = {}
        self._flap_ports: set[int] = set()
        self._initialized = False

    def _initialize(self):
        """Set up initial port states and designate flap ports."""
        for i in range(1, self.port_count + 1):
            # Most ports start UP, a few start DOWN
            self._port_states[i] = "up" if random.random() > 0.1 else "down"

        # Designate 1-2 ports as flappers
        flap_count = min(2, max(1, self.port_count // 12))
        self._flap_ports = set(
            random.sample(range(1, self.port_count + 1), flap_count)
        )
        self._initialized = True

    async def poll(self) -> list[PortPollResult]:
        """
        Simulate polling all ports on the device.
        Returns a list of PortPollResult with current states.
        """
        if not self._initialized:
            self._initialize()

        # Simulate network latency
        latency = random.randint(5, 50)
        await asyncio.sleep(latency / 1000.0)

        results = []
        for port_idx in range(1, self.port_count + 1):
            current = self._port_states[port_idx]

            # Determine transition probability
            if port_idx in self._flap_ports:
                # Flap ports toggle frequently
                flip_prob = 0.35
            else:
                # Normal ports rarely toggle
                flip_prob = 0.02

            # Maybe flip the state
            if random.random() < flip_prob:
                new_state = "down" if current == "up" else "up"
                self._port_states[port_idx] = new_state
            else:
                new_state = current

            # Generate interface name and speed
            if port_idx <= self.port_count - 4:
                iface_name = f"GigabitEthernet0/{port_idx}"
                speed = "1000 Mbps"
            else:
                iface_name = f"TenGigabitEthernet0/{port_idx}"
                speed = "10000 Mbps"

            results.append(PortPollResult(
                port_index=port_idx,
                interface_name=iface_name,
                speed=speed,
                oper_status=new_state,
                polling_latency_ms=latency + random.randint(0, 10)
            ))

        return results
