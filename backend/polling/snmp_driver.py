"""
PortOrange — SNMP Device Driver

Real SNMP driver using pysnmp for polling ifOperStatus, ifDescr,
and ifSpeed from network devices via SNMP v2c/v3.
"""

import asyncio
from typing import Optional
from backend.models import PortPollResult

# SNMP OIDs
IF_OPER_STATUS = '1.3.6.1.2.1.2.2.1.8'   # ifOperStatus
IF_DESCR = '1.3.6.1.2.1.2.2.1.2'          # ifDescr
IF_SPEED = '1.3.6.1.2.1.2.2.1.5'          # ifSpeed

# ifOperStatus value mapping
STATUS_MAP = {
    1: "up",
    2: "down",
    3: "testing",
    4: "unknown",
    5: "dormant",
    6: "notPresent",
    7: "lowerLayerDown"
}


class SNMPDriver:
    """
    Real SNMP driver for polling port states from network devices.

    Uses pysnmp async API for non-blocking SNMP walks.
    Supports SNMP v2c (community string) and can be extended for v3.
    """

    def __init__(self, device_id: str, host: str,
                 community: str = "public", version: str = "2c",
                 timeout: int = 10, retries: int = 2):
        self.device_id = device_id
        self.host = host
        self.community = community
        self.version = version
        self.timeout = timeout
        self.retries = retries

    async def poll(self) -> list[PortPollResult]:
        """
        Poll all ports on the device via SNMP walk.
        Returns list of PortPollResult with current states.
        """
        try:
            from pysnmp.hlapi.asyncio import (
                SnmpEngine, CommunityData, UdpTransportTarget,
                ContextData, ObjectType, ObjectIdentity, nextCmd
            )
        except ImportError:
            print(f"  ⚠ pysnmp not installed, cannot poll {self.device_id}")
            return []

        import time
        start = time.monotonic()

        results_map: dict[int, dict] = {}

        engine = SnmpEngine()

        # Walk ifOperStatus
        try:
            iterator = nextCmd(
                engine,
                CommunityData(self.community),
                UdpTransportTarget(
                    (self.host, 161),
                    timeout=self.timeout,
                    retries=self.retries
                ),
                ContextData(),
                ObjectType(ObjectIdentity(IF_OPER_STATUS)),
                lexicographicMode=False
            )

            async for (err_indication, err_status, err_index,
                       var_binds) in iterator:
                if err_indication:
                    print(f"  ⚠ SNMP error ({self.device_id}): "
                          f"{err_indication}")
                    break
                if err_status:
                    break
                for var_bind in var_binds:
                    oid, val = var_bind
                    # Extract port index from OID
                    port_idx = int(str(oid).split('.')[-1])
                    status_int = int(val)
                    results_map.setdefault(port_idx, {})
                    results_map[port_idx]['oper_status'] = STATUS_MAP.get(
                        status_int, "unknown"
                    )

            # Walk ifDescr
            iterator = nextCmd(
                engine,
                CommunityData(self.community),
                UdpTransportTarget(
                    (self.host, 161),
                    timeout=self.timeout,
                    retries=self.retries
                ),
                ContextData(),
                ObjectType(ObjectIdentity(IF_DESCR)),
                lexicographicMode=False
            )

            async for (err_indication, err_status, err_index,
                       var_binds) in iterator:
                if err_indication or err_status:
                    break
                for var_bind in var_binds:
                    oid, val = var_bind
                    port_idx = int(str(oid).split('.')[-1])
                    results_map.setdefault(port_idx, {})
                    results_map[port_idx]['interface_name'] = str(val)

            # Walk ifSpeed
            iterator = nextCmd(
                engine,
                CommunityData(self.community),
                UdpTransportTarget(
                    (self.host, 161),
                    timeout=self.timeout,
                    retries=self.retries
                ),
                ContextData(),
                ObjectType(ObjectIdentity(IF_SPEED)),
                lexicographicMode=False
            )

            async for (err_indication, err_status, err_index,
                       var_binds) in iterator:
                if err_indication or err_status:
                    break
                for var_bind in var_binds:
                    oid, val = var_bind
                    port_idx = int(str(oid).split('.')[-1])
                    results_map.setdefault(port_idx, {})
                    speed_bps = int(val)
                    if speed_bps >= 1_000_000_000:
                        results_map[port_idx]['speed'] = (
                            f"{speed_bps // 1_000_000_000} Gbps"
                        )
                    elif speed_bps >= 1_000_000:
                        results_map[port_idx]['speed'] = (
                            f"{speed_bps // 1_000_000} Mbps"
                        )
                    else:
                        results_map[port_idx]['speed'] = f"{speed_bps} bps"

        except Exception as e:
            print(f"  ⚠ SNMP poll failed ({self.device_id}): {e}")
            return []
        finally:
            engine.close_dispatcher()

        elapsed_ms = int((time.monotonic() - start) * 1000)

        # Build results
        results = []
        for port_idx, data in sorted(results_map.items()):
            results.append(PortPollResult(
                port_index=port_idx,
                interface_name=data.get('interface_name', f'Port {port_idx}'),
                speed=data.get('speed', ''),
                oper_status=data.get('oper_status', 'unknown'),
                polling_latency_ms=elapsed_ms
            ))

        return results
