# Architecture

Milestone 1 is a closed-loop **software simulation**. It has no RF transmission, reception, jamming, interference, or radio configuration.

```text
ESP32-C3-DevKitC-02 v1.1 -- USB Serial or Wi-Fi TCP --> Python controller --> simulated channel model
             ON / OFF / STATUS                    reads/writes          clearly labeled values
             |                                                                    (SIMULATED only)
             `---------------------- Wi-Fi UDP --> Python telemetry receiver
```

## Data flow

1. The Python controller or an operator sends newline-delimited `ON`, `OFF`, or `STATUS` over USB serial at 115200 baud or TCP (default port 8765).
2. The ESP32 stores only a boolean test-mode state, returns a text response on the originating transport, and never controls an RF peripheral.
3. Wi-Fi reconnection is attempted periodically without blocking Serial. The TCP server accepts one bounded-line client at a time.
4. The ESP32 optionally sends UDP **device telemetry** (device, mode, uptime, sequence) to a configured host/port; it never claims simulated values as measured RF data.
5. The Python controller reads `MODE:NORMAL` or `MODE:TEST` through either transport and updates `RFChannelSimulator`, which produces separately labeled `SIMULATED` values.

The controller sends only these three validated protocol commands and parses the board's newline-delimited responses. Manual CLI operation uses the identical state-transition path without hardware. Both sockets and serial ports close on exit. PlatformIO builds `firmware/esp32_controller/src/main.cpp` for `esp32-c3-devkitc-02`; its configured Linux upload/monitor port is `/dev/ttyUSB0`. See [protocol.md](protocol.md) for frame formats.
