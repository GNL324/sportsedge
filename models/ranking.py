from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sportsedge.models.arbitrage import ArbitrageOpportunity


@dataclass(frozen=True)
class RankedOpportunity:
    """Ranked wrapper for sportsbook arbitrage opportunities."""

    rank: int
    score: float
    opportunity: ArbitrageOpportunity

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["opportunity"] = self.opportunity.to_dict()
        return data

