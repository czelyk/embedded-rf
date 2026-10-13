# Control and telemetry protocols

All control messages are ASCII/UTF-8, uppercase, and newline-delimited.

## Serial and TCP control

Serial is 115200 baud, 8N1. TCP defaults to port `8765`; configure it in the
local Wi-Fi header if needed. Both transports accept the same commands:

| Command | Response |
| --- | --- |
| `ON` | `OK:TEST_MODE_ENABLED` then `MODE:TEST` |
| `OFF` | `OK:TEST_MODE_DISABLED` then `MODE:NORMAL` |
| `STATUS` | `MODE:NORMAL` or `MODE:TEST` |

Unknown commands return `ERR:UNKNOWN_COMMAND`; lines longer than 95 bytes are
discarded and return `ERR:LINE_TOO_LONG`. TCP accepts fragmented and multiple
lines without blocking the main loop.

## UDP device telemetry

The ESP32 sends this semicolon-separated device-state message at most every five
seconds to the configured host and port (default `8766`):

```text
device=esp32-c3;mode=NORMAL;uptime_ms=123456;sequence=42
```

This is **DEVICE TELEMETRY**, not RF telemetry. It contains no RSSI, noise,
packet success, or claim of RF measurement. Python-generated channel output is
separate and always labeled `SIMULATED`.
