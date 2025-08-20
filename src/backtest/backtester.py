from __future__ import annotations

import numpy as np
import pandas as pd

from src.strategy.ema_cross import add_ema_features


def run_backtest(
    df: pd.DataFrame,
    fast: int = 12,
    slow: int = 26,
    fee_bps: float = 10.0,
) -> dict:
    data = add_ema_features(df, fast=fast, slow=slow).dropna().copy()

    position = (data["cross"] == 1).astype(int)
    position = position.replace(0, np.nan).ffill().fillna(0)

    ret = data["close"].pct_change().fillna(0.0)
    gross = position.shift(1).fillna(0) * ret
    fee = np.where(data["cross"] != 0, fee_bps / 10000.0, 0.0)
    net = gross - fee

    equity = (1.0 + net).cumprod()

    stats = {
        "start": str(data.index[0]),
        "end": str(data.index[-1]),
        "bars": int(len(data)),
        "fast": fast,
        "slow": slow,
        "final_equity": float(equity.iloc[-1]),
        "return_pct": float((equity.iloc[-1] - 1.0) * 100.0),
        "max_dd_pct": float(_max_drawdown(equity) * 100.0),
        "sharpe": float(_sharpe(net)),
        "trades": int((data["cross"].abs() == 1).sum()),
    }
    return {"equity_curve": equity, "stats": stats, "data": data}


def _max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    dd = (equity / roll_max) - 1.0
    return float(dd.min())


def _sharpe(returns: pd.Series, risk_free: float = 0.0, period: int = 365) -> float:
    excess = returns - (risk_free / period)
    if excess.std() == 0:
        return 0.0
    return float(np.sqrt(period) * excess.mean() / excess.std()) 