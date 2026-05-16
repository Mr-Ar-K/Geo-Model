"""Throw estimation helpers."""

from __future__ import annotations


def estimate_throw(fw_rl: float, hw_rl: float) -> float:
    return fw_rl - hw_rl
