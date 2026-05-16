"""Seam continuity checks."""

from __future__ import annotations

from typing import Iterable, Mapping


def is_continuous(previous_row: Mapping[str, object], next_row: Mapping[str, object], tolerance: float = 0.05) -> bool:
    return float(next_row['from']) >= float(previous_row['to']) - tolerance
