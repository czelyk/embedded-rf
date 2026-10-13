"""Synthetic RF channel measurements; this module never accesses radio hardware."""
from dataclasses import dataclass
from enum import Enum
import random

class ChannelMode(str, Enum):
    NORMAL = "NORMAL"
    TEST = "TEST"

@dataclass(frozen=True)
class Measurement:
    mode: ChannelMode
    rssi_dbm: float
    noise_dbm: float
    packet_success_percent: float

class RFChannelSimulator:
    """Produces bounded pseudo-random, explicitly simulated channel values."""
    RANGES = {
        ChannelMode.NORMAL: {"rssi": (-72.0, -45.0), "noise": (-101.0, -88.0), "success": (94.0, 100.0)},
        ChannelMode.TEST: {"rssi": (-92.0, -65.0), "noise": (-82.0, -68.0), "success": (35.0, 82.0)},
    }
    def __init__(self, mode: ChannelMode = ChannelMode.NORMAL, rng: random.Random | None = None):
        self._mode = mode
        self._rng = rng or random.Random()
    @property
    def mode(self) -> ChannelMode:
        return self._mode
    def set_mode(self, mode: ChannelMode | str) -> ChannelMode:
        self._mode = ChannelMode(mode.upper())
        return self._mode
    def enable_test_mode(self) -> ChannelMode:
        return self.set_mode(ChannelMode.TEST)
    def disable_test_mode(self) -> ChannelMode:
        return self.set_mode(ChannelMode.NORMAL)
    def measure(self) -> Measurement:
        bounds = self.RANGES[self._mode]
        return Measurement(self._mode, round(self._rng.uniform(*bounds["rssi"]), 1), round(self._rng.uniform(*bounds["noise"]), 1), round(self._rng.uniform(*bounds["success"]), 1))
