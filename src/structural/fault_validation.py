"""Fault validation helpers."""

from __future__ import annotations

from typing import Mapping


def validate_fault_presence(observed_rl: float, expected_rl: float, threshold: float = 10.0) -> bool:
    return abs(observed_rl - expected_rl) >= threshold
