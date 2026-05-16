"""Seam QA/QC checks."""

from __future__ import annotations

from typing import Mapping


def seam_thickness_matches(row: Mapping[str, object], tolerance: float = 0.05) -> bool:
    return abs(float(row['to']) - float(row['from']) - float(row['seam_thickness'])) <= tolerance
