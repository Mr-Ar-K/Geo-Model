# Geo-Model

Dependency-free CSV pipeline for borehole seam QA/QC, stratigraphic seam splitting, and Minex-ready fault/seam export.

## Inputs

The pipeline expects:

- Collar CSV with `bhid`, `x`, `y`, `z`, and optionally `total_depth`
- Seam intercept CSV with `bhid`, `from`, `to`, `seam_thickness`, `seam_name`
- Optional fault polyline CSV with `fault_name`, `x`, `y`, and an optional vertex order column such as `sequence`
- Optional split-rule JSON for parent seam to split seam conversion

## Run

```bash
# Interactive (recommended)
python main.py

# Non-interactive (scriptable) — use the workflow wrapper which accepts CLI flags
# Example:
python src/workflows/run_qaqc.py \
	--collar data/raw/collar.csv \
	--seams data/raw/seam_intercepts.csv \
	--split-rules config/seam_split_rules.yaml \
	--output-dir outputs/exports
```

`main.py` prompts for the required inputs and always runs the same workflow sequence.

Defaults used by `main.py` prompts:
- Collar: `data/raw/collar.csv`
- Seams: `data/raw/seam_intercepts.csv`
- Faults: `data/raw/fault_polylines.csv` (optional)
- Split rules: `config/seam_split_rules.yaml`
- Output dir: `outputs/exports`

Notes:
- The pipeline accepts split rules in JSON or a simple YAML-style mapping (see `config/seam_split_rules.yaml`).
- Use the wrapper scripts under `src/workflows/` for fully automated runs from CI or shells.

## Outputs

- `Minex_Corrected_Seams.csv` with `bhid, from, to, seam_thickness, seam_name`
- `Minex_Fault_Inputs.csv` with `fault_name, x, y, dip, throw`
- `qa_qc_report.json` with seam QA/QC and fault estimation summaries

## Split Rule Example

```json
{
	"Seam_IX": {
		"top_name": "Seam_IX_Top",
		"bottom_name": "Seam_IX_Bot",
		"top_pct": 0.45,
		"bot_pct": 0.55
	}
}
```

The fault throw estimate is conservative: it uses nearby boreholes on both sides of the mapped trace when a common seam is available, then tapers throw to zero at polyline tips.