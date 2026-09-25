"""CLI for the simulation-only RF channel model and device-state sessions."""
import argparse
import time

from .channel import RFChannelSimulator
from .controller import SerialController, apply_serial_line
from .dashboard import TerminalDashboard
from .session import CsvSessionWriter, Session, SessionLogError, format_summary
from .telemetry import TelemetryReceiver
from .transports import TcpController


def main() -> int:
    parser = argparse.ArgumentParser(description="Simulation-only RF monitor (no RF hardware control).")
    parser.add_argument("--port", help="ESP32 USB serial port, e.g. /dev/ttyUSB0 or COM3")
    parser.add_argument("--host", help="ESP32 TCP host or IP address")
    parser.add_argument("--tcp-port", type=int, default=8765, help="ESP32 TCP control port (default: 8765)")
    parser.add_argument("--udp-bind", default="0.0.0.0", help="local bind address for device telemetry")
    parser.add_argument("--udp-port", type=int, default=8766, help="device telemetry UDP port (default: 8766)")
    parser.add_argument("--no-udp", action="store_true", help="do not receive device-state UDP telemetry")
    parser.add_argument("--csv", help="write structured session records to this CSV path")
    parser.add_argument("--dashboard", action="store_true", help="show a refreshing terminal dashboard")
    parser.add_argument("--interval", type=float, default=1.0, help="measurement interval in seconds")
    parser.add_argument("--manual", action="store_true", help="read ON, OFF, STATUS, or QUIT from the keyboard")
    parser.add_argument("--command", action="append", default=[], help="send ON, OFF, or STATUS after connecting (repeatable)")
    parser.add_argument("--count", type=int, help="stop after this many hardware measurement cycles")
    args = parser.parse_args()
    if args.interval <= 0: parser.error("--interval must be positive")
    if args.count is not None and args.count <= 0: parser.error("--count must be positive")
    if args.port and args.host: parser.error("choose either --port or --host")
    if not 1 <= args.tcp_port <= 65535 or not 1 <= args.udp_port <= 65535: parser.error("port must be 1..65535")
    if not args.port and not args.host and not args.manual: parser.error("choose --manual, --port, or --host")
    try:
        writer = CsvSessionWriter(args.csv) if args.csv else None
    except SessionLogError as error:
        print(f"CSV error: {error}")
        return 2
    simulator, session = RFChannelSimulator(), Session()
    controller = receiver = None
    dashboard = TerminalDashboard() if args.dashboard else None
    tcp_status, udp_status = "NOT CONNECTED", "DISABLED"

    def write(record) -> None:
        if writer: writer.write(record)

    def update_mode(line: str, record_update: bool = True) -> None:
        result = apply_serial_line(line, simulator)
        if result:
            if record_update: write(session.record_mode_update(simulator.mode.value))
            else:
                session.mode = simulator.mode.value
                session.statistics.set_mode(session.mode)
        if result and not dashboard: print(result)
        elif line and not dashboard: print(f"ESP32: {line}")

    def poll_telemetry() -> None:
        nonlocal udp_status
        if not receiver: return
        for _ in range(16):
            packet = receiver.receive()
            if packet is None: break
            udp_status = "RECEIVING"
            write(session.record_telemetry(packet))
            update_mode(f"MODE:{packet['mode']}", record_update=False)
            if not dashboard:
                print(f"DEVICE TELEMETRY device={packet['device']} mode={packet['mode']} uptime_ms={packet['uptime_ms']} sequence={packet['sequence']} gap={packet['sequence_gap']}")

    try:
        if args.port or args.host:
            controller = SerialController(args.port) if args.port else TcpController(args.host, args.tcp_port)
            endpoint = args.port or f"{args.host}:{args.tcp_port}"
            controller.connect(); tcp_status = "CONNECTED"
            if not dashboard: print(f"Connected to {endpoint}; awaiting ESP32 mode messages.")
            for command in args.command:
                controller.send_command(command)
                if not dashboard: print(f"Sent ESP32 command: {command.strip().upper()}")
            if not args.no_udp:
                try:
                    receiver = TelemetryReceiver(args.udp_bind, args.udp_port, timeout=0.0)
                    udp_status = "LISTENING"
                except OSError as error:
                    udp_status = "UNAVAILABLE"
                    print(f"UDP telemetry unavailable: {error}")
        if not dashboard: print("All displayed RF values are SIMULATED; no RF signal is measured or transmitted.")
        cycles = 0
        while True:
            if args.manual:
                command = input("Command [ON/OFF/STATUS/QUIT]: ").strip()
                if command.upper() == "QUIT": break
                if command.upper() == "STATUS":
                    if not dashboard: print(f"Simulator mode: {simulator.mode.value}")
                else: update_mode(command)
            else:
                poll_telemetry()
                controller.poll(update_mode)
            poll_telemetry()
            measurement = simulator.measure()
            write(session.record_sample(measurement))
            if dashboard: dashboard.draw(session, tcp_status, udp_status)
            else: print(f"SIMULATED mode={measurement.mode.value} RSSI={measurement.rssi_dbm:.1f} dBm noise={measurement.noise_dbm:.1f} dBm packet_success={measurement.packet_success_percent:.1f}%")
            cycles += 1
            if not args.manual and args.count is not None and cycles >= args.count: break
            if not args.manual: time.sleep(args.interval)
    except (RuntimeError, SessionLogError) as error:
        print(f"Session error: {error}")
        return 2
    except (KeyboardInterrupt, EOFError): print("\nStopped.")
    finally:
        if receiver: receiver.close()
        if controller: controller.close()
        if dashboard: dashboard.close()
        if writer: writer.close()
        print(format_summary(session, args.csv if writer else None))
    return 0


if __name__ == "__main__": raise SystemExit(main())
