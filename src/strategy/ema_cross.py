from __future__ import annotations

import pandas as pd


def add_ema_features(df: pd.DataFrame, fast: int = 12, slow: int = 26) -> pd.DataFrame:
    out = df.copy()
    out[f"ema_{fast}"] = out["close"].ewm(span=fast, adjust=False).mean()
    out[f"ema_{slow}"] = out["close"].ewm(span=slow, adjust=False).mean()
    out["signal"] = 0
    out.loc[out[f"ema_{fast}"] > out[f"ema_{slow}"], "signal"] = 1
    out.loc[out[f"ema_{fast}"] < out[f"ema_{slow}"], "signal"] = -1
    out["cross"] = out["signal"].diff().fillna(0)
    return out 