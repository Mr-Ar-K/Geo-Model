"""Input readers for Geo-Model CSV and config files."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List
import csv
import json


def read_csv(path: str | Path) -> List[Dict[str, Any]]:
    with open(path, 'r', newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def read_json(path: str | Path) -> Any:
    with open(path, 'r', encoding='utf-8') as handle:
        return json.load(handle)
