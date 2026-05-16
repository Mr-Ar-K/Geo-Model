"""Minex-ready CSV exporters."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Mapping
import csv


def export_csv(path: str | Path, rows: Iterable[Mapping[str, object]], fieldnames: list[str]) -> None:
    with open(path, 'w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
