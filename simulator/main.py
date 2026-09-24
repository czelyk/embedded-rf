"""CLI for the simulation-only RF channel model."""
import argparse
import time
from .channel import RFChannelSimulator
from .controller import SerialController, apply_serial_line
from .transports import TcpController

def print_measurement(simulator: RFChannelSimulator) -> None:
    sample = simulator.measure()
    print(f"SIMULATED mode={sample.mode.value} RSSI={sample.rssi_dbm:.1f} dBm noise={sample.noise_dbm:.1f} dBm packet_success={sample.packet_success_percent:.1f}%")

def main() -> int:
    parser = argparse.ArgumentParser(description="Simulation-only RF monitor (no RF hardware control).")
    parser.add_argument("--port", help="ESP32 USB serial port, e.g. /dev/ttyUSB0 or COM3")
    parser.add_argument("--host", help="ESP32 TCP host or IP address")
    parser.add_argument("--tcp-port", type=int, default=8765, help="ESP32 TCP control port (default: 8765)")
    parser.add_argument("--interval", type=float, default=1.0, help="measurement interval in seconds")
    parser.add_argument("--manual", action="store_true", help="read ON, OFF, STATUS, or QUIT from the keyboard")
    parser.add_argument("--command", action="append", default=[], help="send ON, OFF, or STATUS after connecting (repeatable)")
    parser.add_argument("--count", type=int, help="stop after this many hardware measurement cycles")
    args = parser.parse_args()
    if args.interval <= 0: parser.error("--interval must be positive")
    if args.count is not None and args.count <= 0: parser.error("--count must be positive")
    if args.port and args.host: parser.error("choose either --port or --host")
    if args.tcp_port <= 0 or args.tcp_port > 65535: parser.error("--tcp-port must be 1..65535")
    if not args.port and not args.host and not args.manual: parser.error("choose --manual, --port, or --host")
    simulator, controller = RFChannelSimulator(), None
    if args.port or args.host:
        controller = SerialController(args.port) if args.port else TcpController(args.host, args.tcp_port)
        try:
            endpoint = args.port or f"{args.host}:{args.tcp_port}"
            controller.connect(); print(f"Connected to {endpoint}; awaiting ESP32 mode messages.")
            for command in args.command:
                controller.send_command(command)
                print(f"Sent ESP32 command: {command.strip().upper()}")
        except RuntimeError as error:
            print(f"Serial error: {error}"); return 2
        except ValueError as error:
            print(f"Command error: {error}"); controller.close(); return 2
    print("All displayed values are simulated; no RF signal is measured or transmitted.")
    try:
        cycles = 0
        while True:
            if args.manual:
                command = input("Command [ON/OFF/STATUS/QUIT]: ").strip()
                if command.upper() == "QUIT": break
                if command.upper() == "STATUS":
                    print(f"Simulator mode: {simulator.mode.value}")
                else:
                    result = apply_serial_line(command, simulator)
                    print(result or "Unknown command; use ON, OFF, STATUS, or QUIT.")
                print_measurement(simulator)
            else:
                controller.poll(lambda line: print(apply_serial_line(line, simulator) or f"ESP32: {line}"))
                print_measurement(simulator); cycles += 1
                if args.count is not None and cycles >= args.count: break
                time.sleep(args.interval)
    except RuntimeError as error:
        print(f"Serial error: {error}")
        return 2
    except (KeyboardInterrupt, EOFError): print("\nStopped.")
    finally:
        if controller: controller.close()
    return 0
if __name__ == "__main__": raise SystemExit(main())
