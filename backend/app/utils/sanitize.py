"""
NaN-safe float utilities.

yfinance, NumPy, and financial ratio calculations can produce NaN/Inf values
that crash JSON serializers. This module provides reusable guards for every
layer of the pipeline.

Also converts np.float64/int64 → native Python float/int to prevent
SQLAlchemy "schema \"np\" does not exist" errors.
"""
import math
import numpy as np


def _native(v):
    """np.float64/int64 → native Python float/int, else pass-through."""
    if isinstance(v, (np.floating,)):
        return float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    return v


def is_nan(v) -> bool:
    """True if *v* is a float and math.isnan(v)."""
    return isinstance(v, float) and math.isnan(v)


def is_bad_float(v) -> bool:
    """True if *v* is NaN or Inf (positive or negative)."""
    return isinstance(v, float) and not math.isfinite(v)


def sanitize_float(v, default=None):
    """Return *default* (None) if *v* is NaN/Inf, else *v* unchanged.
    Converts np.float64 to native Python float."""
    if v is None:
        return default
    v = _native(v)
    if isinstance(v, float) and not math.isfinite(v):
        return default
    return v


def sanitize_dict(d: dict) -> dict:
    """Recursively replaces NaN/Inf float values with None in-place.
    Converts np.float64/int64 to native Python types.

    Handles nested dicts and lists-of-dicts.  Returns *d* for chaining.
    """
    for k, v in d.items():
        v = _native(v)
        d[k] = v
        if isinstance(v, float) and not math.isfinite(v):
            d[k] = None
        elif isinstance(v, dict):
            sanitize_dict(v)
        elif isinstance(v, list):
            d[k] = [_native(item) for item in v]
            for item in d[k]:
                if isinstance(item, dict):
                    sanitize_dict(item)
    return d
