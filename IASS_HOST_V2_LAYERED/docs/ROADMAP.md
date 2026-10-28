# IASS V1 Roadmap

### Stage 1 — Transport
Phone -> hotspot -> IASS WebSocket -> FrameHub -> dashboard.

### Stage 2 — Perception
FrameHub -> face/person detector -> overlay -> metrics.

### Stage 3 — Identity
Enrollment -> local database -> face sample comparison -> authorization state.

### Stage 4 — Tracking
Detection centroid -> deadband -> proportional pan command -> Arduino.

### Stage 5 — Hardening
Reconnects, logging, recordings, calibration, permissions, safety interlocks, and tests.

### Stage 6 — Production AI
Replace prototype recognition/detection backends with validated models, benchmark CPU/GPU latency, and add liveness/anti-spoofing before real access-control deployment.
