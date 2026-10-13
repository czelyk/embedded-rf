"""Deterministic, hardware-free replay of recorded embedded-rf sessions."""
from __future__ import annotations

import argparse
import time
from collections.abc import Callable

from .analysis import AnalysisError, AnalysisRow, LoadedSession, load_session_csv
from .channel import ChannelMode, Measurement
from .dashboard import TerminalDashboard
from .session import Session, format_summary
from .web import DEFAULT_WEB_BIND, DEFAULT_WEB_PORT, WebDashboard, create_app


def validate_speed(value: str) -> float:
    try:
        speed = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("speed must be a positive number") from error
    if not 0 < speed < float("inf"):
        raise argparse.ArgumentTypeError("speed must be a positive finite number")
    return speed


def replay_delay(previous: AnalysisRow | None, current: AnalysisRow, speed: float) -> float:
    if previous is None or previous.timestamp is None or current.timestamp is None:
        return 0.0
    return max(0.0, (current.timestamp - previous.timestamp).total_seconds()) / speed


def apply_replay_row(session: Session, row: AnalysisRow) -> None:
    """Apply recorded values to normal shared state without generating RF data."""
    if row.event == "telemetry" and row.mode in {"NORMAL", "TEST"}:
        previous = session.sequence
        gap = max(0, row.sequence - previous - 1) if row.sequence is not None and previous is not None else 0
        session.record_telemetry({
            "device": row.device or session.device,
            "mode": row.mode,
            "uptime_ms": row.uptime_ms or 0,
            "sequence": row.sequence if row.sequence is not None else (session.sequence or 0),
            "sequence_gap": gap,
        })
    elif row.event == "control" and row.mode in {"NORMAL", "TEST"}:
        session.record_mode_update(row.mode)
    elif row.event == "sample" and row.mode in {"NORMAL", "TEST"}:
        if None in (row.simulated_rssi_dbm, row.simulated_noise_dbm, row.simulated_packet_success_percent):
            return
        session.record_sample(Measurement(
            ChannelMode(row.mode), row.simulated_rssi_dbm, row.simulated_noise_dbm,
            row.simulated_packet_success_percent,
        ))


def run_replay(loaded: LoadedSession, session: Session | None = None, speed: float = 1.0,
               no_delay: bool = False, sleep: Callable[[float], None] = time.sleep,
               on_update: Callable[[Session], None] | None = None) -> Session:
    if speed <= 0 or speed == float("inf"):
        raise ValueError("speed must be a positive finite number")
    state = session or Session(source="REPLAY")
    state.source = "REPLAY"
    previous = None
    for row in loaded.rows:
        delay = 0.0 if no_delay else replay_delay(previous, row, speed)
        if delay: sleep(delay)
        apply_replay_row(state, row)
        if on_update: on_update(state)
        previous = row
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay a recorded session with recorded SIMULATED RF values; no hardware required.")
    parser.add_argument("session", help="Milestone 3 CSV session")
    parser.add_argument("--speed", type=validate_speed, default=1.0, help="timing multiplier (default: 1.0)")
    parser.add_argument("--no-delay", action="store_true", help="replay immediately without recorded delays")
    parser.add_argument("--dashboard", action="store_true", help="show replay in the terminal dashboard")
    parser.add_argument("--web-dashboard", action="store_true", help="show replay in the local browser dashboard")
    parser.add_argument("--web-bind", default=DEFAULT_WEB_BIND, help=f"web bind address (default: {DEFAULT_WEB_BIND})")
    parser.add_argument("--web-port", type=int, default=DEFAULT_WEB_PORT, help=f"web port (default: {DEFAULT_WEB_PORT})")
    args = parser.parse_args()
    if not 1 <= args.web_port <= 65535: parser.error("--web-port must be 1..65535")
    state, terminal, web, completed = Session(source="REPLAY"), None, None, False
    try:
        loaded = load_session_csv(args.session)
        terminal = TerminalDashboard() if args.dashboard else None
        if args.web_dashboard:
            web = WebDashboard(create_app(state, lambda: ("REPLAY / NO HARDWARE", "REPLAY / NO HARDWARE")), args.web_bind, args.web_port)
            web.start()
            print(f"REPLAY MODE web dashboard: {web.url} (bound to {args.web_bind})")
        def update(current: Session) -> None:
            if terminal: terminal.draw(current, "REPLAY / NO HARDWARE", "REPLAY / NO HARDWARE")
        print(f"REPLAY MODE: {loaded.path} at {args.speed:g}x" + (" (no delay)" if args.no_delay else ""))
        run_replay(loaded, state, args.speed, args.no_delay, on_update=update)
        completed = True
        if loaded.issues: print(f"Replay retained {len(loaded.issues)} malformed field(s) as unavailable.")
    except (AnalysisError, OSError, ValueError) as error:
        print(f"Replay error: {error}")
        return 2
    except KeyboardInterrupt:
        print("\nReplay stopped.")
    finally:
        if terminal: terminal.close()
        if web: web.close()
        print("REPLAY MODE complete" if completed else "REPLAY MODE ended")
        print(format_summary(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
