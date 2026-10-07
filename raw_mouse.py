"""Windows Raw Input mouse (relative counts), message-only window."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Callable

WM_INPUT = 0x00FF
WM_DESTROY = 0x0002
RID_INPUT = 0x10000003
RIM_TYPEMOUSE = 0
RIDEV_INPUTSINK = 0x00000100
RIDEV_REMOVE = 0x00000001
MOUSE_MOVE_ABSOLUTE = 0x01
RI_MOUSE_WHEEL = 0x0400
HID_USAGE_PAGE_GENERIC = 0x01
HID_USAGE_GENERIC_MOUSE = 0x02
HWND_MESSAGE = wintypes.HWND(-3)

WNDPROC = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM
)


class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", wintypes.USHORT),
        ("usUsage", wintypes.USHORT),
        ("dwFlags", wintypes.DWORD),
        ("hwndTarget", wintypes.HWND),
    ]


class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType", wintypes.DWORD),
        ("dwSize", wintypes.DWORD),
        ("hDevice", wintypes.HANDLE),
        ("wParam", wintypes.WPARAM),
    ]


class _RAWMOUSEBUTTONS(ctypes.Union):
    class _Names(ctypes.Structure):
        _fields_ = [
            ("usButtonFlags", wintypes.USHORT),
            ("usButtonData", wintypes.USHORT),
        ]

    _anonymous_ = ("names",)
    _fields_ = [
        ("ulButtons", wintypes.ULONG),
        ("names", _Names),
    ]


class RAWMOUSE(ctypes.Structure):
    _fields_ = [
        ("usFlags", wintypes.USHORT),
        ("buttons", _RAWMOUSEBUTTONS),
        ("ulRawButtons", wintypes.ULONG),
        ("lLastX", wintypes.LONG),
        ("lLastY", wintypes.LONG),
        ("ulExtraInformation", wintypes.ULONG),
    ]


class RAWINPUT(ctypes.Structure):
    class _Data(ctypes.Union):
        _fields_ = [("mouse", RAWMOUSE)]

    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("data", _Data),
    ]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [
        ("style", wintypes.UINT),
        ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int),
        ("cbWndExtra", ctypes.c_int),
        ("hInstance", wintypes.HINSTANCE),
        ("hIcon", wintypes.HANDLE),
        ("hCursor", wintypes.HANDLE),
        ("hbrBackground", wintypes.HBRUSH),
        ("lpszMenuName", wintypes.LPCWSTR),
        ("lpszClassName", wintypes.LPCWSTR),
    ]


if sys.platform == "win32":
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    user32.DefWindowProcW.argtypes = [
        wintypes.HWND,
        wintypes.UINT,
        wintypes.WPARAM,
        wintypes.LPARAM,
    ]
    user32.DefWindowProcW.restype = ctypes.c_ssize_t

    user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
    user32.RegisterClassW.restype = wintypes.ATOM

    user32.CreateWindowExW.argtypes = [
        wintypes.DWORD,
        wintypes.LPCWSTR,
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        wintypes.HWND,
        wintypes.HMENU,
        wintypes.HINSTANCE,
        wintypes.LPVOID,
    ]
    user32.CreateWindowExW.restype = wintypes.HWND

    user32.DestroyWindow.argtypes = [wintypes.HWND]
    user32.DestroyWindow.restype = wintypes.BOOL

    user32.RegisterRawInputDevices.argtypes = [
        ctypes.POINTER(RAWINPUTDEVICE),
        wintypes.UINT,
        wintypes.UINT,
    ]
    user32.RegisterRawInputDevices.restype = wintypes.BOOL

    user32.GetRawInputData.argtypes = [
        wintypes.HANDLE,
        wintypes.UINT,
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.UINT),
        wintypes.UINT,
    ]
    user32.GetRawInputData.restype = wintypes.UINT

    kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
    kernel32.GetModuleHandleW.restype = wintypes.HMODULE
else:
    user32 = None
    kernel32 = None


class RawMouseListener:
    """Hidden HWND_MESSAGE window that forwards relative mouse deltas."""

    def __init__(
        self,
        on_delta: Callable[[int, int], None],
        on_wheel: Callable[[int], None] | None = None,
    ) -> None:
        if user32 is None:
            raise RuntimeError("Raw mouse requires Windows.")
        self._on_delta = on_delta
        self._on_wheel = on_wheel
        self._hwnd = None
        self._atom = 0
        self._class_name = "KeyboardMidiRawMouse"
        self._wndproc = WNDPROC(self._wnd_proc)
        self._raw = RAWINPUT()
        self._raw_size = wintypes.UINT(ctypes.sizeof(RAWINPUT))
        self._header_size = ctypes.sizeof(RAWINPUTHEADER)
        self._register_window()
        self._register_raw()

    def _wnd_proc(self, hwnd, msg, wparam, lparam) -> int:
        if msg == WM_INPUT:
            self._handle_input(lparam)
            return 0
        return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _register_window(self) -> None:
        inst = kernel32.GetModuleHandleW(None)
        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = self._wndproc
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = inst
        wc.hIcon = None
        wc.hCursor = None
        wc.hbrBackground = None
        wc.lpszMenuName = None
        wc.lpszClassName = self._class_name
        atom = user32.RegisterClassW(ctypes.byref(wc))
        if not atom:
            err = ctypes.get_last_error()
            if err != 1410:  # ERROR_CLASS_ALREADY_EXISTS
                raise ctypes.WinError(err)
        self._atom = atom
        hwnd = user32.CreateWindowExW(
            0,
            self._class_name,
            "KeyboardMidiRawMouse",
            0,
            0,
            0,
            0,
            0,
            HWND_MESSAGE,
            None,
            inst,
            None,
        )
        if not hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self._hwnd = hwnd

    def _register_raw(self) -> None:
        rid = RAWINPUTDEVICE()
        rid.usUsagePage = HID_USAGE_PAGE_GENERIC
        rid.usUsage = HID_USAGE_GENERIC_MOUSE
        rid.dwFlags = RIDEV_INPUTSINK
        rid.hwndTarget = self._hwnd
        if not user32.RegisterRawInputDevices(
            ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE)
        ):
            raise ctypes.WinError(ctypes.get_last_error())

    def _handle_input(self, hraw) -> None:
        self._raw_size.value = ctypes.sizeof(RAWINPUT)
        got = user32.GetRawInputData(
            hraw,
            RID_INPUT,
            ctypes.byref(self._raw),
            ctypes.byref(self._raw_size),
            self._header_size,
        )
        if got == 0xFFFFFFFF or got == 0:
            return
        raw = self._raw
        if raw.header.dwType != RIM_TYPEMOUSE:
            return
        mouse = raw.data.mouse
        if not (mouse.usFlags & MOUSE_MOVE_ABSOLUTE):
            dx = int(mouse.lLastX)
            dy = int(mouse.lLastY)
            if dx or dy:
                self._on_delta(dx, dy)
        flags = int(mouse.buttons.names.usButtonFlags)
        if flags & RI_MOUSE_WHEEL and self._on_wheel is not None:
            wheel = ctypes.c_short(mouse.buttons.names.usButtonData).value
            if wheel:
                self._on_wheel(int(wheel))

    def close(self) -> None:
        if user32 is None:
            return
        if self._hwnd:
            rid = RAWINPUTDEVICE()
            rid.usUsagePage = HID_USAGE_PAGE_GENERIC
            rid.usUsage = HID_USAGE_GENERIC_MOUSE
            rid.dwFlags = RIDEV_REMOVE
            rid.hwndTarget = None
            user32.RegisterRawInputDevices(
                ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE)
            )
            user32.DestroyWindow(self._hwnd)
            self._hwnd = None
