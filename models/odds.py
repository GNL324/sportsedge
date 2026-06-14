from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class NormalizedOdds:
    """Provider-neutral sportsbook odds row."""

    provider: str
    sportsbook_key: str | None
    sportsbook_name: str | None
    league: str | None
    sport_key: str | None
    event_id: str | None
    event_name: str | None
    commence_time: str | None
    home_team: str | None
    away_team: str | None
    market_key: str | None
    market_name: str | None
    market_type: str | None
    period: str = "full_game"
    selection_name: str | None = None
    side: str | None = None
    player_name: str | None = None
    team_name: str | None = None
    line: float | None = None
    american_odds: float | None = None
    decimal_odds: float | None = None
    implied_probability: float | None = None
    last_update: str | None = None
    is_live: bool | None = None
    is_main: bool | None = None
    deeplink_desktop: str | None = None
    deeplink_mobile: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def american_to_implied_probability(value: Any) -> float | None:
    odds = number_or_none(value)
    if odds is None or odds == 0:
        return None
    if odds > 0:
        probability = 100 / (odds + 100)
    else:
        probability = abs(odds) / (abs(odds) + 100)
    return round(probability, 4)


def decimal_to_implied_probability(value: Any) -> float | None:
    odds = number_or_none(value)
    if odds is None or odds <= 1:
        return None
    return round(1 / odds, 4)


def normalize_side(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if text in {"over", "o"} or text.startswith("over"):
        return "over"
    if text in {"under", "u"} or text.startswith("under"):
        return "under"
    if text in {"yes", "y"}:
        return "yes"
    if text in {"no", "n"}:
        return "no"
    return None


def normalize_market(value: Any) -> str | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    canonical = {
        "h2h": "h2h",
        "moneyline": "h2h",
        "spreads": "spreads",
        "spread": "spreads",
        "totals": "totals",
        "total": "totals",
        "outrights": "outrights",
        "outright": "outrights",
        "points + rebounds + assists": "player_points_rebounds_assists",
        "points rebounds assists": "player_points_rebounds_assists",
        "points + rebounds": "player_points_rebounds",
        "points rebounds": "player_points_rebounds",
        "points + assists": "player_points_assists",
        "points assists": "player_points_assists",
        "rebounds + assists": "player_rebounds_assists",
        "assists + rebounds": "player_rebounds_assists",
        "rebounds assists": "player_rebounds_assists",
        "assists rebounds": "player_rebounds_assists",
        "blocks + steals": "player_blocks_steals",
        "blocks steals": "player_blocks_steals",
        "points": "player_points",
        "rebounds": "player_rebounds",
        "assists": "player_assists",
        "threes": "player_threes",
        "3-pointers": "player_threes",
        "blocks": "player_blocks",
        "steals": "player_steals",
        "turnovers": "player_turnovers",
    }
    if text.startswith("player_"):
        return text
    for needle, normalized in canonical.items():
        if text == needle or needle in text:
            return normalized
    return text.replace(" ", "_")


def normalize_period(value: Any) -> str:
    text = str(value or "").strip().lower()
    compact = " ".join("".join(ch if ch.isalnum() else " " for ch in text).split())
    if "1st quarter" in compact or "first quarter" in compact or compact.startswith("q1 "):
        return "first_quarter"
    if "2nd quarter" in compact or "second quarter" in compact or compact.startswith("q2 "):
        return "second_quarter"
    if "3rd quarter" in compact or "third quarter" in compact or compact.startswith("q3 "):
        return "third_quarter"
    if "4th quarter" in compact or "fourth quarter" in compact or compact.startswith("q4 "):
        return "fourth_quarter"
    if "1st half" in compact or "first half" in compact:
        return "first_half"
    if "2nd half" in compact or "second half" in compact:
        return "second_half"
    return "full_game"


def normalize_league(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    known = {
        "basketball_nba": "NBA",
        "americanfootball_nfl": "NFL",
        "baseball_mlb": "MLB",
        "icehockey_nhl": "NHL",
        "nba": "NBA",
        "nfl": "NFL",
        "mlb": "MLB",
        "nhl": "NHL",
    }
    return known.get(text.lower(), text.upper() if len(text) <= 5 else text)


def normalize_sport_key(value: Any) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    mapping = {
        "NBA": "basketball_nba",
        "NFL": "americanfootball_nfl",
        "MLB": "baseball_mlb",
        "NHL": "icehockey_nhl",
    }
    return mapping.get(text.upper(), text.lower())


def number_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        text = str(value).strip()
        if text.startswith("+"):
            text = text[1:]
        try:
            return float(text)
        except ValueError:
            return None

