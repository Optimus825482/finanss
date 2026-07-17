"""
NaN-safe float utilities.

yfinance, NumPy, and financial ratio calculations can produce NaN/Inf values
that crash JSON serializers. This module provides reusable guards for every
layer of the pipeline.
"""
import math


def is_nan(v) -> bool:
    """True if *v* is a float and math.isnan(v)."""
    return isinstance(v, float) and math.isnan(v)


def is_bad_float(v) -> bool:
    """True if *v* is NaN or Inf (positive or negative)."""
    return isinstance(v, float) and not math.isfinite(v)


def sanitize_float(v, default=None):
    """Return *default* (None) if *v* is NaN/Inf, else *v* unchanged."""
    if v is None:
        return default
    if isinstance(v, float) and not math.isfinite(v):
        return default
    return v


def sanitize_dict(d: dict) -> dict:
    """Recursively replaces NaN/Inf float values with None in-place.

    Handles nested dicts and lists-of-dicts.  Returns *d* for chaining.
    """
    for k, v in d.items():
        if isinstance(v, float) and not math.isfinite(v):
            d[k] = None
        elif isinstance(v, dict):
            sanitize_dict(v)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, dict):
                    sanitize_dict(item)
    return d
