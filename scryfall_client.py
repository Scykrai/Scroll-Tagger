"""
Scryfall REST API client.

Used to fetch cards associated with a given oracle tag via the
official Scryfall search endpoint (https://api.scryfall.com/cards/search).
This is a reliable fallback / supplement to the Tagger GraphQL API
when we need a complete card list for a tag.
"""

import logging
import time
from typing import Any, Generator

import requests

logger = logging.getLogger(__name__)

SEARCH_URL = "https://api.scryfall.com/cards/search"
REQUEST_DELAY = 0.1  # Scryfall requests at most 10 req/s


class ScryfallClient:
    """Minimal Scryfall REST API client for oracle-tag searches."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update(
            {
                "User-Agent": "ScrollTagger/1.0 (https://github.com/Scykrai/Scroll-Tagger)",
                "Accept": "application/json",
            }
        )
        self._last_request_time: float = 0.0

    def _get(self, url: str, params: dict[str, Any]) -> dict[str, Any]:
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)

        for attempt in range(1, 6):
            try:
                resp = self._session.get(url, params=params, timeout=30)
                self._last_request_time = time.time()

                if resp.status_code == 404:
                    # Tag exists in Tagger but has no searchable cards yet
                    return {}

                resp.raise_for_status()
                return resp.json()

            except requests.RequestException as exc:
                if attempt == 5:
                    raise
                backoff = min(2 ** attempt, 30)
                logger.warning(
                    "Scryfall request failed (attempt %d/5): %s – retrying in %ds",
                    attempt,
                    exc,
                    backoff,
                )
                time.sleep(backoff)

        raise RuntimeError("Unreachable")

    def cards_for_oracle_tag(self, tag_slug: str) -> Generator[dict[str, Any], None, None]:
        """
        Yield card dicts for every card that carries the given oracle tag.

        Uses the Scryfall search query ``otag:<slug>``, de-duplicates by
        oracle_id (unique=cards), and follows pagination automatically.

        Each yielded dict has at minimum:
          name, oracle_id, type_line, mana_cost, oracle_text, colors,
          color_identity, cmc, set (set code), rarity
        """
        params: dict[str, Any] = {
            "q": f"otag:{tag_slug}",
            "unique": "cards",
            "order": "name",
            "format": "json",
        }

        url: str | None = SEARCH_URL
        while url:
            data = self._get(url, params)

            if not data:
                # 404 – no cards for this tag
                return

            for card in data.get("data", []):
                yield {
                    "name": card.get("name", ""),
                    "oracle_id": card.get("oracle_id", ""),
                    "type_line": card.get("type_line", ""),
                    "mana_cost": card.get("mana_cost", ""),
                    "oracle_text": card.get("oracle_text", ""),
                    "colors": card.get("colors", []),
                    "color_identity": card.get("color_identity", []),
                    "cmc": card.get("cmc", 0),
                    "set": card.get("set", ""),
                    "rarity": card.get("rarity", ""),
                    "legalities": card.get("legalities", {}),
                }

            if data.get("has_more"):
                url = data.get("next_page")
                params = {}  # next_page URL already has all params
            else:
                url = None
