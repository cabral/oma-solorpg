# oma-solorpg: the commands, one make target each. `make` alone lists them.
#
# Your books, the packs built from them and your campaigns live in SOLO_HOME
# (~/Games/solo), never in this folder. Nothing here writes into the repository.

SHELL      := /bin/sh
SOLO_BIN   := $(CURDIR)/bin/solo
ASK        := $(CURDIR)/bin/ask-agent
SOLO_HOME  ?= $(HOME)/Games/solo
export SOLO_HOME

PLUGIN     := cabral.oma-solorpg
SYSTEMS    := $(SOLO_HOME)/systems
SOURCES    := $(SOLO_HOME)/sources
ADVENTURES := $(SOLO_HOME)/adventures
# Dragonbane's rules in two layers over the names this repository ships: the rulebook, and
# on top the pack campaigns use, which holds the solo rules when you have that book.
RULEBOOK   := $(SYSTEMS)/dragonbane-rulebook
TOP        := $(SYSTEMS)/dragonbane
SOLO_TASK    = The solo rules are extracted in $(SOURCES)/dragonbane-solo and go into $(TOP) (it extends dragonbane-rulebook), whose inventory is started too.
NO_SOLO_TASK = I have no solo rules book: leave $(TOP) as it is.

.PHONY: help install deps rules check adventure check-adventure test qml-check site

help:
	@echo "oma-solorpg"
	@echo ""
	@echo "  make install                         link solo, the GM skills and the Omarchy plugin; enable the plugin"
	@echo "  make rules BOOK=<pdf> [SOLO_BOOK=<pdf>]  build Dragonbane's rules from your rulebook (and the solo rules booklet)"
	@echo "  make check                           validate the rules you built and audit them against the books"
	@echo "  make adventure ID=<id> PDF=<pdf>     start an adventure pack from a PDF you own"
	@echo "  make adventure ID=<id> FOUNDRY=<dir> start one from a Foundry VTT export"
	@echo "  make check-adventure ID=<id>         validate an adventure, show its outline, audit it"
	@echo "  make test                            the engine's tests"
	@echo "  make qml-check                       load the plugin's QML offscreen (needs PySide6)"
	@echo "  make site                            serve the website (site/) on http://localhost:8000"
	@echo ""
	@echo "  AGENT=claude|codex picks the agent that does the reading (default: Omarchy's default agent)."
	@echo "  SOLO_HOME=$(SOLO_HOME)"

install:
	$(SOLO_BIN) setup --plugin
	@if command -v omarchy >/dev/null 2>&1; then omarchy plugin enable $(PLUGIN); \
	else echo "Enable the plugin with: omarchy plugin enable $(PLUGIN)"; fi

# PyMuPDF reads the PDFs. Only the import commands need it.
deps:
	@python3 -c "import pymupdf" 2>/dev/null || { \
	  echo "solo extract needs PyMuPDF: uv pip install --system pymupdf"; exit 1; }

# 1. The books as text, page by page (once: a second run keeps what is there).
# 2. The two packs, each saying what it is laid over.
# 3. A first inventory per book: an item per section and table, every page cited.
# 4. Your agent reads the books and fills the packs, with the solo-rules-import skill.
rules: deps
	@test -n "$(BOOK)" || { echo "usage: make rules BOOK=~/Books/<rulebook>.pdf [SOLO_BOOK=~/Books/<solo rules>.pdf]"; exit 2; }
	@test -f "$(SOURCES)/dragonbane-rulebook/manifest.json" || $(SOLO_BIN) extract "$(BOOK)" --out "$(SOURCES)/dragonbane-rulebook"
	@mkdir -p "$(RULEBOOK)" "$(TOP)"
	@test -f "$(RULEBOOK)/system.toml" || echo 'extends = "bundled:dragonbane"' > "$(RULEBOOK)/system.toml"
	@test -f "$(TOP)/system.toml" || echo 'extends = "dragonbane-rulebook"' > "$(TOP)/system.toml"
	@grep -q 'dragonbane-rulebook' "$(TOP)/system.toml" || { \
	  echo "$(TOP)/system.toml doesn't extend dragonbane-rulebook: an older pack is there. Move it aside and run make rules again."; exit 1; }
	@test -f "$(RULEBOOK)/inventory.toml" || $(SOLO_BIN) inventory "$(RULEBOOK)" --extract "$(SOURCES)/dragonbane-rulebook"
	@if [ -n "$(SOLO_BOOK)" ]; then \
	  test -f "$(SOURCES)/dragonbane-solo/manifest.json" || $(SOLO_BIN) extract "$(SOLO_BOOK)" --out "$(SOURCES)/dragonbane-solo"; \
	  test -f "$(TOP)/inventory.toml" || $(SOLO_BIN) inventory "$(TOP)" --extract "$(SOURCES)/dragonbane-solo"; \
	fi
	@$(ASK) "$(SOLO_HOME)" "Use the solo-rules-import skill to build Dragonbane's rules from my books. The repository is $(CURDIR): read docs/INGESTION.md and docs/PACK_FORMAT.md there first. The rulebook is extracted in $(SOURCES)/dragonbane-rulebook and goes into $(RULEBOOK), whose inventory is started. $(if $(SOLO_BOOK),$(SOLO_TASK),$(NO_SOLO_TASK)) The bundled pack holds only names: every key it lists under needs must come from the rulebook. Work a chapter at a time, and run make check in the repository until it passes."

