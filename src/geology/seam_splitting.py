"""Parent seam splitting helpers."""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping


def split_parent_seam(row: Mapping[str, object], rule: Mapping[str, object]) -> List[Dict[str, object]]:
    """Return top and bottom split intervals for a single parent seam row."""
    total = float(row['seam_thickness'])
    top_pct = float(rule['top_pct'])
    bot_pct = float(rule['bot_pct'])
    top_thickness = total * top_pct
    bot_thickness = total * bot_pct

    top_row = dict(row)
    top_row['seam_name'] = rule['top_name']
    top_row['seam_thickness'] = top_thickness
    top_row['to'] = float(row['from']) + top_thickness

    bottom_row = dict(row)
    bottom_row['seam_name'] = rule['bottom_name']
    bottom_row['seam_thickness'] = bot_thickness
    bottom_row['from'] = top_row['to']
    bottom_row['to'] = float(row['to'])

    return [top_row, bottom_row]
