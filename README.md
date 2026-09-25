# embedded-rf

`embedded-rf` is a safe, simulation-only ESP32-controlled RF-channel training platform. It models RSSI, noise, and packet success in Python; it does **not** measure, transmit, jam, interfere with, or otherwise operate on real RF signals.

## Quick Start

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd firmware/esp32_controller && pio run
cp include/wifi_config.example.h include/wifi_config.h
# Fill only local ignored wifi_config.h; never commit it.
pio run -t upload
cd ../..
.venv/bin/python -m simulator.main --host ESP32_IP --dashboard --csv logs/session.csv
```

Stop cleanly with Ctrl+C, then run `.venv/bin/python -m simulator.analysis logs/session.csv --plot --output-dir analysis/session --report analysis/session/report.md`. Run `.venv/bin/python -m unittest discover -s tests -v` for regression. `ESP32_IP` is the safe status value printed by the board; do not put credentials in tracked files.

## Architecture

```text
ESP32-C3 -- USB Serial / Wi-Fi TCP --> Python controller --> RF channel simulator
    |                                      |                    `- SIMULATED RF values
    `-------------- Wi-Fi UDP ------------> UDP telemetry receiver
```

See [the architecture document](docs/architecture.md) for the data flow.

## Repository layout

- `firmware/esp32_controller/` — ESP32-C3 Serial/Wi-Fi/TCP/UDP state controller
- `simulator/` — Python synthetic channel model and CLI
- `tests/` — hardware-independent simulator tests
- `docs/` — design documentation

## Requirements

- Python 3.10+
- `pip install -r requirements.txt` for physical serial support
- PlatformIO (tested with the `esp32-c3-devkitc-02` board definition)

Create an isolated environment; no system Python packages need to be changed:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Run without an ESP32

```bash
.venv/bin/python -m simulator.main --manual
```

Enter `ON` for TEST, `OFF` for NORMAL, `STATUS` to show state, or `QUIT` to exit. All values are explicitly synthetic.

For a live terminal display and a CSV session record:

```bash
.venv/bin/python -m simulator.main --manual --dashboard --csv logs/manual.csv
```

The dashboard is optional and uses only normal terminal escape sequences. Its RF
section is always headed **SIMULATED RF**: those values are Python-generated,
not measurements reported by an ESP32.

## Connect an ESP32

1. Connect an ESP32-C3-DevKitC-02 v1.1 with its USB data cable.
2. Build and upload with PlatformIO:
   ```bash
   cd firmware/esp32_controller
   pio run
   pio run -t upload
   ```
3. Return to the repository root and run (Linux example):
   ```bash
   .venv/bin/python -m simulator.main --port /dev/ttyUSB0
   ```

The application can also send commands itself. This finite command sequence is useful for a repeatable integration test:

```bash
.venv/bin/python -m simulator.main --port /dev/ttyUSB0 --command STATUS --command ON --command STATUS --command OFF --count 8 --interval 0.1
```

## Build/upload

`firmware/esp32_controller/platformio.ini` specifies `board = esp32-c3-devkitc-02`, 115200 baud, and `/dev/ttyUSB0` for upload/monitor. The active PlatformIO source is `src/main.cpp`; it uses only `Serial` and includes no RF library or radio configuration.

For a manual serial check, first ensure no terminal/monitor holds `/dev/ttyUSB0`, then run `pio device monitor --baud 115200` from the firmware directory. On reset it prints `ESP32_SIM_CONTROLLER:READY` and `MODE:NORMAL`; send each command followed by Enter. Exit the monitor before starting Python.

## Wi-Fi, TCP, and UDP

Copy `firmware/esp32_controller/include/wifi_config.example.h` to
`wifi_config.h` in the same directory and enter your local SSID, password, and
the Linux host/IP for telemetry. The real config file is ignored by Git. With no
credentials configured, the firmware still builds and Serial still works; it
prints `WIFI:CONFIG_REQUIRED`.

After upload, Serial prints `WIFI:CONNECTING` and then `WIFI:CONNECTED IP:...`.
The ESP32 runs a newline-delimited TCP control server on port `8765` by default:

```bash
.venv/bin/python -m simulator.main --host ESP32_IP --tcp-port 8765 \
  --command STATUS --command ON --command STATUS --command OFF \
  --count 8 --interval 0.2
