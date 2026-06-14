import os
import unittest
from unittest.mock import patch

from sportsedge.adapters.oddsblaze import MissingOddsBlazeKey, OddsBlazeAdapter, normalize_oddsblaze_payload
from sportsedge.models.odds import NormalizedOdds


def oddsblaze_payload():
    return {
        "updated": "2026-06-10T12:00:00Z",
        "league": "nba",
        "sportsbook": {"id": "betmgm", "name": "BetMGM"},
        "events": [
            {
                "id": "evt",
                "start_time": "2026-06-10T23:00:00Z",
                "home_team": "New York Knicks",
                "away_team": "San Antonio Spurs",
                "odds": [
                    {
                        "id": "over",
                        "market": "Player Points + Rebounds",
                        "name": "OG Anunoby Over 22.5",
                        "price": "+100",
                        "main": True,
                        "selection": {"line": 22.5, "name": "OG Anunoby", "side": "Over"},
                        "player": {"id": "player-1", "name": "OG Anunoby"},
                        "links": {"desktop": "https://example.test/desktop"},
                    }
                ],
            }
        ],
    }


class OddsBlazeAdapterTests(unittest.TestCase):
    def test_oddsblaze_normalizes_to_model(self):
        rows = normalize_oddsblaze_payload(oddsblaze_payload())

        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIsInstance(row, NormalizedOdds)
        self.assertEqual(row.provider, "oddsblaze")
        self.assertEqual(row.sportsbook_key, "betmgm")
        self.assertEqual(row.sportsbook_name, "BetMGM")
        self.assertEqual(row.league, "NBA")
        self.assertEqual(row.sport_key, "basketball_nba")
        self.assertEqual(row.event_id, "evt")
        self.assertEqual(row.market_type, "player_points_rebounds")
        self.assertEqual(row.period, "full_game")
        self.assertEqual(row.side, "over")
        self.assertEqual(row.player_name, "OG Anunoby")
        self.assertEqual(row.line, 22.5)
        self.assertEqual(row.american_odds, 100)
        self.assertEqual(row.implied_probability, 0.5)
        self.assertEqual(row.deeplink_desktop, "https://example.test/desktop")
        self.assertNotIn("links", row.raw)

    def test_oddsblaze_fetch_uses_normalized_payload(self):
        client = OddsBlazeAdapter(api_key="key", raw_dir=".")
        with patch.object(client, "_get_json", return_value=oddsblaze_payload()):
            rows = client.fetch_odds(sportsbook="betmgm", league="nba", market_contains="Player")

        self.assertEqual(rows[0].provider, "oddsblaze")
        self.assertEqual(rows[0].sportsbook_key, "betmgm")

    def test_oddsblaze_missing_key(self):
        with patch.dict(os.environ, {}, clear=True):
            client = OddsBlazeAdapter(raw_dir=".")
            with self.assertRaisesRegex(MissingOddsBlazeKey, "ODDSBLAZE_API_KEY"):
                client.fetch_odds(sportsbook="draftkings", league="nba")


if __name__ == "__main__":
    unittest.main()
