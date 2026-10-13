# Windows setup and software validation

This guide covers a hardware-independent Windows workflow for `embedded-rf`.
It was exercised with Windows PowerShell and Python 3 without a physical
ESP32-C3. It validates the Python tools, firmware compilation, and replay
dashboards; it does not validate communication with a device.

## Clone and open the repository

In PowerShell, clone the repository and change to its root directory:

```powershell
git clone https://github.com/czelyk/embedded-rf.git
Set-Location embedded-rf
```

All commands below run from the repository root. They use relative paths so the
workflow does not depend on a particular Windows user name or checkout folder.

## Create the Python environment

Create a virtual environment with an installed Python 3 interpreter, install
the project requirements, and install PlatformIO Core into the same environment:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pip install platformio
```

Using `.venv\Scripts\python.exe` explicitly avoids depending on PowerShell
activation state or a different Python installation on `PATH`. PlatformIO can
likewise be invoked as `.venv\Scripts\platformio.exe`.

## Run the software checks

Run the Python test suite and compile the Python modules:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -m compileall -q simulator tests
```

The Windows validation session ran 45 tests: 43 passed and two POSIX/serial
integration tests were skipped as expected. A skip is not evidence that a
physical Windows serial connection works.

Build the ESP32-C3 firmware without uploading it:

```powershell
.venv\Scripts\platformio.exe run -d firmware\esp32_controller
```

Finish with Git's whitespace check:

```powershell
git diff --check
```

This build proves that the firmware compiles for the configured
`esp32-c3-devkitc-02` target. It does not prove that firmware upload, boot, or
device communications work.

## Replay a recorded session

The committed fixture is safe for hardware-free testing. Run it in the terminal
at recorded speed, faster, slower, or without timing delays:

```powershell
.venv\Scripts\python.exe -m simulator.replay tests\fixtures\replay_session.csv --dashboard --speed 1.0
.venv\Scripts\python.exe -m simulator.replay tests\fixtures\replay_session.csv --dashboard --speed 2.0
.venv\Scripts\python.exe -m simulator.replay tests\fixtures\replay_session.csv --dashboard --speed 0.5
.venv\Scripts\python.exe -m simulator.replay tests\fixtures\replay_session.csv --dashboard --no-delay
```

The fixture progresses from `NORMAL` to `TEST` and back to `NORMAL`. Replay
uses its recorded values rather than generating replacements. The dashboard
must identify the source as `REPLAY` and RF values as `SIMULATED RF`.

For browser replay, use a slower speed so there is time to inspect the page:

```powershell
.venv\Scripts\python.exe -m simulator.replay tests\fixtures\replay_session.csv --web-dashboard --speed 0.5
```

Open <http://127.0.0.1:8080> while replay is running. From a second PowerShell
window, the credential-free state endpoint can be checked with:

```powershell
Invoke-RestMethod http://127.0.0.1:8080/api/state | ConvertTo-Json -Depth 5
```

The page and `/api/state` should show replay state, the
`NORMAL -> TEST -> NORMAL` progression, and clearly labeled software-simulated
values. Browser history is bounded to 120 samples, and the only command buttons
are `STATUS`, `ON`, and `OFF`; there is no arbitrary command input. Replay shuts
down the local web server after applying the final row.

## Find a serial device for future hardware testing

Do not assume the ESP32 is `COM1` or any other fixed COM number. Connect the
board with a USB data cable and compare discovery output before and after
connection. Safe PowerShell and PlatformIO discovery commands include:

```powershell
[System.IO.Ports.SerialPort]::GetPortNames()
Get-CimInstance Win32_SerialPort | Select-Object DeviceID, Name
.venv\Scripts\platformio.exe device list
```

Use the port associated with the ESP32-C3 for that session, and close serial
monitors before another process opens it. Discovery alone does not validate the
USB serial protocol or firmware upload.

## Security and simulation boundaries

- `firmware/esp32_controller/include/wifi_config.h` is a local, Git-ignored
  file. Never commit it or any Wi-Fi credentials.
- Do not commit machine-specific LAN IP addresses, private device logs, or
  private session CSV files.
- Do not paste credentials or credential-bearing command output into issues or
  pull requests.
- RSSI, noise, and packet-success values produced by the Python simulator are
  **SOFTWARE SIMULATED**. They are not physical ESP32 RF measurements.
- The project does not implement real RF jamming or interference.

## Validation scope

The Windows session verified the Python tests, `compileall`, the PlatformIO
firmware build, terminal replay, web replay, the localhost dashboard, and its
state API and bounded control surface.

No physical ESP32 was available. The session did **not** verify firmware upload,
the physical USB serial protocol, ESP32 Wi-Fi, physical TCP or UDP behavior, or
a device-backed web dashboard. Those checks remain future hardware work.
