from __future__ import annotations

import argparse
from decimal import Decimal

import pandas as pd

from src.backtest.backtester import run_backtest
from src.config import settings
from src.data.market_data import fetch_klines_df
from src.exchange.binance_client import BinanceSpotClient
from src.exchange.binance_futures_client import BinanceUSDMClient
from src.live.trader import EMATrader
from src.live.futures_trader import EMAFuturesTrader


def main() -> None:
    parser = argparse.ArgumentParser(description="Binance Quant Trading (EMA Crossover)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    # backtest (spot)
    p_back = sub.add_parser("backtest", help="Run backtest (spot data)")
    p_back.add_argument("--symbol", default=settings.backtest_symbol)
    p_back.add_argument("--interval", default=settings.backtest_interval)
    p_back.add_argument("--limit", type=int, default=settings.backtest_limit)
    p_back.add_argument("--fast", type=int, default=12)
    p_back.add_argument("--slow", type=int, default=26)

    # futures backtest (USDM)
    p_fback = sub.add_parser("futures-backtest", help="Run backtest with USDM futures data")
    p_fback.add_argument("--symbol", default=settings.backtest_symbol)
    p_fback.add_argument("--interval", default=settings.backtest_interval)
    p_fback.add_argument("--limit", type=int, default=settings.backtest_limit)
    p_fback.add_argument("--fast", type=int, default=12)
    p_fback.add_argument("--slow", type=int, default=26)

    # futures paper
    p_fpaper = sub.add_parser("futures-paper", help="USDM paper trading (no orders)")
    p_fpaper.add_argument("--symbol", default=settings.backtest_symbol)
    p_fpaper.add_argument("--interval", default=settings.backtest_interval)
    p_fpaper.add_argument("--fast", type=int, default=12)
    p_fpaper.add_argument("--slow", type=int, default=26)
    p_fpaper.add_argument("--leverage", type=int, default=5)

    # futures live
    p_flive = sub.add_parser("futures-live", help="USDM live trading (testnet by default)")
    p_flive.add_argument("--symbol", default=settings.backtest_symbol)
    p_flive.add_argument("--interval", default=settings.backtest_interval)
    p_flive.add_argument("--fast", type=int, default=12)
    p_flive.add_argument("--slow", type=int, default=26)
    p_flive.add_argument("--leverage", type=int, default=5)

    args = parser.parse_args()

    if args.cmd == "backtest":
        client = BinanceSpotClient(use_testnet=True)
        df = fetch_klines_df(client, args.symbol, args.interval, limit=args.limit)
        result = run_backtest(df, fast=args.fast, slow=args.slow)
        stats = result["stats"]
        print("Backtest Stats:")
        for k, v in stats.items():
            print(f"- {k}: {v}")
    elif args.cmd == "futures-backtest":
        fclient = BinanceUSDMClient(
            api_key=settings.binance_api_key,
            api_secret=settings.binance_api_secret,
            use_testnet=settings.use_testnet,
        )
        df = fetch_futures_klines_df(fclient, args.symbol, args.interval, limit=args.limit)
        result = run_backtest(df, fast=args.fast, slow=args.slow)
        for k, v in result["stats"].items():
            print(f"- {k}: {v}")
    elif args.cmd in {"futures-paper", "futures-live"}:
        fclient = BinanceUSDMClient(
            api_key=settings.binance_api_key,
            api_secret=settings.binance_api_secret,
            use_testnet=settings.use_testnet,
        )
        trader = EMAFuturesTrader(
            client=fclient,
            symbol=args.symbol,
            interval=args.interval,
            fast=args.fast,
            slow=args.slow,
            leverage=args.leverage,
            dry_run=(args.cmd == "futures-paper"),
        )
        trader.step()
    else:
        parser.error("Unknown command")


if __name__ == "__main__":
    main() 