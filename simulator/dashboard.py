"""Small standard-library terminal dashboard for session state."""
from __future__ import annotations

import sys

from .session import Session, format_duration


def render_dashboard(session: Session, tcp_status: str, udp_status: str) -> str:
    stats, sample = session.statistics, session.last_measurement
    def value(number: float | None, suffix: str) -> str:
        return "--" if number is None else f"{number:.1f}{suffix}"
    return "\n".join((
        "embedded-rf | LIVE", "--------------------------------",
        f"Device       {session.device.upper()}", f"Mode         {session.mode}",
        f"Uptime       {format_duration((session.uptime_ms or 0) / 1000)}",
        f"Sequence     {session.sequence if session.sequence is not None else '--'}",
        f"Packet gaps  {stats.sequence_gaps}", "", "SIMULATED RF",
        f"RSSI         {value(sample.rssi_dbm if sample else None, ' dBm')}",
        f"Noise        {value(sample.noise_dbm if sample else None, ' dBm')}",
        f"Success      {value(sample.packet_success_percent if sample else None, ' %')}", "",
        f"TCP          {tcp_status}", f"UDP          {udp_status}", f"Samples      {stats.samples}",
        "--------------------------------",
    ))


class TerminalDashboard:
    def __init__(self, stream=None):
        self.stream = stream or sys.stdout
        self._closed = False

    def draw(self, session: Session, tcp_status: str, udp_status: str) -> None:
        self.stream.write("\x1b[2J\x1b[H" + render_dashboard(session, tcp_status, udp_status) + "\n")
        self.stream.flush()

    def close(self) -> None:
        if not self._closed:
            self.stream.write("\x1b[0m\n")
            self.stream.flush()
            self._closed = True
