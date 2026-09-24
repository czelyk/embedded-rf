# embedded-rf

`embedded-rf` is a safe, simulation-only ESP32-controlled RF-channel training platform. It models RSSI, noise, and packet success in Python; it does **not** measure, transmit, jam, interfere with, or otherwise operate on real RF signals.

## Architecture

```text
ESP32 -- USB Serial --> Python controller / RF channel simulator
                              |- NORMAL mode
                              |- TEST mode
                              `- synthetic RSSI, noise, packet success
```

See [the architecture document](docs/architecture.md) for the data flow.

## Repository layout

- `firmware/esp32_controller/` — Arduino USB-serial state controller
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

These are bounded random values, not live readings. State resets on reboot; no GUI or logging exists. Safe future work can add configuration profiles, CSV logging, repeatable scenarios, visualisation, and serial reconnection. It must remain simulation-first and avoid RF disruption.
