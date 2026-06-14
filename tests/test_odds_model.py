import unittest

from sportsedge.models.odds import (
    NormalizedOdds,
    american_to_implied_probability,
    decimal_to_implied_probability,
    normalize_market,
    normalize_period,
    normalize_side,
)


class OddsModelTests(unittest.TestCase):
    def test_normalized_odds_to_dict(self):
        row = NormalizedOdds(
            provider="test",
            sportsbook_key="book",
            sportsbook_name="Book",
            league="NBA",
            sport_key="basketball_nba",
            event_id="evt",
            event_name="Away @ Home",
            commence_time="2026-06-10T00:00:00Z",
            home_team="Home",
            away_team="Away",
            market_key="player_points",
            market_name="Player Points",
            market_type="player_points",
            selection_name="Over",
            side="over",
            line=28.5,
            american_odds=120,
            implied_probability=0.4545,
        )

        self.assertEqual(row.to_dict()["sportsbook_key"], "book")
        self.assertEqual(row.to_dict()["raw"], {})

    def test_odds_helpers(self):
        self.assertEqual(american_to_implied_probability(130), 0.4348)
        self.assertEqual(american_to_implied_probability("-110"), 0.5238)
        self.assertEqual(decimal_to_implied_probability(2.5), 0.4)
        self.assertEqual(normalize_side("Over 28.5"), "over")
        self.assertEqual(normalize_market("Player Points + Rebounds"), "player_points_rebounds")
        self.assertEqual(normalize_period("1st Half Player Assists"), "first_half")


if __name__ == "__main__":
    unittest.main()
