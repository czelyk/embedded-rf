"""Offline analysis for embedded-rf CSV sessions.

All RF fields handled here are software-generated simulated values, never ESP32
RF measurements.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path
import statistics
from typing import Iterable

from .session import CSV_FIELDS, format_duration

RF_FIELDS = ("simulated_rssi_dbm", "simulated_noise_dbm", "simulated_packet_success_percent")
VALID_EVENTS = frozenset({"sample", "telemetry", "control"})
VALID_MODES = frozenset({"NORMAL", "TEST"})


class AnalysisError(RuntimeError):
    """A readable error for invalid or inaccessible session data."""


@dataclass(frozen=True)
class AnalysisRow:
    line_number: int
    timestamp: datetime | None
    event: str
    device: str
    mode: str
    uptime_ms: int | None
    sequence: int | None
    simulated_rssi_dbm: float | None
    simulated_noise_dbm: float | None
    simulated_packet_success_percent: float | None


@dataclass
class LoadedSession:
    path: Path
    rows: list[AnalysisRow]
    issues: list[str]


@dataclass(frozen=True)
class MetricStatistics:
    count: int
    minimum: float | None
    average: float | None
    maximum: float | None
    standard_deviation: float | None


@dataclass(frozen=True)
class ModeStatistics:
    name: str
    sample_count: int
    duration_seconds: float | None
    rssi: MetricStatistics
    noise: MetricStatistics
    success: MetricStatistics


@dataclass(frozen=True)
class TelemetryStatistics:
    count: int
    sequence_gaps: int
    duplicate_sequences: int
    sequence_resets: int


@dataclass(frozen=True)
class SessionAnalysis:
    session: LoadedSession
    duration_seconds: float | None
    total_rows: int
    sample_count: int
    telemetry_count: int
    control_count: int
    unknown_event_count: int
    telemetry: TelemetryStatistics
    overall: ModeStatistics
    normal: ModeStatistics
    test: ModeStatistics


def _parse_timestamp(value: str, issue: str, issues: list[str]) -> datetime | None:
    if not value: return None
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if timestamp.tzinfo is None:
            issues.append(issue + " has a timestamp without timezone")
            return None
        return timestamp
    except ValueError:
        issues.append(issue + " has an invalid timestamp")
        return None


def _parse_integer(value: str, name: str, issue: str, issues: list[str]) -> int | None:
    if not value: return None
    try:
        number = int(value)
        if number < 0:
            issues.append(f"{issue} has negative {name}")
            return None
        return number
    except ValueError:
        issues.append(f"{issue} has invalid {name}")
        return None


def _parse_float(value: str, name: str, issue: str, issues: list[str]) -> float | None:
    if not value: return None
    try:
        number = float(value)
        if not math.isfinite(number):
            issues.append(f"{issue} has non-finite {name}")
            return None
        return number
    except ValueError:
        issues.append(f"{issue} has invalid {name}")
        return None


def load_session_csv(path: str | Path) -> LoadedSession:
    """Load Milestone 3 CSV data, retaining good rows and reporting bad fields."""
    source, issues, rows = Path(path), [], []
    try:
        with source.open(newline="", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None: raise AnalysisError(f"Session CSV is empty: {source}")
            missing = [field for field in CSV_FIELDS if field not in reader.fieldnames]
            if missing: raise AnalysisError(f"Session CSV is missing required columns: {', '.join(missing)}")
            for line_number, raw in enumerate(reader, start=2):
                issue = f"Row {line_number}"
                event, mode = (raw.get("event") or "").strip(), (raw.get("mode") or "").strip().upper()
                if event not in VALID_EVENTS: issues.append(f"{issue} has unknown event {event or '<empty>'}")
                if mode and mode not in VALID_MODES: issues.append(f"{issue} has unknown mode {mode}")
                rows.append(AnalysisRow(
                    line_number, _parse_timestamp(raw.get("timestamp", ""), issue, issues), event,
                    (raw.get("device") or "").strip(), mode,
                    _parse_integer(raw.get("uptime_ms", ""), "uptime_ms", issue, issues),
                    _parse_integer(raw.get("sequence", ""), "sequence", issue, issues),
                    _parse_float(raw.get("simulated_rssi_dbm", ""), "simulated_rssi_dbm", issue, issues),
                    _parse_float(raw.get("simulated_noise_dbm", ""), "simulated_noise_dbm", issue, issues),
                    _parse_float(raw.get("simulated_packet_success_percent", ""), "simulated_packet_success_percent", issue, issues),
                ))
    except FileNotFoundError as error:
        raise AnalysisError(f"Session CSV was not found: {source}") from error
    except OSError as error:
        raise AnalysisError(f"Could not read session CSV {source}: {error}") from error
    return LoadedSession(source, rows, issues)


def _metric(values: Iterable[float | None]) -> MetricStatistics:
    data = [value for value in values if value is not None]
    if not data: return MetricStatistics(0, None, None, None, None)
    return MetricStatistics(len(data), min(data), statistics.fmean(data), max(data), statistics.pstdev(data) if len(data) > 1 else None)


def _mode_duration(rows: list[AnalysisRow], mode: str) -> float | None:
    timed = [row for row in rows if row.timestamp is not None and row.mode in VALID_MODES]
    if len(timed) < 2: return None
    timed.sort(key=lambda row: (row.timestamp, row.line_number))
    total = 0.0
    for current, following in zip(timed, timed[1:]):
        if current.mode == mode:
            total += max(0.0, (following.timestamp - current.timestamp).total_seconds())
    return total


def _mode_statistics(rows: list[AnalysisRow], name: str, duration: float | None) -> ModeStatistics:
    samples = [row for row in rows if row.event == "sample" and (name == "OVERALL" or row.mode == name)]
    return ModeStatistics(name, len(samples), duration,
                          _metric(row.simulated_rssi_dbm for row in samples),
                          _metric(row.simulated_noise_dbm for row in samples),
                          _metric(row.simulated_packet_success_percent for row in samples))


def _telemetry_statistics(rows: list[AnalysisRow]) -> TelemetryStatistics:
    packets = [row for row in rows if row.event == "telemetry" and row.sequence is not None]
    gaps = duplicates = resets = 0
    previous = None
    for packet in packets:
        if previous is not None:
            if packet.sequence == previous: duplicates += 1
            elif packet.sequence < previous: resets += 1
            else: gaps += packet.sequence - previous - 1
        previous = packet.sequence
    return TelemetryStatistics(len(packets), gaps, duplicates, resets)


def analyze_session(session: LoadedSession) -> SessionAnalysis:
    timestamps = [row.timestamp for row in session.rows if row.timestamp is not None]
    duration = (max(timestamps) - min(timestamps)).total_seconds() if len(timestamps) >= 2 else None
    event_counts = {event: sum(row.event == event for row in session.rows) for event in VALID_EVENTS}
    return SessionAnalysis(
        session, duration, len(session.rows), event_counts["sample"], event_counts["telemetry"], event_counts["control"],
        len(session.rows) - sum(event_counts.values()), _telemetry_statistics(session.rows),
        _mode_statistics(session.rows, "OVERALL", duration),
        _mode_statistics(session.rows, "NORMAL", _mode_duration(session.rows, "NORMAL")),
        _mode_statistics(session.rows, "TEST", _mode_duration(session.rows, "TEST")),
    )


def _number(value: float | None, suffix: str = "") -> str:
    return "N/A" if value is None else f"{value:.2f}{suffix}"


def _metric_lines(label: str, metric: MetricStatistics, suffix: str) -> list[str]:
    if not metric.count: return [f"{label}: N/A"]
    return [f"{label} min/avg/max: {_number(metric.minimum, suffix)} / {_number(metric.average, suffix)} / {_number(metric.maximum, suffix)} (n={metric.count}, stddev={_number(metric.standard_deviation, suffix)})"]


def format_mode_comparison(analysis: SessionAnalysis) -> str:
    lines = ["SIMULATED RF comparison", "Metric                     NORMAL          TEST            TEST - NORMAL"]
    for label, attr, suffix in (("RSSI average", "rssi", " dBm"), ("Noise average", "noise", " dBm"), ("Packet success average", "success", " %")):
        normal, test = getattr(analysis.normal, attr).average, getattr(analysis.test, attr).average
        difference = test - normal if normal is not None and test is not None else None
        lines.append(f"{label:<26} {_number(normal, suffix):<15} {_number(test, suffix):<15} {_number(difference, suffix)}")
    lines.append("Differences describe software-simulated values only; they are not physical RF measurements.")
    return "\n".join(lines)


def format_analysis(analysis: SessionAnalysis) -> str:
    lines = ["embedded-rf Session Analysis", "============================", f"Source: {analysis.session.path}",
             f"Duration: {format_duration(analysis.duration_seconds) if analysis.duration_seconds is not None else 'N/A'}",
             f"Rows: {analysis.total_rows}  Samples: {analysis.sample_count}  Telemetry: {analysis.telemetry_count}  Control: {analysis.control_count}",
             f"Telemetry sequence gaps: {analysis.telemetry.sequence_gaps}  Duplicates: {analysis.telemetry.duplicate_sequences}  Resets: {analysis.telemetry.sequence_resets}", ""]
    for mode in (analysis.overall, analysis.normal, analysis.test):
        lines.extend([mode.name, "-" * len(mode.name), f"Sample count: {mode.sample_count}", f"Duration: {format_duration(mode.duration_seconds) if mode.duration_seconds is not None else 'N/A'}"])
        lines.extend(_metric_lines("SIMULATED RSSI", mode.rssi, " dBm"))
        lines.extend(_metric_lines("SIMULATED noise", mode.noise, " dBm"))
        lines.extend(_metric_lines("SIMULATED packet success", mode.success, " %"))
        lines.append("")
    lines.extend([format_mode_comparison(analysis), ""])
    if analysis.session.issues: lines.append(f"Data quality: {len(analysis.session.issues)} malformed/unknown field(s) retained as unavailable.")
    lines.append("RF metrics in this report are software-simulated values and are not physical RF measurements from the ESP32.")
    return "\n".join(lines)


def format_multi_session_comparison(analyses: list[SessionAnalysis]) -> str:
    lines = ["Multi-session comparison (SIMULATED RF)", "Session | Samples | Telemetry | Gaps | NORMAL/TEST | RSSI avg | Noise avg | Success avg"]
    for analysis in analyses:
        overall = analysis.overall
        lines.append(f"{analysis.session.path.name} | {analysis.sample_count} | {analysis.telemetry_count} | {analysis.telemetry.sequence_gaps} | {analysis.normal.sample_count}/{analysis.test.sample_count} | {_number(overall.rssi.average, ' dBm')} | {_number(overall.noise.average, ' dBm')} | {_number(overall.success.average, ' %')}")
    lines.append("Values are descriptive software-simulated metrics, not ESP32 RF measurements.")
    return "\n".join(lines)


def generate_plots(analysis: SessionAnalysis, output_dir: str | Path) -> list[Path]:
    """Write headless-safe PNG time series and return their paths."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        from matplotlib import pyplot as plt
    except ImportError as error:
        raise AnalysisError("Plotting requires matplotlib; install requirements.txt") from error
    timed_samples = [row for row in analysis.session.rows if row.event == "sample" and row.timestamp is not None]
    if not timed_samples: raise AnalysisError("Cannot plot: session has no timestamped SIMULATED RF samples")
    target = Path(output_dir)
    try: target.mkdir(parents=True, exist_ok=True)
    except OSError as error: raise AnalysisError(f"Could not create plot directory {target}: {error}") from error
    start = min(row.timestamp for row in timed_samples)
    elapsed = [(row.timestamp - start).total_seconds() for row in timed_samples]
    outputs = []
    for field, title, ylabel, filename in (
        ("simulated_rssi_dbm", "SIMULATED RSSI over time", "SIMULATED RSSI (dBm)", "simulated_rssi.png"),
        ("simulated_noise_dbm", "SIMULATED noise over time", "SIMULATED noise (dBm)", "simulated_noise.png"),
        ("simulated_packet_success_percent", "SIMULATED packet success over time", "SIMULATED packet success (%)", "simulated_packet_success.png"),
    ):
        figure, axis = plt.subplots()
        for mode, color in (("NORMAL", "tab:blue"), ("TEST", "tab:orange")):
            points = [(x, getattr(row, field)) for x, row in zip(elapsed, timed_samples) if row.mode == mode and getattr(row, field) is not None]
            if points: axis.plot(*zip(*points), marker="o", linestyle="-", label=mode, color=color)
        axis.set(title=title, xlabel="Elapsed time (s)", ylabel=ylabel); axis.grid(True, alpha=.3); axis.legend()
        path = target / filename; figure.tight_layout(); figure.savefig(path, dpi=140); plt.close(figure); outputs.append(path)
    mode_rows = [row for row in analysis.session.rows if row.timestamp is not None and row.mode in VALID_MODES]
    if mode_rows:
        start = min(row.timestamp for row in mode_rows)
        values = [1 if row.mode == "TEST" else 0 for row in mode_rows]
        figure, axis = plt.subplots(); axis.step([(row.timestamp - start).total_seconds() for row in mode_rows], values, where="post")
        axis.set(title="Device mode over time", xlabel="Elapsed time (s)", ylabel="Mode", yticks=[0, 1], yticklabels=["NORMAL", "TEST"]); axis.grid(True, alpha=.3)
        path = target / "mode_timeline.png"; figure.tight_layout(); figure.savefig(path, dpi=140); plt.close(figure); outputs.append(path)
    return outputs


