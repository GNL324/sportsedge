from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sportsedge.adapters.base import BaseSportsbookAdapter, MissingAPIKey, ProviderError
from sportsedge.models.odds import (
    NormalizedOdds,
    american_to_implied_probability,
    decimal_to_implied_probability,
    normalize_league,
    normalize_market,
    normalize_period,
    normalize_side,
    number_or_none,
)

LOGGER = logging.getLogger(__name__)

PLAYER_PROP_MARKETS = (
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_threes",
    "player_blocks",
    "player_steals",
    "player_turnovers",
    "player_points_rebounds_assists",
    "player_points_rebounds",
    "player_points_assists",
    "player_rebounds_assists",
)


class TheOddsAPIError(ProviderError):
    pass


class MissingTheOddsAPIKey(MissingAPIKey, TheOddsAPIError):
    pass


class TheOddsAPIAdapter(BaseSportsbookAdapter):
    """Adapter for The Odds API v4."""

    provider_name = "theoddsapi"
    base_url = "https://api.the-odds-api.com/v4"

    def __init__(self, api_key: str | None = None, raw_dir: str | Path = "data/raw", timeout: int = 20) -> None:
        self.api_key = api_key or os.environ.get("ODDS_API_KEY")
        self.raw_dir = Path(raw_dir)
        self.timeout = timeout
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def fetch_odds(
        self,
        sport_key: str,
        regions: str = "us",
        markets: str = "h2h,spreads,totals,outrights",
        bookmakers: str | None = None,
        odds_format: str = "american",
    ) -> list[NormalizedOdds]:
        raw_events = self.get_odds(
            sport_key=sport_key,
            regions=regions,
            markets=markets,
            bookmakers=bookmakers,
            odds_format=odds_format,
        )
        return normalize_theoddsapi_events(raw_events, sport_key=sport_key, odds_format=odds_format)

    def list_sports(self, all_sports: bool = False) -> list[dict[str, Any]]:
        params = {"all": "true"} if all_sports else {}
        payload = self._get_json("sports", params, raw_key="sports_all" if all_sports else "sports")
        return payload if isinstance(payload, list) else []

    def get_events(self, sport_key: str) -> list[dict[str, Any]]:
        if not sport_key:
            raise ValueError("sport_key is required")
        payload = self._get_json(f"sports/{sport_key}/events", {}, raw_key=f"events_{sport_key}")
        return payload if isinstance(payload, list) else []

    def get_odds(
        self,
        sport_key: str,
        regions: str = "us",
        markets: str = "h2h,spreads,totals,outrights",
        bookmakers: str | None = None,
        odds_format: str = "american",
    ) -> list[dict[str, Any]]:
        if not sport_key:
            raise ValueError("sport_key is required")
        params: dict[str, Any] = {"regions": regions, "markets": markets, "oddsFormat": odds_format}
        if bookmakers:
            params["bookmakers"] = bookmakers
        payload = self._get_json(f"sports/{sport_key}/odds", params, raw_key=f"odds_{sport_key}")
        return payload if isinstance(payload, list) else []

    def fetch_player_props(
        self,
        sport_key: str,
        event_id: str,
        regions: str = "us",
        markets: str | None = None,
        bookmakers: str | None = None,
        odds_format: str = "american",
    ) -> list[NormalizedOdds]:
        if not sport_key or not event_id:
            raise ValueError("sport_key and event_id are required")
        market_list = markets or ",".join(PLAYER_PROP_MARKETS)
        params: dict[str, Any] = {"regions": regions, "markets": market_list, "oddsFormat": odds_format}
        if bookmakers:
            params["bookmakers"] = bookmakers
        payload = self._get_json(f"sports/{sport_key}/events/{event_id}/odds", params, raw_key=f"player_props_{sport_key}_{event_id}")
        events = [payload] if isinstance(payload, dict) else []
        return normalize_theoddsapi_events(events, sport_key=sport_key, odds_format=odds_format)

    def _get_json(self, endpoint: str, params: dict[str, Any], raw_key: str) -> Any:
        if not self.api_key:
            raise MissingTheOddsAPIKey("ODDS_API_KEY is required to call The Odds API")
        query = urlencode({**params, "apiKey": self.api_key})
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}?{query}"
        safe_url = url.replace(self.api_key, "***")
        LOGGER.info("api call GET %s", safe_url)
        request = Request(url, headers={"User-Agent": "sportsedge/0.1", "Accept": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                payload = json.loads(body) if body else None
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            self._write_raw(raw_key, {"url": safe_url, "status": exc.code, "error": detail}, error=True)
            raise TheOddsAPIError(f"GET {endpoint} failed with HTTP {exc.code}: {detail[:200]}") from exc
        except json.JSONDecodeError as exc:
            self._write_raw(raw_key, {"url": safe_url, "error": "invalid JSON"}, error=True)
            raise TheOddsAPIError(f"GET {endpoint} failed: invalid JSON response") from exc
        except Exception as exc:
            self._write_raw(raw_key, {"url": safe_url, "error": str(exc)}, error=True)
            raise TheOddsAPIError(f"GET {endpoint} failed: {exc}") from exc
        self._write_raw(raw_key, {"url": safe_url, "payload": payload})
        return payload

    def _write_raw(self, key: str, payload: Any, error: bool = False) -> None:
        safe_key = re.sub(r"[^a-zA-Z0-9_.-]+", "_", key)[:80]
        status = "error" if error else "raw"
        path = self.raw_dir / f"theoddsapi_{safe_key}_{status}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def normalize_theoddsapi_events(
    events: list[dict[str, Any]],
    sport_key: str | None = None,
    odds_format: str = "american",
) -> list[NormalizedOdds]:
    rows: list[NormalizedOdds] = []
    for event in events or []:
        current_sport_key = _str_or_none(event.get("sport_key") or sport_key)
        league = normalize_league(event.get("sport_title") or current_sport_key)
        event_id = _str_or_none(event.get("id") or event.get("event_id"))
        home_team = _str_or_none(event.get("home_team"))
        away_team = _str_or_none(event.get("away_team"))
        commence_time = _str_or_none(event.get("commence_time"))
        for bookmaker in event.get("bookmakers", []) or []:
            bookmaker_key = _str_or_none(bookmaker.get("key"))
            bookmaker_name = _str_or_none(bookmaker.get("title") or bookmaker.get("key"))
            for market in bookmaker.get("markets", []) or []:
                market_key_raw = market.get("key")
                market_type = normalize_market(market_key_raw)
                last_update = _str_or_none(market.get("last_update") or bookmaker.get("last_update"))
                for outcome in market.get("outcomes", []) or []:
                    price = outcome.get("price")
                    decimal_odds = number_or_none(price) if odds_format == "decimal" else None
                    american_odds = number_or_none(price) if odds_format != "decimal" else None
                    implied = decimal_to_implied_probability(price) if odds_format == "decimal" else american_to_implied_probability(price)
                    selection_name = _str_or_none(outcome.get("name"))
                    side = normalize_side(selection_name)
                    rows.append(
                        NormalizedOdds(
                            provider="theoddsapi",
                            sportsbook_key=bookmaker_key,
                            sportsbook_name=bookmaker_name,
                            league=league,
                            sport_key=current_sport_key,
                            event_id=event_id,
                            event_name=_event_name(home_team, away_team),
                            commence_time=commence_time,
                            home_team=home_team,
                            away_team=away_team,
                            market_key=market_type,
                            market_name=_str_or_none(market_key_raw),
                            market_type=market_type,
                            period=normalize_period(market_key_raw),
                            selection_name=selection_name,
                            side=side,
                            player_name=_str_or_none(outcome.get("description")) if _is_player_prop(market_type) else None,
                            team_name=selection_name if not side else None,
                            line=number_or_none(outcome.get("point")),
                            american_odds=american_odds,
                            decimal_odds=decimal_odds,
                            implied_probability=implied,
                            last_update=last_update,
                            raw=_compact_raw(outcome),
                        )
                    )
    return rows


def _is_player_prop(market_key: str | None) -> bool:
    return bool(str(market_key or "").startswith("player_"))


def _event_name(home_team: str | None, away_team: str | None) -> str | None:
    if home_team and away_team:
        return f"{away_team} @ {home_team}"
    return None


def _compact_raw(outcome: dict[str, Any]) -> dict[str, Any]:
    keep = ("name", "description", "price", "point")
    return {key: outcome.get(key) for key in keep if key in outcome}


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

