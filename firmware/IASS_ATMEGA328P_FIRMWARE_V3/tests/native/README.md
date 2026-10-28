# Native protocol/dispatch tests

Runs the real firmware protocol/dispatch/handler logic under a normal host
compiler (gcc), against test-only mocks for the AVR-register-backed
drivers (`mock_drivers.c`: UART/GPIO/timer, `mock_servo.c`: servo). This is
what "verified by actually building/running" means for MCU code that can't
run as a whole program off the target -- the parts that don't depend on
real timer/UART hardware (protocol framing, command dispatch, handler
routing, door/alarm actuator logic, event emission) get exercised for
real, not just compiled for AVR and trusted.

`servo.c` itself (the real one, using Timer1 ISRs to generate RC pulses) is
intentionally excluded from this suite -- it's inherently AVR-timer-specific
and not meaningfully testable without simulating interrupts. `mock_servo.c`
stands in so `servo_handlers.c` and `command_dispatch.c` still get exercised
end-to-end.

Run:

```
make run
```

Exits non-zero if any check fails.
