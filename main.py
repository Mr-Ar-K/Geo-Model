"""Interactive entry point for the Geo-Model workflow.

This script asks for the required inputs, then runs the full workflow in a
fixed order every time:
1. Load and validate inputs
2. Apply seam splitting rules
3. Estimate fault throw and dip
4. Export Minex-ready outputs
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def prompt(message: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{message}{suffix}: ").strip()
    if value:
        return value
    if default is not None:
        return default
    raise ValueError(f"No value provided for: {message}")


def prompt_yes_no(message: str, default: bool = True) -> bool:
    default_text = "Y/n" if default else "y/N"
    value = input(f"{message} [{default_text}]: ").strip().lower()
    if not value:
        return default
    return value in {"y", "yes", "true", "1"}


def prompt_float(message: str, default: float) -> float:
    value = input(f"{message} [{default}]: ").strip()
    if not value:
        return default
    return float(value)


def load_pipeline():
    repo_root = Path(__file__).resolve().parent
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)

    from src.workflows.run_full_workflow import build_arg_parser, process_pipeline

    return build_arg_parser, process_pipeline


def build_args_from_prompts():
    build_arg_parser, _ = load_pipeline()
    parser = build_arg_parser()

    print("Geo-Model workflow setup")
    print("The workflow will always run in this order: load -> validate -> split -> fault model -> export")

    defaults = {
        "collar": "data/raw/collar.csv",
        "seams": "data/raw/seam_intercepts.csv",
        "faults": "data/raw/fault_polylines.csv",
        "split_rules": "config/seam_split_rules.yaml",
        "output_dir": "outputs/exports",
        "seam_output": "seam_intercepts_corrected.csv",
        "fault_output": "faults_minex.csv",
        "report_output": "qa_qc_report.json",
        "fault_buffer": 100.0,
        "default_dip": 65.0,
        "tolerance": 0.05,
    }

    collar = prompt("Collar CSV path", defaults["collar"])
    seams = prompt("Seam intercept CSV path", defaults["seams"])
    include_faults = prompt_yes_no("Include fault model inputs", True)
    faults = prompt("Fault polyline CSV path", defaults["faults"]) if include_faults else None

    split_rules = prompt("Seam split rule file", defaults["split_rules"])
    output_dir = prompt("Output directory", defaults["output_dir"])
    seam_output = prompt("Corrected seam output filename", defaults["seam_output"])
    fault_output = prompt("Fault output filename", defaults["fault_output"])
    report_output = prompt("QA/QC report filename", defaults["report_output"])
    fault_buffer = prompt_float("Fault buffer distance", defaults["fault_buffer"])
    default_dip = prompt_float("Default fault dip", defaults["default_dip"])
    tolerance = prompt_float("QA/QC tolerance", defaults["tolerance"])

    args_list = [
        "--collar",
        collar,
        "--seams",
        seams,
        "--split-rules",
        split_rules,
        "--output-dir",
        output_dir,
        "--seam-output",
        seam_output,
        "--fault-output",
        fault_output,
        "--report-output",
        report_output,
        "--fault-buffer",
        str(fault_buffer),
        "--default-dip",
        str(default_dip),
        "--tolerance",
        str(tolerance),
    ]
    if faults:
        args_list.extend(["--faults", faults])

    return parser.parse_args(args_list)


def main() -> int:
    _, process_pipeline = load_pipeline()
    args = build_args_from_prompts()

    print("Running workflow in fixed order...")
    print("1. Load and merge inputs")
    print("2. Apply seam splitting rules")
    print("3. Validate seams and estimate faults")
    print("4. Export Minex-ready outputs")

    summary = process_pipeline(args)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())