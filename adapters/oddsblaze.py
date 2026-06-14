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
    normalize_league,
    normalize_market,
    normalize_period,
    normalize_side,
    normalize_sport_key,
    number_or_none,
)

LOGGER = logging.getLogger(__name__)


class OddsBlazeError(ProviderError):
    pass


class MissingOddsBlazeKey(MissingAPIKey, OddsBlazeError):
    pass


class OddsBlazeAdapter(BaseSportsbookAdapter):
    """Adapter for the OddsBlaze odds endpoint."""

    provider_name = "oddsblaze"
    base_url = "https://odds.oddsblaze.com/"

    def __init__(self, api_key: str | None = None, raw_dir: str | Path = "data/raw", timeout: int = 20) -> None:
        self.api_key = api_key or os.environ.get("ODDSBLAZE_API_KEY")
        self.raw_dir = Path(raw_dir)
        self.timeout = timeout
        self.raw_dir.mkdir(parents=True, exist_ok=True)

    def fetch_odds(
        self,
        sportsbook: str,
        league: str,
        market: str | None = None,
        market_contains: str | None = None,
        main: bool | None = None,
        live: bool | None = None,
        price: str = "american",
    ) -> list[NormalizedOdds]:
        if not self.api_key:
            raise MissingOddsBlazeKey("ODDSBLAZE_API_KEY is required to call OddsBlaze")
        if not sportsbook:
            raise ValueError("sportsbook is required")
        if not league:
            raise ValueError("league is required")

        params: dict[str, Any] = {
            "key": self.api_key,
            "sportsbook": sportsbook,
            "league": league,
            "price": price,
        }
        if market:
            params["market"] = market
        if market_contains:
            params["market_contains"] = market_contains
        if main is not None:
            params["main"] = _bool_param(main)
        if live is not None:
            params["live"] = _bool_param(live)

        payload = self._get_json(params, raw_key=f"{league}_{sportsbook}")
        return normalize_oddsblaze_payload(payload, sportsbook=sportsbook, league=league)

    def _get_json(self, params: dict[str, Any], raw_key: str) -> Any:
        query = urlencode(params)
        url = f"{self.base_url}?{query}"
        safe_url = url.replace(str(self.api_key), "***") if self.api_key else url
        LOGGER.info("api call GET %s", safe_url)
        request = Request(url, headers={"User-Agent": "sportsedge/0.1", "Accept": "application/json"})
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                payload = json.loads(body) if body else {}
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            self._write_raw(raw_key, {"url": safe_url, "status": exc.code, "error": detail}, error=True)
            raise OddsBlazeError(f"GET OddsBlaze odds failed with HTTP {exc.code}: {detail[:200]}") from exc
        except json.JSONDecodeError as exc:
            self._write_raw(raw_key, {"url": safe_url, "error": "invalid JSON"}, error=True)
            raise OddsBlazeError("GET OddsBlaze odds failed: invalid JSON response") from exc
        except Exception as exc:
            self._write_raw(raw_key, {"url": safe_url, "error": str(exc)}, error=True)
            raise OddsBlazeError(f"GET OddsBlaze odds failed: {exc}") from exc
        self._write_raw(raw_key, {"url": safe_url, "payload": payload})
        return payload if isinstance(payload, dict) else {}

    def _write_raw(self, key: str, payload: Any, error: bool = False) -> None:
        safe_key = re.sub(r"[^a-zA-Z0-9_.-]+", "_", key)[:80]
        status = "error" if error else "raw"
        path = self.raw_dir / f"oddsblaze_{safe_key}_{status}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def normalize_oddsblaze_payload(
    payload: dict[str, Any],
    sportsbook: str | None = None,
    league: str | None = None,
) -> list[NormalizedOdds]:
    rows: list[NormalizedOdds] = []
    source_sportsbook = sportsbook or _sportsbook_id(payload.get("sportsbook"))
    source_bookmaker = _sportsbook_name(payload.get("sportsbook")) or source_sportsbook
    source_league = normalize_league(league or payload.get("league"))
    sport_key = normalize_sport_key(source_league)

    for event in payload.get("events", []) or []:
        event_id = event.get("id") or event.get("event_id") or event.get("game_id")
        event_date = event.get("start_time") or event.get("commence_time") or event.get("date") or event.get("event_date")
        home_team = event.get("home_team") or event.get("home") or event.get("homeTeam")
        away_team = event.get("away_team") or event.get("away") or event.get("awayTeam")
        for item in event.get("odds", []) or []:
            price = _first_present(item, "price", "american_price", "odds")
            market = item.get("market") or item.get("market_name") or item.get("market_key")
            market_type = normalize_market(market)
            rows.append(
                NormalizedOdds(
                    provider="oddsblaze",
                    sportsbook_key=_str_or_none(source_sportsbook),
                    sportsbook_name=_str_or_none(source_bookmaker),
                    league=source_league,
                    sport_key=sport_key,
                    event_id=_str_or_none(event_id),
                    event_name=_event_name(home_team, away_team),
                    commence_time=_str_or_none(event_date),
                    home_team=_str_or_none(home_team),
                    away_team=_str_or_none(away_team),
                    market_key=market_type,
                    market_name=_str_or_none(market),
                    market_type=market_type,
                    period=normalize_period(market),
                    selection_name=_str_or_none(item.get("name") or _selection(item).get("name")),
                    side=normalize_side(_side_value(item)),
                    player_name=_str_or_none(_player_name(item)),
                    team_name=_str_or_none(item.get("team")),
                    line=number_or_none(_line_value(item)),
                    american_odds=number_or_none(price),
                    decimal_odds=None,
                    implied_probability=american_to_implied_probability(price),
                    last_update=_str_or_none(item.get("updated") or item.get("last_update") or payload.get("updated")),
                    is_live=_bool_or_none(item.get("live") or payload.get("live")),
                    is_main=_bool_or_none(item.get("main")),
                    deeplink_desktop=_deeplink(item, "desktop"),
                    deeplink_mobile=_deeplink(item, "mobile"),
                    raw=_compact_raw(item),
                )
            )
    return rows


