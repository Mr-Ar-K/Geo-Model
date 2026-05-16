"""Nearest-borehole utilities."""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence


def nearest_boreholes(target_x: float, target_y: float, collars: Sequence[Mapping[str, object]], limit: int = 4):
    ordered = sorted(
        collars,
        key=lambda row: (float(row['x']) - target_x) ** 2 + (float(row['y']) - target_y) ** 2,
    )
    return ordered[:limit]
