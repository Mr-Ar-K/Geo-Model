"""Configuration and defaults for Geo-Model.

Defines stratigraphy order, default split percentages and simple fault assumptions.
"""

STRATIGRAPHY_ORDER = [
    "Overburden",
    "SeamA",
    "SeamB",
    "Underburden",
]

# default split percentages (top/mid/bottom) for seam splitting
DEFAULT_SPLIT = {
    "top": 0.33,
    "mid": 0.34,
    "bottom": 0.33,
}

# simple fault assumptions
FAULT_ASSUMPTIONS = {
    "max_throw_m": 50.0,
    "default_dip": 70.0,
}
