"""Synthetic channel metrics controlled by console or ESP32 USB serial."""
import argparse
import random
import sys
import time


class RFChannelSimulator:
    def __init__(self, rng=None):
        self.test_mode = False
        self.rng = rng or random.Random()

    def set_test_mode(self, enabled):
        self.test_mode = bool(enabled)

    def measure(self):
        ranges = ((-85, -70), (-65, -55), (40, 75)) if self.test_mode else (
            (-60, -45), (-95, -85), (95, 100))
        return dict(zip(
            ('rssi_dbm', 'noise_dbm', 'packet_success_percent'),
            (round(self.rng.uniform(*bounds), 2) for bounds in ranges)))


def handle_command(channel, command):
    command = ' '.join(command.strip().upper().split())
    if command in ('ON', 'TEST ON', 'STATE ON'):
        channel.set_test_mode(True)
        return 'Test mode enabled'
    if command in ('OFF', 'TEST OFF', 'STATE OFF'):
        channel.set_test_mode(False)
        return 'Test mode disabled'
    if command == 'STATUS':
        data = channel.measure()
        mode = 'TEST' if channel.test_mode else 'NORMAL'
        return (f"[{mode}] RSSI: {data['rssi_dbm']} dBm | "
                f"Noise: {data['noise_dbm']} dBm | "
                f"Packet Success: {data['packet_success_percent']}% (simulated)")
    return None


def manual_loop(channel):
    print('Manual commands: on | off | status | quit')
    while True:
        try:
            command = input('rf> ')
        except EOFError:
            return
        if command.strip().lower() in ('quit', 'exit'):
            return
        print(handle_command(channel, command) or 'Unknown command')


class LineDecoder:
    """Bound memory; discard malformed/oversized frames through the next newline."""
    def __init__(self):
        self.buffer = bytearray()
        self.discard = False

    def feed(self, data):
        lines = []
        for byte in data:
            if byte == 10:
                if not self.discard:
                    try:
                        lines.append(self.buffer.decode('ascii').strip())
                    except UnicodeDecodeError:
                        pass
                self.buffer.clear()
                self.discard = False
            elif not self.discard:
                if len(self.buffer) >= 128:
                    self.buffer.clear()
                    self.discard = True
                else:
                    self.buffer.append(byte)
        return lines


def serial_loop(channel, connection):
    decoder = LineDecoder()
    # Opening a USB UART can reset the ESP32. Repeated requests also cover boot delay.
    next_request = 0.0
    last_state = None
    started = time.monotonic()
    while True:
        now = time.monotonic()
        if now >= next_request:
            connection.write(b'STATUS\n')
            next_request = now + 1.0
        for line in decoder.feed(connection.read(128)):
            if line in ('STATE ON', 'STATE OFF', 'TEST ON', 'TEST OFF'):
                last_state = time.monotonic()
                result = handle_command(channel, line)
                print(result, flush=True)
            elif line == 'STATUS' and last_state is not None:
                print(handle_command(channel, line), flush=True)
        # A silent/unplugged controller must not leave stale state active indefinitely.
        if last_state is not None and time.monotonic() - last_state > 5:
            raise OSError('Controller state timed out')
        if last_state is None and time.monotonic() - started > 5:
            raise OSError('No controller state received')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', help='USB serial port; omit for manual mode')
    parser.add_argument('--baud', type=int, default=115200)
    parser.add_argument('--seed', type=int, help='Reproducible synthetic measurements')
    args = parser.parse_args(argv)
    if args.baud <= 0:
        parser.error('--baud must be positive')
    channel = RFChannelSimulator(random.Random(args.seed))
    try:
        if args.port:
            try:
                import serial
            except ImportError:
                print('Serial support missing: pip install -r requirements.txt', file=sys.stderr)
            else:
                try:
                    with serial.Serial(args.port, args.baud, timeout=0.2, write_timeout=1) as conn:
                        print(f'USB serial: {args.port}; Ctrl+C to exit', flush=True)
                        serial_loop(channel, conn)
                except (serial.SerialException, OSError) as exc:
                    print(f'Serial unavailable: {exc}', file=sys.stderr)
            channel.set_test_mode(False)
            print('Falling back to manual mode; test mode reset to OFF.')
        manual_loop(channel)
    except KeyboardInterrupt:
        print('\nExiting...')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
