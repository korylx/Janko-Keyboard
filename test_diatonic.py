"""Diatonic layout: 1=C, 7=B, 8=q=next C."""

from keymap import (
    VK_1,
    VK_7,
    VK_8,
    VK_A,
    VK_I,
    VK_Q,
    midi_note,
    offsets_for,
)


def test_diatonic_c_major() -> None:
    o = offsets_for("diatonic")
    root = 36
    assert midi_note(VK_1, root, o) == 36  # C2
    assert midi_note(VK_7, root, o) == 47  # B2
    assert midi_note(VK_8, root, o) == 48  # C3
    assert midi_note(VK_Q, root, o) == 48  # same C as 8
    assert midi_note(VK_I, root, o) == 60  # C4 (q-row 8th key)
    assert midi_note(VK_A, root, o) == 60  # same C as i


def test_diatonic_scale() -> None:
    o = offsets_for("diatonic")
    root = 36
    from keymap import VK_2, VK_3, VK_4, VK_5, VK_6, VK_W

    assert midi_note(VK_2, root, o) == 38
    assert midi_note(VK_3, root, o) == 40
    assert midi_note(VK_4, root, o) == 41
    assert midi_note(VK_5, root, o) == 43
    assert midi_note(VK_6, root, o) == 45
    assert midi_note(VK_W, root, o) == 50  # D above q's C
    assert midi_note(VK_1, root, o, transpose=12) == 48


if __name__ == "__main__":
    test_diatonic_c_major()
    test_diatonic_scale()
    print("diatonic layout ok")
