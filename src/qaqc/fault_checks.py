"""Fault QA/QC checks."""

from __future__ import annotations

from typing import Mapping


def has_fault_geometry(row: Mapping[str, object]) -> bool:
    return all(field in row and row[field] not in (None, '') for field in ('fault_name', 'x', 'y'))
