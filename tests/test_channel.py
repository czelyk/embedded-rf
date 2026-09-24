import random
import unittest
from simulator.channel import ChannelMode, RFChannelSimulator
from simulator.controller import apply_serial_line

class ChannelSimulatorTests(unittest.TestCase):
    def test_normal_mode_measurement_ranges(self):
        simulator = RFChannelSimulator(rng=random.Random(1)); measurement = simulator.measure(); ranges = simulator.RANGES[ChannelMode.NORMAL]
        self.assertIs(measurement.mode, ChannelMode.NORMAL)
        self.assertTrue(ranges["rssi"][0] <= measurement.rssi_dbm <= ranges["rssi"][1])
        self.assertTrue(ranges["noise"][0] <= measurement.noise_dbm <= ranges["noise"][1])
        self.assertTrue(ranges["success"][0] <= measurement.packet_success_percent <= ranges["success"][1])

    def test_test_mode_measurement_ranges(self):
        simulator = RFChannelSimulator(rng=random.Random(2)); simulator.enable_test_mode(); measurement = simulator.measure(); ranges = simulator.RANGES[ChannelMode.TEST]
        self.assertIs(measurement.mode, ChannelMode.TEST)
        self.assertTrue(ranges["rssi"][0] <= measurement.rssi_dbm <= ranges["rssi"][1])
        self.assertTrue(ranges["noise"][0] <= measurement.noise_dbm <= ranges["noise"][1])
        self.assertTrue(ranges["success"][0] <= measurement.packet_success_percent <= ranges["success"][1])

    def test_on_off_protocol_transitions(self):
        simulator = RFChannelSimulator()
        self.assertEqual(apply_serial_line("ON", simulator), "Simulator mode set to TEST"); self.assertIs(simulator.mode, ChannelMode.TEST)
        self.assertEqual(apply_serial_line("MODE:NORMAL", simulator), "Simulator mode set to NORMAL"); self.assertIs(simulator.mode, ChannelMode.NORMAL)

    def test_unknown_protocol_line_does_not_change_state(self):
        simulator = RFChannelSimulator()
        self.assertIsNone(apply_serial_line("ERR:UNKNOWN_COMMAND", simulator)); self.assertIs(simulator.mode, ChannelMode.NORMAL)
