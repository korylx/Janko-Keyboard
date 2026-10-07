"""US QWERTY virtual-key codes -> MIDI offsets from root_note (key `1`)."""

from __future__ import annotations

# Virtual-key codes (Winuser.h)
VK_0 = 0x30
VK_1 = 0x31
VK_2 = 0x32
VK_3 = 0x33
VK_4 = 0x34
VK_5 = 0x35
VK_6 = 0x36
VK_7 = 0x37
VK_8 = 0x38
VK_9 = 0x39
VK_A = 0x41
VK_B = 0x42
VK_C = 0x43
VK_D = 0x44
VK_E = 0x45
VK_F = 0x46
VK_G = 0x47
VK_H = 0x48
VK_I = 0x49
VK_J = 0x4A
VK_K = 0x4B
VK_L = 0x4C
VK_M = 0x4D
VK_N = 0x4E
VK_O = 0x4F
VK_P = 0x50
VK_Q = 0x51
VK_R = 0x52
VK_S = 0x53
VK_T = 0x54
VK_U = 0x55
VK_V = 0x56
VK_W = 0x57
VK_X = 0x58
VK_Y = 0x59
VK_Z = 0x5A
VK_OEM_1 = 0xBA  # ;
VK_OEM_PLUS = 0xBB  # =
VK_OEM_COMMA = 0xBC  # ,
VK_OEM_MINUS = 0xBD  # -
VK_OEM_PERIOD = 0xBE  # .
VK_OEM_2 = 0xBF  # /
VK_OEM_4 = 0xDB  # [
VK_OEM_6 = 0xDD  # ]
VK_OEM_7 = 0xDE  # '

_NUMBER = [
    VK_1,
    VK_2,
    VK_3,
    VK_4,
    VK_5,
    VK_6,
    VK_7,
    VK_8,
    VK_9,
    VK_0,
    VK_OEM_MINUS,
    VK_OEM_PLUS,
]
_Q = [
    VK_Q,
    VK_W,
    VK_E,
    VK_R,
    VK_T,
    VK_Y,
    VK_U,
    VK_I,
    VK_O,
    VK_P,
    VK_OEM_4,
    VK_OEM_6,
]
_A = [
    VK_A,
    VK_S,
    VK_D,
    VK_F,
    VK_G,
    VK_H,
    VK_J,
    VK_K,
    VK_L,
    VK_OEM_1,
    VK_OEM_7,
]
_Z = [
    VK_Z,
    VK_X,
    VK_C,
    VK_V,
    VK_B,
    VK_N,
    VK_M,
    VK_OEM_COMMA,
    VK_OEM_PERIOD,
    VK_OEM_2,
]


def _janko_offsets() -> dict[int, int]:
    """Whole-tone rows; A/Z two octaves above number/Q."""
    number = [0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20, 22]
    q = [n + 1 for n in number]
    a = [24, 26, 28, 30, 32, 34, 36, 38, 40, 42, 44]
    z = [25, 27, 29, 31, 33, 35, 37, 39, 41, 43]
    offsets: dict[int, int] = {}
    for keys, values in (
        (_NUMBER, number),
        (_Q, q),
        (_A, a),
        (_Z, z),
    ):
        if len(keys) != len(values):
            raise RuntimeError("janko row length mismatch")
        offsets.update(zip(keys, values))
    return offsets


_MAJOR = [0, 2, 4, 5, 7, 9, 11]  # C D E F G A B


def _scale_offset(index: int) -> int:
    octaves, degree = divmod(index, len(_MAJOR))
    return 12 * octaves + _MAJOR[degree]


def _diatonic_offsets() -> dict[int, int]:
    """C-major diatonic. 1=C … 7=B, 8=next C. q is that same C as 8.

    Each lower row starts on the previous row's 8th key (the repeated C).
    """
    starts = [0, 7, 14, 21]
    rows = (_NUMBER, _Q, _A, _Z)
    offsets: dict[int, int] = {}
    for start, row in zip(starts, rows):
        for i, vk in enumerate(row):
            offsets[vk] = _scale_offset(start + i)
    return offsets


def _column_offsets() -> dict[int, int]:
    """Columns 1qaz, 2wsx, ... Down = +1 semitone, right = +4 (major third).

    With root_note 36 (C2): 1 = C2, 4 = C3. Major scale: 1 a 2 w x e c 4.
    """
    rows = (_NUMBER, _Q, _A, _Z)
    offsets: dict[int, int] = {}
    width = max(len(row) for row in rows)
    for col in range(width):
        base = col * 4
        for down, row in enumerate(rows):
            if col < len(row):
                offsets[row[col]] = base + down
    return offsets


LAYOUTS = {
    "janko": _janko_offsets(),
    "column": _column_offsets(),
    "diatonic": _diatonic_offsets(),
}

# Back-compat alias (janko)
OFFSETS = LAYOUTS["janko"]


def offsets_for(layout: str) -> dict[int, int]:
    key = layout.strip().lower()
    if key not in LAYOUTS:
        known = ", ".join(sorted(LAYOUTS))
        raise ValueError(f"Unknown layout {layout!r}. Use one of: {known}")
    return LAYOUTS[key]


def midi_note(
    vk_code: int,
    root_note: int,
    offsets: dict[int, int] | None = None,
    transpose: int = 0,
) -> int | None:
    table = OFFSETS if offsets is None else offsets
    offset = table.get(vk_code)
    if offset is None:
        return None
    note = root_note + offset + transpose
    if note < 0 or note > 127:
        return None
    return note
