"""FIFO cost-basis ledger for the tax-aware backtest engine.

CostBasisLedger tracks open share lots per ticker and disposes them
in FIFO order when a sell is recorded.  Each disposal yields a
DisposedLot ready for the CGT processor (ledger.py has no tax logic
itself — it only tracks quantity and cost basis).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from market_data.backtest.tax.models import DisposedLot, OpenLot

# Residual quantity below this threshold is treated as zero (floating-point
# arithmetic accumulates tiny errors over many partial sells).
_FLOAT_TOLERANCE = 0.001


@dataclass
class CostBasisLedger:
    """FIFO cost-basis ledger.

    Maintains a queue of open lots per ticker.  buy() enqueues;
    sell() dequeues from the front, splitting partial lots when needed.
    """

    _lots: dict[str, list[OpenLot]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def buy(self, ticker: str, lot: OpenLot) -> None:
        """Record a purchase by appending the lot to the ticker's queue."""
        self._lots[ticker].append(lot)

    def sell(
        self,
        ticker: str,
        quantity: float,
        disposed_date: date,
    ) -> list[DisposedLot]:
        """Dispose of *quantity* shares from *ticker* in FIFO order.

        Returns a list of DisposedLot records (one per open lot touched).
        The DisposedLot fields proceeds_aud, proceeds_usd, gain_aud, and
        discount_applied are all set to sentinel values (0.0 / False) here —
        the CGT processor fills them in once it has the sale price and
        holding-period data.

        Raises:
            ValueError: if quantity exceeds total open position for ticker
                        (after floating-point tolerance is applied).
        """
        queue = self._lots[ticker]
        remaining = quantity
        disposed: list[DisposedLot] = []

        while remaining > _FLOAT_TOLERANCE and queue:
            lot = queue[0]

            if lot.quantity <= remaining + _FLOAT_TOLERANCE:
                # Consume this lot entirely.
                take = lot.quantity
                remaining -= take
                queue.pop(0)
                disposed.append(
                    _make_disposed(lot, take, lot.cost_basis_aud, disposed_date)
                )
            else:
                # Partial consumption — split the lot.
                proportion = remaining / lot.quantity
                taken_basis_aud = lot.cost_basis_aud * proportion
                taken_basis_usd = (
                    lot.cost_basis_usd * proportion
                    if lot.cost_basis_usd is not None
                    else None
                )
                leftover_qty = lot.quantity - remaining
                leftover_basis_aud = lot.cost_basis_aud - taken_basis_aud
                leftover_basis_usd = (
                    lot.cost_basis_usd - taken_basis_usd
                    if lot.cost_basis_usd is not None and taken_basis_usd is not None
                    else None
                )

                disposed.append(
                    _make_disposed(lot, remaining, taken_basis_aud, disposed_date)
                )

                # Replace the front lot with the remainder.
                queue[0] = OpenLot(
                    ticker=lot.ticker,
                    acquired_date=lot.acquired_date,
                    quantity=leftover_qty,
                    cost_basis_aud=leftover_basis_aud,
                    cost_basis_usd=leftover_basis_usd,
                )
                remaining = 0.0

        if remaining > _FLOAT_TOLERANCE:
            raise ValueError(
                f"Cannot sell {quantity} of {ticker}: "
                f"position insufficient (residual {remaining:.6f} shares)"
            )

        return disposed


def _make_disposed(
    lot: OpenLot,
    quantity: float,
    cost_basis_aud: float,
    disposed_date: date,
) -> DisposedLot:
    """Build a DisposedLot from an OpenLot with sentinel CGT fields.

    proceeds_aud, proceeds_usd, gain_aud, and discount_applied are
    placeholder values — the CGT processor overwrites them with real
    figures once it has the sale price.
    """
    return DisposedLot(
        ticker=lot.ticker,
        acquired_date=lot.acquired_date,
        disposed_date=disposed_date,
        quantity=quantity,
        cost_basis_usd=lot.cost_basis_usd,
        cost_basis_aud=cost_basis_aud,
        proceeds_usd=None,
        proceeds_aud=0.0,
        gain_aud=0.0,
        discount_applied=False,
    )
