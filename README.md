
# Geo-Model

Light scaffold for a geological modelling pipeline focused on preparing data for Minex import.

Project layout

```
├── data/
│   ├── raw/                  # Input datasets (collars, intercepts, faults, splits)
│   └── minex_ready/          # Final validated outputs for Minex import
│
├── src/
│   ├── __init__.py
│   ├── config.py             # Stratigraphy order, split percentages, fault assumptions
│   ├── data_processor.py     # Desurveying and seam splitting logic
│   ├── fault_kinematics.py   # Throw/dip estimation and HW/FW block assignment
│   └── validator_3d.py       # GemPy and PyVista unfault/refault logic
│
├── notebooks/
│   └── exploratory_qaqc.ipynb# Interactive visualization and QC
│
├── requirements.txt          # pandas, numpy, geopandas, shapely, scipy, gempy, pyvista
└── main.py                   # Master execution script
```

Quickstart

- Install dependencies: `pip install -r requirements.txt`
- Run placeholder script: `python main.py --run`

Next steps

- Fill in processing logic in `src/data_processor.py` and `src/validator_3d.py`.
- Add real datasets under `data/raw/` and iterate in `notebooks/exploratory_qaqc.ipynb`.
