import os
import unittest
from unittest.mock import patch

from sportsedge.adapters.theoddsapi import MissingTheOddsAPIKey, TheOddsAPIAdapter, normalize_theoddsapi_events
from sportsedge.models.odds import NormalizedOdds


def oddsapi_payload():
    return [
        {
            "id": "evt",
            "sport_key": "basketball_nba",
            "sport_title": "NBA",
            "commence_time": "2026-06-10T00:00:00Z",
            "home_team": "New York Knicks",
            "away_team": "San Antonio Spurs",
            "bookmakers": [
                {
                    "key": "draftkings",
                    "title": "DraftKings",
                    "markets": [
                        {
                            "key": "player_points",
                            "last_update": "2026-06-01T00:00:00Z",
                            "outcomes": [
                                {"name": "Over", "description": "Jalen Brunson", "price": -110, "point": 28.5},
                                {"name": "Under", "description": "Jalen Brunson", "price": -105, "point": 28.5},
                            ],
                        },
                        {
                            "key": "h2h",
                            "last_update": "2026-06-01T00:00:00Z",
                            "outcomes": [{"name": "New York Knicks", "price": 120}],
                        },
                    ],
                }
            ],
        }
    ]


class TheOddsAPIAdapterTests(unittest.TestCase):
    def test_theoddsapi_normalizes_player_props_and_moneyline(self):
        rows = normalize_theoddsapi_events(oddsapi_payload(), sport_key="basketball_nba")

        self.assertEqual(len(rows), 3)
        prop = rows[0]
        self.assertIsInstance(prop, NormalizedOdds)
        self.assertEqual(prop.provider, "theoddsapi")
        self.assertEqual(prop.sportsbook_key, "draftkings")
        self.assertEqual(prop.sportsbook_name, "DraftKings")
        self.assertEqual(prop.league, "NBA")
        self.assertEqual(prop.sport_key, "basketball_nba")
        self.assertEqual(prop.market_type, "player_points")
        self.assertEqual(prop.side, "over")
        self.assertEqual(prop.player_name, "Jalen Brunson")
        self.assertEqual(prop.line, 28.5)
        self.assertEqual(prop.american_odds, -110)
        self.assertEqual(prop.implied_probability, 0.5238)

        moneyline = rows[-1]
        self.assertEqual(moneyline.market_type, "h2h")
        self.assertEqual(moneyline.team_name, "New York Knicks")
        self.assertIsNone(moneyline.side)

    def test_theoddsapi_fetch_odds_uses_normalized_payload(self):
        client = TheOddsAPIAdapter(api_key="key", raw_dir=".")
        with patch.object(client, "get_odds", return_value=oddsapi_payload()):
            rows = client.fetch_odds(sport_key="basketball_nba", markets="h2h,player_points")

        self.assertEqual(rows[0].provider, "theoddsapi")
        self.assertEqual(rows[0].sportsbook_key, "draftkings")

    def test_theoddsapi_fetch_player_props(self):
        client = TheOddsAPIAdapter(api_key="key", raw_dir=".")
        with patch.object(client, "_get_json", return_value=oddsapi_payload()[0]):
            rows = client.fetch_player_props(sport_key="basketball_nba", event_id="evt")

        self.assertEqual(rows[0].market_type, "player_points")
        self.assertEqual(rows[0].player_name, "Jalen Brunson")

    def test_theoddsapi_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            client = TheOddsAPIAdapter(raw_dir=".")
            with self.assertRaisesRegex(MissingTheOddsAPIKey, "ODDS_API_KEY"):
                client.fetch_odds(sport_key="basketball_nba")


if __name__ == "__main__":
    unittest.main()
