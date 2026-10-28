# IASS V1 TODO / Engineering Backlog

## P0 — required before field demonstration
- [x] One-command Linux launcher
- [x] FastAPI dashboard
- [x] Phone browser camera WebSocket ingest
- [x] Frame buffer and JPEG API (`jpeg()` and `status()`)
- [x] Live MJPEG dashboard endpoint
- [x] SQLite people/events database
- [x] Person registration UI
- [x] Face detection
- [x] Basic local recognition prototype
- [x] Tracking enable/disable
- [x] Bounded pan commands to ATmega328P
- [ ] Validate phone browser camera on Android/iOS and hotspot routing
- [ ] Validate ATmega328P serial electrical levels and driver wiring
- [ ] Add hardware emergency stop and motor limit switches
- [ ] Add persistent motor calibration/home position

## P1 — AI quality
- [ ] Add YOLO person detector backend with configurable model path
- [ ] Add production face detector/embedding backend
- [ ] Enrollment quality checks: pose, blur, illumination, duplicate identity
- [ ] Multi-sample enrollment and embedding averaging
- [ ] Anti-spoof/liveness evaluation
- [ ] Confidence calibration and operator policy
- [ ] Track IDs and temporal smoothing

## P1 — surveillance
- [ ] Event snapshots and video clips
- [ ] Recording retention policy
- [ ] Camera reconnect/backoff
- [ ] FPS/latency/queue telemetry
- [ ] Multiple camera profiles
- [ ] Tamper/disconnect alerts

## P2 — access control
- [ ] Role-based operator accounts
- [ ] Audit log for registration/deletion/authorization changes
- [ ] Optional GPIO/relay controller
- [ ] Door/access actuator integration
- [ ] Local encrypted backup of authorization database

## P2 — deployment
- [ ] systemd service
- [ ] offline dependency wheel bundle
- [ ] installation/uninstallation scripts
- [ ] firewall rule helper
- [ ] signed configuration

## Hardware Control Layer — V1 implementation status

- [x] Semantic HardwareController API
- [x] Three camera mount model
- [x] Two door lock model
- [x] Two alarm model
- [x] Thread-safe HardwareStateManager
- [x] Device registry and configurable zones
- [x] Command results with command/correlation IDs
- [x] Commanded vs actual-state distinction
- [x] Hardware command/event/access audit tables
- [x] AI semantic intent -> hardware policy translation
- [x] Camera tracking routed through hardware abstraction
- [x] Mock/simulation driver for no-hardware operation
- [x] Versioned REST hardware API
- [x] Hardware state in telemetry UI
- [x] Emergency-stop API architecture (`stop_camera` / future global stop)
- [ ] Physical MCU feedback/ACK protocol
- [ ] Door lock feedback sensors
- [ ] Door open/closed sensors
- [ ] Camera pan/tilt position feedback and calibration
- [ ] Limit switches
- [ ] Physical emergency-stop input
- [ ] RFID reader driver and hardware event ingestion
- [ ] MCU watchdog and handshake implementation
- [ ] Multi-MCU transport support
