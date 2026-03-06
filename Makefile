.PHONY: build install dev clean run help

PYTHON   := python3
VENV     := .venv
BIN      := dist/scroll-tagger

# ── Build a standalone executable (no Python installation needed to run) ──────
build:
	@echo "→ Building standalone executable with PyInstaller…"
	pyinstaller scroll_tagger.spec --noconfirm
	@echo ""
	@echo "✓ Executable ready: $(BIN)"
	@echo "  Run: ./$(BIN) --help"

# ── Install the CLI into the current Python environment ──────────────────────
install:
	@echo "→ Installing scroll-tagger into the current Python environment…"
	$(PYTHON) -m pip install --quiet -e .
	@echo "✓ Installed. Run: scroll-tagger --help"

# ── Set up a development virtual environment ─────────────────────────────────
dev:
	@echo "→ Creating virtual environment at $(VENV)…"
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --quiet --upgrade pip
	$(VENV)/bin/pip install --quiet -r requirements.txt pyinstaller
	@echo "✓ Dev environment ready."
	@echo "  Activate with: source $(VENV)/bin/activate"

# ── Run directly via the package (no install needed) ─────────────────────────
run:
	$(PYTHON) -m scroll_tagger $(ARGS)

# ── Quick test run (first 5 tags, verbose) ────────────────────────────────────
test-run:
	$(PYTHON) -m scroll_tagger --max-tags 5 --log-level DEBUG -o test_output.txt

# ── Clean build artifacts ─────────────────────────────────────────────────────
clean:
	rm -rf build/ dist/ __pycache__ scroll_tagger/__pycache__
	rm -rf *.egg-info scroll_tagger.egg-info
	rm -f *.progress.json test_output.txt

# ── Help ──────────────────────────────────────────────────────────────────────
help:
	@echo "scroll-tagger build targets:"
	@echo ""
	@echo "  make build      Build a standalone binary  →  dist/scroll-tagger"
	@echo "  make install    Install CLI via pip (editable)"
	@echo "  make dev        Create a local virtual environment"
	@echo "  make run        Run via Python module  (pass ARGS='--help' etc.)"
	@echo "  make test-run   Quick smoke-test (first 5 tags)"
	@echo "  make clean      Remove build artefacts"
	@echo ""
	@echo "Examples:"
	@echo "  ./dist/scroll-tagger --help"
	@echo "  ./dist/scroll-tagger -o card_tags.txt"
	@echo "  ./dist/scroll-tagger --namespace ability --min-cards 10"
	@echo "  make run ARGS='--max-tags 20 -o sample.txt'"
