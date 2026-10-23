# Ingestion, next: tables and maps read by a layout model

A plan for the next version of `solo extract` and the importers that read what it writes. Today the extract is PyMuPDF's text plus heuristics of this project's own (reading order by bands and columns, running heads by repetition, tables by ruled lines or by roll-line patterns, a grid read by the gaps between words, a map read by the colour of its labels). Each heuristic was written for one book and tuned on it, and [INGESTION.md](INGESTION.md) lists what each one missed. This plan puts a document layout model under the extract, so that tables come out as cells and maps come out as pictures with their labels, and keeps everything the extract writes today, so that nothing written for the current extract or for pack format 1 changes.

Contents: [What goes wrong today](#what-goes-wrong-today) · [The field in 2026](#the-field-in-2026) · [The choice](#the-choice) · [The design](#the-design) · [What stays the same](#what-stays-the-same) · [Steps](#steps) · [Risks](#risks)

## What goes wrong today

Everything below is from a real import, and is in [INGESTION.md](INGESTION.md) at more length.

- Tables. `solo extract` finds only ruled tables (PyMuPDF's `find_tables`), and marks a page as a roll table when four lines start with a number. The Markdown it writes loses ligatures and scrambles columns, so the importers read tables a second time from the page's lines by geometry: `solo/books/grid.py` cuts cells where words have a gap of five points and tells a header by a size under 8.6 points, `solo/books/dice.py` finds rows by the next number of the die. Both are tuned to one book's typefaces. Tables of six side-by-side columns (random NPCs, quests, journeys, sites) came out wrong as text and were read from the page's picture by the agent, a column at a time. A table that continues on the next page, or that sits in two halves side by side, is a special case each.
- Maps. An adventure's map is a picture, and the importer says so in its notes: "the book's maps are pictures, so the importer can't tell where a way really goes". The ways it reads come from the map's labels only where they are text in the PDF, told from the rest of the page by being white (`adventure.py`, `_WHITE`). A map whose labels are drawn, a map with a legend, a scale or a number keyed to a list, gives the importer nothing, and the exits of a place no bullet names are linked "from the place before it in the book, and back".
- Pictures with words. A card's name and value are art; the agent reads the card's picture and writes `picture/<page>.txt` by hand, and the extract gives it a whole page to look at, not the card.
- The page itself. Running heads are found by repetition at the page's edges, and a spell's "Rank: 1" was taken for one until the rule was tightened. A table of contents without bookmarks is guessed from font sizes. A sidebar on a two-column page lands in the middle of a sentence. A drop cap set as a drawing is guessed from the book's vocabulary. Each has a fix, and each fix is a rule about one book.

What is right today, and must stay: the text is the PDF's own characters, so the audit can read every table result, stat and price back against the page word for word; every number in a pack cites a page; nothing of a book is in the repository; and the importers run with the standard library on files the extract wrote, so their tests run on a made-up book.

## The field in 2026

Document parsing has moved to models that read a page as a picture and write it out as Markdown or HTML, and to pipelines of smaller models (layout detection, table structure, OCR) joined by code. The benchmark the field reports on is OmniDocBench, whose v1.6 (2026-04) scores text (edit distance), tables (TEDS, a tree similarity of the cells) and formulas on a thousand pages of books, papers, slides, newspapers and notes, a good part of them scans and photographs. The numbers below are from its leaderboard and the projects' own pages, read on 2026-10-23.

| Project | What it is | License | Runs on | Text of a born-digital PDF | OmniDocBench v1.6 overall / table TEDS |
|---|---|---|---|---|---|
| PaddleOCR-VL 1.6 | A 0.9B vision model for whole pages, under PaddlePaddle | Apache 2.0 | GPU (CPU not a supported path) | Read off the pixels again | 96.3 / 94.8 |
| MinerU 4.0 (2026-09) | Pipeline of small models (PP-DocLayoutV2, table models, OCR) with a VLM for the harder tiers | Apache 2.0 with conditions (attribution in any online service, a commercial licence over a size) | CPU for the `basic` tier (ONNX), GPU or Vulkan for `standard` and above | The `flash` tier reads the text layer; the VLM tiers read pixels | 95.8 (2.5-Pro) / 93.4; the pipeline alone 86.5 / 81.9 |
| GLM-OCR | A 0.9B vision model | MIT (layout part Apache 2.0) | GPU | Pixels | 95.2 / 92.8 |
| Docling 2.x (IBM) | Pipeline: a PDF parser for the text layer, a layout detector (RT-DETR, "heron"), TableFormer for cells, a figure classifier, a hook for a picture-describing VLM, and an optional whole-page VLM (granite-docling, 258M) | MIT | CPU (about 1 to 2 s a page in its report; a table 2 to 6 s more), GPU optional | The text layer; TableFormer's cells are matched back onto the PDF's own text | Not on the board; granite-docling reports 0.97 structure TEDS on FinTabNet |
| Marker / Chandra (Datalab) | Marker is a pipeline; Chandra a VLM | GPL (Marker), OpenRAIL-M with restrictions (Chandra) | GPU for Chandra | Marker: text layer; Chandra: pixels | Marker 78.4 / 65.8; Chandra isn't on the board (83.1 on olmOCR-bench) |
| dots.ocr, olmOCR 2, DeepSeek-OCR 2 | Vision models | MIT, Apache 2.0, MIT | GPU | Pixels | 90.8, 85.7, 90.3 overall |

Two things the numbers hide. The models at the top read every page as pixels, and win because the benchmark is half scans and photographs: on a born-digital page the PDF's text layer is already exact, and any model that reads it again can only add mistakes (a ligature, a soft hyphen, a 1 for an l), which is what our audit exists to catch. And the models at the top want a GPU and a framework install (PaddlePaddle, vLLM) that an Omarchy desktop doesn't have; the pack has to build on the machine of whoever owns the book.

Sources: [OmniDocBench](https://github.com/opendatalab/OmniDocBench), [MinerU](https://github.com/opendatalab/MinerU) and its [licence](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md), [PaddleOCR-VL-1.6](https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.6), [Docling](https://github.com/docling-project/docling), the [Docling technical report](https://arxiv.org/abs/2408.09869), [granite-docling-258M](https://huggingface.co/ibm-granite/granite-docling-258M), [DocumentFigureClassifier](https://huggingface.co/ds4sd/DocumentFigureClassifier), [olmOCR-bench](https://github.com/allenai/olmocr).

## The choice

Docling, as a structure layer under the extract, with the text left as PyMuPDF reads it. Structure from the model, characters from the PDF.

Why this one:

- It reads a born-digital PDF the way the audit needs: its parser takes the text layer, the layout model decides which cells are a table, a picture, a caption, a heading, a running head or a footnote, and TableFormer predicts the cells of a table and matches them back onto the PDF's own text. No character is re-read. The audit's page check keeps working unchanged.
- It runs where the books are: pip-installable, CPU, offline after the first download of its models (a few hundred megabytes), MIT. A rulebook of 116 pages with a hundred tables is a quarter of an hour on a laptop, once.
- It writes what the importers lack: a table as rows, columns and spans (so the six-column tables, the two halves side by side and the table that goes on to the next page are one case: cells); a picture as a crop with its bounding box and caption, classified, with `map` among its sixteen classes; running heads and footers as labelled regions instead of a repetition count; headings by level for a book without bookmarks.
- It has the hook for the one thing no layout model does, reading words that are pixels (a card's value, a drawn map's labels): a picture-description step that can call a local model or any OpenAI-compatible endpoint, with a prompt of ours.

What it doesn't do, and what this plan does instead: it drops the text inside a picture (a map's "To #3" labels), so the extract keeps those from PyMuPDF's layer and ties them to the picture by its box; it has no score on OmniDocBench, so step 1 measures it on the maintainer's own books before anything is built on it; and it can't read a scan better than the models above, so the structure it writes is one JSON schema that another reader (MinerU's `basic` tier, a VLM) could fill for a scanned book later, without the importers changing. That is a property of the design, not a second plan.

## The design

The extract gains a structure layer and keeps every file it writes today. After `solo extract <pdf>`:

```
manifest.json        as now, plus: structure (the reader and its version, or null), figures, readings
toc.json             as now; when the PDF has no bookmarks, from the layout model's headings (toc_from = "layout")
book.md, pages/, chapters/, layout/, outline.json     exactly as now
structure/0042.json  the page's regions: [{kind, bbox, lines, caption, ref}]
tables/p0042-1.md    as now, and beside it
tables/p0042-1.cells.json   the table as cells: {page, bbox, rows, cols, header_rows, cells: [{r, c, rs, cs, text, bbox, header}]}
tables/index.json    as now, with "cells" naming the cells file and "columns" the count
figures/p0042-1.png  one picture, cropped at 200 dpi, and figures/index.json: [{page, n, kind: map | illustration | chart | ..., bbox, caption, labels, file}]
picture/p0042-1.json what a reader (an agent, or a model `--read-pictures` was given) read off that picture: for a map, its places and ways; for a card, its lines
picture/0042.txt     as now: a page read by an agent, which the audit still reads
```

The pieces, and where each lives:

- `solo/structure.py`: the one module that imports Docling. `solo extract` runs it as a subprocess in the ingest environment (below) and reads back the JSON it writes; the engine itself still imports the standard library and PyMuPDF only. It converts the page with `do_table_structure` (TableFormer in accurate mode, cells matched to the PDF's text), `do_picture_classification`, `generate_picture_images` at scale 2.8 (200 dpi), and writes `structure/`, the cells files and `figures/`. Docling's boxes have their origin at the bottom left; they are turned into PyMuPDF's (top left, points) on the way out, so every file in the extract shares one coordinate system. A region's `lines` are the indices of the lines of `layout/0042.json` whose boxes it covers, so an importer never has to intersect boxes itself.
- Without Docling, the extract is exactly today's: `manifest.structure` is null, and the line the command prints says how to add it. An extract made before this plan loads as it always did (`Book()` checks `layout`, and will check `structure` only where a reader asks for it).
- The ingest environment: `make ingest-deps` makes a virtual environment with `uv` (`~/.local/share/solo/ingest`), installs Docling with CPU PyTorch, and fetches the models once. Arch's Python is externally managed, so nothing goes into the system Python; PyMuPDF keeps coming from pacman as the README says. `solo setup` reports it on its check line like PyMuPDF.
- Tables. `solo import table` reads a cells file as a third input beside Markdown and roll lines, and a cells file is what the extract points the agent and the recipes at first. A roll table is a two-column cells file whose first column is the die; a table of several dice side by side is one cells file whose columns each start with a die, and `solo import table --columns` writes one table per column chained with `then`, which the agent did by hand from the picture. `solo/books/grid.py` and `dice.py` take cells when the section has them and fall back to the line geometry they use now, so a recipe doesn't change; the Dragonbane recipes are the regression test that both readings agree.
- Figures and maps. `figures/index.json` lists every picture the layout model found with its class and caption, and for each the `labels`: the lines of the text layer inside its box, with their positions (the "To #3" and "(hidden)" that `adventure.py` reads today by colour). `_map_ways` reads the labels of the map figures of a place first, and the white lines of the page only when a place has no figure. A map whose labels are drawn has none: the figure is listed with `labels = []`, which is the signal for a reading.
- Readings. A reading is what something that can see wrote about a picture, in `picture/p0042-1.json`: for a map, `{kind: "map", places: [{key, name}], ways: [{from, to, hidden, locked, label}], legend, notes}`; for a card or a page of art, `{kind: "text", lines: [...]}`. The agent writes them with the skills (it opens the crop, not the page, and the schema is in the skill); `solo extract --read-pictures <url>` writes them without an agent through Docling's picture-description step pointed at an OpenAI-compatible endpoint (a local Ollama with a small vision model, or whatever the player runs), with one prompt per figure class, and `manifest.readings` names the model. The audit reads a map reading's places and ways as it reads `picture/<page>.txt` today, and says which pages the pack was checked against a reading of rather than the PDF's text.
- The page. `solo/sections.py` gives each line an owner by region where there is one: a line inside a table region is the table's, inside a picture the picture's, inside a region labelled `page_header` or `page_footer` a running head's, so the sidebar that landed in the middle of a sentence and the "Rank: 1" taken for a running head are decided by the layout model instead of by a count. `strip_running` keeps its repetition test as the check on the model: where the two disagree, the manifest says so under `running_disagreed`, and the first imports will say which to trust. `toc.json` falls back to the model's `section_header` regions, ranked by size, when the PDF has no bookmarks.

## What stays the same

- Pack format 1 is not touched. No key is renamed or given another meaning, so `packs.FORMAT` stays 1 and `packs.UPGRADES` stays empty. What the plan adds to a pack is optional and nothing older packs use: `map` as an inventory `kind` (for the map a reading came from), and `page` on a table result is already there. A pack written today validates, audits and plays unchanged, and a pack built by the new extract is read by today's engine.
- The extract folder keeps every file it writes now, with the same names and contents: `pages/`, `chapters/`, `book.md`, `layout/`, `outline.json`, `toc.json`, `tables/*.md`, `tables/index.json`, `manifest.json`'s keys, `picture/<page>.txt`. An agent, a recipe or a test written against today's extract reads tomorrow's.
- The recipes' contract: `Book`, `Section.lines()` and `text()`, `grid.read`, `dice.read` keep their signatures; cells are an extra input, never a required one, and `tests/fake_book.py` builds a book with or without them.
- The audit's page check: the pack is read back against `pages/*.txt`, which are still PyMuPDF's characters.
- The one rule: nothing of a book in the repository. The fixtures for the new readers are made from `tests/fake_book.py`'s invented text, and the measurements of step 1 stay in the maintainer's notes.

## Steps

Each step ships on its own, with the tests that go with it, and `make test` stays green with Docling absent (the tests that need it skip, as the PyMuPDF ones do).

1. The structure layer, and a measurement. `solo/structure.py`, the `structure/` schema, `make ingest-deps`, `manifest.structure`, the subprocess in `solo extract`, and a `--no-structure` flag. Done when, on the maintainer's books, a script in the extract folder counts: tables the layout model found against the tables the inventories list, pages whose regions disagree with `strip_running`, pictures found and how many are classed `map`, seconds a page. Those numbers decide the rest; the plan expects most of the inventories' tables found and the maps of the two adventure books classed as maps.
2. Tables as cells. The cells files, `tables/index.json`'s new keys, `solo import table` reading cells and `--columns`, `grid.read` and `dice.read` taking cells. Done when `make dragonbane` builds the same packs it builds today from the same books (`solo compare` shows no difference), the six-column tables of the rulebook import from their cells with one command each, and `tests/fake_book.py` has a cells table that `test_books.py` reads both ways.
3. Figures and maps. `figures/` with classes, captions and text-layer labels; `_map_ways` from figures; the `map` inventory kind. Done when the two adventure importers link the ways their maps label without the colour test, and the build's notes no longer say the map is a picture it can't read for a place whose map has text labels.
4. Readings. The `picture/*.json` schema, the audit reading it, the skills telling the agent to read a crop and write one, and `solo extract --read-pictures`. Done when a card deck's values come from readings of the card crops (today twelve of forty treasure cards needed the agent's eyes), a map with drawn labels gives an adventure its exits from a reading, and the audit names the pages that stand on a reading.
5. The page. Regions owning lines in `sections.py`, running heads cross-checked, `toc.json` from headings. Done when the manifest of each of the maintainer's books lists no disagreement that the book settles against the model, the sentence a sidebar cut no longer starts in lowercase in the generated pages, and a PDF without bookmarks gets a contents list that matches its printed one.
6. Writing it down. [INGESTION.md](INGESTION.md)'s process and lessons, [PACK_FORMAT.md](PACK_FORMAT.md)'s "Extracted books" tree and the `map` kind, the README's Troubleshooting (the ingest environment beside PyMuPDF), `make help`, CHANGELOG, and the two import skills. A line in CI that installs Docling in a cached environment for the extract tests, if its models stay under the runner's time; else those tests stay skipped there and run on the maintainer's machine before a release.

## Risks

- The layout model misreads a page the heuristics got right. The measurement in step 1 is for this, and every step keeps the old reading as the fallback and the Dragonbane recipes as a regression test, so the model has to earn each heuristic it replaces.
- The install. PyTorch on CPU is a few hundred megabytes, the models a few hundred more, and a first run downloads them. The ingest environment is one `make` target, outside the system Python, and the extract works without it; the line it prints when it is missing must be as plain as the PyMuPDF one.
- Readings are a model's eyes, not the book's text. The audit already says which pages were checked against a reading; a map reading adds places and ways the user should look at once on the crop, and the skills say so.
- Docling moves (its layout models have changed twice in a year). `solo/structure.py` pins a version and the ingest environment installs that one; the structure schema is this project's, so a change in Docling is a change in one module.
