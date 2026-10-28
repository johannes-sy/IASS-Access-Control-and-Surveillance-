# IASS Host V1 — Professional Surveillance Host

IASS (Interactive Surveillance and Access Control System) is a Linux host application for a phone-camera surveillance node, live dashboard, AI perception, identity registration/authorization, event logging, and Arduino/ATmega328P camera tracking.

## V1 architecture

```text
Phone camera / HTTP-MJPEG / OpenCV source
              |
              v
        FrameHub (latest frame)
          /            \
         v              v
   Web dashboard      AI Worker
                         |
             +-----------+-----------+
             |           |           |
          person       face       tracker
             |           |           |
             +-----------+-----------+
                         v
                 Identity database
                         |
                 AUTHORIZED/UNKNOWN
                         |
                 Tracking Controller
                         |
                    Serial link
                         |
                    ATmega328P
                         |
                    Stepper driver
```

## Quick start

From a fresh terminal, only the following is required:

```bash
cd IASS_HOST_V1_PROFESSIONAL
./start.sh
```

`start.sh` automatically finds the project root, checks Python 3.11+, creates `.venv` when necessary, installs/updates requirements when the dependency stamp is stale, sets the package path, prevents duplicate launches, prints the dashboard/phone URLs, and starts the application.

Open the dashboard at `http://127.0.0.1:5000/`.

To use a phone browser as the camera, open the printed `/camera` URL on the phone while the phone and PC are on the same hotspot. Allow camera access and press **Start Camera**. The dashboard does not need to be restarted when the phone connects or disconnects.

### Startup modes

```bash
./start.sh
./start.sh --debug
./start.sh --offline
```

- Normal mode: normal configured IASS operation.
- `--debug`: preserves normal operation while marking the startup mode for diagnostics.
- `--offline`: uses a local synthetic camera and disables physical Arduino access so the complete UI can be tested without external hardware.

## Hardware-offline behavior

Camera and Arduino availability are runtime states, not startup requirements. IASS can open the dashboard with no phone and no ATmega328P connected.

The dashboard reports states such as:

```text
Application    RUNNING
Database      READY
AI Engine     READY / WAITING FOR CAMERA
Camera        WAITING / LIVE / DISCONNECTED
Arduino       CONNECTED / DISCONNECTED / DISABLED
Stepper       STANDBY / TRACKING
Alarm         STANDBY
```

A stale camera frame is automatically treated as disconnected and the live-video endpoint displays a waiting placeholder instead of failing.

## Camera sources

The configured camera source may be `phone_browser`, `opencv`, or `synthetic`. For an existing HTTP-MJPEG/RTSP-compatible source, set `camera.source_url` in `config/v1.toml`. OpenCV support depends on the installed backend.

## AI and authorization

The V1 perception pipeline keeps person detection, face detection, and recognition separate. Face recognition does not automatically authorize a detected face: authorization requires a match against an enabled registered identity and the configured recognition threshold.

Enrollment now extracts the largest detected face before storing the sample when possible. If no face can be detected, the submitted image is retained rather than silently discarding the registration request.

AI inference runs in a background worker so the phone WebSocket and dashboard do not wait synchronously for OpenCV processing. With no camera frames, the AI remains ready/waiting instead of inventing detections.

## Tracking and hardware

Motor commands remain bounded and rate-limited. The configured `tracking.pan_deadband_px`, `tracking.max_step_command`, and `tracking.command_interval_ms` are respected. Tracking remains disabled by default and physical hardware remains optional.

## Testing

Run:

```bash
PYTHONPATH=src pytest -q
```

The test suite covers normal FrameHub publication, the no-camera JPEG placeholder, and safe clearing/disconnection state.

## Important safety/design notes

- Face recognition is an authorization aid, not a guarantee of identity. Tune thresholds and require operator confirmation for high-risk decisions.
- V1 uses classical OpenCV detectors so the application remains installable without downloading large AI weights. YOLO remains a possible pluggable backend when separately installed.
- Motor commands are rate-limited, bounded, and disabled by default until tracking is explicitly enabled.
- The database stores enrollment samples locally. Treat these as sensitive biometric data and protect the host filesystem.

