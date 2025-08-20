from __future__ import annotations

import time
from decimal import Decimal
from typing import Optional

import pandas as pd

from src.config import settings
from src.data.market_data import fetch_klines_df
from src.exchange.binance_client import BinanceSpotClient
from src.risk.risk_manager import RiskManager
from src.strategy.ema_cross import add_ema_features


class EMATrader:
    def __init__(
        self,
        client: BinanceSpotClient,
        symbol: str,
        interval: str = "1h",
        fast: int = 12,
        slow: int = 26,
        quote_per_trade: Optional[Decimal] = None,
        dry_run: bool = True,
    ) -> None:
        self.client = client
        self.symbol = symbol
        self.interval = interval
        self.fast = fast
        self.slow = slow
        self.dry_run = dry_run
        self.risk = RiskManager()
        self.quote_per_trade = quote_per_trade

    def step(self) -> None:
        df = fetch_klines_df(self.client, self.symbol, self.interval, limit=300)
        df = add_ema_features(df, fast=self.fast, slow=self.slow).dropna()

        last_cross = int(df["cross"].iloc[-1])
        last_signal = int(df["signal"].iloc[-1])
        last_close = Decimal(str(df["close"].iloc[-1]))

        print(f"Last close={last_close}, signal={last_signal}, cross={last_cross}")

        if last_cross == 1:
            self._buy(last_close)
        elif last_cross == -1:
            self._sell_all(last_close)
        else:
            print("No action.")

    def _buy(self, last_price: Decimal) -> None:
        if self.dry_run:
            print("[DRY] BUY signal detected; skipping order.")
            return
        if self.client.private is None:
            raise RuntimeError("Private client not initialized.")

        account = self.client.get_account()
        quote_asset = settings.default_quote_asset
        quote_balance = _get_free_balance(account, quote_asset)

        quote_to_spend = self.quote_per_trade or self.risk.compute_quote_allocation(quote_balance)
        print(f"Placing BUY {self.symbol} for ~{quote_to_spend} {quote_asset} (market, quoteOrderQty)")

        res = self.client.place_market_order(
            symbol=self.symbol,
            side="BUY",
            quote_quantity=quote_to_spend,
        )
        print(f"Order placed: {res.get('orderId')}")

    def _sell_all(self, last_price: Decimal) -> None:
        if self.dry_run:
            print("[DRY] SELL signal detected; skipping order.")
            return
        if self.client.private is None:
            raise RuntimeError("Private client not initialized.")

        account = self.client.get_account()
        base_asset = self.symbol.replace(settings.default_quote_asset, "")
        base_balance = _get_free_balance(account, base_asset)
        if base_balance <= Decimal("0"):
            print("No base asset to sell.")
            return

        filters = self.client.get_symbol_filters(self.symbol)
        qty = self.client.round_to_step(base_balance, filters.lot_step_size)
        if qty <= Decimal("0"):
            print("Quantity after rounding is zero; skip sell.")
            return

        print(f"Placing SELL {self.symbol} qty={qty}")
        res = self.client.place_market_order(
            symbol=self.symbol,
            side="SELL",
            quantity=qty,
        )
        print(f"Order placed: {res.get('orderId')}")


def _get_free_balance(account: dict, asset: str) -> Decimal:
    for b in account.get("balances", []):
        if b.get("asset") == asset:
            return Decimal(b.get("free", "0"))
    return Decimal("0") 