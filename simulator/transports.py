"""Newline-delimited TCP control transport for the ESP32 simulator."""
import socket

VALID_COMMANDS = frozenset({"ON", "OFF", "STATUS"})

def normalize_command(command: str) -> str:
    normalized = command.strip().upper()
    if normalized not in VALID_COMMANDS:
        raise ValueError("Command must be ON, OFF, or STATUS")
    return normalized

class LineFramer:
    """Bounds incoming TCP lines and supports fragmented or coalesced packets."""
    def __init__(self, max_length: int = 96):
        self.max_length, self.buffer, self.discarding = max_length, bytearray(), False
    def feed(self, data: bytes) -> list[str]:
        lines = []
        for byte in data:
            if byte == 10:
                if not self.discarding:
                    lines.append(self.buffer.decode("ascii", errors="replace").strip())
                self.buffer.clear(); self.discarding = False
            elif byte != 13 and not self.discarding:
                if len(self.buffer) >= self.max_length: self.buffer.clear(); self.discarding = True
                else: self.buffer.append(byte)
        return lines

class TcpController:
    """TCP equivalent of SerialController; no RF data is exchanged here."""
    def __init__(self, host: str, port: int = 8765, timeout: float = 0.2):
        self.host, self.port, self.timeout = host, port, timeout
        self._socket = None
        self._framer = LineFramer()
    def connect(self) -> None:
        try:
            self._socket = socket.create_connection((self.host, self.port), timeout=self.timeout)
            self._socket.settimeout(self.timeout)
        except OSError as error:
            raise RuntimeError(f"Could not connect to TCP controller {self.host}:{self.port}: {error}") from error
    def close(self) -> None:
        if self._socket is not None:
            self._socket.close(); self._socket = None
    def send_command(self, command: str) -> None:
        normalized = normalize_command(command)
        if self._socket is None: raise RuntimeError("TCP controller is not connected")
        try: self._socket.sendall((normalized + "\n").encode("ascii"))
        except OSError as error: raise RuntimeError(f"TCP write failed: {error}") from error
    def poll(self, on_line) -> None:
        if self._socket is None: raise RuntimeError("TCP controller is not connected")
        try: data = self._socket.recv(256)
        except socket.timeout: return
        except OSError as error: raise RuntimeError(f"TCP connection lost: {error}") from error
        if not data: raise RuntimeError("TCP controller disconnected")
        for line in self._framer.feed(data):
            if line: on_line(line)
