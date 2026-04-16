"""
PortOrange — Console Notifier

Color-coded terminal output for port state change alerts.
Uses ANSI escape codes for vibrant, scannable console output.
"""

from backend.models import StateChange


# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
DIM = "\033[2m"


class ConsoleNotifier:
    """Outputs state-change alerts to the terminal with color coding."""

    async def send(self, change: StateChange, device_name: str,
                   criticality: str = "standard") -> bool:
        """
        Print a color-coded alert to the console.
        Returns True (always succeeds for console output).
        """
        # Choose color based on new state
        if change.is_flapping:
            state_color = YELLOW
            icon = "⚡"
            label = "FLAPPING"
        elif change.current_state == "up":
            state_color = GREEN
            icon = "🟢"
            label = "UP"
        elif change.current_state == "down":
            state_color = RED
            icon = "🔴"
            label = "DOWN"
        else:
            state_color = DIM
            icon = "⚪"
            label = "UNKNOWN"

        # Criticality badge
        if criticality == "critical":
            crit_badge = f" {RED}[CRITICAL]{RESET}"
        elif criticality == "monitor-only":
            crit_badge = f" {DIM}[MONITOR]{RESET}"
        else:
            crit_badge = ""

        # Format and print
        timestamp = change.timestamp[:19].replace("T", " ")
        print(
            f"  {icon} {state_color}{BOLD}{label}{RESET}"
            f"  {CYAN}{device_name}{RESET}"
            f"  Port {change.port_index}"
            f"  ({change.interface_name})"
            f"  {DIM}{change.previous_state} → {RESET}"
            f"{state_color}{change.current_state}{RESET}"
            f"{crit_badge}"
            f"  {DIM}{timestamp}{RESET}"
            f"  {DIM}({change.polling_latency_ms}ms){RESET}"
        )

        return True


console_notifier = ConsoleNotifier()
