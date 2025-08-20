from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, ROUND_DOWN
from typing import Any, Dict, List, Optional

import requests
import time
import hmac
import hashlib
import random

FAPI_MAIN = "https://fapi.binance.com"
FAPI_TESTNET = "https://testnet.binancefuture.com"
FAPI_ALTS = [
	"https://fapi1.binance.com",
	"https://fapi2.binance.com",
	"https://fapi3.binance.com",
	"https://fapi4.binance.com",
]


@dataclass
class FuturesSymbolFilters:
	lot_step_size: Decimal
	lot_min_qty: Decimal
	price_tick_size: Decimal


class BinanceUSDMClient:
	def __init__(
		self,
		api_key: Optional[str] = None,
		api_secret: Optional[str] = None,
		use_testnet: bool = True,
	) -> None:
		configured_public = os.getenv("BINANCE_FAPI_BASE_URL", FAPI_MAIN)
		self.public_urls: List[str] = [configured_public] + [u for u in FAPI_ALTS if u != configured_public]

		self.api_key = api_key or ""
		self.api_secret = api_secret or ""
		self.use_testnet = use_testnet
		self.private_base = FAPI_TESTNET if use_testnet else FAPI_MAIN

	def _public_get(self, url: str, params: Dict[str, Any] | None = None) -> Any:
		last_exc: Optional[Exception] = None
		for attempt in range(3):
			try:
				resp = requests.get(url, params=params, timeout=7)
				if resp.status_code == 429:
					# backoff with jitter on rate limit
					delay = 0.75 * (attempt + 1) + random.random() * 0.5
					time.sleep(delay)
					continue
				resp.raise_for_status()
				return resp.json()
			except Exception as exc:  # noqa: BLE001
				last_exc = exc
				# backoff for transient network/5xx
				time.sleep(0.5 * (attempt + 1))
				continue
		if last_exc:
			raise last_exc
		raise RuntimeError("Public request failed after retries")

	def _signed_request(self, method: str, path: str, params: Dict[str, Any]) -> Any:
		if not self.api_key or not self.api_secret:
			raise RuntimeError("API Key/Secret 未配置，无法调用私有接口")
		params = dict(params) if params else {}
		params.setdefault("timestamp", int(time.time() * 1000))
		qs = "&".join([f"{k}={params[k]}" for k in sorted(params.keys())])
		signature = hmac.new(self.api_secret.encode(), qs.encode(), hashlib.sha256).hexdigest()
		qs_signed = f"{qs}&signature={signature}"
		url = f"{self.private_base}{path}"
		headers = {"X-MBX-APIKEY": self.api_key}
		resp = requests.request(method.upper(), url, params=None, data=qs_signed, headers=headers, timeout=15)
		resp.raise_for_status()
		return resp.json()

	def _with_public_fallback(self, path: str, params: Dict[str, Any] | None = None) -> Any:
		last_exc: Optional[Exception] = None
		for base in self.public_urls:
			try:
				return self._public_get(f"{base}{path}", params=params)
			except Exception as exc:  # noqa: BLE001
				last_exc = exc
				continue
		if last_exc:
			raise last_exc
		raise RuntimeError("USDM public endpoints unreachable")

	# -------- Market Data --------
	def get_klines(self, symbol: str, interval: str, limit: int = 500) -> List[List[Any]]:
		return self._with_public_fallback("/fapi/v1/klines", params={"symbol": symbol, "interval": interval, "limit": limit})

	def get_exchange_info(self) -> Dict[str, Any]:
		return self._with_public_fallback("/fapi/v1/exchangeInfo")

	def get_symbol_filters(self, symbol: str) -> FuturesSymbolFilters:
		info = self.get_exchange_info()
		s = next(x for x in info["symbols"] if x["symbol"] == symbol)
		lot = next(f for f in s["filters"] if f["filterType"] == "LOT_SIZE")
		price = next(f for f in s["filters"] if f["filterType"] == "PRICE_FILTER")
		return FuturesSymbolFilters(
			lot_step_size=Decimal(lot["stepSize"]),
			lot_min_qty=Decimal(lot["minQty"]),
			price_tick_size=Decimal(price["tickSize"]),
		)

	# -------- Helpers --------
	@staticmethod
	def round_to_step(value: Decimal, step: Decimal) -> Decimal:
		if step == 0:
			return value
		precision = max(0, -step.as_tuple().exponent)
		quantized = (value // step) * step
		return quantized.quantize(Decimal(10) ** -precision, rounding=ROUND_DOWN)

	# -------- Trading (private) --------
	def change_leverage(self, symbol: str, leverage: int) -> Dict[str, Any]:
		return self._signed_request("POST", "/fapi/v1/leverage", {"symbol": symbol, "leverage": leverage})

	def new_market_order(
		self,
		symbol: str,
		side: str,
		quantity: Decimal,
		reduce_only: bool = False,
		position_side: Optional[str] = None,
	) -> Dict[str, Any]:
		params: Dict[str, Any] = {
			"symbol": symbol,
			"side": side.upper(),
			"type": "MARKET",
			"quantity": str(quantity),
		}
		if reduce_only:
			params["reduceOnly"] = "true"
		if position_side:
			params["positionSide"] = position_side
		return self._signed_request("POST", "/fapi/v1/order", params) 