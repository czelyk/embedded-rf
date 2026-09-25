"""Session records, CSV output, and statistics for simulated RF sessions."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import time

from .channel import Measurement

CSV_FIELDS = (
    "timestamp", "event", "device", "mode", "uptime_ms", "sequence",
    "simulated_rssi_dbm", "simulated_noise_dbm", "simulated_packet_success_percent",
)


@dataclass(frozen=True)
class SessionRecord:
    timestamp: str
    event: str
    device: str
    mode: str
    uptime_ms: int | None
    sequence: int | None
    simulated_rssi_dbm: float | None
    simulated_noise_dbm: float | None
    simulated_packet_success_percent: float | None

    def as_csv_row(self) -> dict[str, object | str]:
        return {field: "" if getattr(self, field) is None else getattr(self, field) for field in CSV_FIELDS}


class SessionLogError(RuntimeError):
    """Raised when a requested CSV session log cannot be safely written."""


class CsvSessionWriter:
    """A flushed CSV writer that owns its file handle."""
    def __init__(self, path: str | Path):
        self.path = Path(path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._file = self.path.open("w", newline="", encoding="utf-8")
            self._writer = csv.DictWriter(self._file, fieldnames=CSV_FIELDS)
            self._writer.writeheader()
            self._file.flush()
        except OSError as error:
            raise SessionLogError(f"Could not create CSV log {self.path}: {error}") from error

    def write(self, record: SessionRecord) -> None:
        try:
            self._writer.writerow(record.as_csv_row())
            self._file.flush()
        except OSError as error:
            raise SessionLogError(f"Could not write CSV log {self.path}: {error}") from error

    def close(self) -> None:
        if getattr(self, "_file", None) is not None:
            self._file.close()
            self._file = None


@dataclass
class NumericStats:
    count: int = 0
    total: float = 0.0
    minimum: float | None = None
    maximum: float | None = None

    def add(self, value: float) -> None:
        self.count += 1
        self.total += value
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)

    @property
    def average(self) -> float | None:
        return self.total / self.count if self.count else None


class SessionStatistics:
    """Accumulates sample and device-telemetry statistics independently."""
    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self.started_at = clock()
        self.samples = self.normal_samples = self.test_samples = 0
        self.telemetry_packets = self.sequence_gaps = 0
        self.rssi, self.noise, self.success = NumericStats(), NumericStats(), NumericStats()
        self._mode = "NORMAL"
        self._mode_since = self.started_at
        self.normal_seconds = self.test_seconds = 0.0

    def set_mode(self, mode: str) -> None:
        mode = mode.upper()
        if mode not in {"NORMAL", "TEST"}: return
        now = self._clock()
        elapsed = now - self._mode_since
        if self._mode == "NORMAL": self.normal_seconds += elapsed
        else: self.test_seconds += elapsed
        self._mode, self._mode_since = mode, now

    def record_sample(self, measurement: Measurement) -> None:
        self.set_mode(measurement.mode.value)
        self.samples += 1
        if measurement.mode.value == "NORMAL": self.normal_samples += 1
        else: self.test_samples += 1
        self.rssi.add(measurement.rssi_dbm)
        self.noise.add(measurement.noise_dbm)
        self.success.add(measurement.packet_success_percent)

    def record_telemetry(self, packet: dict[str, object]) -> None:
        self.telemetry_packets += 1
        self.sequence_gaps += int(packet.get("sequence_gap", 0))
        self.set_mode(str(packet["mode"]))

    def duration_seconds(self) -> float:
        return self._clock() - self.started_at

    def mode_seconds(self) -> tuple[float, float]:
        now = self._clock()
        normal, test = self.normal_seconds, self.test_seconds
        if self._mode == "NORMAL": normal += now - self._mode_since
        else: test += now - self._mode_since
        return normal, test


class Session:
    """Combines device state and explicitly simulated RF samples into records."""
    def __init__(self, statistics: SessionStatistics | None = None):
        self.statistics = statistics or SessionStatistics()
        self.device, self.mode = "manual", "NORMAL"
        self.uptime_ms: int | None = None
        self.sequence: int | None = None
        self.last_measurement: Measurement | None = None

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    def _record(self, event: str) -> SessionRecord:
        measurement = self.last_measurement
        return SessionRecord(
            self._timestamp(), event, self.device, self.mode, self.uptime_ms, self.sequence,
            measurement.rssi_dbm if measurement else None,
            measurement.noise_dbm if measurement else None,
            measurement.packet_success_percent if measurement else None,
        )

    def record_telemetry(self, packet: dict[str, object]) -> SessionRecord:
        self.device, self.mode = str(packet["device"]), str(packet["mode"])
        self.uptime_ms, self.sequence = int(packet["uptime_ms"]), int(packet["sequence"])
        self.statistics.record_telemetry(packet)
        return self._record("telemetry")

    def record_sample(self, measurement: Measurement) -> SessionRecord:
        self.mode = measurement.mode.value
        self.last_measurement = measurement
        self.statistics.record_sample(measurement)
        return self._record("sample")

    def record_mode_update(self, mode: str) -> SessionRecord:
        """Record a Serial/TCP mode response without mislabeling it as RF data."""
        self.mode = mode.upper()
        self.statistics.set_mode(self.mode)
        return self._record("control")


def format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    return f"{total // 3600:02d}:{(total // 60) % 60:02d}:{total % 60:02d}"


def format_summary(session: Session, csv_path: str | Path | None = None) -> str:
    stats = session.statistics
    def numeric(label: str, values: NumericStats, suffix: str = "") -> str:
        if values.count == 0: return f"{label}: no samples"
        return f"{label} min/avg/max: {values.minimum:.1f}/{values.average:.1f}/{values.maximum:.1f}{suffix}"
    lines = [
        "Session summary", "---------------", f"Duration: {format_duration(stats.duration_seconds())}",
        f"Samples: {stats.samples}", f"NORMAL: {stats.normal_samples}", f"TEST: {stats.test_samples}",
        f"UDP packets: {stats.telemetry_packets}", f"Sequence gaps: {stats.sequence_gaps}", "",
        "SIMULATED RF", numeric("RSSI", stats.rssi, " dBm"), numeric("Noise", stats.noise, " dBm"),
        numeric("Packet success", stats.success, " %"),
    ]
    if csv_path is not None: lines.extend(["", f"CSV log: {csv_path}"])
    return "\n".join(lines)
