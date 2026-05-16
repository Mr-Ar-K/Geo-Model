"""Heuristics for identifying depositional seam loss."""

from __future__ import annotations

from typing import Iterable, Mapping


def looks_like_washout(lithology_description: str | None) -> bool:
    if not lithology_description:
        return False
    text = lithology_description.lower()
    return 'sandstone' in text or 'channel' in text or 'washout' in text
