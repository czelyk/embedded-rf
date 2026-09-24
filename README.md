# embedded-rf

ESP32 USB Serial controller and a Python RF channel **simulator**. All RSSI,
noise and packet-success values are synthetic; there is no RF transmission,
jamming, radio configuration, or real receiver measurement.

## PC setup

Use Python 3.10+:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python simulator/rf_channel_sim.py
```

On Windows activate with `.venv\Scripts\activate`; use `python` instead of
`python3` where appropriate. Manual mode also works without pyserial.
Commands: `on`, `off`, `status`, `reset`, `quit`. Each status prints one
measurement plus a synthetic virtual-packet outcome and cumulative delivered /
lost counters. `reset` clears those counters without changing TEST mode.
Use `--seed 42` for repeatable synthetic values.

## ESP32 setup

The sketch targets a **classic ESP32 DevKit** with a USB-to-UART bridge.
In Arduino IDE, install Espressif's ESP32 board package, select the actual board
(e.g. ESP32 Dev Module) and USB port, then open and upload
`firmware/esp32_controller/esp32_controller.ino`.

With the board powered off, connect two normally open pushbuttons:

| Button | Connection | Action |
| --- | --- | --- |
| TEST | GPIO25 to GND | Toggle TEST ON/OFF |
| STATUS | GPIO26 to GND | Request a simulated measurement |

Internal pull-ups are enabled; do not connect these inputs to 5 V. Other ESP32
variants may lack these pins or use native USB: adjust pin constants and board
USB settings for your hardware. This repository has not been hardware-validated.

Close Arduino Serial Monitor before running the PC program (one port owner):

```sh
python -m serial.tools.list_ports
python simulator/rf_channel_sim.py --port /dev/ttyUSB0
# Windows example:
python simulator/rf_channel_sim.py --port COM3
```

Both ends use 115200 baud. The PC requests state/status once per second; a button
press also reports immediately. Opening the port can reset the board; boot and
state synchronization are allowed five seconds. Reset starts with TEST OFF.
On Linux, serial access may require membership in the device's owning group
(commonly `dialout`) and a new login. Use a USB data cable.

A missing serial dependency, failed connection, disconnect or five-second state
timeout switches to manual mode and resets TEST OFF. Ctrl+C exits; restart with
`--port` to reconnect. No automatic reconnection is attempted.

## Checks

```sh
python -m unittest discover -s tests -v
python -m compileall -q simulator tests
```

See [architecture and serial protocol](docs/architecture.md).
