"""Cost-basis ledger for the tax-aware backtest engine.

CostBasisLedger tracks open share lots per ticker and disposes them
according to the chosen parcel identification method when a sell is
recorded. Each disposal yields a DisposedLot ready for the CGT
processor (ledger.py has no tax logic itself — it only tracks
quantity and cost basis).

Parcel identification methods (ATO TR 96/4):
    fifo         — First In, First Out. ATO-accepted fallback when
                   specific identification is not possible.
    highest_cost — Specific identification variant: nominates the
                   highest cost-per-share lot first, minimising
                   taxable gain. ATO-accepted when documented before
                   settlement.

Note: LIFO (Last In, First Out) is NOT accepted by the ATO for CGT
parcel identification and is therefore not implemented here.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from market_data.backtest.tax.models import DisposedLot, OpenLot

# Residual quantity below this threshold is treated as zero (floating-point
# arithmetic accumulates tiny errors over many partial sells).
_FLOAT_TOLERANCE = 0.001

ParcelMethod = Literal["fifo", "highest_cost"]


@dataclass
class CostBasisLedger:
    """Cost-basis ledger supporting FIFO and highest-cost parcel identification.

    Maintains a list of open lots per ticker. buy() appends; sell() disposes
    lots in the order dictated by parcel_method.
    """

    _lots: dict[str, list[OpenLot]] = field(default_factory=lambda: defaultdict(list))

    def buy(self, ticker: str, lot: OpenLot) -> None:
        """Record a purchase by appending the lot to the ticker's list."""
        self._lots[ticker].append(lot)

    def sell(
        self,
        ticker: str,
        quantity: float,
        disposed_date: date,
        parcel_method: ParcelMethod = "fifo",
    ) -> list[DisposedLot]:
        """Dispose of *quantity* shares from *ticker* using the given parcel method.

        Returns a list of DisposedLot records (one per open lot touched).
        proceeds_aud, proceeds_usd, gain_aud, and discount_applied are sentinel
        values — the CGT processor fills them once it has the sale price.

        Parcel methods:
            fifo         — oldest lots first (ATO default fallback per TR 96/4)
            highest_cost — highest cost-per-share first (specific identification,
                           minimises taxable gain; ATO-accepted when documented
                           before settlement)

        Raises:
            ValueError: if quantity exceeds total open position for ticker.
        """
        queue = self._lots[ticker]

        # Determine processing order by index into queue.
        if parcel_method == "fifo":
            ordered_indices = list(range(len(queue)))
        else:  # highest_cost
            ordered_indices = sorted(
                range(len(queue)),
                key=lambda i: queue[i].cost_basis_aud / max(queue[i].quantity, 1e-9),
                reverse=True,
            )

        remaining = quantity
        disposed: list[DisposedLot] = []
        consumed: set[int] = set()
        partial: dict[int, OpenLot] = {}

        for idx in ordered_indices:
            if remaining <= _FLOAT_TOLERANCE:
                break
            lot = queue[idx]

            if lot.quantity <= remaining + _FLOAT_TOLERANCE:
                # Consume this lot entirely.
                disposed.append(
                    _make_disposed(lot, lot.quantity, lot.cost_basis_aud, disposed_date)
                )
                remaining -= lot.quantity
                consumed.add(idx)
            else:
                # Partial consumption — split the lot.
                proportion = remaining / lot.quantity
                taken_basis_aud = lot.cost_basis_aud * proportion
                taken_basis_usd = (
                    lot.cost_basis_usd * proportion if lot.cost_basis_usd is not None else None
                )
                disposed.append(_make_disposed(lot, remaining, taken_basis_aud, disposed_date))
                leftover_basis_usd = (
                    lot.cost_basis_usd - taken_basis_usd
                    if lot.cost_basis_usd is not None and taken_basis_usd is not None
                    else None
                )
                partial[idx] = OpenLot(
                    ticker=lot.ticker,
                    acquired_date=lot.acquired_date,
                    quantity=lot.quantity - remaining,
                    cost_basis_aud=lot.cost_basis_aud - taken_basis_aud,
                    cost_basis_usd=leftover_basis_usd,
                )
                remaining = 0.0

        if remaining > _FLOAT_TOLERANCE:
            raise ValueError(
                f"Cannot sell {quantity} of {ticker}: "
                f"position insufficient (residual {remaining:.6f} shares)"
            )

        # Rebuild queue: keep un-consumed lots in original order, update partials.
        self._lots[ticker] = [
            partial.get(i, lot) for i, lot in enumerate(queue) if i not in consumed
        ]

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
