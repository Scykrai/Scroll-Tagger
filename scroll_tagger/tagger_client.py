"""
Scryfall Tagger GraphQL client.

Handles authentication (CSRF token extraction) and queries against the
unofficial Scryfall Tagger GraphQL endpoint at https://tagger.scryfall.com/graphql.
"""

import logging
import re
import time
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://tagger.scryfall.com"
GRAPHQL_URL = f"{BASE_URL}/graphql"

# Minimum seconds between requests to avoid hammering the server
REQUEST_DELAY = 0.5


# ---------------------------------------------------------------------------
# GraphQL query definitions
# ---------------------------------------------------------------------------

_SEARCH_TAGS_QUERY = """
query SearchTags($input: TagSearchInput!) {
  tagSearch(input: $input) {
    results {
      slug
      name
      namespace
      taggingCount
      status
    }
    totalCount
    pageSize
  }
}
"""

_FETCH_TAG_QUERY = """
fragment CardAttrs on Card {
  name
  oracleId
}

fragment TaggingAttrs on Tagging {
  card {
    ...CardAttrs
  }
}

fragment TagAttrs on Tag {
  slug
  name
  namespace
  description
  taggingCount
}

query FetchTag($slug: String!, $page: Int!) {
  tag(slug: $slug) {
    ...TagAttrs
    taggings(page: $page) {
      ...TaggingAttrs
    }
    taggingsCount
  }
}
"""


class TaggerClient:
    """Thin wrapper around the Scryfall Tagger GraphQL API."""

    def __init__(self) -> None:
        self._session = requests.Session()
        self._csrf_token: Optional[str] = None
        self._last_request_time: float = 0.0
        self._authenticate()

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------

    def _authenticate(self) -> None:
        """Visit the tagger home page and extract the CSRF token."""
        logger.debug("Fetching CSRF token from %s", BASE_URL)
        resp = self._session.get(
            BASE_URL,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) "
                    "Gecko/20100101 Firefox/120.0"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
            timeout=30,
        )
        resp.raise_for_status()

        match = re.search(r'<meta name="csrf-token" content="([^"]+)"', resp.text)
        if not match:
            raise RuntimeError(
                "Could not extract CSRF token from Scryfall Tagger. "
                "The page structure may have changed."
            )
        self._csrf_token = match.group(1)
        logger.debug("CSRF token acquired.")

    # ------------------------------------------------------------------
    # Low-level request helper
    # ------------------------------------------------------------------

    def _post(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        """POST a GraphQL query and return the parsed JSON body."""
        # Enforce rate limiting
        elapsed = time.time() - self._last_request_time
        if elapsed < REQUEST_DELAY:
            time.sleep(REQUEST_DELAY - elapsed)

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/plain, */*",
            "Origin": BASE_URL,
            "Referer": BASE_URL + "/",
            "X-CSRF-Token": self._csrf_token or "",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64; rv:120.0) "
                "Gecko/20100101 Firefox/120.0"
            ),
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Sec-Fetch-Dest": "empty",
        }

        for attempt in range(1, 8):
            try:
                resp = self._session.post(
                    GRAPHQL_URL,
                    json={"query": query, "variables": variables},
                    headers=headers,
                    timeout=30,
                )
                self._last_request_time = time.time()
                resp.raise_for_status()
                data = resp.json()

                if "errors" in data:
                    raise ValueError(f"GraphQL errors: {data['errors']}")

                return data["data"]

            except (requests.RequestException, ValueError) as exc:
                if attempt == 7:
                    raise
                backoff = min(2 ** attempt, 60)
                logger.warning(
                    "Request failed (attempt %d/7): %s – retrying in %ds",
                    attempt,
                    exc,
                    backoff,
                )
                time.sleep(backoff)

        raise RuntimeError("Unreachable")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search_tags(self, page: int = 1, name: Optional[str] = None) -> dict[str, Any]:
        """
        Return a page of tags from the tagger search.

        Returns a dict with keys:
          - results: list of tag dicts (slug, name, namespace, taggingCount, status)
          - totalCount: total number of matching tags
          - pageSize: number of results per page
        """
        variables: dict[str, Any] = {"input": {"page": page}}
        if name:
            variables["input"]["name"] = name

        data = self._post(_SEARCH_TAGS_QUERY, variables)
        return data["tagSearch"]

    def fetch_tag_page(self, slug: str, page: int = 1) -> dict[str, Any]:
        """
        Return metadata and one page of taggings (card associations) for a tag.

        Returns a dict with keys:
          - slug, name, namespace, description, taggingCount
          - taggings: list of tagging dicts, each containing a 'card' dict
          - taggingsCount: total number of cards with this tag
        """
        data = self._post(_FETCH_TAG_QUERY, {"slug": slug, "page": page})
        return data["tag"]
