from iass.hardware_interface.protocol.frame import Frame, FrameParser, checksum
from iass.hardware_interface.safety import HardwareSafetyPolicy


def test_firmware_frame_exact_encoding():
    f = Frame(0x01, 0x10, 0x0002)
    assert f.encode() == bytes([0xAA, 0x01, 0x10, 0x00, 0x02, 0x13, 0x55])
    assert checksum(0x01, 0x10, 0x0002) == 0x13


def test_frame_round_trip_fragmented():
    f = Frame(0x01, 0x20, 0x027B)
    parser = FrameParser()
    raw = f.encode()
    assert parser.feed(raw[:3]) == []
    assert parser.feed(raw[3:]) == [f]


def test_invalid_checksum_rejected():
    raw = bytearray(Frame(0x01, 0x10, 1).encode())
    raw[5] ^= 0xFF
    assert FrameParser().feed(bytes(raw)) == []


def test_noise_and_bad_end_do_not_poison_parser():
    good = Frame(0x01, 0x01, 0).encode()
    parser = FrameParser()
    assert parser.feed(b"garbage" + b"\xAA\x01\x01\x00\x00\x00\x00" + good) == [Frame(1, 1, 0)]


def test_telemetry_bitfield_decode():
    # high: failsafe+siren+strobe; low: both locks locked + both doors open
    f = Frame(0x01, 0x80, 0x070F)
    t = f.telemetry_state()
    assert t["failsafe"] and t["siren"] and t["strobe"]
    assert t["door1_locked"] and t["door2_locked"]
    assert t["door1_open"] and t["door2_open"]


def test_unlock_requires_authorization():
    p = HardwareSafetyPolicy()
    p.heartbeat()
    assert not p.authorize_unlock("DOOR_1", "")
    assert p.authorize_unlock("DOOR_1", "AUTHORIZED")


def test_all_firmware_commands_use_system_device_and_seven_byte_frames():
    from iass.hardware_interface.protocol.commands import (
        CMD_HEARTBEAT, CMD_LOCK, CMD_UNLOCK, CMD_SERVO_SET,
        CMD_SERVO_HOME, CMD_SIREN, CMD_STROBE, CMD_TELEMETRY,
        CMD_CLEAR_ALARM,
    )
    commands = [
        Frame(1, CMD_HEARTBEAT, 0), Frame(1, CMD_LOCK, 1),
        Frame(1, CMD_UNLOCK, 2), Frame(1, CMD_SERVO_SET, 0x02B4),
        Frame(1, CMD_SERVO_HOME, 0), Frame(1, CMD_SIREN, 1),
        Frame(1, CMD_STROBE, 1), Frame(1, CMD_TELEMETRY, 0),
        Frame(1, CMD_CLEAR_ALARM, 0),
    ]
    assert all(len(frame.encode()) == 7 for frame in commands)
    assert all(frame.encode()[0] == 0xAA and frame.encode()[-1] == 0x55 for frame in commands)


def test_safety_policy_blocks_unlock_during_estop():
    from iass.hardware_interface.controller import HardwareController
    from iass.hardware_interface.drivers import MockHardwareDriver
    from iass.hardware_interface.models import DeviceType
    from iass.hardware_control.device_registry import DeviceDefinition, DeviceRegistry
    from iass.hardware_state import HardwareStateManager
    from types import SimpleNamespace

    settings = SimpleNamespace(hardware_command_dedup_seconds=.75)
    defs = [DeviceDefinition("door_1", DeviceType.DOOR_LOCK.value, zone="MAIN_ENTRANCE", limits={"max_unlock_duration": 10})]
    safety = HardwareSafetyPolicy()
    h = HardwareController(settings, DeviceRegistry(defs), HardwareStateManager(), MockHardwareDriver(), safety=safety)
    h.start()

    # Normal unlock succeeds with no e-stop active.
    r = h.unlock_door("door_1")
    assert r.success is True

    # Once e-stop trips, unlock must be refused, not just slow/queued.
    safety.emergency_stop()
    r = h.unlock_door("door_1")
    assert r.success is False
    assert r.result == "SAFETY_BLOCKED"

    # Clearing e-stop without operator authorization must NOT lift the block.
    assert safety.clear_estop(operator_authorized=False) is False
    r = h.unlock_door("door_1")
    assert r.success is False

    # Only an authorized clear restores normal operation.
    assert safety.clear_estop(operator_authorized=True) is True
    r = h.unlock_door("door_1")
    assert r.success is True
