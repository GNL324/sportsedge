import unittest

from sportsedge.models.arbitrage import ArbitrageOpportunity
from sportsedge.models.odds import NormalizedOdds
from sportsedge.models.ranking import RankedOpportunity
from sportsedge.scanners.arbitrage import find_arbitrage_opportunities, rank_opportunities


def odds(
    *,
    sportsbook="book",
    market_type="h2h",
    selection="Team A",
    side=None,
    line=None,
    american=100,
    event_id="evt",
):
    return NormalizedOdds(
        provider="test",
        sportsbook_key=sportsbook.lower(),
        sportsbook_name=sportsbook,
        league="NBA",
        sport_key="basketball_nba",
        event_id=event_id,
        event_name="Team B @ Team A",
        commence_time="2026-06-10T00:00:00Z",
        home_team="Team A",
        away_team="Team B",
        market_key=market_type,
        market_name=market_type,
        market_type=market_type,
        selection_name=selection,
        side=side,
        team_name=None if side else selection,
        line=line,
        american_odds=american,
    )


class ArbitrageEngineTests(unittest.TestCase):
    def test_detects_moneyline_arbitrage(self):
        rows = [
            odds(sportsbook="BookA", selection="Team A", american=140),
            odds(sportsbook="BookB", selection="Team A", american=110),
            odds(sportsbook="BookC", selection="Team B", american=140),
        ]

        opportunities = find_arbitrage_opportunities(rows, total_stake=100)

        self.assertEqual(len(opportunities), 1)
        opportunity = opportunities[0]
        self.assertIsInstance(opportunity, ArbitrageOpportunity)
        self.assertEqual(opportunity.market_type, "h2h")
        self.assertAlmostEqual(opportunity.implied_probability, 0.833333, places=6)
        self.assertAlmostEqual(opportunity.overround, -0.166667, places=6)
        self.assertAlmostEqual(opportunity.arbitrage_percentage, 0.166667, places=6)
        self.assertEqual(opportunity.expected_profit, 20.0)
        self.assertEqual({leg.odds.sportsbook_key for leg in opportunity.legs}, {"booka", "bookc"})

    def test_detects_totals_arbitrage(self):
        rows = [
            odds(sportsbook="BookA", market_type="totals", selection="Over", side="over", line=218.5, american=130),
            odds(sportsbook="BookB", market_type="totals", selection="Under", side="under", line=218.5, american=130),
            odds(sportsbook="BookC", market_type="totals", selection="Under", side="under", line=219.5, american=150),
        ]

        opportunities = find_arbitrage_opportunities(rows, total_stake=250)

        self.assertEqual(len(opportunities), 1)
        opportunity = opportunities[0]
        self.assertEqual(opportunity.market_type, "totals")
        self.assertEqual(opportunity.line, 218.5)
        self.assertEqual({leg.outcome_key for leg in opportunity.legs}, {"over", "under"})
        self.assertEqual(opportunity.expected_profit, 37.5)

    def test_detects_spread_arbitrage(self):
        rows = [
            odds(sportsbook="BookA", market_type="spreads", selection="Team A", line=-2.5, american=120),
            odds(sportsbook="BookB", market_type="spreads", selection="Team B", line=2.5, american=120),
        ]

        opportunities = find_arbitrage_opportunities(rows, total_stake=100)

        self.assertEqual(len(opportunities), 1)
        self.assertEqual(opportunities[0].market_type, "spreads")
        self.assertEqual(opportunities[0].line, 2.5)
        self.assertGreater(opportunities[0].expected_profit, 9)

    def test_rejects_no_arbitrage(self):
        rows = [
            odds(sportsbook="BookA", selection="Team A", american=-110),
            odds(sportsbook="BookB", selection="Team B", american=-110),
        ]

        self.assertEqual(find_arbitrage_opportunities(rows), [])

    def test_ranks_opportunities(self):
        weak = find_arbitrage_opportunities(
            [
                odds(sportsbook="BookA", selection="Team A", american=110, event_id="weak"),
                odds(sportsbook="BookB", selection="Team B", american=110, event_id="weak"),
            ]
        )[0]
        strong = find_arbitrage_opportunities(
            [
                odds(sportsbook="BookA", selection="Team A", american=200, event_id="strong"),
                odds(sportsbook="BookB", selection="Team B", american=200, event_id="strong"),
            ]
        )[0]

        ranked = rank_opportunities([weak, strong])

        self.assertIsInstance(ranked[0], RankedOpportunity)
        self.assertEqual(ranked[0].rank, 1)
        self.assertEqual(ranked[0].opportunity.event_id, "strong")
        self.assertGreater(ranked[0].score, ranked[1].score)


if __name__ == "__main__":
    unittest.main()
