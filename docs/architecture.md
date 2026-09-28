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
6. An optional Python session layer records device-state updates and simulated samples separately, maintains statistics, writes flushed CSV rows, and renders an optional terminal dashboard. It owns at most one nonblocking UDP listener; no ESP32 firmware changes are required.
7. The offline analysis module consumes only those CSV records, validates them, and can generate descriptive NORMAL/TEST summaries, headless plots, and Markdown reports. It continues to label RSSI, noise, and packet-success fields as **SIMULATED**.
8. The optional Flask web adapter serializes that same session state at `/api/state`; browser polling and canvas charts add no second statistics or protocol implementation. Its control route delegates only `STATUS`, `ON`, and `OFF` to the connected controller.
9. The replay loader applies CSV telemetry, control, and recorded simulated sample rows to a `Session` in file order. It needs no transport or hardware and never regenerates recorded RF values.

The controller sends only these three validated protocol commands and parses the board's newline-delimited responses. Manual CLI operation uses the identical state-transition path without hardware. Both sockets and serial ports close on exit. PlatformIO builds `firmware/esp32_controller/src/main.cpp` for `esp32-c3-devkitc-02`; its configured Linux upload/monitor port is `/dev/ttyUSB0`. See [protocol.md](protocol.md) for frame formats.

The web server defaults to `127.0.0.1:8080`, updates by JSON polling, and keeps
at most 120 chart samples in memory. Live and replay processes shut it down and
join its thread deterministically.
