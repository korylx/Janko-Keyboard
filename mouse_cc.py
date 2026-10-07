"""Relative mouse deltas → clamped absolute sliders."""

from __future__ import annotations

PITCH_CENTER = 8192
PITCH_MAX = 16383
WHEEL_NOTCH = 120.0


def apply_delta(
    value: float,
    delta: float,
    sensitivity: float,
    lo: float = 0.0,
    hi: float = 127.0,
) -> float:
    """Add delta*sensitivity and clamp. Overflow past lo/hi is discarded."""
    return max(float(lo), min(float(hi), float(value) + float(delta) * float(sensitivity)))


def cc_int(value: float, lo: int = 0, hi: int = 127) -> int:
    return max(lo, min(hi, int(round(value))))


def wheel_notches(raw_delta: int) -> float:
    return float(raw_delta) / WHEEL_NOTCH
