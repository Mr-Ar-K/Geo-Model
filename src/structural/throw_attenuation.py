"""Throw tapering along fault traces."""

from __future__ import annotations


def taper_factor(chainage: float, total_length: float) -> float:
    if total_length <= 0:
        return 1.0
    ratio = max(0.0, min(1.0, chainage / total_length))
    return max(0.0, 1.0 - abs(2.0 * ratio - 1.0))
