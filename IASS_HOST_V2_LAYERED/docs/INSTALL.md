# Installation

## Normal startup

1. Ubuntu 24.04+ with Python 3.12 is recommended.
2. Connect the PC to the phone hotspot if phone-camera streaming is required.
3. Run:

```bash
./start.sh
```

No manual virtual-environment activation or `PYTHONPATH` configuration is required.

4. Open the printed dashboard URL on the PC.
5. Open the printed `/camera` URL on the phone and press **Start Camera**.
6. Return to the dashboard. The live frame should appear automatically.
7. Register a person using a clear face image.
8. Enable tracking only after connecting and testing the ATmega328P motor controller.

## Test without hardware

Run:

```bash
./start.sh --offline
```

This starts the complete application with a synthetic local camera and physical Arduino access disabled. It is intended for UI/startup testing without external devices.

## Optional hardware

The phone camera, Arduino/ATmega328P, stepper and other hardware are optional at boot. Their absence is represented as runtime state and should not prevent the dashboard from opening.

## Phone camera troubleshooting

If the phone page cannot connect, verify that IASS is bound to `0.0.0.0`, the PC firewall allows TCP 5000 on the hotspot interface, and both devices are on the same hotspot subnet. If the phone disconnects after streaming has started, the dashboard remains alive and returns the camera state to `WAITING`/`DISCONNECTED`.