## Troubleshooting

### `python3 -m venv` fails

On Ubuntu install the standard Python environment packages:

```bash
sudo apt install python3-venv python3-full
```

### Phone cannot connect

Verify that IASS is bound to `0.0.0.0`, the PC firewall allows TCP 5000 on the hotspot interface, and both devices are on the same hotspot subnet. IASS itself should still remain usable from the PC dashboard when the phone is unavailable.

### Arduino is absent

No manual workaround is required. IASS reports `Arduino: DISCONNECTED` and continues running. Connect the ATmega328P later and enable/test tracking only after the hardware path is verified.

## Project status

See `docs/ROADMAP.md`, `docs/TODO.md`, and `docs/PROPOSAL_TRACEABILITY.md`.

## V1 Command Center UI

The host dashboard is now a multi-panel command center. The main page contains the live camera grid, primary tracking feed, AI overlay, face-recognition previews, operational status, event timeline, and host/hardware telemetry.

Personnel registration is intentionally separated from the dashboard at `/register`. Registration captures the current live IASS camera frame; it does not require uploading an image file. Start the phone camera first, align the face with the enrollment target, then use **Capture & Save Face Encoding**.

Additional camera tiles are represented as explicit offline camera slots until physical/stream sources are configured. IASS does not fabricate live feeds for cameras that are not connected.

### Startup

Use only:

```bash
./start.sh
```

Do not manually activate `.venv` or run `uvicorn`. The startup script manages the persistent Python environment and only installs dependencies on the first run or when `requirements.txt` changes.

## Hardware Control Layer (V1)

IASS now includes a semantic hardware abstraction layer for three camera mounts, two door locks and two alarms. Upper layers do not send serial commands directly.

The main entry points are:

- `iass.hardware.controller.HardwareController`
- `iass.hardware.state.HardwareStateManager`
- `iass.hardware.registry.DeviceRegistry`
- `iass.hardware.models.HardwareIntent`

The physical driver boundary retains the existing ATmega328P link while adding a simulation driver. Simulation is enabled by default so IASS can boot and demonstrate the complete control/state/audit path without physical hardware.

Hardware state is available from `/api/v1/hardware/state` and the existing telemetry page. Hardware commands/events are persisted in SQLite and correlated with AI/security events.

See `docs/HARDWARE_ARCHITECTURE.md`, `docs/HARDWARE_API.md`, and `docs/HARDWARE_PROTOCOL.md`.


## Hardware Layer Refactor
See `docs/HARDWARE_ARCHITECTURE.md`. The new hardware stack is additive and keeps legacy modules intact.

## ATmega328P hardware integration

The host hardware layer now speaks the exact binary protocol implemented by the bundled ATmega328P firmware. The V1 wire frame is fixed at seven bytes (`AA DEVICE COMMAND VALUE_H VALUE_L XOR 55`). The host sends a one-second heartbeat and consumes the firmware's 100 ms telemetry stream.

For physical testing, set these values in `config/v1.toml`:

```toml
[serial]
enabled = true
port = "/dev/ttyACM0"
baud = 115200

[hardware]
simulation = false
```

Then start with `./start.sh`. If the ATmega is absent, IASS remains operational and reports the hardware as disconnected. The MCU itself remains responsible for its watchdog and five-second communication-loss failsafe.

See `docs/HARDWARE_PROTOCOL.md`, `docs/HARDWARE_API.md`, `docs/HARDWARE_TESTING.md`, and `docs/SAFETY.md` for the integration contract and test procedure.


## AI / Security Integration

See `docs/AI_ARCHITECTURE.md`. AI perception now emits semantic events; the host security scenario engine converts those events into existing hardware intents. The ATmega firmware is not used for security decisions.

## Hardware Control V2

The host hardware subsystem now uses a stateful security scenario engine, rate-limited
camera tracking, cross-camera handoff support, risk escalation, tailgating/restricted
access hooks, a command lifecycle manager, a richer semantic protocol contract, hardware
event bus, explicit transport health and simulation/ATmega driver parity.

See `docs/HARDWARE_CONTROL_ARCHITECTURE.md` and `docs/HARDWARE_PROTOCOL.md`.
