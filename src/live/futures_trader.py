from __future__ import annotations

from decimal import Decimal
from typing import Optional

from src.config import settings
from src.data.market_data import fetch_futures_klines_df
from src.exchange.binance_futures_client import BinanceUSDMClient
from src.risk.risk_manager import RiskManager
from src.strategy.ema_cross import add_ema_features


class EMAFuturesTrader:
	def __init__(
		self,
		client: BinanceUSDMClient,
		symbol: str,
		interval: str = "1h",
		fast: int = 12,
		slow: int = 26,
		leverage: int = 5,
		quote_per_trade: Optional[Decimal] = None,
		dry_run: bool = True,
		position_side: Optional[str] = None,  # ONEWAY: None; HEDGE: LONG/SHORT
	) -> None:
		self.client = client
		self.symbol = symbol
		self.interval = interval
		self.fast = fast
		self.slow = slow
		self.leverage = leverage
		self.quote_per_trade = quote_per_trade
		self.dry_run = dry_run
		self.position_side = position_side
		self.risk = RiskManager()

	def ensure_leverage(self) -> None:
		if self.dry_run:
			return
		self.client.change_leverage(self.symbol, self.leverage)

	def step(self) -> None:
		df = fetch_futures_klines_df(self.client, self.symbol, self.interval, limit=300)
		df = add_ema_features(df, fast=self.fast, slow=self.slow).dropna()

		last_cross = int(df["cross"].iloc[-1])
		last_close = Decimal(str(df["close"].iloc[-1]))

		print(f"Futures last close={last_close}, cross={last_cross}")
		self.ensure_leverage()

		if last_cross == 1:
			self._open_long(last_close)
		elif last_cross == -1:
			self._close_long()
		else:
			print("No action.")

	def _compute_qty(self, price: Decimal) -> Decimal:
		# Futures uses quantity. Convert quote allocation into base qty using leverage
		quote_alloc = self.quote_per_trade or self.risk.compute_quote_allocation(Decimal("100"))  # fallback
		notional = quote_alloc * Decimal(str(self.leverage))
		qty = (notional / price)
		filters = self.client.get_symbol_filters(self.symbol)
		qty = self.client.round_to_step(Decimal(qty), filters.lot_step_size)
		return qty

	def _open_long(self, last_price: Decimal) -> None:
		if self.dry_run:
			print("[DRY] OPEN LONG")
			return
		qty = self._compute_qty(last_price)
		if qty <= Decimal("0"):
			print("Qty is zero; skip buy.")
			return
		print(f"OPEN LONG {self.symbol} qty={qty}")
		res = self.client.new_market_order(
			symbol=self.symbol,
			side="BUY",
			quantity=qty,
			position_side=self.position_side,
		)
		print(f"Order: {res.get('orderId')}")

	def _close_long(self) -> None:
		if self.dry_run:
			print("[DRY] CLOSE LONG (reduceOnly)")
			return
		# In one-way mode, reduceOnly SELL without specifying qty closes proportionally.
		# We compute a conservative qty by filters (user can refine to fetch real position size).
		filters = self.client.get_symbol_filters(self.symbol)
		qty = filters.lot_min_qty
		print(f"CLOSE LONG {self.symbol} qty>={qty} reduceOnly")
		res = self.client.new_market_order(
			symbol=self.symbol,
			side="SELL",
			quantity=qty,
			reduce_only=True,
			position_side=self.position_side,
		)
		print(f"Order: {res.get('orderId')}") 