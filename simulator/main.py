"""CLI for the simulation-only RF channel model."""
import argparse
import time
from .channel import RFChannelSimulator
from .controller import SerialController, apply_serial_line

def print_measurement(simulator: RFChannelSimulator) -> None:
    sample = simulator.measure()
    print(f"SIMULATED mode={sample.mode.value} RSSI={sample.rssi_dbm:.1f} dBm noise={sample.noise_dbm:.1f} dBm packet_success={sample.packet_success_percent:.1f}%")

def main() -> int:
    parser = argparse.ArgumentParser(description="Simulation-only RF monitor (no RF hardware control).")
    parser.add_argument("--port", help="ESP32 USB serial port, e.g. /dev/ttyUSB0 or COM3")
    parser.add_argument("--interval", type=float, default=1.0, help="measurement interval in seconds")
    parser.add_argument("--manual", action="store_true", help="read ON, OFF, STATUS, or QUIT from the keyboard")
    args = parser.parse_args()
    if args.interval <= 0: parser.error("--interval must be positive")
    if not args.port and not args.manual: parser.error("choose --manual or provide --port")
    simulator, controller = RFChannelSimulator(), None
    if args.port:
        controller = SerialController(args.port)
        try:
            controller.connect(); print(f"Connected to {args.port}; awaiting ESP32 mode messages.")
        except RuntimeError as error:
            print(f"Serial error: {error}"); return 2
    print("All displayed values are simulated; no RF signal is measured or transmitted.")
    try:
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
                print_measurement(simulator); time.sleep(args.interval)
    except (KeyboardInterrupt, EOFError): print("\nStopped.")
    finally:
        if controller: controller.close()
    return 0
if __name__ == "__main__": raise SystemExit(main())
