# Scroll-Tagger

A tool that extracts **Card Tags** from [Scryfall Tagger](https://tagger.scryfall.com), retrieves every Magic: The Gathering card assigned to each tag, and writes a structured text file ready for AI model training.

Artwork tags and Printing tags are automatically excluded — only functional **Card** tags are processed.

---

## Quickest start — pre-built executable

Download or build the standalone binary (no Python installation required):

```bash
# Build it yourself (see "Build" section below)
make build

# Then run it
./dist/scroll-tagger --help
./dist/scroll-tagger -o card_tags_dataset.txt
```

---

## Installation (Python package)

Requires **Python 3.11+**.

```bash
pip install -r requirements.txt
pip install -e .          # registers the 'scroll-tagger' CLI command
scroll-tagger --help
```

Or without installing:

```bash
pip install -r requirements.txt
python -m scroll_tagger --help
```

---

## Build a standalone executable

Produces a single self-contained binary at `dist/scroll-tagger` that runs on any compatible Linux x86-64 machine without a Python installation.

```bash
# Option 1: via Make
make build

# Option 2: directly
pip install pyinstaller
pyinstaller scroll_tagger.spec --noconfirm
```

---

## Usage

```bash
# Full extraction — all card tags, all cards
./dist/scroll-tagger -o card_tags_dataset.txt

# Quick test: first 20 tags only
./dist/scroll-tagger --max-tags 20 -o test_output.txt

# Filter to specific namespaces
./dist/scroll-tagger --namespace ability --namespace mechanic -o abilities.txt

# Skip tags with fewer than 5 cards
./dist/scroll-tagger --min-cards 5 -o card_tags_dataset.txt

# Resume an interrupted run
./dist/scroll-tagger --resume card_tags_dataset.txt.progress.json

# Verbose / debug output
./dist/scroll-tagger --log-level DEBUG -o card_tags_dataset.txt
```

Same flags work with `python -m scroll_tagger` or `scroll-tagger` (when installed via pip).

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

### `--tag-source` explained

| Value | Description |
|---|---|
| `scryfall` | Uses the official Scryfall REST API (`otag:` search). **Recommended** — stable, well-tested, rich card data. |
| `tagger` | Uses the Tagger GraphQL `taggings` field. Faster per tag but paginated and unofficial. |
| `both` | Fetches from both and merges results (Scryfall data takes precedence). |

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

================================================================================

### TAG: creature-type/merfolk
...
```

---

## Make targets

| Target | Description |
|---|---|
| `make build` | Build the standalone `dist/scroll-tagger` binary |
| `make install` | Install `scroll-tagger` CLI via pip (editable) |
| `make dev` | Create `.venv/` virtual environment with all dependencies |
| `make run ARGS='...'` | Run via `python -m scroll_tagger` with optional args |
| `make test-run` | Quick smoke-test: first 5 tags, debug logging |
| `make clean` | Remove build artefacts |

---

## How it works

1. **Tag discovery** — visits `tagger.scryfall.com`, extracts a CSRF token from the HTML `<meta>` tag, then queries the Tagger GraphQL API (`/graphql`) with pagination to collect every tag. Tags in `art`/`print`/`artwork`/`printing` namespaces are excluded automatically.

2. **Card retrieval** — for each card tag, queries the *official* Scryfall REST API using `otag:<slug>` search syntax, following pagination until all cards are collected.

3. **Output** — streams results to the output text file as they are fetched, with a `.progress.json` sidecar for resumable runs.

---

## Project structure

```
Scroll-Tagger/
├── scroll_tagger/           # Python package
│   ├── __init__.py
│   ├── __main__.py          # Entry point for python -m scroll_tagger
│   ├── extract_tags.py      # CLI orchestration
│   ├── tagger_client.py     # Scryfall Tagger GraphQL client
│   ├── scryfall_client.py   # Official Scryfall REST API client
│   └── output_writer.py     # Structured text file formatter
├── scroll_tagger.spec       # PyInstaller build spec
├── pyproject.toml           # Package metadata & console_scripts
├── Makefile                 # Build/install/run helpers
├── requirements.txt         # Runtime dependencies
└── README.md
```

---

## Notes

- The Scryfall Tagger GraphQL API is **unofficial and undocumented**. Tag discovery may break if Scryfall changes the API. Card retrieval via the official REST API (`--tag-source scryfall`, the default) is stable.
- No login is required. A CSRF token is obtained automatically by visiting the Tagger homepage.
- Rate limiting is built in (≥ 0.5 s between Tagger requests, ≥ 0.1 s between Scryfall REST requests) with exponential-backoff retries on failures.
- Output uses UTF-8 encoding.
- The standalone binary was built with **PyInstaller 6** and targets **Linux x86-64**. To build for other platforms, run `make build` on that platform.
