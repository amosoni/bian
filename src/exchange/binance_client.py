from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, List, Optional

from binance.spot import Spot as SpotClient


MAINNET_BASE_URL = "https://api.binance.com"
ALT_PUBLIC_URLS = [
	"https://api1.binance.com",
	"https://api2.binance.com",
	"https://api3.binance.com",
	"https://api4.binance.com",
]
TESTNET_BASE_URL = "https://testnet.binance.vision"


@dataclass
class SymbolFilters:
	lot_step_size: Decimal
	lot_min_qty: Decimal
	price_tick_size: Decimal
	min_notional: Optional[Decimal]


class BinanceSpotClient:
	def __init__(
		self,
		api_key: Optional[str] = None,
		api_secret: Optional[str] = None,
		use_testnet: bool = True,
	) -> None:
		# Prepare list of public endpoints with env override first
		configured_public = os.getenv("BINANCE_PUBLIC_BASE_URL", MAINNET_BASE_URL)
		self.public_urls: List[str] = [configured_public] + [u for u in ALT_PUBLIC_URLS if u != configured_public]

		# Private client for account/orders. Defaults to SPOT testnet for safety.
		private_base_url = TESTNET_BASE_URL if use_testnet else MAINNET_BASE_URL
		if api_key and api_secret:
			self.private = SpotClient(
				api_key=api_key,
				api_secret=api_secret,
				base_url=private_base_url,
			)
		else:
			self.private = None

	# ---------- Public helpers with fallback ----------
	def _with_public_fallback(self, func_name: str, **kwargs: Any) -> Any:
		last_exc: Optional[Exception] = None
		for url in self.public_urls:
			try:
				client = SpotClient(base_url=url)
				func = getattr(client, func_name)
				return func(**kwargs)
			except Exception as exc:  # noqa: BLE001 - we want to surface last exception
				last_exc = exc
				continue
		if last_exc:
			raise last_exc
		raise RuntimeError("Public Binance endpoints are not reachable.")

	# ---------- Market Data ----------
	def get_klines(self, symbol: str, interval: str, limit: int = 500) -> List[List[Any]]:
		return self._with_public_fallback("klines", symbol=symbol, interval=interval, limit=limit)

	def get_exchange_info(self) -> Dict[str, Any]:
		return self._with_public_fallback("exchange_info")

	def get_symbol_filters(self, symbol: str) -> SymbolFilters:
		info = self.get_exchange_info()
		symbol_info = next(s for s in info["symbols"] if s["symbol"] == symbol)
		lot_filter = next(f for f in symbol_info["filters"] if f["filterType"] == "LOT_SIZE")
		price_filter = next(f for f in symbol_info["filters"] if f["filterType"] == "PRICE_FILTER")
		min_notional_filter = next(
			(f for f in symbol_info["filters"] if f["filterType"] == "MIN_NOTIONAL"),
			None,
		)
		return SymbolFilters(
			lot_step_size=Decimal(lot_filter["stepSize"]),
			lot_min_qty=Decimal(lot_filter["minQty"]),
			price_tick_size=Decimal(price_filter["tickSize"]),
			min_notional=Decimal(min_notional_filter["minNotional"]) if min_notional_filter else None,
		)

	# ---------- Rounding helpers ----------
	@staticmethod
	def round_to_step(value: Decimal, step: Decimal) -> Decimal:
		if step == 0:
			return value
		precision = max(0, -step.as_tuple().exponent)
		quantized = (value // step) * step
		return quantized.quantize(Decimal(10) ** -precision, rounding=ROUND_DOWN)

	# ---------- Trading ----------
	def place_market_order(
		self,
		symbol: str,
		side: str,
		quantity: Optional[Decimal] = None,
		quote_quantity: Optional[Decimal] = None,
	) -> Dict[str, Any]:
		if self.private is None:
			raise RuntimeError("Private client not initialized; provide API keys.")
		if (quantity is None) == (quote_quantity is None):
			raise ValueError("Provide exactly one of quantity or quote_quantity.")

		params: Dict[str, Any] = {"symbol": symbol, "side": side.upper(), "type": "MARKET"}
		if quantity is not None:
			params["quantity"] = str(quantity)
		if quote_quantity is not None:
			params["quoteOrderQty"] = str(quote_quantity)
		return self.private.new_order(**params)

	def get_account(self) -> Dict[str, Any]:
		if self.private is None:
			raise RuntimeError("Private client not initialized; provide API keys.")
		return self.private.account()

	def get_price(self, symbol: str) -> Decimal:
		ticker = self._with_public_fallback("ticker_price", symbol=symbol)
		return Decimal(ticker["price"]) 