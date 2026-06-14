from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from sportsedge.models.arbitrage import ArbitrageOpportunity, OpportunityLeg
from sportsedge.models.odds import NormalizedOdds
from sportsedge.models.ranking import RankedOpportunity

SUPPORTED_MARKETS = {"h2h", "spreads", "totals"}
DEFAULT_STAKE = 100.0


@dataclass(frozen=True)
class _CandidateLeg:
    outcome_key: str
    odds: NormalizedOdds
    implied_probability: float


def find_arbitrage_opportunities(
    odds_rows: Iterable[NormalizedOdds],
    *,
    total_stake: float = DEFAULT_STAKE,
) -> list[ArbitrageOpportunity]:
    """Find sportsbook arbitrage in normalized moneyline, spread, and totals odds."""

    groups: dict[tuple[object, ...], list[_CandidateLeg]] = defaultdict(list)
    for row in odds_rows:
        market_type = str(row.market_type or row.market_key or "").lower()
        if market_type not in SUPPORTED_MARKETS:
            continue
        outcome_key = _outcome_key(row, market_type)
        group_key = _group_key(row, market_type)
        implied_probability = _implied_probability(row)
        if not outcome_key or not group_key or implied_probability is None or implied_probability <= 0:
            continue
        groups[group_key].append(_CandidateLeg(outcome_key=outcome_key, odds=row, implied_probability=implied_probability))

    opportunities: list[ArbitrageOpportunity] = []
    for group_key, candidates in groups.items():
        best_by_outcome = _best_legs(candidates)
        if len(best_by_outcome) < _required_outcome_count(str(group_key[3])):
            continue
        implied_total = sum(leg.implied_probability for leg in best_by_outcome)
        overround = implied_total - 1.0
        if implied_total >= 1.0:
            continue
        opportunities.append(_build_opportunity(group_key, best_by_outcome, implied_total, overround, total_stake))

    return [ranked.opportunity for ranked in rank_opportunities(opportunities)]


def rank_opportunities(opportunities: Iterable[ArbitrageOpportunity]) -> list[RankedOpportunity]:
    """Rank opportunities by profit and ROI, highest first."""

    ordered = sorted(
        opportunities,
        key=lambda opportunity: (opportunity.expected_profit, opportunity.expected_roi, opportunity.arbitrage_percentage),
        reverse=True,
    )
    return [
        RankedOpportunity(rank=index + 1, score=_ranking_score(opportunity), opportunity=opportunity)
        for index, opportunity in enumerate(ordered)
    ]


def _group_key(row: NormalizedOdds, market_type: str) -> tuple[object, ...] | None:
    base = (
        row.sport_key,
        row.event_id,
        row.period or "full_game",
        market_type,
    )
    if market_type == "h2h":
        return (*base, None)
    if market_type == "totals":
        if row.line is None:
            return None
        return (*base, round(float(row.line), 4))
    if market_type == "spreads":
        if row.line is None:
            return None
        return (*base, round(abs(float(row.line)), 4))
    return None


def _outcome_key(row: NormalizedOdds, market_type: str) -> str | None:
    if market_type == "totals":
        return row.side if row.side in {"over", "under"} else None
    if market_type in {"h2h", "spreads"}:
        value = row.team_name or row.selection_name
        text = str(value or "").strip().lower()
        return text or None
    return None


def _implied_probability(row: NormalizedOdds) -> float | None:
    if row.implied_probability is not None:
        return float(row.implied_probability)
    if row.decimal_odds is not None:
        if row.decimal_odds <= 1:
            return None
        return 1 / row.decimal_odds
    if row.american_odds is None or row.american_odds == 0:
        return None
    if row.american_odds > 0:
        return 100 / (row.american_odds + 100)
    return abs(row.american_odds) / (abs(row.american_odds) + 100)


def _best_legs(candidates: list[_CandidateLeg]) -> list[_CandidateLeg]:
    best: dict[str, _CandidateLeg] = {}
    for candidate in candidates:
        current = best.get(candidate.outcome_key)
        if current is None or candidate.implied_probability < current.implied_probability:
            best[candidate.outcome_key] = candidate
    return list(best.values())


def _required_outcome_count(market_type: str) -> int:
    return 2 if market_type in {"spreads", "totals"} else 2


def _build_opportunity(
    group_key: tuple[object, ...],
    best_legs: list[_CandidateLeg],
    implied_total: float,
    overround: float,
    total_stake: float,
) -> ArbitrageOpportunity:
    sport_key, event_id, period, market_type, line = group_key
    expected_return = total_stake / implied_total
    expected_profit = expected_return - total_stake
    legs = tuple(
        OpportunityLeg(
            outcome_key=leg.outcome_key,
            odds=leg.odds,
            implied_probability=round(leg.implied_probability, 6),
            stake=round(total_stake * (leg.implied_probability / implied_total), 2),
            expected_return=round(expected_return, 2),
        )
        for leg in sorted(best_legs, key=lambda item: item.outcome_key)
    )
    first = best_legs[0].odds
    return ArbitrageOpportunity(
        opportunity_id=_opportunity_id(group_key, legs),
        sport_key=str(sport_key) if sport_key else None,
        league=first.league,
        event_id=str(event_id) if event_id else None,
        event_name=first.event_name,
        market_type=str(market_type),
        market_key=str(market_type),
        period=str(period),
        line=float(line) if line is not None else None,
        legs=legs,
        implied_probability=round(implied_total, 6),
        overround=round(overround, 6),
        arbitrage_percentage=round(1.0 - implied_total, 6),
        total_stake=round(total_stake, 2),
        expected_return=round(expected_return, 2),
        expected_profit=round(expected_profit, 2),
        expected_roi=round(expected_profit / total_stake, 6) if total_stake else 0.0,
    )


def _opportunity_id(group_key: tuple[object, ...], legs: tuple[OpportunityLeg, ...]) -> str:
    leg_text = "|".join(f"{leg.outcome_key}:{leg.odds.provider}:{leg.odds.sportsbook_key}:{leg.odds.american_odds}:{leg.odds.decimal_odds}" for leg in legs)
    raw = "|".join(str(item) for item in group_key) + "|" + leg_text
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _ranking_score(opportunity: ArbitrageOpportunity) -> float:
    return round((opportunity.expected_roi * 10000) + opportunity.expected_profit, 4)
