"""Run the QWERTY MIDI controller (Windows Python, not WSL)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent / "config.json"


def send_cc_test(
    midi,
    cc_y: int | None,
    wheel_cc: int | None,
    pitch_bend: bool = True,
) -> None:
    import time

    print(
        "Sending MIDI test (expression/pitch only if enabled).\n"
        "Ableton MIDI Map only hears this if the loopMIDI input has Track AND Remote enabled\n"
        "(Preferences > Link, Tempo & MIDI).\n"
    )
    if cc_y is not None:
        for value in range(0, 128, 8):
            midi.control_change(cc_y, value)
            print(f"  sent CC{cc_y}={value:3d}")
            time.sleep(0.04)
        midi.control_change(cc_y, 127)
    if pitch_bend:
        for pb in (0, 4096, 8192, 12288, 16383):
            midi.pitch_bend(pb)
            print(f"  sent pitch bend={pb}")
            time.sleep(0.04)
        midi.pitch_bend(8192)
    if wheel_cc is not None:
        for value in (0, 64, 127):
            midi.control_change(wheel_cc, value)
            print(f"  sent CC{wheel_cc}={value}")
            time.sleep(0.04)
    midi.note_on(60, 100)
    print("  sent note-on  60 vel=100")
    time.sleep(0.25)
    midi.note_off(60)
    print("  sent note-off 60")
    print("Done.")


def load_config() -> dict:
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    if sys.platform != "win32":
        print(
            "This program uses a Windows keyboard hook and WinMM MIDI.\n"
            "Run it with Windows Python (py -3 main.py), not from WSL.",
            file=sys.stderr,
        )
        return 1

    import ctypes
    import gc
    from ctypes import wintypes

    from hook import KeyboardController
    from midi_out import MidiOut, list_outputs
    from raw_mouse import RawMouseListener

    user32 = ctypes.WinDLL("user32")
    kernel32 = ctypes.WinDLL("kernel32")
    winmm = ctypes.WinDLL("winmm")
    PM_REMOVE = 0x0001
    WM_QUIT = 0x0012
    QS_ALLINPUT = 0x04FF
    INFINITE = 0xFFFFFFFF
    HIGH_PRIORITY_CLASS = 0x00000080
    THREAD_PRIORITY_HIGHEST = 2
    CTRL_C_EVENT = 0
    CTRL_BREAK_EVENT = 1
    CTRL_CLOSE_EVENT = 2

    kernel32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.SetPriorityClass.restype = wintypes.BOOL
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.GetCurrentThread.restype = wintypes.HANDLE
    kernel32.GetCurrentThreadId.restype = wintypes.DWORD
    kernel32.SetThreadPriority.argtypes = [wintypes.HANDLE, ctypes.c_int]
    kernel32.SetThreadPriority.restype = wintypes.BOOL
    kernel32.SetConsoleCtrlHandler.argtypes = [ctypes.c_void_p, wintypes.BOOL]
    kernel32.SetConsoleCtrlHandler.restype = wintypes.BOOL
    winmm.timeBeginPeriod.argtypes = [wintypes.UINT]
    winmm.timeBeginPeriod.restype = wintypes.UINT
    winmm.timeEndPeriod.argtypes = [wintypes.UINT]
    winmm.timeEndPeriod.restype = wintypes.UINT
    user32.MsgWaitForMultipleObjects.argtypes = [
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.BOOL,
        wintypes.DWORD,
        wintypes.DWORD,
    ]
    user32.MsgWaitForMultipleObjects.restype = wintypes.DWORD
    user32.PostThreadMessageW.argtypes = [
        wintypes.DWORD,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]

    kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), HIGH_PRIORITY_CLASS)
    kernel32.SetThreadPriority(kernel32.GetCurrentThread(), THREAD_PRIORITY_HIGHEST)
    winmm.timeBeginPeriod(1)
    gc.disable()

    class POINT(ctypes.Structure):
        _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

    class MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt", POINT),
        ]

    user32.PeekMessageW.argtypes = [
        ctypes.POINTER(MSG),
        wintypes.HWND,
        wintypes.UINT,
        wintypes.UINT,
        wintypes.UINT,
    ]
    user32.PeekMessageW.restype = wintypes.BOOL
    user32.DispatchMessageW.argtypes = [ctypes.POINTER(MSG)]

    cfg = load_config()
    cc_y_raw = cfg.get("mouse_cc_y", 11)
    cc_y = None if cc_y_raw in (None, "null") else int(cc_y_raw)
    mouse_pitch_bend = bool(cfg.get("mouse_pitch_bend", True))
    wheel_cc = cfg.get("mouse_wheel_cc", 1)
    if wheel_cc is None or wheel_cc == "null":
        wheel_cc_arg = None
    else:
        wheel_cc_arg = int(wheel_cc)
    print("MIDI outputs:")
    for index, name in list_outputs():
        print(f"  {index}: {name}")

    midi = MidiOut(cfg["port"], int(cfg.get("channel", 0)))
    print(f"Opened {cfg['port']!r} (device {midi.device_id}), channel {midi.channel + 1}")

    if "--send-test" in sys.argv:
        try:
            send_cc_test(midi, cc_y, wheel_cc_arg, mouse_pitch_bend)
        finally:
            midi.close()
            winmm.timeEndPeriod(1)
            gc.enable()
        return 0
    layout = str(cfg.get("layout", "column"))
    print("Caps Lock + Alt toggles. Space = sustain. Arrows transpose. Diatonic: Shift bends, Alt+Shift legato.")
    print("Mouse: expression/pitch off unless enabled in config. Wheel=CC if set.")

    debug = bool(cfg.get("debug", False))
    if debug:
        print("debug=true: printing every note-key down/up. Ghosted keys never show a down.\n")

    controller = KeyboardController(
        midi=midi,
        root_note=int(cfg.get("root_note", 36)),
        velocities=cfg.get("velocity", {}),
        on_status=print,
        debug=debug,
        layout=layout,
        mouse_cc_y=cc_y,
        mouse_pitch_bend=mouse_pitch_bend,
        mouse_sensitivity=float(cfg.get("mouse_sensitivity", 0.4)),
        mouse_pitch_sensitivity=float(cfg.get("mouse_pitch_sensitivity", 24.0)),
        mouse_wheel_cc=wheel_cc_arg,
        mouse_wheel_sensitivity=float(cfg.get("mouse_wheel_sensitivity", 8.0)),
    )
    controller.install()
    mouse = RawMouseListener(controller.on_mouse_delta, controller.on_mouse_wheel)

    main_tid = kernel32.GetCurrentThreadId()
    HandlerRoutine = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.DWORD)

    def _on_console_ctrl(ctrl_type: int) -> bool:
        if ctrl_type in (CTRL_C_EVENT, CTRL_BREAK_EVENT, CTRL_CLOSE_EVENT):
            user32.PostThreadMessageW(main_tid, WM_QUIT, 0, 0)
            return True
        return False

    ctrl_handler = HandlerRoutine(_on_console_ctrl)
    kernel32.SetConsoleCtrlHandler(ctrl_handler, True)

    msg = MSG()
    try:
        while True:
            user32.MsgWaitForMultipleObjects(0, None, False, INFINITE, QS_ALLINPUT)
            while user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                if msg.message == WM_QUIT:
                    raise KeyboardInterrupt
                user32.DispatchMessageW(ctypes.byref(msg))
    except KeyboardInterrupt:
        print("\nQuitting.")
    finally:
        kernel32.SetConsoleCtrlHandler(ctrl_handler, False)
        winmm.timeEndPeriod(1)
        mouse.close()
        controller.uninstall()
        midi.close()
        gc.enable()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
