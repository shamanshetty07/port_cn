"""
PortOrange — Webhook Notifier

Generic webhook notifications for Slack, Microsoft Teams, and PagerDuty.
Uses httpx for async HTTP POST delivery.
"""

import httpx
from backend.models import StateChange
from backend.config import get_config


class WebhookNotifier:
    """Sends webhook notifications via HTTP POST."""

    async def send(self, change: StateChange, device_name: str,
                   criticality: str = "standard") -> bool:
        """
        Send a webhook alert for a state change.
        Returns True on success, False on failure.
        """
        config = get_config()
        webhook_cfg = config.alerting.channels.webhook

        if not webhook_cfg.enabled or not webhook_cfg.url:
            return False

        try:
            payload = self._build_payload(
                change, device_name, criticality, webhook_cfg.type
            )

            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.post(
                    webhook_cfg.url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                return response.status_code < 300

        except Exception as e:
            print(f"  ⚠ Webhook send failed: {e}")
            return False

    def _build_payload(self, change: StateChange, device_name: str,
                       criticality: str, webhook_type: str) -> dict:
        """Build webhook payload based on the target platform."""
        if webhook_type == "slack":
            return self._slack_payload(change, device_name, criticality)
        elif webhook_type == "teams":
            return self._teams_payload(change, device_name, criticality)
        elif webhook_type == "pagerduty":
            return self._pagerduty_payload(change, device_name, criticality)
        else:
            return self._generic_payload(change, device_name, criticality)

    def _slack_payload(self, change: StateChange, device_name: str,
                       criticality: str) -> dict:
        emoji = "🔴" if change.current_state == "down" else "🟢"
        if change.is_flapping:
            emoji = "⚡"
        color = "#ef4444" if change.current_state == "down" else "#22c55e"
        if change.is_flapping:
            color = "#f59e0b"

        return {
            "attachments": [{
                "color": color,
                "blocks": [{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (
                            f"{emoji} *Port State Change*\n"
                            f"*Device:* {device_name}\n"
                            f"*Port:* {change.interface_name} "
                            f"(#{change.port_index})\n"
                            f"*Transition:* {change.previous_state} → "
                            f"*{change.current_state.upper()}*\n"
                            f"*Criticality:* {criticality}\n"
                            f"*Time:* {change.timestamp}"
                        )
                    }
                }]
            }]
        }

    def _teams_payload(self, change: StateChange, device_name: str,
                       criticality: str) -> dict:
        color = "FF0000" if change.current_state == "down" else "00FF00"
        return {
            "@type": "MessageCard",
            "themeColor": color,
            "summary": f"Port {change.port_index} on {device_name} is "
                       f"{change.current_state}",
            "sections": [{
                "activityTitle": "PortOrange Alert",
                "facts": [
                    {"name": "Device", "value": device_name},
                    {"name": "Port",
                     "value": f"{change.interface_name} (#{change.port_index})"},
                    {"name": "Transition",
                     "value": f"{change.previous_state} → "
                              f"{change.current_state}"},
                    {"name": "Criticality", "value": criticality},
                    {"name": "Time", "value": change.timestamp}
                ]
            }]
        }

    def _pagerduty_payload(self, change: StateChange, device_name: str,
                           criticality: str) -> dict:
        severity = "critical" if criticality == "critical" else "warning"
        if change.current_state == "up":
            severity = "info"

        return {
            "routing_key": "",  # Set via webhook URL
            "event_action": "trigger",
            "payload": {
                "summary": (f"Port {change.interface_name} on "
                           f"{device_name} is {change.current_state}"),
                "severity": severity,
                "source": "portorange",
                "component": device_name,
                "custom_details": {
                    "port_index": change.port_index,
                    "previous_state": change.previous_state,
                    "current_state": change.current_state,
                    "criticality": criticality,
                    "timestamp": change.timestamp
                }
            }
        }

    def _generic_payload(self, change: StateChange, device_name: str,
                         criticality: str) -> dict:
        return {
            "event": "port_state_change",
            "device": device_name,
            "device_id": change.device_id,
            "port_index": change.port_index,
            "interface_name": change.interface_name,
            "previous_state": change.previous_state,
            "current_state": change.current_state,
            "is_flapping": change.is_flapping,
            "criticality": criticality,
            "timestamp": change.timestamp,
            "polling_latency_ms": change.polling_latency_ms
        }


webhook_notifier = WebhookNotifier()
