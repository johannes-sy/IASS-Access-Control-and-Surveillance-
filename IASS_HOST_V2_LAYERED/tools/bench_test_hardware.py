#!/usr/bin/env python3
"""Standalone ATmega328P hardware bench test.

Talks directly to the board over the real serial port using the exact same
ArduinoLink/Frame classes the full IASS app uses -- no camera, no AI, no
security engine, no simulation. This exists so you can verify your wiring
(buzzer/LED on the alarm or door-lock pins) works *before* trying to debug
it through the whole app.

It walks the checklist in your firmware's own docs/TEST_PLAN.md, sections
2 (legacy protocol), 4 (camera mounts/servos), 5 (doors), and 6 (alarms).
It does NOT attempt sections 3 (rich protocol), 7 (safety/watchdog), or 8
(full host integration) -- those need either the rich V2 protocol client
(not yet exposed as a standalone tool) or the running app.

Usage:
    python tools/bench_test_hardware.py --port /dev/ttyACM0
    python tools/bench_test_hardware.py --port /dev/ttyACM0 --baud 115200
    python tools/bench_test_hardware.py --port /dev/ttyACM0 --only alarms
    python tools/bench_test_hardware.py --port /dev/ttyACM0 --step

Each step prints what it just commanded and what the firmware's telemetry
reports back, so you can watch your buzzer/LED and confirm it matches.
Nothing here "passes" or "fails" automatically for the alarm/servo/door
steps -- YOU are the sensor. --step pauses after every command so you have
time to actually look at the hardware before the next one fires.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from iass.hardware_interface.serial_link import ArduinoLink  # noqa: E402


SECTIONS = ("heartbeat", "servos", "doors", "alarms")


def banner(text):
    print(f"\n{'='*60}\n{text}\n{'='*60}")


def wait_for_telemetry(link, timeout=1.5):
    """Give the firmware's ~100ms periodic telemetry a moment to arrive and
    return the most recent decode, or {} if nothing came back."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if link.telemetry:
            return dict(link.telemetry)
        time.sleep(0.05)
    return dict(link.telemetry)


def pause(interactive, message="Press Enter to continue..."):
    if interactive:
        input(f"    -> {message}")
    else:
        time.sleep(1.0)


def run_heartbeat(link, interactive):
    banner("HEARTBEAT (TEST_PLAN.md section 2)")
    print("Sending heartbeat. The firmware's 5-second heartbeat-loss failsafe")
    print("resets its timer on every heartbeat, lock command, or unlock command.")
    ok = link.send_heartbeat()
    print(f"  send_heartbeat() -> {ok}")
    tel = wait_for_telemetry(link)
    print(f"  telemetry after heartbeat: {tel or '(none received -- check wiring/port/baud)'}")
    pause(interactive)


def run_servos(link, interactive):
    banner("CAMERA MOUNT SERVOS (TEST_PLAN.md section 4)")
    print("Sweeping each of the 3 servo outputs: home -> 0 -> 180 -> intermediate -> home.")
    print("Watch each mount move; the firmware ramps at SERVO_MAX_SPEED_DEG_PER_SEC,")
    print("so movement should be smooth, not an instant jump.")
    for servo in (0, 1, 2):
        print(f"\n  Servo {servo}:")
        for label, angle in (("home (90)", 90), ("min (0)", 0), ("max (180)", 180), ("mid (45)", 45)):
            ok = link.send_servo_set(servo, angle)
            print(f"    -> {label}: send_servo_set({servo}, {angle}) = {ok}")
            pause(interactive, f"Confirm servo {servo} is at ~{angle} degrees, then continue")
    print("\n  Homing all servos...")
    ok = link.send_servo_home()
    print(f"    -> send_servo_home() = {ok}")
    pause(interactive)

    print("\n  Invalid-input check (link layer should reject this before it's even sent):")
    bad_servo_ok = link.send_servo_set(9, 90)
    print(f"    -> send_servo_set(9, 90) [invalid servo id] returned {bad_servo_ok}")
    print("       Expected False -- ArduinoLink.send_servo_set() rejects any servo id")
    print("       outside {0,1,2} itself and never transmits, so nothing should move.")
    print("       If a real servo moved just now, that's a bug in this test tool or a")
    print("       version mismatch with serial_link.py, not your firmware.")
    pause(interactive)


