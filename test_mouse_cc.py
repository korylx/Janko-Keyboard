"""Pure mapping tests (no Windows / MIDI required)."""

from mouse_cc import apply_delta, cc_int, PITCH_CENTER, PITCH_MAX, wheel_notches


def test_clamp_at_rail() -> None:
    v = 120.0
    v = apply_delta(v, 1000, 0.4)
    assert v == 127.0
    v = apply_delta(v, 1000, 0.4)
    assert v == 127.0


def test_reverse_immediately() -> None:
    v = 127.0
    v = apply_delta(v, 5000, 0.4)  # past the rail
    assert v == 127.0
    v = apply_delta(v, -1, 0.4)
    assert v == 126.6
    assert cc_int(v) == 127
    v = apply_delta(v, -2, 0.4)
    assert cc_int(v) == 126


def test_clamp_at_zero() -> None:
    v = 0.0
    v = apply_delta(v, -800, 0.4)
    assert v == 0.0
    v = apply_delta(v, 1, 0.4)
    assert v == 0.4
    assert cc_int(v) == 0
    v = apply_delta(v, 2, 0.4)
    assert cc_int(v) == 1


def test_up_uses_negative_raw_y() -> None:
    v = 0.0
    v = apply_delta(v, -(-10), 0.4)  # lastY=-10 means up; CC uses -lastY
    assert v == 4.0


def test_pitch_clamp_and_reverse() -> None:
    v = float(PITCH_CENTER)
    v = apply_delta(v, 50000, 24.0, lo=0, hi=PITCH_MAX)
    assert v == float(PITCH_MAX)
    v = apply_delta(v, -1, 24.0, lo=0, hi=PITCH_MAX)
    assert v == float(PITCH_MAX) - 24.0
    assert cc_int(v, 0, PITCH_MAX) == PITCH_MAX - 24


def test_wheel_notches() -> None:
    assert wheel_notches(120) == 1.0
    assert wheel_notches(-240) == -2.0


if __name__ == "__main__":
    test_clamp_at_rail()
    test_reverse_immediately()
    test_clamp_at_zero()
    test_up_uses_negative_raw_y()
    test_pitch_clamp_and_reverse()
    test_wheel_notches()
    print("mouse_cc mapping ok")
