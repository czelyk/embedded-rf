import csv
import io
import tempfile
import unittest
from pathlib import Path

from simulator.channel import ChannelMode, Measurement
from simulator.dashboard import TerminalDashboard, render_dashboard
from simulator.session import CSV_FIELDS, CsvSessionWriter, Session, SessionStatistics, format_summary
from simulator.telemetry import parse_telemetry


class Clock:
    def __init__(self): self.value = 0.0
    def __call__(self): return self.value
    def advance(self, seconds): self.value += seconds


class SessionTests(unittest.TestCase):
    def test_csv_writes_header_and_normal_test_rows(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "session.csv"
            session = Session()
            writer = CsvSessionWriter(path)
            writer.write(session.record_sample(Measurement(ChannelMode.NORMAL, -55.0, -95.0, 98.0)))
            writer.write(session.record_sample(Measurement(ChannelMode.TEST, -75.0, -70.0, 60.0)))
            writer.close()
            with path.open(newline="", encoding="utf-8") as file: rows = list(csv.DictReader(file))
        self.assertEqual(tuple(rows[0]), CSV_FIELDS)
        self.assertEqual([row["mode"] for row in rows], ["NORMAL", "TEST"])
        self.assertEqual(rows[0]["simulated_rssi_dbm"], "-55.0")
        self.assertEqual(rows[1]["simulated_packet_success_percent"], "60.0")

    def test_statistics_min_average_max_and_mode_counts(self):
        clock = Clock(); stats = SessionStatistics(clock=clock); session = Session(stats)
        session.record_sample(Measurement(ChannelMode.NORMAL, -60.0, -100.0, 99.0))
        clock.advance(2); session.record_sample(Measurement(ChannelMode.TEST, -80.0, -70.0, 50.0))
        clock.advance(3)
        self.assertEqual((stats.samples, stats.normal_samples, stats.test_samples), (2, 1, 1))
        self.assertEqual((stats.rssi.minimum, stats.rssi.average, stats.rssi.maximum), (-80.0, -70.0, -60.0))
        self.assertEqual((stats.noise.minimum, stats.noise.average, stats.noise.maximum), (-100.0, -85.0, -70.0))
        self.assertEqual((stats.success.minimum, stats.success.average, stats.success.maximum), (50.0, 74.5, 99.0))
        self.assertEqual(stats.mode_seconds(), (2.0, 3.0))

    def test_telemetry_records_sequence_gaps_separately_from_samples(self):
        session = Session()
        session.record_telemetry({"device": "esp32-c3", "mode": "NORMAL", "uptime_ms": 10, "sequence": 4, "sequence_gap": 0})
        record = session.record_telemetry({"device": "esp32-c3", "mode": "TEST", "uptime_ms": 20, "sequence": 7, "sequence_gap": 2})
        self.assertEqual((session.statistics.telemetry_packets, session.statistics.sequence_gaps), (2, 2))
        self.assertEqual((record.device, record.mode, record.sequence), ("esp32-c3", "TEST", 7))
        self.assertEqual(session.statistics.samples, 0)

    def test_control_mode_update_is_a_structured_non_rf_event(self):
        session = Session()
        record = session.record_mode_update("TEST")
        self.assertEqual((record.event, record.mode), ("control", "TEST"))
        self.assertIsNone(record.simulated_rssi_dbm)

    def test_dashboard_labels_simulated_values_and_known_state(self):
        session = Session()
        session.record_telemetry({"device": "esp32-c3", "mode": "TEST", "uptime_ms": 62000, "sequence": 12, "sequence_gap": 1})
        session.record_sample(Measurement(ChannelMode.TEST, -78.0, -73.0, 61.0))
        output = render_dashboard(session, "CONNECTED", "RECEIVING")
        self.assertIn("SIMULATED RF", output)
        self.assertIn("Device       ESP32-C3", output)
        self.assertIn("Mode         TEST", output)
        self.assertIn("Packet gaps  1", output)
        self.assertIn("TCP          CONNECTED", output)

    def test_dashboard_cleanup_and_summary(self):
        stream = io.StringIO(); dashboard = TerminalDashboard(stream)
        dashboard.close(); dashboard.close()
        self.assertEqual(stream.getvalue(), "\x1b[0m\n")
        summary = format_summary(Session())
        self.assertIn("Session summary", summary)
        self.assertIn("SIMULATED RF", summary)

    def test_malformed_telemetry_is_safe(self):
        self.assertIsNone(parse_telemetry(b"device=esp32-c3;mode=TEST;sequence=bad"))


if __name__ == "__main__": unittest.main()
