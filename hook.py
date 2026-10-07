"""Low-level keyboard hook: notes, sustain, velocity Alts, Caps+Alt toggle."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Callable

from keymap import midi_note, offsets_for
from midi_out import MidiOut
from mouse_cc import (
    PITCH_CENTER,
    PITCH_MAX,
    apply_delta,
    cc_int,
    wheel_notches,
)

VK_SPACE = 0x20
VK_CAPITAL = 0x14
VK_SHIFT = 0x10
VK_LSHIFT = 0xA0
VK_RSHIFT = 0xA1
VK_MENU = 0x12
VK_LMENU = 0xA4
VK_RMENU = 0xA5
VK_LEFT = 0x25
VK_UP = 0x26
VK_RIGHT = 0x27
VK_DOWN = 0x28

WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105

LLKHF_EXTENDED = 0x01
LLKHF_UP = 0x80
HC_ACTION = 0

LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
)

if sys.platform == "win32":
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.SetWindowsHookExW.argtypes = [
        ctypes.c_int,
        LowLevelKeyboardProc,
        wintypes.HINSTANCE,
        wintypes.DWORD,
    ]
    user32.SetWindowsHookExW.restype = wintypes.HHOOK

    user32.CallNextHookEx.argtypes = [
        wintypes.HHOOK,
        ctypes.c_int,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.CallNextHookEx.restype = ctypes.c_ssize_t

    user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
    user32.UnhookWindowsHookEx.restype = wintypes.BOOL

    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
else:
    user32 = None
    kernel32 = None


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD),
        ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_size_t),
    ]


def _clamp_velocity(value: int) -> int:
    return max(1, min(127, int(value)))


class KeyboardController:
    def __init__(
        self,
        midi: MidiOut,
        root_note: int,
        velocities: dict[str, int],
        on_status: Callable[[str], None] | None = None,
        debug: bool = False,
        layout: str = "column",
        mouse_cc_y: int | None = 11,
        mouse_pitch_bend: bool = True,
        mouse_sensitivity: float = 0.4,
        mouse_pitch_sensitivity: float = 24.0,
        mouse_wheel_cc: int | None = 1,
        mouse_wheel_sensitivity: float = 8.0,
    ) -> None:
        if user32 is None:
            raise RuntimeError("Keyboard hook requires Windows. Run from Windows Python, not WSL.")
        self.midi = midi
        self.root_note = root_note
        self.layout = layout.strip().lower()
        self.offsets = offsets_for(self.layout)
        self.vel_default = _clamp_velocity(velocities.get("default", 80))
        self.vel_left = _clamp_velocity(velocities.get("left_alt", 50))
        self.vel_right = _clamp_velocity(velocities.get("right_alt", 110))
        self.on_status = on_status or (lambda _msg: None)
        self.debug = debug
        self.mouse_cc_y = int(mouse_cc_y) if mouse_cc_y is not None else None
        self.mouse_pitch_bend = bool(mouse_pitch_bend)
        self.mouse_sensitivity = float(mouse_sensitivity)
        self.mouse_pitch_sensitivity = float(mouse_pitch_sensitivity)
        self.mouse_wheel_cc = int(mouse_wheel_cc) if mouse_wheel_cc is not None else None
        self.mouse_wheel_sensitivity = float(mouse_wheel_sensitivity)
        self._cc_y = 0.0
        self._pitch = float(PITCH_CENTER)
        self._wheel_cc = 0.0
        self._last_cc_y = 0
        self._last_pitch = PITCH_CENTER
        self._last_wheel_cc = 0

        self.enabled = False
        self._caps = False
        self._lalt = False
        self._ralt = False
        self._swallow_lalt = False
        self._swallow_ralt = False
        self._toggle_armed = True
        self._held_notes: dict[int, int] = {}  # vk -> sounding midi
        self._held_natural: dict[int, int] = {}  # vk -> unbent layout midi
        self._space = False
        self._lshift = False
        self._rshift = False
        self._transpose = 0

        self._hook = None
        self._proc = LowLevelKeyboardProc(self._low_level)
        self._installed = False

    def on_mouse_delta(self, dx: int, dy: int) -> None:
        if not self.enabled:
            return
        if self.mouse_pitch_bend and dx:
            self._pitch = apply_delta(
                self._pitch,
                dx,
                self.mouse_pitch_sensitivity,
                lo=0.0,
                hi=float(PITCH_MAX),
            )
            pitch = cc_int(self._pitch, 0, PITCH_MAX)
            if pitch != self._last_pitch:
                self.midi.pitch_bend(pitch)
                self._last_pitch = pitch
                if self.debug:
                    self.on_status(f"  mouse LR    pitch={pitch}")
        if self.mouse_cc_y is not None and dy:
            self._cc_y = apply_delta(self._cc_y, -dy, self.mouse_sensitivity)
            up = cc_int(self._cc_y)
            if up != self._last_cc_y:
                self.midi.control_change(self.mouse_cc_y, up)
                self._last_cc_y = up
                if self.debug:
                    self.on_status(f"  mouse up    CC{self.mouse_cc_y}={up}")

    def on_mouse_wheel(self, wheel_delta: int) -> None:
        if not self.enabled or self.mouse_wheel_cc is None:
            return
        notches = wheel_notches(wheel_delta)
        self._wheel_cc = apply_delta(
            self._wheel_cc,
            notches,
            self.mouse_wheel_sensitivity,
        )
        value = cc_int(self._wheel_cc)
        if value != self._last_wheel_cc:
            self.midi.control_change(self.mouse_wheel_cc, value)
            self._last_wheel_cc = value
            if self.debug:
                self.on_status(f"  wheel       CC{self.mouse_wheel_cc}={value}")

    def current_velocity(self) -> int:
        if self._ralt:
            return self.vel_right
        if self._lalt:
            return self.vel_left
        return self.vel_default

    def install(self) -> None:
        handle = kernel32.GetModuleHandleW(None)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._proc, handle, 0)
        if not self._hook:
            raise ctypes.WinError(ctypes.get_last_error())
        self._installed = True
        self._emit_status()

    def uninstall(self) -> None:
        if self._installed and self._hook:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
            self._installed = False
        self._silence()

    def _emit_status(self) -> None:
        state = "ON" if self.enabled else "OFF"
        self.on_status(
            f"[{state}] layout={self.layout} velocity={self.current_velocity()} "
            f"(default={self.vel_default} LAlt={self.vel_left} RAlt={self.vel_right})"
            f" cc{self.mouse_cc_y}={self._last_cc_y} pitch={self._last_pitch}"
            f" wheel_cc={self.mouse_wheel_cc}={self._last_wheel_cc if self.mouse_wheel_cc is not None else 'off'}"
            f" transpose={self._transpose}"
        )

    def _silence(self) -> None:
        if self._space:
            try:
                self.midi.sustain(False)
            except RuntimeError:
                pass
            self._space = False
        self._held_notes.clear()
        self._held_natural.clear()
        try:
            self.midi.panic()
        except RuntimeError:
            pass

    def _toggle(self) -> None:
        self.enabled = not self.enabled
        if not self.enabled:
            self._silence()
        self._emit_status()

    def _is_left_alt(self, vk: int, flags: int) -> bool:
        if vk == VK_LMENU:
            return True
        if vk == VK_MENU and not (flags & LLKHF_EXTENDED):
            return True
        return False

    def _is_right_alt(self, vk: int, flags: int) -> bool:
        if vk == VK_RMENU:
            return True
        if vk == VK_MENU and (flags & LLKHF_EXTENDED):
            return True
        return False

    def _is_left_shift(self, vk: int) -> bool:
        return vk in (VK_LSHIFT, VK_SHIFT)

    def _is_right_shift(self, vk: int) -> bool:
        return vk == VK_RSHIFT

    def _any_alt(self) -> bool:
        return self._lalt or self._ralt

    def _any_shift(self) -> bool:
        return self._lshift or self._rshift

    def _bend_semitones(self) -> int:
        if self._rshift:
            return 1
        if self._lshift:
            return -1
        return 0

    def _diatonic(self) -> bool:
        return self.layout == "diatonic"

    def _natural_note(self, vk: int) -> int | None:
        return midi_note(vk, self.root_note, self.offsets, self._transpose)

    def _apply_bend(self, natural: int) -> int:
        return max(0, min(127, natural + self._bend_semitones()))

    def _should_bend_new_note(self) -> bool:
        return self._diatonic() and self._bend_semitones() != 0

    def _unbend_held_notes(self) -> None:
        if not self._diatonic():
            return
        for vk, old in list(self._held_notes.items()):
            natural = self._held_natural.get(vk)
            if natural is None or natural == old:
                continue
            self.midi.note_off(old)
            self.midi.note_on(natural, self.current_velocity())
            self._held_notes[vk] = natural
            if self.debug:
                self.on_status(f"  unbend {old}->{natural}")

    def _retarget_held_notes(self, *, single_only: bool = False) -> None:
        if not self._diatonic():
            return
        if single_only and len(self._held_notes) != 1:
            return
        for vk, old in list(self._held_notes.items()):
            natural = self._held_natural.get(vk)
            if natural is None:
                continue
            new_note = self._apply_bend(natural)
            if new_note == old:
                continue
            self.midi.note_off(old)
            self.midi.note_on(new_note, self.current_velocity())
            self._held_notes[vk] = new_note
            if self.debug:
                self.on_status(f"  retarget {old}->{new_note}")

    def _reset_toggle_arm(self) -> None:
        if not self._caps and not self._any_alt():
            self._toggle_armed = True

    def _low_level(self, nCode: int, wParam: int, lParam: int) -> int:
        try:
            if nCode < HC_ACTION:
                return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)
            info = ctypes.cast(lParam, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
            vk = int(info.vkCode)
            flags = int(info.flags)
            is_up = bool(flags & LLKHF_UP) or wParam in (WM_KEYUP, WM_SYSKEYUP)
            eat = self._handle_key(vk, flags, is_up)
            if eat:
                return 1
        except Exception as exc:  # noqa: BLE001 — never throw out of a hook
            try:
                self.on_status(f"hook error: {exc}")
            except Exception:
                pass
        return user32.CallNextHookEx(self._hook, nCode, wParam, lParam)

    def _handle_key(self, vk: int, flags: int, is_up: bool) -> bool:
        if vk == VK_CAPITAL:
            return self._handle_caps(is_up)
        if self._is_left_alt(vk, flags) or self._is_right_alt(vk, flags):
            return self._handle_alt(vk, flags, is_up)
        if not self.enabled:
            return False
        if self._is_left_shift(vk) or self._is_right_shift(vk):
            return self._handle_shift(vk, is_up)
        if vk in (VK_LEFT, VK_RIGHT, VK_UP, VK_DOWN):
            return self._handle_arrow(vk, is_up)
        if vk == VK_SPACE:
            return self._handle_space(is_up)
        if vk in self.offsets:
            return self._handle_note(vk, is_up)
        return False

    def _handle_caps(self, is_up: bool) -> bool:
        if is_up:
            self._caps = False
            self._reset_toggle_arm()
            return True
        if self._caps:
            return True
        self._caps = True
        if self._any_alt() and self._toggle_armed:
            self._toggle()
            self._toggle_armed = False
        return True

    def _handle_alt(self, vk: int, flags: int, is_up: bool) -> bool:
        left = self._is_left_alt(vk, flags)
        if is_up:
            if left:
                self._lalt = False
                swallow = self._swallow_lalt
                self._swallow_lalt = False
            else:
                self._ralt = False
                swallow = self._swallow_ralt
                self._swallow_ralt = False
            self._reset_toggle_arm()
            if self.enabled:
                self._emit_status()
            return swallow
        if left:
            if self._lalt:
                return self._swallow_lalt
            self._lalt = True
        else:
            if self._ralt:
                return self._swallow_ralt
            self._ralt = True
        if self._caps and self._toggle_armed:
            self._toggle()
            self._toggle_armed = False
        eat = self.enabled or self._caps
        if left:
            self._swallow_lalt = eat
        else:
            self._swallow_ralt = eat
        if self.enabled:
            self._emit_status()
        return eat

    def _handle_shift(self, vk: int, is_up: bool) -> bool:
        left = self._is_left_shift(vk) and not self._is_right_shift(vk)
        if is_up:
            if left:
                self._lshift = False
            else:
                self._rshift = False
            self._retarget_held_notes()
            return True
        if left:
            if self._lshift:
                return True
            self._lshift = True
        else:
            if self._rshift:
                return True
            self._rshift = True
        self._retarget_held_notes(single_only=True)
        return True

    def _handle_arrow(self, vk: int, is_up: bool) -> bool:
        if is_up:
            return True
        if vk == VK_UP:
            self._transpose += 12
        elif vk == VK_DOWN:
            self._transpose -= 12
        elif vk == VK_RIGHT:
            self._transpose += 1
        elif vk == VK_LEFT:
            self._transpose -= 1
        self._emit_status()
        return True

    def _handle_space(self, is_up: bool) -> bool:
        if is_up:
            if self._space:
                self.midi.sustain(False)
                self._space = False
            return True
        if self._space:
            return True
        self.midi.sustain(True)
        self._space = True
        return True

    def _handle_note(self, vk: int, is_up: bool) -> bool:
        if is_up:
            note = self._held_notes.pop(vk, None)
            self._held_natural.pop(vk, None)
            if note is not None:
                self.midi.note_off(note)
            return True
        if vk in self._held_notes:
            return True
        natural = self._natural_note(vk)
        if natural is None:
            return True
        bend_new = self._should_bend_new_note()
        if bend_new and self._held_notes:
            self._unbend_held_notes()
        note = self._apply_bend(natural) if bend_new else natural
        vel = self.current_velocity()
        self.midi.note_on(note, vel)
        self._held_notes[vk] = note
        self._held_natural[vk] = natural
        if self.debug:
            bent = " bent" if note != natural else ""
            self.on_status(
                f"  note-on {note}{bent} vel={vel} held={list(self._held_notes.values())}"
            )
        return True
