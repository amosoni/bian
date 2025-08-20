from __future__ import annotations

from typing import Literal
import pandas as pd

from src.exchange.binance_client import BinanceSpotClient
from src.exchange.binance_futures_client import BinanceUSDMClient


def fetch_klines_df(
    client: BinanceSpotClient,
    symbol: str,
    interval: Literal[
        "1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"
    ] = "1h",
    limit: int = 500,
) -> pd.DataFrame:
    raw = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    cols = [
        "open_time",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_asset_volume",
        "number_of_trades",
        "taker_buy_base",
        "taker_buy_quote",
        "ignore",
    ]
    df = pd.DataFrame(raw, columns=cols)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df.set_index("close_time", inplace=True)
    return df[["open", "high", "low", "close", "volume"]]


def fetch_futures_klines_df(
	client: BinanceUSDMClient,
	symbol: str,
	interval: Literal[
		"1m", "3m", "5m", "15m", "30m", "1h", "2h", "4h", "6h", "8h", "12h", "1d"
	] = "1h",
	limit: int = 500,
) -> pd.DataFrame:
	raw = client.get_klines(symbol=symbol, interval=interval, limit=limit)
	cols = [
		"open_time",
		"open",
		"high",
		"low",
		"close",
		"volume",
		"close_time",
		"quote_asset_volume",
		"number_of_trades",
		"taker_buy_base",
		"taker_buy_quote",
		"ignore",
	]
	df = pd.DataFrame(raw, columns=cols)
	df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
	df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
	for col in ["open", "high", "low", "close", "volume"]:
		df[col] = df[col].astype(float)
	df.set_index("close_time", inplace=True)
	return df[["open", "high", "low", "close", "volume"]] 