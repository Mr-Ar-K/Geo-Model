"""Fault-to-borehole distance helpers."""

from __future__ import annotations

import math


def point_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    return math.hypot(x2 - x1, y2 - y1)
