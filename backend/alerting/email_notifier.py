"""
PortOrange — Email Notifier

SMTP-based email notifications for port state changes.
Uses aiosmtplib for async, non-blocking delivery.
"""

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from backend.models import StateChange
from backend.config import get_config


class EmailNotifier:
    """Sends HTML-formatted email alerts via SMTP."""

    async def send(self, change: StateChange, device_name: str,
                   criticality: str = "standard") -> bool:
        """
        Send an email alert for a state change.
        Returns True on success, False on failure.
        """
        config = get_config()
        email_cfg = config.alerting.channels.email

        if not email_cfg.enabled:
            return False

        try:
            import aiosmtplib

            # Build email
            msg = MIMEMultipart("alternative")
            msg["Subject"] = self._build_subject(change, device_name)
            msg["From"] = email_cfg.from_address
            msg["To"] = ", ".join(email_cfg.to_addresses)

            html = self._build_html(change, device_name, criticality)
            msg.attach(MIMEText(html, "html"))

            # Send
            await aiosmtplib.send(
                msg,
                hostname=email_cfg.smtp_host,
                port=email_cfg.smtp_port,
                username=email_cfg.smtp_user,
                password=email_cfg.smtp_password,
                use_tls=True
            )
            return True

        except Exception as e:
            print(f"  ⚠ Email send failed: {e}")
            return False

    def _build_subject(self, change: StateChange,
                       device_name: str) -> str:
        state = "🔴 DOWN" if change.current_state == "down" else "🟢 UP"
        if change.is_flapping:
            state = "⚡ FLAPPING"
        return (f"[PortOrange] {state} — {device_name} "
                f"Port {change.port_index}")

    def _build_html(self, change: StateChange, device_name: str,
                    criticality: str) -> str:
        color = "#ef4444" if change.current_state == "down" else "#22c55e"
        if change.is_flapping:
            color = "#f59e0b"

        config = get_config()
        dashboard_url = config.server.dashboard_url

        return f"""
        <div style="font-family: -apple-system, sans-serif; max-width: 500px;
                    margin: 0 auto; padding: 20px;">
            <div style="background: {color}; color: white; padding: 16px;
                        border-radius: 8px 8px 0 0; text-align: center;">
                <h2 style="margin: 0;">Port State Change</h2>
            </div>
            <div style="background: #1e293b; color: #e2e8f0; padding: 20px;
                        border-radius: 0 0 8px 8px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr><td style="padding: 8px; color: #94a3b8;">Device</td>
                        <td style="padding: 8px; font-weight: bold;">{device_name}</td></tr>
                    <tr><td style="padding: 8px; color: #94a3b8;">Port</td>
                        <td style="padding: 8px;">{change.interface_name} (#{change.port_index})</td></tr>
                    <tr><td style="padding: 8px; color: #94a3b8;">Transition</td>
                        <td style="padding: 8px;">{change.previous_state} → <strong style="color: {color};">{change.current_state}</strong></td></tr>
                    <tr><td style="padding: 8px; color: #94a3b8;">Criticality</td>
                        <td style="padding: 8px;">{criticality.upper()}</td></tr>
                    <tr><td style="padding: 8px; color: #94a3b8;">Time (UTC)</td>
                        <td style="padding: 8px;">{change.timestamp}</td></tr>
                    <tr><td style="padding: 8px; color: #94a3b8;">Latency</td>
                        <td style="padding: 8px;">{change.polling_latency_ms} ms</td></tr>
                </table>
                <div style="text-align: center; margin-top: 16px;">
                    <a href="{dashboard_url}" style="display: inline-block;
                       background: {color}; color: white; padding: 10px 24px;
                       text-decoration: none; border-radius: 6px;">
                       View Dashboard</a>
                </div>
            </div>
        </div>
        """


email_notifier = EmailNotifier()
