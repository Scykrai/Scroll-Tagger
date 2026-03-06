#!/usr/bin/env python3
"""
Scryfall Card Tagger Extractor
==============================

Fetches every *Card* tag from https://tagger.scryfall.com (ignoring Artwork
and Printing tags), then for each tag retrieves all cards assigned to it, and
writes the result to a structured text file suitable for AI model training.

Usage
-----
    python extract_tags.py [OPTIONS]

Options
-------
    -o, --output PATH        Output file path  [default: card_tags_dataset.txt]
    --namespace NAMESPACE    Only extract tags in this namespace (repeatable)
    --min-cards N            Skip tags with fewer than N associated cards [default: 1]
    --max-tags N             Stop after processing N tags (useful for testing)
    --tag-source {tagger,scryfall,both}
                             Where to fetch the card list for each tag.
                             tagger  = use Tagger GraphQL taggings
                             scryfall = use official REST API otag: search (default)
                             both    = merge results from both sources
    --resume PATH            Resume from a previous run's progress file
    --log-level LEVEL        Logging verbosity [default: INFO]
    -h, --help               Show this message and exit

Card Tag Namespaces (examples)
------------------------------
    ability     – keyword abilities (flying, trample, …)
    creature-type – tribal creature types
    spell-type  – spell archetypes (counter, removal, ramp, …)
    theme       – deck archetypes and strategies
    mechanic    – game mechanics
    (and many more – use --namespace to filter)

Output format
-------------
See output_writer.py for a full description of the text format.
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

from output_writer import OutputWriter
from scryfall_client import ScryfallClient
from tagger_client import TaggerClient

# Namespaces that indicate this is NOT a pure card tag.
# Scryfall Tagger uses 'art' for artwork tags and 'print' for printing tags.
EXCLUDED_NAMESPACES = {"art", "print", "printing", "artwork"}

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="extract_tags.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-o",
        "--output",
        default="card_tags_dataset.txt",
        help="Output file path (default: card_tags_dataset.txt)",
    )
    parser.add_argument(
        "--namespace",
        action="append",
        dest="namespaces",
        metavar="NAMESPACE",
        help=(
            "Only extract tags in this namespace. "
            "Can be specified multiple times. "
            "If omitted, all non-artwork/non-printing namespaces are included."
        ),
    )
    parser.add_argument(
        "--min-cards",
        type=int,
        default=1,
        metavar="N",
        help="Skip tags with fewer than N associated cards (default: 1)",
    )
    parser.add_argument(
        "--max-tags",
        type=int,
        default=None,
        metavar="N",
        help="Stop after processing N tags (useful for testing)",
    )
    parser.add_argument(
        "--tag-source",
        choices=["tagger", "scryfall", "both"],
        default="scryfall",
        help=(
            "Source used to fetch the card list for each tag. "
            "'scryfall' uses the official REST API (recommended). "
            "'tagger' uses the Tagger GraphQL taggings. "
            "'both' merges results from both sources."
        ),
    )
    parser.add_argument(
        "--resume",
        metavar="PATH",
        help="Path to a progress file from a previous (interrupted) run.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default: INFO)",
    )
    return parser.parse_args(argv)


# ---------------------------------------------------------------------------
# Tag discovery
# ---------------------------------------------------------------------------


def discover_all_card_tags(
    tagger: TaggerClient,
    allowed_namespaces: list[str] | None,
) -> list[dict[str, Any]]:
    """
    Return a deduplicated list of all card tags from the Tagger.

    Tags in EXCLUDED_NAMESPACES (artwork, printing) are automatically
    filtered out.  If *allowed_namespaces* is provided, only tags in
    those namespaces are returned.
    """
    all_tags: list[dict[str, Any]] = []
    seen_slugs: set[str] = set()
    page = 1

    logger.info("Discovering card tags from Scryfall Tagger…")

    while True:
        logger.debug("Fetching tag search page %d", page)
        try:
            result = tagger.search_tags(page=page)
        except Exception as exc:
            logger.error("Failed to fetch tag page %d: %s", page, exc)
            break

        tags = result.get("results", [])
        total = result.get("totalCount", 0)
        page_size = result.get("pageSize", 0) or len(tags) or 1

        for tag in tags:
            slug = tag.get("slug", "")
            namespace = tag.get("namespace", "") or ""

            # Skip duplicates
            if slug in seen_slugs:
                continue
            seen_slugs.add(slug)

            # Skip artwork / printing tags
            if namespace.lower() in EXCLUDED_NAMESPACES:
                continue

            # Skip if namespace filter is set and this doesn't match
            if allowed_namespaces and namespace.lower() not in [
                n.lower() for n in allowed_namespaces
            ]:
                continue

            all_tags.append(tag)

        logger.info(
            "Page %d: %d tags fetched, %d card tags collected so far (total across all types: %d)",
            page,
            len(tags),
            len(all_tags),
            total,
        )

        # Stop when the API returns no results or we've paged through everything
        if not tags or (page_size > 0 and page * page_size >= total):
            break

        page += 1

    logger.info("Tag discovery complete: %d card tags found.", len(all_tags))
    return all_tags


# ---------------------------------------------------------------------------
# Card fetching
# ---------------------------------------------------------------------------


def fetch_cards_from_tagger(
    tagger: TaggerClient, slug: str, expected_total: int
) -> list[dict[str, Any]]:
    """Fetch all cards for a tag using Tagger GraphQL pagination."""
    cards: list[dict[str, Any]] = []
    seen_oracle_ids: set[str] = set()
    page = 1

    while True:
        try:
            tag_data = tagger.fetch_tag_page(slug, page=page)
        except Exception as exc:
            logger.warning("Tagger: could not fetch page %d for '%s': %s", page, slug, exc)
            break

        taggings = tag_data.get("taggings") or []
        if not taggings:
            break

        for tagging in taggings:
            card = tagging.get("card")
            if not card:
                continue
            oracle_id = card.get("oracleId", "") or card.get("oracle_id", "")
            if oracle_id in seen_oracle_ids:
                continue
            seen_oracle_ids.add(oracle_id)
            cards.append(
                {
                    "name": card.get("name", ""),
                    "oracle_id": oracle_id,
                    "type_line": card.get("typeLine", "") or card.get("type_line", ""),
                    "mana_cost": card.get("manaCost", "") or card.get("mana_cost", ""),
                    "oracle_text": card.get("oracleText", "") or card.get("oracle_text", ""),
                    "colors": card.get("colors", []),
                    "color_identity": card.get("colorIdentity", []) or card.get("color_identity", []),
                    "cmc": card.get("convertedManaCost") or card.get("cmc", 0),
                    "set": card.get("set", ""),
                    "rarity": card.get("rarity", ""),
                }
            )

        taggings_count = tag_data.get("taggingsCount") or expected_total
        if len(cards) >= taggings_count or len(taggings) == 0:
            break

        page += 1

    return cards


def fetch_cards_from_scryfall(
    scryfall: ScryfallClient, slug: str
) -> list[dict[str, Any]]:
    """Fetch all cards for a tag using the official Scryfall REST API."""
    try:
        return list(scryfall.cards_for_oracle_tag(slug))
    except Exception as exc:
        logger.warning("Scryfall: could not fetch cards for tag '%s': %s", slug, exc)
        return []


def merge_card_lists(
    tagger_cards: list[dict[str, Any]],
    scryfall_cards: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge two card lists, preferring Scryfall data (richer) and deduplicating."""
    by_oracle: dict[str, dict[str, Any]] = {}
    # Add tagger cards first
    for card in tagger_cards:
        oid = card.get("oracle_id") or card.get("name", "")
        if oid:
            by_oracle[oid] = card
    # Overwrite / supplement with scryfall data (richer fields)
    for card in scryfall_cards:
        oid = card.get("oracle_id") or card.get("name", "")
        if oid:
            by_oracle[oid] = card
    return sorted(by_oracle.values(), key=lambda c: c.get("name", ""))


