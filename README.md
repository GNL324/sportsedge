# SportsEdge

SportsEdge is a sportsbook odds intelligence project split out from Polylens. Phase 1 provides provider adapters and a provider-neutral odds schema.

## Phase 1 Features

- Normalized sportsbook odds model.
- Adapter interface for sportsbook providers.
- OddsBlaze adapter.
- The Odds API adapter.
- Unit tests for normalization and adapter behavior.

Not included in Phase 1:

- Arbitrage detection.
- Dashboards.
- Bankroll management.
- Persistent storage.

## Environment

```text
ODDSBLAZE_API_KEY    Required for live OddsBlaze calls.
ODDS_API_KEY         Required for live The Odds API calls.
```

## Usage

```python
from sportsedge.adapters import OddsBlazeAdapter, TheOddsAPIAdapter

oddsblaze_rows = OddsBlazeAdapter().fetch_odds(
    sportsbook="draftkings",
    league="nba",
    market_contains="Player",
)

oddsapi_rows = TheOddsAPIAdapter().fetch_odds(
    sport_key="basketball_nba",
    markets="h2h,spreads,totals",
)

first = oddsapi_rows[0]
print(first.to_dict())
```

## Testing

```bash
python -m unittest discover -s sportsedge/tests
```
