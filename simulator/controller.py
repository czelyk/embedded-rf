"""Serial protocol parsing and optional pyserial transport."""
from collections.abc import Callable
from .channel import ChannelMode, RFChannelSimulator

def apply_serial_line(line: str, simulator: RFChannelSimulator) -> str | None:
    """Apply an ESP32 command or MODE response; unknown input does not alter state."""
    mapping = {"ON": ChannelMode.TEST, "OFF": ChannelMode.NORMAL, "MODE:TEST": ChannelMode.TEST, "MODE:NORMAL": ChannelMode.NORMAL}
    mode = mapping.get(line.strip().upper())
    if mode is None:
        return None
    simulator.set_mode(mode)
    return f"Simulator mode set to {mode.value}"

class SerialController:
    """pyserial wrapper; it contains no RF functionality."""
    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 0.2):
        self.port, self.baudrate, self.timeout, self._serial = port, baudrate, timeout, None
    def connect(self) -> None:
        try:
            import serial
            self._serial = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        except ImportError as error:
            raise RuntimeError("pyserial is required for --port; install requirements.txt") from error
        except Exception as error:
            raise RuntimeError(f"Could not open serial port {self.port}: {error}") from error
    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._serial = None
    def send_command(self, command: str) -> None:
        """Send one supported newline-delimited command to the ESP32."""
        if self._serial is None:
            raise RuntimeError("Serial port is not connected")
        normalized = command.strip().upper()
        if normalized not in {"ON", "OFF", "STATUS"}:
            raise ValueError("Command must be ON, OFF, or STATUS")
        try:
            self._serial.write((normalized + "\n").encode("ascii"))
            self._serial.flush()
        except Exception as error:
            raise RuntimeError(f"Serial write failed: {error}") from error
    def poll(self, on_line: Callable[[str], None]) -> None:
        if self._serial is None:
            raise RuntimeError("Serial port is not connected")
        try:
            raw = self._serial.readline()
        except Exception as error:
            raise RuntimeError(f"Serial connection lost: {error}") from error
        if raw:
            on_line(raw.decode("utf-8", errors="replace").strip())
