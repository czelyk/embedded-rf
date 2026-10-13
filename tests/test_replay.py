import tempfile
import unittest
from pathlib import Path

from simulator.analysis import load_session_csv
from simulator.dashboard import render_dashboard
from simulator.replay import replay_delay, run_replay, validate_speed
from simulator.session import CSV_FIELDS, Session
from simulator.web import serialize_state


FIXTURE = Path(__file__).parent / "fixtures" / "replay_session.csv"


class ReplayTests(unittest.TestCase):
    def test_valid_replay_order_values_modes_and_completion(self):
        updates, sleeps = [], []
        state = run_replay(load_session_csv(FIXTURE), sleep=sleeps.append,
                           on_update=lambda session: updates.append((session.mode, session.statistics.samples)))
        self.assertEqual(state.source, "REPLAY")
        self.assertEqual((state.statistics.samples, state.statistics.normal_samples, state.statistics.test_samples), (3, 2, 1))
        self.assertEqual([point["rssi"] for point in state.history], [-55.5, -77.25, -54.0])
        self.assertIn(("TEST", 1), updates)
        self.assertEqual(state.mode, "NORMAL")
        self.assertEqual(state.statistics.sequence_gaps, 1)
        self.assertEqual(sleeps, [1.0] * 6)

    def test_speed_and_no_delay_are_injected_without_real_time(self):
        sleeps = []
        run_replay(load_session_csv(FIXTURE), speed=2.0, sleep=sleeps.append)
        self.assertEqual(sleeps, [0.5] * 6)
        sleeps.clear()
        run_replay(load_session_csv(FIXTURE), no_delay=True, sleep=sleeps.append)
        self.assertEqual(sleeps, [])
        for bad in ("0", "-1", "nan", "inf", "bad"):
            with self.assertRaises(Exception): validate_speed(bad)

    def test_missing_and_reverse_timestamps_never_sleep_negative(self):
        header = ",".join(CSV_FIELDS)
        rows = [
            ",sample,manual,NORMAL,,,-50,-90,99",
            "2026-01-01T00:00:02+00:00,sample,manual,TEST,,,-70,-60,50",
            "2026-01-01T00:00:01+00:00,sample,manual,NORMAL,,,-51,-91,98",
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "irregular.csv"
            path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
            loaded = load_session_csv(path)
        sleeps = []
        state = run_replay(loaded, sleep=sleeps.append)
        self.assertEqual(state.statistics.samples, 3)
        self.assertEqual(sleeps, [])
        self.assertEqual(replay_delay(loaded.rows[1], loaded.rows[2], 1), 0)

    def test_terminal_and_web_share_same_replay_state(self):
        state = run_replay(load_session_csv(FIXTURE), no_delay=True)
        terminal = render_dashboard(state, "REPLAY / NO HARDWARE", "REPLAY / NO HARDWARE")
        web = serialize_state(state, "REPLAY / NO HARDWARE", "REPLAY / NO HARDWARE")
        self.assertIn("SOURCE: REPLAY", terminal)
        self.assertTrue(web["replay"])
        self.assertEqual(web["simulated_rf"]["rssi_dbm"], state.last_measurement.rssi_dbm)
        self.assertEqual(web["session"]["samples"], state.statistics.samples)


if __name__ == "__main__": unittest.main()
