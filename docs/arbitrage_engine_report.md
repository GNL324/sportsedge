# SportsEdge Phase 2 Arbitrage Engine Report

Date: 2026-06-14

## Summary

Phase 2 adds a pure arbitrage scanner that consumes Phase 1 `NormalizedOdds` rows and returns structured `ArbitrageOpportunity` objects. It supports moneyline, spread, and totals markets. Alerts, dashboards, persistence, and bankroll management remain intentionally out of scope.

## Implemented Components

| Component | Path | Responsibility |
|---|---|---|
| Opportunity model | `sportsedge/models/arbitrage.py` | `OpportunityLeg` and `ArbitrageOpportunity` dataclasses. |
| Ranking model | `sportsedge/models/ranking.py` | `RankedOpportunity` dataclass. |
| Arbitrage engine | `sportsedge/scanners/arbitrage.py` | Groups normalized odds, selects best legs, calculates arbitrage metrics, and ranks opportunities. |
| Tests | `sportsedge/tests/test_arbitrage_engine.py` | Unit tests for moneyline, spreads, totals, no-arb rejection, and ranking. |

## Supported Markets

- `h2h`: moneyline. Outcomes are grouped by event and team/selection.
- `spreads`: spread markets. Outcomes are grouped by event and absolute spread line.
- `totals`: over/under totals. Outcomes are grouped by event and total line.

Only normalized odds rows with `market_type` in `h2h`, `spreads`, or `totals` are scanned.

## Calculations

For each event-market group, the engine:

1. Computes implied probability from `NormalizedOdds.implied_probability`, `decimal_odds`, or `american_odds`.
2. Selects the lowest implied probability for each outcome, which corresponds to the best available payout.
3. Computes total implied probability across selected legs.
4. Computes overround as `total_implied_probability - 1`.
5. Detects arbitrage when total implied probability is below `1`.
6. Computes arbitrage percentage as `1 - total_implied_probability`.
7. Computes expected return as `total_stake / total_implied_probability`.
8. Computes expected profit as `expected_return - total_stake`.
9. Allocates illustrative stakes proportionally by each leg's implied probability.

The default illustrative stake is `$100`. This is a calculation input, not bankroll management.

## Ranking

`rank_opportunities` sorts opportunities by:

1. Expected profit.
2. Expected ROI.
3. Arbitrage percentage.

It returns `RankedOpportunity` objects with a rank and numeric score.

## Explicit Non-Goals

- No alerting.
- No dashboards.
- No storage or opportunity persistence.
- No bankroll limits, bankroll sizing policy, or risk management.
- No player-prop arbitrage detection in Phase 2.

## Verification

Run:

```bash
python -m unittest discover -s sportsedge/tests
```

