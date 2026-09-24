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
- Arduino IDE with ESP32 board package, or PlatformIO, to upload firmware

## Run without an ESP32

```bash
python3 -m simulator.main --manual
```

Enter `ON` for TEST, `OFF` for NORMAL, `STATUS` to show state, or `QUIT` to exit. All values are explicitly synthetic.

## Connect an ESP32

1. Upload `firmware/esp32_controller/esp32_controller.ino`.
2. Connect its normal USB port, identify it (for example `/dev/ttyUSB0` or `COM3`), and run:
   ```bash
   python3 -m simulator.main --port /dev/ttyUSB0
   ```
3. In a serial terminal at 115200 baud send `ON`, `OFF`, or `STATUS` followed by newline.

## Build/upload

Open the `.ino` sketch in Arduino IDE, select a standard ESP32 board and USB port, then Upload. It uses only `Serial`; it includes no RF library or radio configuration.

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
