# embedded-rf v1.0.0 release notes

embedded-rf is a simulation-first ESP32-C3 demo for USB/TCP control, UDP device telemetry, dashboard/CSV sessions, and offline analysis. Supported hardware is ESP32-C3-DevKitC-02 v1.1. Install with `pip install -r requirements.txt`; build/upload using PlatformIO in `firmware/esp32_controller`.

The ESP32 provides control/device telemetry. RSSI, noise, and packet-success RF metrics are software-simulated and are not physical RF measurements. The project does not transmit, jam, interfere with, or disrupt RF signals. See the README and [demo guide](demo.md).
