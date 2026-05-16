"""Desurveying and seam splitting utilities.

Includes robust functions for Phase 1 (ingestion & base QA/QC) and
Phase 2 (desurveying & stratigraphic sorting).
"""
from typing import Dict, List, Any, Tuple
import pandas as pd
import numpy as np
from scipy.spatial import cKDTree
from shapely.geometry import Point, LineString


REQUIRED_COLLAR_COLS = {"bhid", "x", "y", "z", "total_depth", "dip", "azimuth"}
REQUIRED_INTERCEPT_COLS = {"bhid", "from", "to", "seam_thickness", "seam_name"}


def load_csvs(collars_path: str, intercepts_path: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load collars and intercepts CSVs into DataFrames and validate columns.

    Raises ValueError for missing required columns.
    """
    collars = pd.read_csv(collars_path)
    intercepts = pd.read_csv(intercepts_path)

    missing = REQUIRED_COLLAR_COLS - set(collars.columns)
    if missing:
        raise ValueError(f"Collars file missing columns: {missing}")

    missing_i = REQUIRED_INTERCEPT_COLS - set(intercepts.columns)
    if missing_i:
        raise ValueError(f"Intercepts file missing columns: {missing_i}")

    return collars, intercepts


def validate_base_qaqc(collars: pd.DataFrame, intercepts: pd.DataFrame) -> Dict[str, Any]:
    """Run basic QA/QC checks and return a summary dict with flags.

    Checks performed:
    - Nulls in required columns
    - `total_depth` >= deepest intercept `to` per `bhid`
    - Overlapping intervals within a `bhid`
    - from < to for all intercepts
    """
    summary: Dict[str, Any] = {"nulls": [], "td_violations": [], "overlaps": [], "inverted_intervals": []}

    # Null checks
    for col in REQUIRED_COLLAR_COLS:
        if collars[col].isnull().any():
            summary["nulls"].append(("collars", col))
    for col in REQUIRED_INTERCEPT_COLS:
        if intercepts[col].isnull().any():
            summary["nulls"].append(("intercepts", col))

    # total_depth vs intercepts
    max_to_per_bh = intercepts.groupby("bhid")["to"].max().reset_index()
    merged = pd.merge(collars[["bhid", "total_depth"]], max_to_per_bh, on="bhid", how="left")
    for _, row in merged.iterrows():
        if pd.notnull(row["to"]) and row["total_depth"] < row["to"]:
            summary["td_violations"].append(row["bhid"])

    # inverted intervals and overlaps
    for bhid, group in intercepts.groupby("bhid"):
        g = group.sort_values(by="from").reset_index(drop=True)
        # inverted intervals
        inverted = g[g["from"] >= g["to"]]
        if not inverted.empty:
            summary["inverted_intervals"].append(bhid)

        # overlapping
        for i in range(len(g) - 1):
            if g.loc[i + 1, "from"] < g.loc[i, "to"] - 1e-6:
                summary["overlaps"].append(bhid)
                break

    return summary


def desurvey_and_merge(collars: pd.DataFrame, intercepts: pd.DataFrame) -> pd.DataFrame:
    """Compute absolute elevations for intercepts and return merged DataFrame.

    Adds columns:
    - `z_roof` = `z` - `from`
    - `z_floor` = `z` - `to`

    Also preserves original `from`/`to` (downhole depths).
    """
    # merge collars into intercepts (include dip/azimuth if present)
    collar_cols = ["bhid", "x", "y", "z"]
    if "dip" in collars.columns:
        collar_cols.append("dip")
    if "azimuth" in collars.columns:
        collar_cols.append("azimuth")
    data = pd.merge(intercepts.copy(), collars[collar_cols], on="bhid", how="left")
    if data[["x", "y", "z"]].isnull().any().any():
        raise ValueError("Some intercepts do not have matching collar positions (bhid mismatch)")

    data["z_roof"] = data["z"] - data["from"]
    data["z_floor"] = data["z"] - data["to"]
    data["seam_thickness"] = data["to"] - data["from"]

    return data


def assign_strat_index(intercepts: pd.DataFrame, seam_order: List[str]) -> pd.DataFrame:
    """Assign a numeric `strat_index` to each seam according to user-provided seam order.

    Top seam should be first in `seam_order` (index = 1).
    Unknown seams will receive index = NaN and should be reviewed.
    """
    order_map = {name: idx + 1 for idx, name in enumerate(seam_order)}
    intercepts = intercepts.copy()
    intercepts["strat_index"] = intercepts["seam_name"].map(order_map).astype("float")
    return intercepts


def load_and_desurvey(collars_path: str, intercepts_path: str, seam_order: List[str]) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Full Phase 1+2 runner: load, validate, desurvey, and assign strat index.

    Returns merged DataFrame and QA/QC summary.
    """
    collars, intercepts = load_csvs(collars_path, intercepts_path)
    summary = validate_base_qaqc(collars, intercepts)
    merged = desurvey_and_merge(collars, intercepts)
    merged = assign_strat_index(merged, seam_order)

    return merged, summary


def analyze_missing_seams(merged: pd.DataFrame,
                          seam_order: List[str],
                          faults_df: pd.DataFrame = None,
                          neighbor_radius: float = 1000.0,
                          min_neighbors: int = 3,
                          fault_tol: float = 50.0,
                          pinchout_thickness_thresh: float = 0.2) -> pd.DataFrame:
    """Analyze boreholes for missing seams and propose geological causes.

    Parameters
    - merged: output from `desurvey_and_merge` with columns at least
      `bhid,x,y,seam_name,strat_index,z_roof,z_floor,seam_thickness`
    - seam_order: top-to-bottom seam name list
    - faults_df: optional DataFrame with `fault_name,x,y` polyline points
    - neighbor_radius: search radius (m) for neighbors
    - min_neighbors: minimum neighbors required to make a call
    - fault_tol: distance (m) to consider a borehole 'near' a fault
    - pinchout_thickness_thresh: median thickness below which seam may be pinching out

    Returns a DataFrame with one row per missing-seam occurrence and fields
    describing the proposed classification and metrics used.
    """
    results = []

    # build KDTree per seam for fast neighbor queries
    seam_groups = {s: merged[merged["seam_name"] == s].reset_index(drop=True) for s in seam_order}
    kdtree_map = {}
    for s, df in seam_groups.items():
        if len(df) >= 1:
            coords = df[["x", "y"]].values
            kdtree_map[s] = cKDTree(coords)

    # build fault LineStrings if faults provided
    fault_lines = {}
    if faults_df is not None and not faults_df.empty:
        for fname, grp in faults_df.groupby("fault_name"):
            pts = [tuple(xy) for xy in grp.sort_index()[["x", "y"]].values]
            if len(pts) >= 2:
                fault_lines[fname] = LineString(pts)

    # function to compute nearest fault distance
    def nearest_fault_distance(x, y) -> float:
        if not fault_lines:
            return np.nan
        p = Point(x, y)
        dmin = min(p.distance(line) for line in fault_lines.values())
        return float(dmin)

    # iterate over boreholes
    bh_positions = merged[["bhid", "x", "y"]].drop_duplicates(subset=["bhid"]).set_index("bhid")
    for bhid, row in bh_positions.iterrows():
        bx, by = float(row["x"]), float(row["y"])
        present = set(merged[merged["bhid"] == bhid]["seam_name"].unique())
        for idx, seam in enumerate(seam_order):
            if seam in present:
                continue

            entry = {"bhid": bhid, "missing_seam": seam, "strat_index": idx + 1}

            # check neighbor seam points
            seam_df = seam_groups.get(seam)
            if seam_df is None or len(seam_df) == 0:
                entry.update({"neighbor_count": 0, "expected_z_roof": np.nan, "median_neighbor_thickness": np.nan, "classification": "insufficient_data"})
                # distance to fault (if any)
                entry["min_fault_distance"] = nearest_fault_distance(bx, by)
                results.append(entry)
                continue

            tree = kdtree_map.get(seam)
            # query all neighbors within radius (fallback to nearest k)
            dists, idxs = tree.query([bx, by], k=min_neighbors, distance_upper_bound=neighbor_radius)
            if np.isinf(dists).all():
                # no neighbors within radius
                entry.update({"neighbor_count": 0, "expected_z_roof": np.nan, "median_neighbor_thickness": np.nan, "classification": "insufficient_data"})
                entry["min_fault_distance"] = nearest_fault_distance(bx, by)
                results.append(entry)
                continue

            # filter valid indices
            valid_mask = np.isfinite(dists)
            valid_idxs = np.atleast_1d(idxs)[valid_mask]
            neighbor_count = len(valid_idxs)
            neighbor_z = seam_df.iloc[valid_idxs]["z_roof"].values
            neighbor_thicks = seam_df.iloc[valid_idxs]["seam_thickness"].values
            expected_z = float(np.median(neighbor_z))
            median_thick = float(np.median(neighbor_thicks)) if len(neighbor_thicks) > 0 else np.nan

            entry["neighbor_count"] = int(neighbor_count)
            entry["expected_z_roof"] = expected_z
            entry["median_neighbor_thickness"] = median_thick
            entry["min_fault_distance"] = nearest_fault_distance(bx, by)

            # simple decision rules
            if neighbor_count < min_neighbors:
                entry["classification"] = "insufficient_data"
            elif not np.isfinite(entry["min_fault_distance"]) and median_thick < pinchout_thickness_thresh:
                entry["classification"] = "pinchout"
            elif entry["min_fault_distance"] <= fault_tol:
                # near a fault — possible fault displacement
                entry["classification"] = "possible_fault"
            elif median_thick < pinchout_thickness_thresh:
                entry["classification"] = "pinchout"
            else:
                entry["classification"] = "possible_non_fault_process_or_data_issue"

            results.append(entry)

    return pd.DataFrame(results)

