import socket
import threading
import unittest

from simulator.channel import ChannelMode, RFChannelSimulator
from simulator.controller import apply_serial_line
from simulator.telemetry import TelemetryReceiver, parse_telemetry
from simulator.transports import LineFramer, TcpController

class NetworkTests(unittest.TestCase):
    def test_tcp_framer_handles_partial_and_multiple_lines(self):
        framer = LineFramer()
        self.assertEqual(framer.feed(b"MODE:TE"), [])
        self.assertEqual(framer.feed(b"ST\nMODE:NORMAL\n"), ["MODE:TEST", "MODE:NORMAL"])

    def test_tcp_framer_discards_oversized_line(self):
        framer = LineFramer(4)
        self.assertEqual(framer.feed(b"abcdef\nOK\n"), ["OK"])

    def test_transport_independent_mode_parsing(self):
        simulator = RFChannelSimulator()
        apply_serial_line("MODE:TEST", simulator)
        self.assertIs(simulator.mode, ChannelMode.TEST)
        apply_serial_line("MODE:NORMAL", simulator)
        self.assertIs(simulator.mode, ChannelMode.NORMAL)

    def test_tcp_controller_sends_command_and_reads_lines(self):
        listener = socket.socket(); listener.bind(("127.0.0.1", 0)); listener.listen(1)
        port = listener.getsockname()[1]
        received = []
        def server():
            connection, _ = listener.accept()
            received.append(connection.recv(64))
            connection.sendall(b"MODE:TE"); connection.sendall(b"ST\nMODE:NORMAL\n")
            connection.close(); listener.close()
        thread = threading.Thread(target=server); thread.start()
        controller = TcpController("127.0.0.1", port, timeout=1); controller.connect(); controller.send_command("on")
        lines = []
        while len(lines) < 2: controller.poll(lines.append)
        controller.close(); thread.join()
        self.assertEqual(received, [b"ON\n"]); self.assertEqual(lines, ["MODE:TEST", "MODE:NORMAL"])

    def test_tcp_controller_rejects_invalid_command(self):
        controller = TcpController("unused")
        with self.assertRaises(ValueError): controller.send_command("BAD")

    def test_udp_telemetry_parse_and_malformed_packet(self):
        item = parse_telemetry(b"device=esp32-c3;mode=TEST;uptime_ms=12;sequence=4")
        self.assertEqual(item["mode"], "TEST"); self.assertIsNone(parse_telemetry(b"not telemetry"))

    def test_udp_sequence_gap(self):
        receiver = TelemetryReceiver("127.0.0.1", 0); port = receiver.socket.getsockname()[1]
        sender = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sender.sendto(b"device=esp32-c3;mode=NORMAL;uptime_ms=1;sequence=3", ("127.0.0.1", port))
        self.assertEqual(receiver.receive()["sequence_gap"], 0)
        sender.sendto(b"device=esp32-c3;mode=TEST;uptime_ms=2;sequence=6", ("127.0.0.1", port))
        self.assertEqual(receiver.receive()["sequence_gap"], 2)
        sender.close(); receiver.close()