# Each book's pack against its inventory and its pages, then the whole against what a
# campaign needs.
check:
	@for pack in "$(RULEBOOK)" "$(TOP)"; do \
	  if [ -f "$$pack/inventory.toml" ]; then $(SOLO_BIN) audit --system "$$pack" || exit 1; fi; \
	done
	$(SOLO_BIN) validate --system dragonbane

adventure:
	@test -n "$(ID)" || { echo "usage: make adventure ID=<id> PDF=<pdf>   or   make adventure ID=<id> FOUNDRY=<export files or folder>"; exit 2; }
	@test -n "$(PDF)$(FOUNDRY)" || { echo "give the adventure: PDF=<pdf> or FOUNDRY=<export files or folder>"; exit 2; }
	@mkdir -p "$(ADVENTURES)/$(ID)"
ifneq ($(FOUNDRY),)
	$(SOLO_BIN) import foundry adventure $(FOUNDRY) --out "$(ADVENTURES)/$(ID)"
	@$(ASK) "$(SOLO_HOME)" "Use the solo-import skill to enrich the adventure pack in $(ADVENTURES)/$(ID), imported from a Foundry export: factions, clocks, gates, branches, NPC profiles, voices. The repository is $(CURDIR): read docs/INGESTION.md and docs/PACK_FORMAT.md there first. Run make check-adventure ID=$(ID) in the repository until it is clean, then walk me through what you inferred."
else
	@$(MAKE) --no-print-directory deps
	@test -f "$(SOURCES)/$(ID)/manifest.json" || $(SOLO_BIN) extract "$(PDF)" --out "$(SOURCES)/$(ID)"
	@test -f "$(ADVENTURES)/$(ID)/inventory.toml" || $(SOLO_BIN) inventory "$(ADVENTURES)/$(ID)" --extract "$(SOURCES)/$(ID)"
	@$(ASK) "$(SOLO_HOME)" "Use the solo-import skill to build the adventure pack in $(ADVENTURES)/$(ID) from the PDF extracted in $(SOURCES)/$(ID), whose inventory is started. Give adventure.toml a system (dragonbane) and a summary so it shows on the New adventure screen. The repository is $(CURDIR): read docs/INGESTION.md and docs/PACK_FORMAT.md there first. Run make check-adventure ID=$(ID) in the repository until it is clean, then walk me through what you inferred."
endif

check-adventure:
	@test -n "$(ID)" || { echo "usage: make check-adventure ID=<id>"; exit 2; }
	$(SOLO_BIN) validate --adventure "$(ID)"
	$(SOLO_BIN) outline --adventure "$(ID)"
	@if [ -f "$(ADVENTURES)/$(ID)/inventory.toml" ]; then $(SOLO_BIN) audit --adventure "$(ID)"; fi

test:
	python3 -m unittest discover -s tests

qml-check:
	QT_QPA_PLATFORM=offscreen python3 tests/qml/panel_check.py $${TMPDIR:-/tmp}/oma-solorpg-qml

# The website, as GitHub Pages serves it (.github/workflows/pages.yml publishes site/).
site:
	python3 -m http.server 8000 --directory site
