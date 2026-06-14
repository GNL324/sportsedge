from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sportsedge.models.odds import NormalizedOdds


@dataclass(frozen=True)
class OpportunityLeg:
    """One selected sportsbook leg inside an arbitrage opportunity."""

    outcome_key: str
    odds: NormalizedOdds
    implied_probability: float
    stake: float
    expected_return: float

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["odds"] = self.odds.to_dict()
        return data


@dataclass(frozen=True)
class ArbitrageOpportunity:
    """A complete arbitrage opportunity built from best available sportsbook legs."""

    opportunity_id: str
    sport_key: str | None
    league: str | None
    event_id: str | None
    event_name: str | None
    market_type: str
    market_key: str
    period: str
    line: float | None
    legs: tuple[OpportunityLeg, ...]
    implied_probability: float
    overround: float
    arbitrage_percentage: float
    total_stake: float
    expected_return: float
    expected_profit: float
    expected_roi: float

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["legs"] = [leg.to_dict() for leg in self.legs]
        return data