def run_doors(link, interactive):
    banner("DOORS (TEST_PLAN.md section 5)")
    print("Doors start LOCKED on firmware boot. This exercises unlock -> auto-relock,")
    print("and immediate re-lock, on both door channels independently.")
    for door in (1, 2):
        print(f"\n  Door {door}:")
        ok = link.send_unlock(door)
        print(f"    -> send_unlock({door}) = {ok}  (LED/lock output should activate)")
        pause(interactive, f"Confirm door {door}'s LED/actuator is ON (unlocked), then continue")
        tel = wait_for_telemetry(link, timeout=0.5)
        print(f"    telemetry: {tel}")
        print(f"    Waiting for the firmware's own auto-relock timeout (DOOR_DEFAULT_UNLOCK_MS)...")
        time.sleep(5.2)
        tel = wait_for_telemetry(link, timeout=0.5)
        print(f"    telemetry after auto-relock window: {tel}")
        print(f"    -> Confirm door {door}'s LED/actuator turned back OFF (locked) on its own.")
        pause(interactive)

    print("\n  Explicit immediate lock (should not wait for any timeout):")
    for door in (1, 2):
        ok = link.send_lock(door)
        print(f"    -> send_lock({door}) = {ok}")
    pause(interactive)

    print("\n  Invalid door id (link layer does NOT validate door ids -- this genuinely")
    print("  tests whether your firmware rejects it, unlike the servo check above):")
    ok = link.send_lock(9)
    print(f"    -> send_lock(9) [invalid] transmitted={ok}")
    print("       Watch that nothing on doors 1/2 (or any other pin) reacted.")
    pause(interactive)


def run_alarms(link, interactive):
    banner("ALARMS / BUZZER / STROBE (TEST_PLAN.md section 6)")
    print("This is the buzzer/LED test. Siren -> ALARM output pins (D4/D5 by default,")
    print("see your firmware's config.h). Wire your buzzer or LED there before running this.")

    print("\n  Siren ON (buzzer should sound):")
    print(f"    -> send_siren(True) = {link.send_siren(True)}")
    pause(interactive, "Confirm buzzer is ON")

    print("  Siren OFF:")
    print(f"    -> send_siren(False) = {link.send_siren(False)}")
    pause(interactive, "Confirm buzzer is OFF")

    print("\n  Strobe ON (LED should light/flash):")
    print(f"    -> send_strobe(True) = {link.send_strobe(True)}")
    pause(interactive, "Confirm LED is ON")

    print("  Strobe OFF:")
    print(f"    -> send_strobe(False) = {link.send_strobe(False)}")
    pause(interactive, "Confirm LED is OFF")

    print("\n  Siren + strobe simultaneously (both channels, independent GPIO pins):")
    link.send_siren(True)
    link.send_strobe(True)
    tel = wait_for_telemetry(link)
    print(f"    telemetry: {tel}")
    pause(interactive, "Confirm BOTH buzzer and LED are active at once")

    print("\n  Clear alarm (should silence/clear both channels at once):")
    print(f"    -> clear_alarm() = {link.clear_alarm()}")
    tel = wait_for_telemetry(link)
    print(f"    telemetry: {tel}")
    pause(interactive, "Confirm both buzzer and LED are OFF")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--port", required=True, help="Serial port, e.g. /dev/ttyACM0 or COM3")
    p.add_argument("--baud", type=int, default=115200)
    p.add_argument("--only", choices=SECTIONS, help="Run only one section")
    p.add_argument("--step", action="store_true", help="Pause after every command for visual confirmation (recommended)")
    args = p.parse_args()

    link = ArduinoLink(True, args.port, args.baud)
    print(f"Connecting to {args.port} @ {args.baud} baud...")
    if not link.connect():
        print(f"FAILED to open {args.port}: {link.error}")
        print("Check the port name, that nothing else (e.g. the Arduino IDE serial")
        print("monitor, or the full IASS app) has it open, and that the board is powered.")
        sys.exit(1)

    time.sleep(1.0)  # let the board finish its own boot/reset after DTR toggle
    print(f"Connected. Link state: {link.state}")

    try:
        sections = [args.only] if args.only else list(SECTIONS)
        for name in sections:
            {"heartbeat": run_heartbeat, "servos": run_servos,
             "doors": run_doors, "alarms": run_alarms}[name](link, args.step)
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        print("\nReturning hardware to a safe state (lock doors, clear alarms, home servos)...")
        link.send_lock(1)
        link.send_lock(2)
        link.clear_alarm()
        link.send_servo_home()
        time.sleep(0.3)
        link.stop()
        print("Done.")


if __name__ == "__main__":
    main()
