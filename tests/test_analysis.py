import csv
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import unittest

from simulator.analysis import (AnalysisError, analyze_session, format_analysis,
                                format_mode_comparison, format_multi_session_comparison,
                                generate_plots, load_session_csv, write_markdown_report)
from simulator.session import CSV_FIELDS


def row(timestamp, event, mode, *, sequence="", rssi="", noise="", success="", device="esp32-c3"):
    return {"timestamp": timestamp, "event": event, "device": device, "mode": mode,
            "uptime_ms": "10" if event == "telemetry" else "", "sequence": sequence,
            "simulated_rssi_dbm": rssi, "simulated_noise_dbm": noise,
            "simulated_packet_success_percent": success}


class AnalysisTests(unittest.TestCase):
    def write_csv(self, directory, rows, name="session.csv"):
        path = Path(directory) / name
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_FIELDS); writer.writeheader(); writer.writerows(rows)
        return path

    def valid_rows(self):
        return [
            row("2026-01-01T00:00:00+00:00", "sample", "NORMAL", rssi="-50", noise="-95", success="99"),
            row("2026-01-01T00:00:01+00:00", "telemetry", "NORMAL", sequence="1"),
            row("2026-01-01T00:00:02+00:00", "control", "TEST"),
            row("2026-01-01T00:00:03+00:00", "sample", "TEST", rssi="-70", noise="-72", success="60"),
            row("2026-01-01T00:00:04+00:00", "telemetry", "TEST", sequence="4"),
        ]

    def test_valid_loader_and_statistics(self):
        with tempfile.TemporaryDirectory() as directory:
            analysis = analyze_session(load_session_csv(self.write_csv(directory, self.valid_rows())))
        self.assertEqual((analysis.total_rows, analysis.sample_count, analysis.telemetry_count, analysis.control_count), (5, 2, 2, 1))
        self.assertEqual((analysis.normal.sample_count, analysis.test.sample_count), (1, 1))
        self.assertEqual((analysis.overall.rssi.minimum, analysis.overall.rssi.average, analysis.overall.rssi.maximum), (-70.0, -60.0, -50.0))
        self.assertEqual(analysis.overall.rssi.standard_deviation, 10.0)
        self.assertEqual(analysis.telemetry.sequence_gaps, 2)
        self.assertEqual((analysis.normal.duration_seconds, analysis.test.duration_seconds), (2.0, 2.0))

    def test_missing_empty_and_header_only_csvs_are_safe(self):
        with self.assertRaisesRegex(AnalysisError, "not found"): load_session_csv("missing-session.csv")
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory) / "empty.csv"; empty.write_text("", encoding="utf-8")
            with self.assertRaisesRegex(AnalysisError, "empty"): load_session_csv(empty)
            header = self.write_csv(directory, [], "header.csv")
            analysis = analyze_session(load_session_csv(header))
        self.assertEqual(analysis.sample_count, 0)
        self.assertIn("SIMULATED RSSI: N/A", format_analysis(analysis))

    def test_missing_columns_and_malformed_fields_do_not_crash(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.csv"; missing.write_text("timestamp,event\n", encoding="utf-8")
            with self.assertRaisesRegex(AnalysisError, "missing required columns"): load_session_csv(missing)
            rows = [row("not-a-time", "mystery", "OTHER", rssi="bad", noise="", success="nope")]
            loaded = load_session_csv(self.write_csv(directory, rows, "bad.csv"))
        self.assertEqual(len(loaded.rows), 1)
        self.assertGreaterEqual(len(loaded.issues), 4)
        self.assertEqual(analyze_session(loaded).sample_count, 0)

    def test_single_mode_no_sample_and_sequence_duplicate_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            only_normal = [row("2026-01-01T00:00:00+00:00", "sample", "NORMAL", rssi="-55", noise="-95", success="99")]
            normal = analyze_session(load_session_csv(self.write_csv(directory, only_normal, "normal.csv")))
            telemetry = [row("2026-01-01T00:00:00+00:00", "telemetry", "NORMAL", sequence="4"), row("2026-01-01T00:00:01+00:00", "telemetry", "NORMAL", sequence="4"), row("2026-01-01T00:00:02+00:00", "telemetry", "NORMAL", sequence="2")]
            quality = analyze_session(load_session_csv(self.write_csv(directory, telemetry, "telemetry.csv")))
        self.assertEqual((normal.normal.sample_count, normal.test.sample_count), (1, 0))
        self.assertIsNone(normal.test.rssi.average)
        self.assertEqual((quality.telemetry.duplicate_sequences, quality.telemetry.sequence_resets, quality.telemetry.sequence_gaps), (1, 1, 0))

    def test_comparison_report_and_simulated_labeling(self):
        with tempfile.TemporaryDirectory() as directory:
            first_path = self.write_csv(directory, self.valid_rows(), "first.csv")
            second_rows = [row("2026-01-01T00:00:00+00:00", "sample", "NORMAL", rssi="-45", noise="-98", success="100")]
            second_path = self.write_csv(directory, second_rows, "second.csv")
            first, second = analyze_session(load_session_csv(first_path)), analyze_session(load_session_csv(second_path))
            report = write_markdown_report(first, Path(directory) / "report.md", comparisons=[second])
            content = report.read_text(encoding="utf-8")
        comparison = format_mode_comparison(first)
        self.assertIn("-20.00 dBm", comparison)
        self.assertIn("Multi-session comparison", format_multi_session_comparison([first, second]))
        self.assertIn("software-simulated values", content)
        self.assertIn("SIMULATED RF summary", content)

    def test_headless_plot_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            analysis = analyze_session(load_session_csv(self.write_csv(directory, self.valid_rows())))
            plots = generate_plots(analysis, Path(directory) / "plots")
            self.assertEqual({plot.name for plot in plots}, {"simulated_rssi.png", "simulated_noise.png", "simulated_packet_success.png", "mode_timeline.png"})
            self.assertTrue(all(plot.stat().st_size > 0 for plot in plots))


if __name__ == "__main__": unittest.main()
