"""Safe parser and optional receiver for ESP32 device-state UDP telemetry."""
import argparse
import socket

def parse_telemetry(packet: bytes) -> dict[str, object] | None:
    try:
        fields = dict(item.split("=", 1) for item in packet.decode("ascii").split(";") if "=" in item)
        if fields.get("device") != "esp32-c3" or fields.get("mode") not in {"NORMAL", "TEST"}: return None
        fields["uptime_ms"] = int(fields["uptime_ms"]); fields["sequence"] = int(fields["sequence"])
        if fields["uptime_ms"] < 0 or fields["sequence"] < 0: return None
        return fields
    except (UnicodeDecodeError, KeyError, ValueError): return None

class TelemetryReceiver:
    def __init__(self, bind_address: str = "0.0.0.0", port: int = 8766, timeout: float | None = 0.5):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((bind_address, port)); self.socket.settimeout(timeout)
        self.last_sequence = None
    def receive(self):
        try: packet, address = self.socket.recvfrom(256)
        except (BlockingIOError, socket.timeout): return None
        item = parse_telemetry(packet)
        if item is None: return None
        sequence = item["sequence"]
        item["sequence_gap"] = 0 if self.last_sequence is None else max(0, sequence - self.last_sequence - 1)
        self.last_sequence = sequence
        item["address"] = address
        return item
    def close(self): self.socket.close()

def main() -> int:
    parser = argparse.ArgumentParser(description="Receive ESP32 device-state telemetry; never RF measurements.")
    parser.add_argument("--bind", default="0.0.0.0"); parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args(); receiver = TelemetryReceiver(args.bind, args.port)
    print(f"Listening for DEVICE TELEMETRY on {args.bind}:{args.port}")
    try:
        while True:
            item = receiver.receive()
            if item: print(f"DEVICE TELEMETRY mode={item['mode']} uptime_ms={item['uptime_ms']} sequence={item['sequence']} gap={item['sequence_gap']}")
    except KeyboardInterrupt: print("\nStopped.")
    finally: receiver.close()
    return 0
if __name__ == "__main__": raise SystemExit(main())
