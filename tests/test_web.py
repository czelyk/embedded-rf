import unittest

from simulator.channel import ChannelMode, Measurement
from simulator.session import Session
from simulator.web import DEFAULT_WEB_BIND, create_app, serialize_state


class WebDashboardTests(unittest.TestCase):
    def setUp(self):
        self.session = Session()
        self.session.record_telemetry({"device": "esp32-c3", "mode": "TEST", "uptime_ms": 1234, "sequence": 4, "sequence_gap": 2})
        self.session.record_sample(Measurement(ChannelMode.TEST, -75.25, -61.5, 52.75))

    def test_defaults_and_state_serialization(self):
        self.assertEqual(DEFAULT_WEB_BIND, "127.0.0.1")
        state = serialize_state(self.session, "CONNECTED", "RECEIVING")
        self.assertEqual(state["device"]["sequence_gaps"], 2)
        self.assertEqual(state["session"]["test_samples"], 1)
        self.assertEqual(state["simulated_rf"]["rssi_dbm"], -75.25)
        self.assertIn("SOFTWARE-SIMULATED", state["simulated_rf"]["label"])
        self.assertNotIn("password", str(state).lower())

    def test_chart_history_is_bounded(self):
        session = Session(history_size=3)
        for value in range(5):
            session.record_sample(Measurement(ChannelMode.NORMAL, float(value), -90.0, 99.0))
        self.assertEqual([point["rssi"] for point in serialize_state(session)["history"]], [2.0, 3.0, 4.0])

    def test_page_and_api_make_simulated_boundary_obvious(self):
        client = create_app(self.session, lambda: ("CONNECTED", "RECEIVING")).test_client()
        page = client.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"REAL DEVICE/CONTROL TELEMETRY", page.data)
        self.assertIn(b"SOFTWARE-SIMULATED RF METRICS", page.data)
        response = client.get("/api/state")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["connection"]["udp"], "RECEIVING")

    def test_unavailable_state_is_safe(self):
        response = create_app(None).test_client().get("/api/state")
        self.assertEqual(response.status_code, 503)
        self.assertIn("unavailable", response.get_json()["error"])

    def test_controls_are_allowlisted_and_use_handler(self):
        commands = []
        client = create_app(self.session, command_handler=commands.append).test_client()
        for command in ("STATUS", "ON", "OFF"):
            response = client.post("/api/control", json={"command": command})
            self.assertEqual(response.status_code, 200)
        self.assertEqual(commands, ["STATUS", "ON", "OFF"])
        for payload in ({"command": "RESET"}, {"command": "ON\nSTATUS"}, {"raw": "ON"}, {}):
            self.assertEqual(client.post("/api/control", json=payload).status_code, 400)

    def test_controls_report_unavailable_and_handler_errors(self):
        self.assertEqual(create_app(self.session).test_client().post("/api/control", json={"command": "ON"}).status_code, 409)
        def fail(_command): raise RuntimeError("offline")
        response = create_app(self.session, command_handler=fail).test_client().post("/api/control", json={"command": "STATUS"})
        self.assertEqual(response.status_code, 503)


if __name__ == "__main__": unittest.main()
