"""Collar QA/QC checks."""

from __future__ import annotations

from typing import Mapping


def has_required_collar_fields(row: Mapping[str, object]) -> bool:
    return all(field in row and row[field] not in (None, '') for field in ('bhid', 'x', 'y', 'z'))
