"""ATmega328P V1 fixed-frame protocol.

Wire format (exactly 7 bytes):
    AA | DEVICE | COMMAND | VALUE_H | VALUE_L | XOR | 55

XOR = DEVICE ^ COMMAND ^ VALUE_H ^ VALUE_L
"""
from __future__ import annotations

from dataclasses import dataclass

from .commands import END, START, DEVICE_SYSTEM, TEL_STATUS


def checksum(device: int, command: int, value: int) -> int:
    value &= 0xFFFF
    return (int(device) ^ int(command) ^ ((value >> 8) & 0xFF) ^ (value & 0xFF)) & 0xFF


@dataclass(frozen=True)
class Frame:
    device: int
    command: int
    value: int = 0

    def __post_init__(self):
        if not 0 <= int(self.device) <= 0xFF:
            raise ValueError("device must be 0..255")
        if not 0 <= int(self.command) <= 0xFF:
            raise ValueError("command must be 0..255")
        if not 0 <= int(self.value) <= 0xFFFF:
            raise ValueError("value must be 0..65535")

    @property
    def value_high(self) -> int:
        return (int(self.value) >> 8) & 0xFF

    @property
    def value_low(self) -> int:
        return int(self.value) & 0xFF

    def encode(self) -> bytes:
        return bytes((
            START,
            int(self.device),
            int(self.command),
            self.value_high,
            self.value_low,
            checksum(self.device, self.command, self.value),
            END,
        ))

    def telemetry_state(self) -> dict:
        """Decode the firmware's TEL_STATUS bitfields."""
        if int(self.device) != DEVICE_SYSTEM or int(self.command) != TEL_STATUS:
            return {}
        hi, lo = self.value_high, self.value_low
        return {
            "failsafe": bool(hi & 0x01),
            "siren": bool(hi & 0x02),
            "strobe": bool(hi & 0x04),
            "door1_locked": bool(lo & 0x01),
            "door2_locked": bool(lo & 0x02),
            "door1_open": bool(lo & 0x04),
            "door2_open": bool(lo & 0x08),
            "raw_high": hi,
            "raw_low": lo,
        }


class FrameParser:
    """Incremental parser safe against fragmentation, noise and bad checksums."""

    def __init__(self):
        self._buffer = bytearray()

    def feed(self, data: bytes) -> list[Frame]:
        if data:
            self._buffer.extend(data)
        frames: list[Frame] = []
        while True:
            try:
                start = self._buffer.index(START)
            except ValueError:
                self._buffer.clear()
                break
            if start:
                del self._buffer[:start]
            if len(self._buffer) < 7:
                break
            raw = bytes(self._buffer[:7])
            del self._buffer[:7]
            if raw[6] != END:
                # Re-scan from the next byte rather than discarding a possible
                # overlapping start marker.
                self._buffer = bytearray(raw[1:]) + self._buffer
                continue
            frame = Frame(raw[1], raw[2], (raw[3] << 8) | raw[4])
            if checksum(frame.device, frame.command, frame.value) != raw[5]:
                continue
            frames.append(frame)
        return frames
