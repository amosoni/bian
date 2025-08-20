from __future__ import annotations

from decimal import Decimal

from src.config import settings


class RiskManager:
    def __init__(self, fraction: float | None = None) -> None:
        self.fraction = Decimal(str(fraction if fraction is not None else settings.risk_fraction))

    def compute_quote_allocation(self, quote_balance: Decimal) -> Decimal:
        allocation = (quote_balance * self.fraction).quantize(Decimal("0.01"))
        if allocation <= Decimal("0"):
            raise ValueError("Computed allocation is non-positive.")
        return allocation 