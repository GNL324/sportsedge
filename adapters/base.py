from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sportsedge.models.odds import NormalizedOdds


class ProviderError(RuntimeError):
    """Base error for sportsbook provider failures."""


class MissingAPIKey(ProviderError):
    """Raised when a provider API key is required but unavailable."""


class BaseSportsbookAdapter(ABC):
    """Interface implemented by all sportsbook odds providers."""

    provider_name: str

    @abstractmethod
    def fetch_odds(self, **kwargs: Any) -> list[NormalizedOdds]:
        """Fetch provider odds and return SportsEdge-normalized odds objects."""

