# Architecture

```text
TEST / STATUS buttons -> ESP32 -> USB UART (115200, 8N1)
                                      |
                                      v
                           Python command parser
                                      |
                                      v
                         Synthetic channel measurements
```

The ESP32 owns TEST state while connected. It uses debounced active-low buttons
(40 ms) without delay calls or radio libraries. The PC owns the model and console
output. In manual fallback, the console owns TEST state. A connection failure
resets the simulator to NORMAL before accepting manual commands.

## Line protocol

ASCII lines end in LF; CRLF is accepted. ESP32 output is uppercase:

| Direction | Line | Meaning |
| --- | --- | --- |
| PC -> ESP32 | `STATUS` | Request current state and a measurement event |
| ESP32 -> PC | `TEST ON` / `TEST OFF` | Button changed TEST state |
| ESP32 -> PC | `STATE ON` / `STATE OFF` | Absolute, idempotent state snapshot |
| ESP32 -> PC | `STATUS` | Generate and display one synthetic measurement |

Boot, STATUS button and each PC poll emit `STATE ...` then `STATUS`.
TEST button emits `TEST ...`, then the same state/status pair. Repeated state
snapshots repair a missed toggle message. The host ignores status until it has
received state, ignores boot noise/unknown lines, and drops malformed ASCII or
lines longer than 128 bytes. Firmware bounds input to 31 characters and discards
oversized frames. Fragmented reads are retained across serial timeouts.

The PC polls every second, with 0.2-second reads and a one-second write timeout.
No state for five seconds ends serial mode. There is no acknowledgement of
physical button actions, remote TEST mutation, or concurrent manual control in
serial mode. The two directions are parsed separately to avoid response loops.

## Model limits

NORMAL samples RSSI -60..-45 dBm, noise -95..-85 dBm and packet success 95..100%.
TEST samples RSSI -85..-70 dBm, noise -65..-55 dBm and packet success 40..75%.
These independent uniform distributions illustrate changed conditions; packet
success is not calculated from SNR and this is not a calibrated propagation or
physical-layer model. There are no actual packets, receivers or RF emissions.
