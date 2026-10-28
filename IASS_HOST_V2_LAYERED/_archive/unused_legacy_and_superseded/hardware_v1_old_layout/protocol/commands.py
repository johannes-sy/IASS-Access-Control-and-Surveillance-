"""Authoritative Python mirror of the ATmega328P firmware protocol constants.

The firmware currently exposes one logical system device and a fixed 7-byte
frame. Do not duplicate numeric command values elsewhere in the host.
"""
from enum import IntEnum

START = 0xAA
END = 0x55
DEVICE_SYSTEM = 0x01

CMD_HEARTBEAT = 0x01
CMD_LOCK = 0x10
CMD_UNLOCK = 0x11
CMD_SERVO_SET = 0x20
CMD_SERVO_HOME = 0x21
CMD_SIREN = 0x30
CMD_STROBE = 0x31
CMD_TELEMETRY = 0x40
CMD_CLEAR_ALARM = 0x41
TEL_STATUS = 0x80


class Device(IntEnum):
    SYSTEM = DEVICE_SYSTEM


class Command(IntEnum):
    HEARTBEAT = CMD_HEARTBEAT
    LOCK = CMD_LOCK
    UNLOCK = CMD_UNLOCK
    SERVO_SET = CMD_SERVO_SET
    SERVO_HOME = CMD_SERVO_HOME
    SIREN = CMD_SIREN
    STROBE = CMD_STROBE
    TELEMETRY = CMD_TELEMETRY
    CLEAR_ALARM = CMD_CLEAR_ALARM
    TELEMETRY_STATUS = TEL_STATUS
