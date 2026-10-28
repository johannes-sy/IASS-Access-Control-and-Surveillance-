# Safety and Security

1. Motor tracking is disabled by default. Do not connect an uncontrolled motor load until direction, step rate, current limit, and mechanical travel have been verified.
2. The host must have a physical/electrical emergency stop for powered actuators.
3. Do not treat face recognition alone as proof of identity. Use a second factor for consequential access decisions.
4. Enrollment images and biometric templates are sensitive. Restrict filesystem permissions and implement deletion/retention before production use.
5. Keep the camera and control network on a trusted LAN during development.
