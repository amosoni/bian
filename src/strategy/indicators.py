from __future__ import annotations

import pandas as pd


def compute_bollinger_bands(
    df: pd.DataFrame,
    period: int = 20,
    std_multiplier: float = 2.0,
) -> pd.DataFrame:
    out = df.copy()
    mid = out["close"].rolling(window=period, min_periods=period).mean()
    std = out["close"].rolling(window=period, min_periods=period).std(ddof=0)
    upper = mid + std_multiplier * std
    lower = mid - std_multiplier * std

    out["bb_mid"] = mid
    out["bb_upper"] = upper
    out["bb_lower"] = lower

    # Bandwidth and %B for additional diagnostics
    band_width = (upper - lower) / out["close"]
    percent_b = (out["close"] - lower) / (upper - lower)

    out["bb_bandwidth"] = band_width
    out["bb_percent_b"] = percent_b
    return out 