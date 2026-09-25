# Safe end-to-end demo

This demo combines real ESP32 control/device telemetry with clearly labeled **SIMULATED** Python RF values. It does not measure or transmit RF.

1. Build/upload and create the local ignored Wi-Fi configuration as described in the README. Note `ESP32_IP` from USB Serial.
2. Start dashboard, UDP receiver, and recording on USB:

```bash
.venv/bin/python -m simulator.main --port /dev/ttyUSB0 --dashboard --csv logs/demo.csv
```

3. In another terminal, use TCP control. `--no-udp` prevents a second listener:

```bash
.venv/bin/python -m simulator.main --host ESP32_IP --no-udp --command STATUS --count 1
.venv/bin/python -m simulator.main --host ESP32_IP --no-udp --command ON --count 1
sleep 6
.venv/bin/python -m simulator.main --host ESP32_IP --no-udp --command OFF --count 1
sleep 6
```

Observe real mode/uptime/sequence updates and separate **SIMULATED RF** values. Stop cleanly with Ctrl+C, then analyze:

```bash
.venv/bin/python -m simulator.analysis logs/demo.csv --plot --output-dir analysis/demo --report analysis/demo/report.md
```

The CSV, plots, and report show real device state alongside software-simulated metrics only.
