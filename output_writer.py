"""
Output writer for the Scryfall Tagger extraction tool.

Produces a plain-text file structured for AI model training.
Each record consists of a TAG block followed by all CARD entries
assigned to that tag, separated by blank lines.

Format example
--------------
### TAG: creature-type/merfolk
NAME: Merfolk
NAMESPACE: creature-type
DESCRIPTION: Cards with the Merfolk creature type.
TOTAL_CARDS: 142

CARD: Merrow Reejerey
  TYPE: Legendary Creature — Merfolk Soldier
  MANA_COST: {2}{U}
  CMC: 3.0
  COLORS: U
  ORACLE_TEXT: Other Merfolk you control get +1/+1. Whenever you cast a Merfolk spell, you may tap or untap target permanent.
  RARITY: uncommon

...

================================================================================
"""

import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

SEPARATOR = "=" * 80


def _colors_str(colors: list[str]) -> str:
    return "".join(colors) if colors else "C"  # C = colorless


def _safe(value: Any) -> str:
    """Convert a value to a single-line string safe for the output file."""
    return str(value).replace("\n", " ").replace("\r", "").strip()


class OutputWriter:
    """Streams tag + card data to an output file."""

    def __init__(self, output_path: Path, append: bool = False) -> None:
        self._path = output_path
        mode = "a" if append else "w"
        self._fh = output_path.open(mode, encoding="utf-8")
        self._tags_written = 0
        self._cards_written = 0
        if not append:
            self._write_header()

    def _write_header(self) -> None:
        self._fh.write(
            "# Scryfall Card Tags – AI Training Dataset\n"
            "#\n"
            "# Source: https://tagger.scryfall.com  (Card tags only; artwork and\n"
            "#         printing tags are excluded.)\n"
            "#\n"
            "# Format:\n"
            "#   ### TAG: <namespace>/<slug>\n"
            "#   NAME: <human-readable tag name>\n"
            "#   NAMESPACE: <tag namespace>\n"
            "#   DESCRIPTION: <tag description if available>\n"
            "#   TOTAL_CARDS: <number of cards carrying this tag>\n"
            "#   (blank line)\n"
            "#   CARD: <card name>\n"
            "#     TYPE: <type line>\n"
            "#     MANA_COST: <mana cost>\n"
            "#     CMC: <converted mana cost>\n"
            "#     COLORS: <color symbols>\n"
            "#     ORACLE_TEXT: <oracle text>\n"
            "#     RARITY: <rarity>\n"
            "#   (blank line per card, separator between tags)\n"
            "#\n"
            + SEPARATOR
            + "\n\n"
        )

    def write_tag_block(
        self,
        tag: dict[str, Any],
        cards: list[dict[str, Any]],
    ) -> None:
        """Write one complete TAG block with all associated cards."""
        slug = tag.get("slug", "unknown")
        namespace = tag.get("namespace", "")
        name = tag.get("name", slug)
        description = tag.get("description") or ""
        total = tag.get("taggingCount") or len(cards)

        # Tag header
        self._fh.write(f"### TAG: {namespace}/{slug}\n")
        self._fh.write(f"NAME: {_safe(name)}\n")
        self._fh.write(f"NAMESPACE: {_safe(namespace)}\n")
        if description:
            self._fh.write(f"DESCRIPTION: {_safe(description)}\n")
        self._fh.write(f"TOTAL_CARDS: {total}\n")
        self._fh.write("\n")

        # Card entries
        for card in cards:
            self._fh.write(f"CARD: {_safe(card.get('name', ''))}\n")
            self._fh.write(f"  TYPE: {_safe(card.get('type_line', ''))}\n")
            self._fh.write(f"  MANA_COST: {_safe(card.get('mana_cost', ''))}\n")
            self._fh.write(f"  CMC: {card.get('cmc', 0)}\n")
            self._fh.write(f"  COLORS: {_colors_str(card.get('colors', []))}\n")
            oracle = _safe(card.get("oracle_text", ""))
            self._fh.write(f"  ORACLE_TEXT: {oracle}\n")
            self._fh.write(f"  RARITY: {_safe(card.get('rarity', ''))}\n")
            self._fh.write("\n")
            self._cards_written += 1

        self._fh.write(SEPARATOR + "\n\n")
        self._tags_written += 1

        if self._tags_written % 25 == 0:
            self._fh.flush()

    def close(self) -> None:
        """Flush and close the output file."""
        self._fh.write(
            f"# END OF DATASET\n"
            f"# Total tags: {self._tags_written}\n"
            f"# Total card–tag associations: {self._cards_written}\n"
        )
        self._fh.flush()
        self._fh.close()
        logger.info(
            "Output written to %s  (%d tags, %d card entries)",
            self._path,
            self._tags_written,
            self._cards_written,
        )

    # Context-manager support
    def __enter__(self) -> "OutputWriter":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
