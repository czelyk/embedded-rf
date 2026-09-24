# Architecture

Milestone 1 is a closed-loop **software simulation**. It has no RF transmission, reception, jamming, interference, or radio configuration.

```text
ESP32-C3-DevKitC-02 v1.1 -- USB (/dev/ttyUSB0) --> Python controller --> simulated channel model
             ON / OFF / STATUS                 reads/writes           synthetic measurements
```

## Data flow

1. The Python controller or an operator sends newline-delimited `ON`, `OFF`, or `STATUS` over USB serial at 115200 baud.
2. The ESP32 stores only a boolean test-mode state and returns a text status response; it never controls an RF peripheral.
3. The Python controller reads `MODE:NORMAL` or `MODE:TEST` and updates `RFChannelSimulator`.
4. The simulator samples bounded pseudo-random RSSI, noise, and packet-success values for that state and labels them `SIMULATED`.

The controller sends only these three validated protocol commands and parses the board's newline-delimited responses. Manual CLI operation uses the identical state-transition path without hardware. Serial failures are reported clearly and the port is closed when the process exits. PlatformIO builds `firmware/esp32_controller/src/main.cpp` for `esp32-c3-devkitc-02`; its configured Linux upload/monitor port is `/dev/ttyUSB0`.