def _bool_param(value: bool) -> str:
    return "true" if bool(value) else "false"


def _first_present(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value is not None and value != "":
            return value
    return None


def _selection(item: dict[str, Any]) -> dict[str, Any]:
    selection = item.get("selection") or {}
    return selection if isinstance(selection, dict) else {}


def _side_value(item: dict[str, Any]) -> Any:
    selection = _selection(item)
    return item.get("side") or item.get("selection_side") or selection.get("side") or selection.get("type") or item.get("name")


def _line_value(item: dict[str, Any]) -> Any:
    selection = _selection(item)
    return _first_present(item, "line", "point", "selection_line") or selection.get("line") or selection.get("point")


def _player_name(item: dict[str, Any]) -> Any:
    player = item.get("player_name") or item.get("player") or item.get("participant")
    if isinstance(player, dict):
        return player.get("name") or player.get("full_name")
    selection = _selection(item)
    if not player and selection.get("name"):
        player = selection.get("name")
    metadata = item.get("player_metadata") or item.get("playerMeta") or {}
    if isinstance(metadata, dict):
        return player or metadata.get("name") or metadata.get("full_name")
    return player


def _sportsbook_id(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("id") or value.get("key") or value.get("name")
    return value


def _sportsbook_name(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("name") or value.get("title") or value.get("id")
    return value


def _event_name(home_team: Any, away_team: Any) -> str | None:
    if home_team and away_team:
        return f"{away_team} @ {home_team}"
    return None


def _deeplink(item: dict[str, Any], platform: str) -> str | None:
    links = item.get("links") or {}
    if isinstance(links, dict):
        return _str_or_none(links.get(platform) or links.get(f"{platform}_url"))
    return None


def _compact_raw(item: dict[str, Any]) -> dict[str, Any]:
    keep = ("id", "market", "name", "price", "main", "side", "selection", "line", "player_name", "team")
    return {key: item.get(key) for key in keep if key in item}


def _bool_or_none(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _str_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None

