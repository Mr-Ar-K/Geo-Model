"""Workflow entry point for the full Geo-Model pipeline."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple


Row = Dict[str, Any]


def normalize_key(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def read_csv_rows(path: str) -> List[Row]:
    with open(path, "r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows: List[Row] = []
        for index, raw_row in enumerate(reader):
            row = {
                normalize_key(key): value.strip() if isinstance(value, str) else value
                for key, value in raw_row.items()
            }
            row["_input_index"] = index
            rows.append(row)
        return rows


def write_csv_rows(path: str, rows: Sequence[Row], fieldnames: Sequence[str]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def require_field(row: Row, field: str, context: str) -> str:
    value = row.get(field)
    if value is None or str(value).strip() == "":
        raise ValueError(f"Missing required field '{field}' in {context}")
    return str(value).strip()


def parse_float(value: Any, field: str, context: str) -> float:
    if value is None or str(value).strip() == "":
        raise ValueError(f"Missing numeric field '{field}' in {context}")
    try:
        return float(str(value).strip())
    except ValueError as exc:
        raise ValueError(f"Invalid numeric value for '{field}' in {context}: {value!r}") from exc


def almost_equal(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def load_collars(path: str) -> Dict[str, Row]:
    rows = read_csv_rows(path)
    collars: Dict[str, Row] = {}
    for index, row in enumerate(rows):
        context = f"collar row {index + 1}"
        bhid = require_field(row, "bhid", context)
        x = parse_float(row.get("x"), "x", context)
        y = parse_float(row.get("y"), "y", context)
        z_field = "z" if row.get("z") not in (None, "") else "collar_z"
        z = parse_float(row.get(z_field), z_field, context)
        total_depth = None
        if row.get("total_depth") not in (None, ""):
            total_depth = parse_float(row.get("total_depth"), "total_depth", context)
        elif row.get("depth") not in (None, ""):
            total_depth = parse_float(row.get("depth"), "depth", context)
        collars[bhid] = {"bhid": bhid, "x": x, "y": y, "z": z, "total_depth": total_depth}
    return collars


def load_seams(path: str) -> List[Row]:
    rows = read_csv_rows(path)
    for index, row in enumerate(rows):
        context = f"seam row {index + 1}"
        require_field(row, "bhid", context)
        require_field(row, "seam_name", context)
        parse_float(row.get("from"), "from", context)
        parse_float(row.get("to"), "to", context)
        parse_float(row.get("seam_thickness"), "seam_thickness", context)
    return rows


def load_faults(path: Optional[str]) -> List[Row]:
    if not path:
        return []
    rows = read_csv_rows(path)
    for index, row in enumerate(rows):
        context = f"fault row {index + 1}"
        require_field(row, "fault_name", context)
        parse_float(row.get("x"), "x", context)
        parse_float(row.get("y"), "y", context)
    return rows


def load_split_rules(path: Optional[str]) -> Dict[str, Row]:
    if not path:
        return {}
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read().strip()

    try:
        raw = json.loads(text)
    except json.JSONDecodeError:
        raw = parse_simple_yaml_mapping(text)

    rules: Dict[str, Row] = {}
    for parent_name, rule in raw.items():
        parent = str(parent_name).strip()
        top_name = rule.get("top_name") or rule.get("top")
        bot_name = rule.get("bottom_name") or rule.get("bottom")
        if not top_name or not bot_name:
            raise ValueError(f"Split rule for {parent} must define top_name/top and bottom_name/bottom")
        top_pct = float(rule.get("top_pct", rule.get("top_percentage", 0.0)))
        bot_pct = float(rule.get("bot_pct", rule.get("bottom_pct", rule.get("bot_percentage", 0.0))))
        if not almost_equal(top_pct + bot_pct, 1.0, 1e-6):
            raise ValueError(f"Split rule for {parent} must sum to 1.0; got {top_pct + bot_pct}")
        rules[parent] = {
            "top_name": str(top_name).strip(),
            "bottom_name": str(bot_name).strip(),
            "top_pct": top_pct,
            "bot_pct": bot_pct,
        }
    return rules


def parse_simple_yaml_mapping(text: str) -> Dict[str, Dict[str, Any]]:
    lines = [line.rstrip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not lines:
        return {}

    result: Dict[str, Dict[str, Any]] = {}
    current_top: Optional[str] = None
    current_item: Optional[Dict[str, Any]] = None
    in_split_rules_section = False

    for raw_line in lines:
        stripped = raw_line.strip()
        indent = len(raw_line) - len(raw_line.lstrip(" "))

        if indent == 0 and stripped == "split_rules:":
            in_split_rules_section = True
            continue

        if indent == 0 and stripped.endswith(":") and not stripped.startswith("-"):
            key = stripped[:-1].strip()
            if current_top and current_item is not None:
                result[current_top] = current_item
            current_top = key
            current_item = {}
            continue

        if not in_split_rules_section or current_top is None or current_item is None:
            continue

        if indent >= 2 and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value.startswith("\"") and value.endswith("\""):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            if value in {"true", "false"}:
                parsed_value: Any = value == "true"
            else:
                try:
                    parsed_value = float(value) if "." in value or value.isdigit() else value
                except ValueError:
                    parsed_value = value
            current_item[key] = parsed_value

    if current_top and current_item is not None:
        result[current_top] = current_item

    return result


def merge_seams_with_collars(seam_rows: Sequence[Row], collars: Dict[str, Row]) -> List[Row]:
    merged: List[Row] = []
    for index, row in enumerate(seam_rows):
        context = f"seam row {index + 1}"
        bhid = require_field(row, "bhid", context)
        if bhid not in collars:
            raise ValueError(f"No collar found for bhid {bhid!r} in {context}")
        collar = collars[bhid]
        from_depth = parse_float(row.get("from"), "from", context)
        to_depth = parse_float(row.get("to"), "to", context)
        thickness = parse_float(row.get("seam_thickness"), "seam_thickness", context)
        merged_row = dict(row)
        merged_row.update(
            {
                "bhid": bhid,
                "from": from_depth,
                "to": to_depth,
                "seam_thickness": thickness,
                "x": collar["x"],
                "y": collar["y"],
                "z": collar["z"],
                "roof_rl": collar["z"] - from_depth,
                "floor_rl": collar["z"] - to_depth,
            }
        )
        merged.append(merged_row)
    return merged


def qa_qc_seams(seam_rows: Sequence[Row], tolerance: float) -> List[Row]:
    issues: List[Row] = []
    by_bhid: Dict[str, List[Row]] = defaultdict(list)
    for row in seam_rows:
        by_bhid[str(row["bhid"])].append(row)

    for bhid, rows in by_bhid.items():
        ordered = sorted(rows, key=lambda item: (float(item["from"]), float(item["to"]), str(item["seam_name"])))
        previous_to: Optional[float] = None
        previous_name: Optional[str] = None
        for row in ordered:
            from_depth = float(row["from"])
            to_depth = float(row["to"])
            thickness = float(row["seam_thickness"])
            calc_thickness = to_depth - from_depth
            if to_depth <= from_depth:
                issues.append(
                    {
                        "bhid": bhid,
                        "seam_name": row.get("seam_name", ""),
                        "issue_type": "invalid_interval",
                        "detail": f"to ({to_depth}) must be greater than from ({from_depth})",
                    }
                )
            if not almost_equal(calc_thickness, thickness, tolerance):
                issues.append(
                    {
                        "bhid": bhid,
                        "seam_name": row.get("seam_name", ""),
                        "issue_type": "thickness_mismatch",
                        "detail": f"calculated thickness {calc_thickness} differs from seam_thickness {thickness}",
                    }
                )
            if previous_to is not None and from_depth < previous_to - tolerance:
                issues.append(
                    {
                        "bhid": bhid,
                        "seam_name": row.get("seam_name", ""),
                        "issue_type": "overlap",
                        "detail": f"interval overlaps previous seam {previous_name!r}",
                    }
                )
            previous_to = to_depth
            previous_name = str(row.get("seam_name", ""))
    return issues


def apply_split_rules(seam_rows: Sequence[Row], split_rules: Dict[str, Row], tolerance: float) -> List[Row]:
    corrected: List[Row] = []
    for row in seam_rows:
        seam_name = str(row.get("seam_name", "")).strip()
        if seam_name not in split_rules:
            corrected.append(dict(row))
            continue

        rule = split_rules[seam_name]
        total = float(row["seam_thickness"])
        top_pct = float(rule["top_pct"])
        bot_pct = float(rule["bot_pct"])
        top_thickness = total * top_pct
        bot_thickness = total * bot_pct
        if not almost_equal(top_thickness + bot_thickness, total, tolerance):
            raise ValueError(f"Split thicknesses for {seam_name} do not sum to the original thickness")

        top_row = dict(row)
        top_row["seam_name"] = rule["top_name"]
        top_row["seam_thickness"] = top_thickness
        top_row["to"] = float(row["from"]) + top_thickness

        bottom_row = dict(row)
        bottom_row["seam_name"] = rule["bottom_name"]
        bottom_row["seam_thickness"] = bot_thickness
        bottom_row["from"] = top_row["to"]
        bottom_row["to"] = float(row["to"])

        for child in (top_row, bottom_row):
            child["roof_rl"] = float(child["z"]) - float(child["from"])
            child["floor_rl"] = float(child["z"]) - float(child["to"])
        corrected.extend([top_row, bottom_row])

    return corrected


def point_to_segment_distance(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> Tuple[float, float, float]:
    vx = bx - ax
    vy = by - ay
    wx = px - ax
    wy = py - ay
    seg_len_sq = vx * vx + vy * vy
    if seg_len_sq == 0:
        distance = math.hypot(px - ax, py - ay)
        return distance, 0.0, 0.0
    t = max(0.0, min(1.0, (wx * vx + wy * vy) / seg_len_sq))
    proj_x = ax + t * vx
    proj_y = ay + t * vy
    distance = math.hypot(px - proj_x, py - proj_y)
    cross = vx * wy - vy * wx
    side = 0.0 if distance == 0 else (1.0 if cross > 0 else -1.0)
    return distance, side, t


def extract_fault_vertices(rows: Sequence[Row]) -> List[Tuple[float, float, Row]]:
    order_fields = ["sequence", "vertex", "vertex_id", "point_id", "order", "seq"]
    order_field = next((field for field in order_fields if any(field in row for row in rows)), None)
    indexed_rows = list(enumerate(rows))
    if order_field:
        indexed_rows.sort(key=lambda item: (float(item[1].get(order_field, item[0])), item[0]))
    vertices = []
    for _, row in indexed_rows:
        vertices.append((float(row["x"]), float(row["y"]), row))
    return vertices


def choose_reference_seam(seam_rows: Sequence[Row], borehole_sides: Dict[str, float]) -> Optional[str]:
    side_sets = {side: {bhid for bhid, bh_side in borehole_sides.items() if bh_side == side} for side in (-1.0, 1.0)}
    if not side_sets[-1.0] or not side_sets[1.0]:
        return None

    seam_support: Dict[str, Dict[float, int]] = defaultdict(lambda: defaultdict(int))
    for row in seam_rows:
        seam_name = str(row.get("seam_name", "")).strip()
        bhid = str(row.get("bhid", "")).strip()
        for side in (-1.0, 1.0):
            if bhid in side_sets[side]:
                seam_support[seam_name][side] += 1

    viable = []
    for seam_name, support in seam_support.items():
        if len(support) >= 2:
            total = sum(support.values())
            viable.append((total, seam_name))
    if not viable:
        return None
    viable.sort(reverse=True)
    return viable[0][1]


def estimate_fault_throw(
    fault_vertices: Sequence[Tuple[float, float, Row]],
    seam_rows: Sequence[Row],
    collar_lookup: Dict[str, Row],
    fault_buffer: float,
) -> Tuple[float, Dict[str, Any]]:
    borehole_sides: Dict[str, float] = {}
    for bhid, collar in collar_lookup.items():
        px = float(collar["x"])
        py = float(collar["y"])
        best_distance = None
        best_side = 0.0
        for index, (ax, ay, _) in enumerate(fault_vertices[:-1]):
            bx, by, _ = fault_vertices[index + 1]
            distance, side, _ = point_to_segment_distance(px, py, ax, ay, bx, by)
            if best_distance is None or distance < best_distance:
                best_distance = distance
                best_side = side
        if best_distance is not None and best_distance <= fault_buffer and best_side != 0.0:
            borehole_sides[bhid] = best_side

    reference_seam = choose_reference_seam(seam_rows, borehole_sides)
    if reference_seam is None:
        return 0.0, {
            "reference_seam": None,
            "fw_mean_rl": None,
            "hw_mean_rl": None,
            "sample_count": 0,
            "note": "No common seam available on both sides of the fault; throw set to zero.",
        }

    side_samples: Dict[float, List[float]] = defaultdict(list)
    for row in seam_rows:
        if str(row.get("seam_name", "")).strip() != reference_seam:
            continue
        bhid = str(row.get("bhid", "")).strip()
        side = borehole_sides.get(bhid)
        if side is None:
            continue
        side_samples[side].append(float(row["roof_rl"]))

    if not side_samples[-1.0] or not side_samples[1.0]:
        return 0.0, {
            "reference_seam": reference_seam,
            "fw_mean_rl": None,
            "hw_mean_rl": None,
            "sample_count": sum(len(values) for values in side_samples.values()),
            "note": "Insufficient boreholes on both sides of the fault; throw set to zero.",
        }

    mean_negative = sum(side_samples[-1.0]) / len(side_samples[-1.0])
    mean_positive = sum(side_samples[1.0]) / len(side_samples[1.0])
    if mean_positive >= mean_negative:
        fw_mean = mean_positive
        hw_mean = mean_negative
    else:
        fw_mean = mean_negative
        hw_mean = mean_positive

    throw = fw_mean - hw_mean
    return throw, {
        "reference_seam": reference_seam,
        "fw_mean_rl": fw_mean,
        "hw_mean_rl": hw_mean,
        "sample_count": sum(len(values) for values in side_samples.values()),
        "note": "Throw estimated from mean roof RL difference across the fault.",
    }


def taper_factor(chainage: float, total_length: float) -> float:
    if total_length <= 0:
        return 1.0
    ratio = max(0.0, min(1.0, chainage / total_length))
    return max(0.0, 1.0 - abs(2.0 * ratio - 1.0))


def build_fault_output(
    fault_rows: Sequence[Row],
    seam_rows: Sequence[Row],
    collar_lookup: Dict[str, Row],
    fault_buffer: float,
    default_dip: float,
) -> Tuple[List[Row], List[Row]]:
    grouped: Dict[str, List[Row]] = defaultdict(list)
    for row in fault_rows:
        grouped[str(row["fault_name"])].append(row)

    output_rows: List[Row] = []
    summaries: List[Row] = []
    for fault_name, rows in grouped.items():
        vertices = extract_fault_vertices(rows)
        throw_value, summary = estimate_fault_throw(vertices, seam_rows, collar_lookup, fault_buffer)
        summaries.append({"fault_name": fault_name, **summary, "estimated_throw": throw_value})

        coords = [(x, y) for x, y, _ in vertices]
        segment_lengths: List[float] = []
        total_length = 0.0
        for start, end in zip(coords, coords[1:]):
            seg_len = math.hypot(end[0] - start[0], end[1] - start[1])
            segment_lengths.append(seg_len)
            total_length += seg_len

        cumulative = 0.0
        for index, (x, y, _) in enumerate(vertices):
            if index > 0:
                cumulative += segment_lengths[index - 1]
            factor = taper_factor(cumulative, total_length)
            output_rows.append(
                {
                    "fault_name": fault_name,
                    "x": x,
                    "y": y,
                    "dip": default_dip,
                    "throw": round(throw_value * factor, 6),
                }
            )

    return output_rows, summaries


def build_qa_report(seam_issues: Sequence[Row], split_rules: Dict[str, Row], seam_rows: Sequence[Row], fault_summaries: Sequence[Row]) -> Dict[str, Any]:
    seam_counts = Counter(str(row.get("seam_name", "")) for row in seam_rows)
    return {
        "seam_issue_count": len(seam_issues),
        "seam_issue_types": dict(Counter(issue["issue_type"] for issue in seam_issues)),
        "split_rule_count": len(split_rules),
        "seam_counts": dict(seam_counts),
        "fault_summaries": list(fault_summaries),
    }


def process_pipeline(args: argparse.Namespace) -> Dict[str, Any]:
    collars = load_collars(args.collar)
    raw_seams = load_seams(args.seams)
    raw_faults = load_faults(args.faults)
    split_rules = load_split_rules(args.split_rules)

    merged = merge_seams_with_collars(raw_seams, collars)
    seam_issues = qa_qc_seams(merged, args.tolerance)
    corrected = apply_split_rules(merged, split_rules, args.tolerance)
    seam_issues_after_split = qa_qc_seams(corrected, args.tolerance)
    all_issues = list(seam_issues) + list(seam_issues_after_split)

    final_seams = sorted(
        corrected,
        key=lambda row: (str(row["bhid"]), float(row["from"]), float(row["to"]), str(row["seam_name"])),
    )
    final_seam_rows = [
        {
            "bhid": row["bhid"],
            "from": round(float(row["from"]), 6),
            "to": round(float(row["to"]), 6),
            "seam_thickness": round(float(row["seam_thickness"]), 6),
            "seam_name": str(row["seam_name"]),
        }
        for row in final_seams
    ]

    fault_output_rows: List[Row] = []
    fault_summaries: List[Row] = []
    if raw_faults:
        fault_output_rows, fault_summaries = build_fault_output(
            raw_faults,
            final_seams,
            collars,
            args.fault_buffer,
            args.default_dip,
        )

    report = build_qa_report(all_issues, split_rules, final_seams, fault_summaries)

    os.makedirs(args.output_dir, exist_ok=True)
    seam_output_path = os.path.join(args.output_dir, args.seam_output)
    write_csv_rows(seam_output_path, final_seam_rows, ["bhid", "from", "to", "seam_thickness", "seam_name"])

    fault_output_path = None
    if raw_faults:
        fault_output_path = os.path.join(args.output_dir, args.fault_output)
        write_csv_rows(fault_output_path, fault_output_rows, ["fault_name", "x", "y", "dip", "throw"])

    report_path = os.path.join(args.output_dir, args.report_output)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, sort_keys=True)

    return {
        "seam_output": seam_output_path,
        "fault_output": fault_output_path,
        "report_output": report_path,
        "seam_issue_count": len(all_issues),
    }


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Geo-model seam and fault processing pipeline")
    parser.add_argument("--collar", required=True, help="Path to collar CSV")
    parser.add_argument("--seams", required=True, help="Path to seam intercept CSV")
    parser.add_argument("--faults", help="Path to fault polyline CSV")
    parser.add_argument("--split-rules", help="Path to seam split rule JSON")
    parser.add_argument("--output-dir", default="output", help="Directory for exported CSV files")
    parser.add_argument("--seam-output", default="Minex_Corrected_Seams.csv", help="Output seam CSV name")
    parser.add_argument("--fault-output", default="Minex_Fault_Inputs.csv", help="Output fault CSV name")
    parser.add_argument("--report-output", default="qa_qc_report.json", help="Output QA/QC report name")
    parser.add_argument("--fault-buffer", type=float, default=100.0, help="Fault buffer in map units")
    parser.add_argument("--default-dip", type=float, default=65.0, help="Default fault dip in degrees")
    parser.add_argument("--tolerance", type=float, default=0.05, help="Numeric tolerance for QA/QC checks")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    summary = process_pipeline(args)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