# ---------------------------------------------------------------------------
# Progress tracking (for resumable runs)
# ---------------------------------------------------------------------------


def load_progress(path: str) -> set[str]:
    """Return the set of tag slugs already completed in a previous run."""
    try:
        with open(path, encoding="utf-8") as fh:
            return set(json.load(fh))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_progress(path: str, completed: set[str]) -> None:
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(sorted(completed), fh)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    output_path = Path(args.output)
    progress_path = args.resume or (str(output_path) + ".progress.json")

    # Load any existing progress so we can resume
    completed_slugs = load_progress(progress_path) if args.resume else set()
    if completed_slugs:
        logger.info("Resuming: %d tags already processed.", len(completed_slugs))

    # Initialise clients
    logger.info("Connecting to Scryfall Tagger…")
    try:
        tagger = TaggerClient()
    except Exception as exc:
        logger.error("Could not initialise Tagger client: %s", exc)
        return 1

    scryfall = ScryfallClient() if args.tag_source in ("scryfall", "both") else None

    # Discover all card tags
    all_tags = discover_all_card_tags(tagger, args.namespaces)
    if not all_tags:
        logger.error("No card tags discovered. Exiting.")
        return 1

    # Apply --max-tags limit
    if args.max_tags is not None:
        all_tags = all_tags[: args.max_tags]
        logger.info("Limited to first %d tags.", args.max_tags)

    total_tags = len(all_tags)
    processed = 0
    skipped = 0

    resuming = bool(completed_slugs)
    if resuming:
        logger.info("Appending to existing output file %s", output_path)

    start_time = time.time()

    with OutputWriter(output_path, append=resuming) as writer:
        for idx, tag in enumerate(all_tags, start=1):
            slug = tag.get("slug", "")
            name = tag.get("name", slug)
            namespace = tag.get("namespace", "")
            tagging_count = tag.get("taggingCount") or 0

            # Skip if already done in a previous run
            if slug in completed_slugs:
                logger.debug("[%d/%d] Skipping already-processed tag '%s'", idx, total_tags, slug)
                skipped += 1
                continue

            # Skip if below --min-cards threshold
            if tagging_count < args.min_cards:
                logger.debug(
                    "[%d/%d] Skipping tag '%s' (%d cards < min %d)",
                    idx,
                    total_tags,
                    slug,
                    tagging_count,
                    args.min_cards,
                )
                skipped += 1
                continue

            logger.info(
                "[%d/%d] Processing tag: %s/%s  (%d cards)",
                idx,
                total_tags,
                namespace,
                slug,
                tagging_count,
            )

            # Fetch card list
            tagger_cards: list[dict[str, Any]] = []
            scryfall_cards: list[dict[str, Any]] = []

            if args.tag_source in ("tagger", "both"):
                tagger_cards = fetch_cards_from_tagger(tagger, slug, tagging_count)
                logger.debug("  Tagger returned %d cards", len(tagger_cards))

            if args.tag_source in ("scryfall", "both") and scryfall:
                scryfall_cards = fetch_cards_from_scryfall(scryfall, slug)
                logger.debug("  Scryfall returned %d cards", len(scryfall_cards))

            if args.tag_source == "tagger":
                cards = tagger_cards
            elif args.tag_source == "scryfall":
                cards = scryfall_cards
            else:
                cards = merge_card_lists(tagger_cards, scryfall_cards)

            if not cards and args.min_cards > 0:
                logger.debug("  No cards found for tag '%s', skipping.", slug)
                skipped += 1
                completed_slugs.add(slug)
                save_progress(progress_path, completed_slugs)
                continue

            # Enrich tag dict with description if available from GraphQL
            try:
                tag_detail = tagger.fetch_tag_page(slug, page=1)
                tag["description"] = tag_detail.get("description") or ""
            except Exception:
                tag["description"] = ""

            # Write to output
            writer.write_tag_block(tag, cards)
            processed += 1
            completed_slugs.add(slug)
            save_progress(progress_path, completed_slugs)

            # Periodic ETA estimate
            if processed % 10 == 0:
                elapsed = time.time() - start_time
                rate = processed / elapsed if elapsed > 0 else 0
                remaining = total_tags - idx
                eta_s = remaining / rate if rate > 0 else 0
                logger.info(
                    "Progress: %d/%d tags done  |  %.1f tags/min  |  ETA ~%.0f min",
                    processed,
                    total_tags,
                    rate * 60,
                    eta_s / 60,
                )

    logger.info(
        "Done. %d tags written, %d skipped. Output: %s",
        processed,
        skipped,
        output_path,
    )

    # Clean up progress file on successful completion
    if processed > 0:
        try:
            Path(progress_path).unlink(missing_ok=True)
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
