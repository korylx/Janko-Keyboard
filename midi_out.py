"""WinMM MIDI output (Windows only)."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

MAXPNAMELEN = 32
MMSYSERR_NOERROR = 0

if sys.platform != "win32":
    winmm = None
else:
    winmm = ctypes.WinDLL("winmm")


class MIDIOUTCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid", wintypes.WORD),
        ("wPid", wintypes.WORD),
        ("vDriverVersion", wintypes.UINT),
        ("szPname", wintypes.WCHAR * MAXPNAMELEN),
        ("wTechnology", wintypes.WORD),
        ("wVoices", wintypes.WORD),
        ("wNotes", wintypes.WORD),
        ("wChannelMask", wintypes.WORD),
        ("dwSupport", wintypes.DWORD),
    ]


if winmm is not None:
    winmm.midiOutGetNumDevs.restype = wintypes.UINT

    winmm.midiOutGetDevCapsW.argtypes = [
        ctypes.c_size_t,
        ctypes.POINTER(MIDIOUTCAPSW),
        wintypes.UINT,
    ]
    winmm.midiOutGetDevCapsW.restype = wintypes.UINT

    winmm.midiOutOpen.argtypes = [
        ctypes.POINTER(wintypes.HANDLE),
        ctypes.c_uint,
        ctypes.c_size_t,
        ctypes.c_size_t,
        wintypes.DWORD,
    ]
    winmm.midiOutOpen.restype = wintypes.UINT

    winmm.midiOutShortMsg.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    winmm.midiOutShortMsg.restype = wintypes.UINT

    winmm.midiOutReset.argtypes = [wintypes.HANDLE]
    winmm.midiOutReset.restype = wintypes.UINT

    winmm.midiOutClose.argtypes = [wintypes.HANDLE]
    winmm.midiOutClose.restype = wintypes.UINT


def _require_winmm() -> None:
    if winmm is None:
        raise RuntimeError("MIDI output requires Windows (winmm). Run this from Windows Python, not WSL.")


def list_outputs() -> list[tuple[int, str]]:
    _require_winmm()
    devices: list[tuple[int, str]] = []
    n = winmm.midiOutGetNumDevs()
    for i in range(n):
        caps = MIDIOUTCAPSW()
        err = winmm.midiOutGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps))
        if err == MMSYSERR_NOERROR:
            devices.append((i, caps.szPname))
    return devices


def find_device_id(port_name: str) -> int:
    devices = list_outputs()
    if not devices:
        raise RuntimeError("No MIDI output devices found. Install loopMIDI and create a port.")

    needle = port_name.strip().lower()
    exact = [i for i, name in devices if name.lower() == needle]
    if exact:
        return exact[0]
    partial = [i for i, name in devices if needle in name.lower()]
    if len(partial) == 1:
        return partial[0]
    listing = ", ".join(f"{i}: {name}" for i, name in devices)
    if partial:
        raise RuntimeError(
            f"Port {port_name!r} matches multiple devices. Available: {listing}"
        )
    raise RuntimeError(f"Port {port_name!r} not found. Available: {listing}")


class MidiOut:
    def __init__(self, port_name: str, channel: int = 0) -> None:
        _require_winmm()
        if not 0 <= channel <= 15:
            raise ValueError("channel must be 0-15")
        self.channel = channel
        self.device_id = find_device_id(port_name)
        self._handle = wintypes.HANDLE()
        err = winmm.midiOutOpen(
            ctypes.byref(self._handle),
            self.device_id,
            0,
            0,
            0,
        )
        if err != MMSYSERR_NOERROR:
            raise RuntimeError(f"midiOutOpen failed with error {err}")
        self._h = self._handle
        self._short_msg = winmm.midiOutShortMsg
        self._status_note_on = 0x90 | self.channel
        self._status_note_off = 0x80 | self.channel
        self._status_cc = 0xB0 | self.channel
        self._status_pb = 0xE0 | self.channel

    def _short(self, status: int, data1: int, data2: int = 0) -> None:
        self._short_msg(
            self._h,
            (status & 0xFF) | ((data1 & 0x7F) << 8) | ((data2 & 0x7F) << 16),
        )

    def note_on(self, note: int, velocity: int) -> None:
        self._short_msg(
            self._h,
            self._status_note_on | ((note & 0x7F) << 8) | ((velocity & 0x7F) << 16),
        )

    def note_off(self, note: int, velocity: int = 0) -> None:
        self._short_msg(
            self._h,
            self._status_note_off | ((note & 0x7F) << 8) | ((velocity & 0x7F) << 16),
        )

    def control_change(self, cc: int, value: int) -> None:
        self._short_msg(
            self._h,
            self._status_cc | ((cc & 0x7F) << 8) | ((value & 0x7F) << 16),
        )

    def pitch_bend(self, value: int) -> None:
        value = max(0, min(16383, int(value)))
        self._short_msg(
            self._h,
            self._status_pb | ((value & 0x7F) << 8) | (((value >> 7) & 0x7F) << 16),
        )

    def sustain(self, down: bool) -> None:
        self.control_change(64, 127 if down else 0)

    def panic(self) -> None:
        try:
            self.pitch_bend(8192)
            self.control_change(64, 0)
            self.control_change(123, 0)
        except RuntimeError:
            pass
        winmm.midiOutReset(self._handle)

    def close(self) -> None:
        if self._handle:
            try:
                self.panic()
            except RuntimeError:
                pass
            winmm.midiOutClose(self._handle)
            self._handle = wintypes.HANDLE()
