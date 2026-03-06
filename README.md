# Scroll-Tagger

A tool that extracts **Card Tags** from [Scryfall Tagger](https://tagger.scryfall.com), retrieves every Magic: The Gathering card assigned to each tag, and writes a structured text file ready for AI model training.

Artwork tags and Printing tags are automatically excluded — only functional **Card** tags are processed.

---

## How it works

1. **Tag discovery** – queries the Scryfall Tagger GraphQL API (`tagger.scryfall.com/graphql`) with pagination to collect every card-level tag (namespaces such as `ability`, `creature-type`, `mechanic`, `theme`, `spell-type`, etc.).
2. **Card retrieval** – for each tag, fetches the full card list using the official Scryfall REST API search syntax (`otag:<slug>`), which is stable and rate-limit friendly.
3. **Output** – writes a human-readable, AI-parseable text file where every tag block lists its metadata followed by each associated card's name, type, mana cost, oracle text, and rarity.

---

## Requirements

- Python 3.11+
- `requests`

```
pip install -r requirements.txt
```

---

## Quick start

```bash
# Full extraction (all card tags, cards via official Scryfall API)
python extract_tags.py -o card_tags_dataset.txt

# Test run: first 20 tags only
python extract_tags.py --max-tags 20 -o test_output.txt

# Only extract tags in the 'ability' and 'mechanic' namespaces
python extract_tags.py --namespace ability --namespace mechanic -o abilities.txt

# Skip tags with fewer than 5 cards
python extract_tags.py --min-cards 5

# Resume an interrupted run
python extract_tags.py --resume card_tags_dataset.txt.progress.json

# Verbose output
python extract_tags.py --log-level DEBUG
```

---

## Output format

```
# Scryfall Card Tags – AI Training Dataset
# Source: https://tagger.scryfall.com
# ...
================================================================================

### TAG: ability/flying
NAME: Flying
NAMESPACE: ability
DESCRIPTION: Cards with the Flying keyword ability.
TOTAL_CARDS: 1823

CARD: Aven Mindcensor
  TYPE: Creature — Bird Wizard
  MANA_COST: {2}{W}
  CMC: 3.0
  COLORS: W
  ORACLE_TEXT: Flash. Flying. If an opponent would search a library, that player searches the top four cards of that library instead.
  RARITY: uncommon

CARD: Birds of Paradise
  TYPE: Creature — Bird
  MANA_COST: {G}
  CMC: 1.0
  COLORS: G
  ORACLE_TEXT: Flying. {T}: Add one mana of any color.
  RARITY: rare

...

================================================================================

### TAG: creature-type/merfolk
...
```

---

## Options

| Option | Default | Description |
|---|---|---|
| `-o / --output` | `card_tags_dataset.txt` | Output file path |
| `--namespace` | *(all)* | Filter to one or more namespaces (repeatable) |
| `--min-cards` | `1` | Skip tags with fewer cards than this |
| `--max-tags` | *(all)* | Stop after N tags (for testing) |
| `--tag-source` | `scryfall` | Card source: `scryfall`, `tagger`, or `both` |
| `--resume` | *(none)* | Resume from a `.progress.json` file |
| `--log-level` | `INFO` | `DEBUG`, `INFO`, `WARNING`, or `ERROR` |

---

## Notes

- The Scryfall Tagger GraphQL API is **unofficial and undocumented**. Tag discovery may break if Scryfall changes the API.  Card retrieval via the official REST API (`--tag-source scryfall`) is stable.
- A CSRF token is obtained automatically by visiting the Tagger homepage; no login is required.
- Rate limiting is built in (≥ 0.5 s between Tagger requests, ≥ 0.1 s between Scryfall REST requests) to stay within polite usage limits.
- A `.progress.json` sidecar file is written alongside the output so long runs can be resumed after interruption.
- The output file uses UTF-8 encoding.

---

## Files

| File | Purpose |
|---|---|
| `extract_tags.py` | Main entry point and orchestration |
| `tagger_client.py` | Scryfall Tagger GraphQL client |
| `scryfall_client.py` | Official Scryfall REST API client (`otag:` search) |
| `output_writer.py` | Formats and streams data to the output text file |
| `requirements.txt` | Python dependencies |
