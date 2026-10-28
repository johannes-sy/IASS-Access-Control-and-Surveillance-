# Hardware Safety Notes

## Watchdog

The AVR watchdog is configured for approximately 2 seconds. A stalled main loop therefore resets the MCU.

## Host communication failsafe

If no valid heartbeat is received for more than 5 seconds:

1. both doors are commanded locked;
2. all camera mounts are commanded to 90 degrees;
3. the siren output is silenced;
4. the dedicated alarm/strobe channel is asserted.

When a valid heartbeat returns, the failsafe indication is cleared.

## Command expiry and duplicate protection

Every command except `CMD_HEARTBEAT` carries an issued MCU uptime and TTL in its meta block (see `docs/PROTOCOL.md`). Expired commands are rejected with `ERR_STALE_COMMAND`. A small bounded recent-transaction cache rejects a replayed transaction id with `ERR_DUPLICATE`, preventing accidental repeated physical actuation if a host retries after losing an ACK in transit.

## Emergency stop priority

A `CMD_EMERGENCY_STOP` frame flagged `FLAG_PRIORITY_EMERGENCY` jumps the inbound command queue ahead of whatever's already buffered. If the queue is already full, the single oldest buffered frame is evicted to make room -- the emergency stop is never the frame that gets silently dropped under load.

## Servo limits

The MCU independently validates 0..180 degrees. Production installations should narrow each camera mount's limits to its calibrated mechanical range.

## Door state

The current prototype has no dedicated lock-position sensor. Therefore:

- `commanded_lock` = what the MCU has requested from the actuator output;
- `actual_lock` = the MCU's best actuator-state estimate;
- `door_open` = a real sensor value only when `IASS_ENABLE_DOOR_SENSORS=1`.

Do not treat the prototype estimate as a mechanically verified lock.

## Optional sensors and overrides

Door-position sensors and local overrides are retained in the architecture but disabled by default because the current D4/D5 alarm outputs occupy those physical pins.

Enable them only after changing the pin map and wiring dedicated inputs.

## Emergency stop

Emergency stop stops camera movement and locks both doors. Alarm outputs are cleared. A hardwired emergency-stop/safety circuit is still required where the real installation needs one.

## Power and drivers

The ATmega GPIO must not directly drive solenoids, electric strikes, sirens, high-current LEDs, motors, or other inductive/high-current loads. Use suitable MOSFET/transistor/relay drivers, flyback protection, separate power rails, common-ground strategy or isolation as appropriate, and correctly rated fusing.

## Prototype polarity

The supplied prototype uses LEDs for door simulation. The default setting is:

```text
DOOR_OUTPUT_ACTIVE_HIGH_LOCKED = 0
```

so the LED is ON while the logical door is unlocked. Change this setting for the actual relay/strike electrical polarity.