def write_markdown_report(analysis: SessionAnalysis, path: str | Path, plots: Iterable[Path] = (), comparisons: list[SessionAnalysis] | None = None) -> Path:
    target = Path(path)
    lines = ["# embedded-rf Session Analysis", "", "RF metrics in this report are software-simulated values and are not physical RF measurements from the ESP32.", "", "## Session information", "", f"- Source: `{analysis.session.path}`", f"- Duration: {format_duration(analysis.duration_seconds) if analysis.duration_seconds is not None else 'N/A'}", f"- Rows: {analysis.total_rows}; samples: {analysis.sample_count}; telemetry: {analysis.telemetry_count}; control: {analysis.control_count}", "", "## Mode distribution", "", f"- NORMAL samples: {analysis.normal.sample_count}; duration: {format_duration(analysis.normal.duration_seconds) if analysis.normal.duration_seconds is not None else 'N/A'}", f"- TEST samples: {analysis.test.sample_count}; duration: {format_duration(analysis.test.duration_seconds) if analysis.test.duration_seconds is not None else 'N/A'}", "", "## SIMULATED RF summary", "", "```text", format_analysis(analysis), "```", "", "## NORMAL vs TEST", "", "```text", format_mode_comparison(analysis), "```", "", "## Telemetry quality", "", f"- Sequence gaps: {analysis.telemetry.sequence_gaps}", f"- Duplicate sequences: {analysis.telemetry.duplicate_sequences}", f"- Sequence resets: {analysis.telemetry.sequence_resets}"]
    if comparisons:
        lines.extend(["", "## Multi-session comparison", "", "```text", format_multi_session_comparison([analysis, *comparisons]), "```"])
    lines.extend(["", "## Generated plots", ""])
    plot_list = list(plots)
    lines.extend([f"- [{plot.name}]({plot.name})" for plot in plot_list] or ["- None generated."])
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except OSError as error: raise AnalysisError(f"Could not write report {target}: {error}") from error
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze embedded-rf CSV sessions; RF values are SIMULATED.")
    parser.add_argument("session", help="Milestone 3 CSV session")
    parser.add_argument("--summary", action="store_true", help="print summary (the default)")
    parser.add_argument("--plot", action="store_true", help="write headless PNG plots")
    parser.add_argument("--output-dir", default="analysis", help="directory for generated plots")
    parser.add_argument("--compare", action="append", default=[], metavar="CSV", help="compare another session (repeatable)")
    parser.add_argument("--report", help="write a Markdown analysis report")
    args = parser.parse_args()
    try:
        analysis = analyze_session(load_session_csv(args.session))
        comparisons = [analyze_session(load_session_csv(path)) for path in args.compare]
        plots = generate_plots(analysis, args.output_dir) if args.plot else []
        print(format_analysis(analysis))
        if comparisons: print("\n" + format_multi_session_comparison([analysis, *comparisons]))
        if args.report: print(f"Report written: {write_markdown_report(analysis, args.report, plots, comparisons)}")
        if plots: print("Plots written: " + ", ".join(str(path) for path in plots))
    except AnalysisError as error:
        print(f"Analysis error: {error}")
        return 2
    return 0


if __name__ == "__main__": raise SystemExit(main())
