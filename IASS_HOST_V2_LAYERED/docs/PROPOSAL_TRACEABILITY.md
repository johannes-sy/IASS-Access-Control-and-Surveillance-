# Proposal Traceability

| Proposal capability | V1 implementation | Status |
|---|---|---|
| Live camera capture | Phone browser WebSocket / OpenCV source | Implemented |
| Host-side image processing | FrameHub + perception worker path | Implemented |
| Person/face analysis | OpenCV HOG + Haar | Prototype |
| Identity registration | SQLite + registration UI | Implemented |
| Authorization decision | Registered enabled identity vs unknown | Prototype |
| Camera tracking | Proportional pan controller | Implemented |
| ATmega328P control | Serial command interface | Implemented |
| Dashboard | FastAPI + responsive web UI | Implemented |
| Event history | SQLite events | Implemented |
| Recording | Directory reserved | TODO |
| Advanced YOLO AI | Pluggable path planned | TODO |
| Liveness/anti-spoof | Required for high-assurance deployment | TODO |
| Multi-camera | Architecture-ready | TODO |
| USB security/inline network functions | Separate appliance subsystem | Not part of this host V1 build |

## Hardware Control & Interface Addendum

| Requirement | Implementation |
|---|---|
| Hardware abstraction | `src/iass/hardware/controller.py` |
| Stateful hardware | `src/iass/hardware/state.py` |
| Device registry | `src/iass/hardware/registry.py` |
| Physical driver boundary | `src/iass/hardware/drivers.py`, `serial.py` |
| 3 camera mounts | Configured in `config/v1.toml` and registered at startup |
| 2 door locks | Configured and registered at startup |
| 2 alarms | Configured and registered at startup |
| Semantic AI intents | `HardwareIntent` + `HardwarePolicy` |
| Command audit | `hardware_commands` database table |
| State/event audit | `hardware_events` database table |
| RFID/access audit foundation | `access_events` + `/api/v1/hardware/access/decide` |
| Correlated AI/hardware events | `correlation_id` on AI/hardware/access records |
| Offline/no-hardware operation | `MockHardwareDriver` / existing offline mode |
| Existing serial compatibility | `ArduinoLink` retained and wrapped by `AtmegaHardwareDriver` |
| Hardware REST API | `/api/v1/hardware/...` |
| Existing APIs preserved | Existing `/api/...` routes retained |
| Telemetry UI | Existing telemetry page extended with hardware inventory/state |