```

TCP uses the same `ON`, `OFF`, and `STATUS` protocol as Serial. USB Serial stays
available as a debug and fallback control channel. See [protocol details](docs/protocol.md).

The ESP32 may send device-state-only UDP telemetry every five seconds. Receive it
on the configured Linux host/port (default `8766`):

```bash
.venv/bin/python -m simulator.telemetry --bind 0.0.0.0 --port 8766
```

`DEVICE TELEMETRY` contains only device, mode, uptime, and sequence. It is never
an RF measurement; RSSI/noise/packet-success remain Python-generated `SIMULATED` data.

## Dashboard, CSV sessions, and statistics

When connecting over TCP, the main application can receive the ESP32's UDP
device-state telemetry itself. Do not run the standalone UDP receiver on the
same port at the same time. This command gives a live view and records both
device-state updates and simulated samples:

```bash
.venv/bin/python -m simulator.main --host ESP32_IP --tcp-port 8765 \
  --dashboard --csv logs/session.csv --command STATUS --command ON \
  --command STATUS --command OFF --count 30 --interval 1
```

`--udp-bind` and `--udp-port` select the local telemetry listener (default
`0.0.0.0:8766`); use `--no-udp` when no device telemetry is wanted. The
application owns one nonblocking listener, so the dashboard, CSV writer, and
statistics share the same received packets.

CSV files have a header and include timestamp, event type, device state
(`device`, `mode`, `uptime_ms`, `sequence`), and separately named
`simulated_*` RF fields. A row is flushed for each device telemetry update,
TCP/Serial mode update, and simulated sample. Parent directories are created as needed. The default
`logs/` location is Git-ignored; generated logs must not be committed.

On clean exit or Ctrl+C, a summary reports duration, NORMAL/TEST sample counts,
UDP packet and sequence-gap counts, and min/average/max **SIMULATED RF** values.

## Offline session analysis

Analyze a Milestone 3 CSV after recording; this is Python-side offline analysis
of software-generated values, not ESP32 RF measurement:

```bash
.venv/bin/python -m simulator.analysis logs/session.csv
```

The textual report separates OVERALL, NORMAL, and TEST samples, reports
telemetry sequence gaps/duplicates/resets, and compares NORMAL vs TEST averages
descriptively. Missing or malformed fields are reported as unavailable rather
than invented.

Create headless PNG time-series plots and a Markdown report (both output paths
are Git-ignored by default):

```bash
.venv/bin/python -m simulator.analysis logs/session.csv --plot \
  --output-dir analysis/session1 --report analysis/session1/report.md
```

Plots are titled and labelled **SIMULATED** and include RSSI (dBm), noise (dBm),
packet success (%), and a device-mode timeline. Compare recorded sessions with:

```bash
.venv/bin/python -m simulator.analysis logs/session1.csv --compare logs/session2.csv
```

Plotting uses `matplotlib`, included in `requirements.txt`; install it through
the existing `.venv/bin/python -m pip install -r requirements.txt` workflow.
All analysis reports explicitly state that RF metrics are software-simulated and
not physical RF measurements from the ESP32.

## Tests and troubleshooting

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m compileall -q simulator tests
cd firmware/esp32_controller && pio run
```

Use a USB data cable, verify the board's printed IP is reachable on the same
network, and close any serial monitor before using the Python USB client. Wi-Fi
is retried every ten seconds without blocking Serial/TCP processing. TCP accepts
one client at a time; reconnect after a disconnect.

## Serial protocol

UTF-8 text, 115200 baud, 8N1, newline-delimited:

| Host command | ESP32 response | Meaning |
| --- | --- | --- |
| `ON` | `OK:TEST_MODE_ENABLED`, `MODE:TEST` | enable simulated TEST condition |
| `OFF` | `OK:TEST_MODE_DISABLED`, `MODE:NORMAL` | return to simulated NORMAL |
| `STATUS` | `MODE:NORMAL` or `MODE:TEST` | query stored state |

Boot emits `ESP32_SIM_CONTROLLER:READY` then the current mode. Unknown commands return `ERR:UNKNOWN_COMMAND`.

## Example output

```text
SIMULATED mode=NORMAL RSSI=-58.7 dBm noise=-95.6 dBm packet_success=98.2%
Simulator mode set to TEST
SIMULATED mode=TEST RSSI=-75.1 dBm noise=-72.4 dBm packet_success=62.8%
```

## Limitations and roadmap

These are bounded random values, not live readings. State resets on reboot. The
terminal dashboard and CSV records are session tools, not RF instrumentation.
Safe future work can add configuration profiles, repeatable scenarios,
visualisation, authenticated network control, and serial reconnection. It must
remain simulation-first and avoid RF disruption.

## Demo and release

Follow the complete reproducible workflow in [docs/demo.md](docs/demo.md). See [v1.0.0 release notes](docs/release-v1.0.0.md) and [CHANGELOG.md](CHANGELOG.md). The supported CLI help is available through `.venv/bin/python -m simulator.main --help` and `.venv/bin/python -m simulator.analysis --help`.
