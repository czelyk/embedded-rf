import random
import unittest
from unittest.mock import patch
from simulator.rf_channel_sim import RFChannelSimulator, LineDecoder, handle_command, serial_loop, main


class SimulatorTests(unittest.TestCase):
    def test_ranges_and_modes(self):
        channel = RFChannelSimulator(random.Random(3))
        for mode, ranges in ((False, ((-60, -45), (-95, -85), (95, 100))),
                             (True, ((-85, -70), (-65, -55), (40, 75)))):
            channel.set_test_mode(mode)
            for _ in range(100):
                for value, (lo, hi) in zip(channel.measure().values(), ranges):
                    self.assertTrue(lo <= value <= hi)

    def test_commands(self):
        channel = RFChannelSimulator()
        for command in ('on', 'TEST ON', 'STATE ON'):
            handle_command(channel, command)
            self.assertTrue(channel.test_mode)
            self.assertIn('[TEST]', handle_command(channel, 'status'))
            handle_command(channel, 'STATE OFF')
            self.assertFalse(channel.test_mode)
        self.assertIsNone(handle_command(channel, 'garbage'))

    def test_framing(self):
        decoder = LineDecoder()
        self.assertEqual(decoder.feed(b'STA'), [])
        self.assertEqual(decoder.feed(b'TE ON\r\nSTATUS\n'), ['STATE ON', 'STATUS'])
        self.assertEqual(decoder.feed(b'X' * 500 + b'TEST ON\n\xff\nSTATE OFF\n'), ['STATE OFF'])

    def test_serial_stream_and_disconnect(self):
        class FakePort:
            def __init__(self):
                self.parts = iter([b'boot noise\nSTATUS\nSTA', b'TE ON\nSTATUS\n', b'STATE OFF\nSTATUS\n'])
                self.writes = []
            def write(self, data):
                self.writes.append(data)
            def read(self, size):
                try:
                    return next(self.parts)
                except StopIteration:
                    raise OSError('disconnected')
        channel, port = RFChannelSimulator(), FakePort()
        with patch('builtins.print') as output, self.assertRaises(OSError):
            serial_loop(channel, port)
        text = ' '.join(str(call) for call in output.call_args_list)
        self.assertIn('[TEST]', text)
        self.assertIn('[NORMAL]', text)
        self.assertFalse(channel.test_mode)
        self.assertEqual(port.writes, [b'STATUS\n'])

    def test_handshake_timeout(self):
        from unittest.mock import Mock
        with patch('simulator.rf_channel_sim.time.monotonic', side_effect=[0, 0, 6]):
            with self.assertRaisesRegex(OSError, 'No controller'):
                serial_loop(RFChannelSimulator(), Mock(read=lambda n: b''))

    def test_manual_quit(self):
        with patch('builtins.input', side_effect=['on', 'status', 'off', 'quit']), patch('builtins.print'):
            self.assertEqual(main([]), 0)


if __name__ == '__main__':
    unittest.main()
