# Architecture

Milestone 1 is a closed-loop **software simulation**. It has no RF transmission, reception, jamming, interference, or radio configuration.

```text
ESP32 development board -- USB serial --> Python controller --> simulated channel model
       ON / OFF / STATUS                  parses state          synthetic measurements
```

## Data flow

1. An operator sends `ON`, `OFF`, or `STATUS` to the ESP32 over USB serial.
2. The ESP32 stores only a boolean test-mode state and returns a text status response; it never controls an RF peripheral.
3. The Python controller reads `MODE:NORMAL` or `MODE:TEST` and updates `RFChannelSimulator`.
4. The simulator samples bounded pseudo-random RSSI, noise, and packet-success values for that state and labels them `SIMULATED`.

Manual CLI operation uses the identical state-transition path without hardware. Serial failures are reported clearly and the port is closed when the process exits.
