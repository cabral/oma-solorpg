---
name: solo-rules-import
description: Turn a tabletop RPG rulebook PDF the user owns (Dragonbane's core rules first, then Year Zero games or others) into a system pack the `solo` engine runs and the GM reads, verified page by page against the book. Use when the user wants to import, ingest or digest a rulebook, a bestiary, a spell book or a GM screen, build or correct a system pack from a book, add price lists, travel rules, monsters or tables from a book, or fix what `solo audit --system` reports.
---

# Importing a rulebook

You are compiling a book the user owns into data and pages. The engine runs the data (dice, rests, fights, tables, prices, monsters); the GM reads the pages (`solo rule <topic>`) for everything it rules on itself. Every number comes from a page of the book, and `solo audit` checks that it does.

Read `docs/INGESTION.md` (how books became packs before, and what went wrong) and `docs/PACK_FORMAT.md` (every key) before you start. The adventure side is the `solo-import` skill.

## Before you start: settle with the user

1. Which book, and where the PDF is. The PDF never goes through the chat.
2. Where the pack goes. For Dragonbane, `make rules` has set it up (see "Dragonbane: what the bundled pack leaves to the book" below): the rulebook goes in `~/Games/solo/systems/dragonbane-rulebook/`, laid over the bundled pack (`extends = "bundled:dragonbane"`), and `~/Games/solo/systems/dragonbane/` sits on top of it, the pack campaigns use, holding the solo rules when the user has that book. A game the repository doesn't have gets a full pack in `~/Games/solo/systems/<game>/`.
3. What may be committed to the repository: nothing from the book, ever. This repository is public, and the publisher's license lets it use the game's terms but not carry a copy of its rules. The book's text, tables and numbers stay in `~/Games/solo`.

## The pipeline

### 1. Extract

```bash
uv pip install --system pymupdf
solo extract ~/Books/<book>.pdf          # into ~/Games/solo/sources/<book>/
```

Check what it says and what it wrote:

- Pages that need OCR: run `ocrmypdf` on the PDF and extract again.
- `toc.json` from the PDF's outline, or guessed from font sizes (then check it against the contents page).
- `manifest.json`: `running` lists the headers and footers taken out of the text; `labels` maps PDF pages to printed ones (`labels_from` says whether from the PDF or its footers). Cite PDF pages everywhere; use `labels` to follow the book's own "see page 42".
- `chapters/` is what you read, a chapter at a time. `tables/` has each table found, as Markdown and as a picture of its page. When a table's columns come out scrambled, the picture is the truth.

### 2. Start the pack and its inventory

```bash
mkdir -p ~/Games/solo/systems/dragonbane-rulebook
echo 'extends = "bundled:dragonbane"' > ~/Games/solo/systems/dragonbane-rulebook/system.toml
solo inventory ~/Games/solo/systems/dragonbane-rulebook --extract ~/Games/solo/sources/<book>
```

`make rules BOOK=<pdf>` in the repository runs steps 1 and 2 (and the solo booklet's, with `SOLO_BOOK=<pdf>`), then opens your agent on the rest. Check what it left before you begin: `solo inventory` refuses a pack that already has an inventory, so a second run picks up where the first stopped.

`solo inventory` writes `inventory.toml` and a file per chapter under `inventory/`: an item per section and per table found, each `todo` with its pages and a guessed kind. Every page with text is cited from the start. Your job is to turn each chapter's items into what the book really holds (merge, split, rename, fix kinds), and give each a status: `mapped` with `to`, `engine`, `skipped` or `house`, each of the last three with a `note`.

### 3. Read and map, a chapter at a time

Read the chapter from `chapters/`, then its inventory file. For each item, decide where it goes (the table below) and write it there. Keep the book's wording for anything the GM reads; keep numbers exact.

On a long book, give each chapter to its own agent. Each writes only its own files: its `inventory/<chapter>.toml`, the tables, rules pages and bestiary entries it creates, and `drafts/<chapter>.toml` for anything that goes into the shared files (`system.toml`, `gear.toml`, `creation.toml`). You merge the drafts. Ids are shared across the whole pack; `solo audit` reports an item id used twice.

### 4. Tables

```bash
solo import table ~/Games/solo/sources/<book>/tables/p0045-1.md --out <pack>/tables/fear.toml --name "Fear" --pages 45
sed -n '12,20p' ~/Games/solo/sources/<book>/pages/0045.txt | solo import table - --out <pack>/tables/fear.toml --pages 45
```

It reads a Markdown grid or roll lines ("2-3 Shaken"), takes the dice from the header ("D6", "2D6", "D66") or the ranges, joins results that run onto a second line, and says when the ranges don't cover the dice. Check the result against the page's picture. Then add what the engine runs: `damage` (with `defend`, `parry`, `armor`) on a monster's attack results, `roll` for a value written as `{value}`, `choices`, `then` for a table rolled next. Never retype a table by hand when this can read it.

### 5. What the book holds, and where it goes

| The book has | Put it in |
|---|---|
| Attributes, skills and their attributes, conditions and what they bane, tracks (HP, WP) | `system.toml`: `[attributes]`, `[skills]`, `[conditions]`, `[tracks]` |
| Boons and banes, the base chance of an untrained skill | `system.toml`: `untrained`; the page in `rules/` |
| Time units (round, stretch, shift, day) | `system.toml`: `[time]` in seconds |
| Pushing a roll, rests and what they heal, dying and death rolls, advancement | `system.toml`: `[push]`, `[rest.<id>]`, `[dying]`, `[advancement]` |
| Initiative, damage bonus, what a Dragon or Demon does in a fight, unarmed attacks | `system.toml`: `[combat]` |
| Weapons (skill, damage, what can parry) and armor | `system.toml`: `[weapons.<id>]`, `[armor]`; their prices go in `gear.toml` under the same ids |
| Coins and what they're worth | `gear.toml`: `[money] coins = { gold = 100, silver = 10, copper = 1 }` (worth in the smallest coin), `aliases` for abbreviations |
| Price lists: gear, clothing, food and lodging, services, animals, transport | `gear.toml`: `[gear.<id>]` with `name`, `category` (the book's heading), `price` as written, and `weight`, `supply`, `note` when the book gives them |
| Character creation: kin, profession, age, names, starting gear | `creation.toml` (docs/PACK_FORMAT.md). Hero names can stay the bundled pack's: a kin option without `names` draws from `[names]` in the bundled `creation.toml` under its id |
| Heroic abilities, kin abilities | Data the engine runs where it can (`[abilities.<id>]`: initiative cards, paying for a push); otherwise a rules page and an `engine` item |
| Spells and magic schools, their costs | A rules page per school (the GM runs them); an `engine` item for casting and WP |
| Monsters with stat blocks and attack tables | `bestiary/<id>.toml` (`name`, `role`, `[stats]` hp, armor, ferocity, immune; `attacks = "<table>"` or `[attack]`) and `tables/<id>_attacks.toml` |
| Journeys and travel: distance per shift by terrain, getting lost, weather, camping, food and sleep | A rules page with every number the GM needs to turn a journey into game time, plus the tables (weather, mishaps, encounters); an `engine` item if the user wants travel rolled by the engine |
| Fear, poison, disease, cold, falling, drowning, fire | A rules page each, with the book's numbers; the GM applies them with `solo check` and `solo wound hero` |
| Random tables of any kind (encounters, treasure, mishaps) | `tables/<id>.toml`, exact |
| Game master advice | `skill:solo-gm` if it changes how the GM should run solo play (tell the user), else `skipped` |
| Setting, lore, maps, fiction | A rules page if the GM needs it in play (a village's inn, the calendar), else `skipped` with why |
| Credits, index, contents, adverts | `skipped` |

The bundled pack has no numbers at all: every number in your pack comes from a page, and every section the bundled pack lists under `needs` must be in it before a campaign can start.

### Dragonbane: what the bundled pack leaves to the book

The bundled `packs/dragonbane` holds only names: `[attributes]`, `[conditions]`, `[tracks]`, `[skills]` and hero names. The engine refuses to start a campaign until the packs over it hold every key in its `needs` list, so these come from the rulebook, into `dragonbane-rulebook`:

| Key | From the rulebook |
|---|---|
| `untrained` | the base chance of an untrained skill, by attribute |
| `[time]` | round, stretch, shift in seconds |
| `[push]` | `cost = "condition"` |
| `[rest.round]`, `[rest.stretch]`, `[rest.shift]` | what each recovers and heals, how long it takes, how often |
| `[light.torch]` | how long a torch burns (optional, but the Book shows it) |
| `[dying]` | the death roll's attribute, successes and failures, what a rally restores |
| `[advancement]` | what marks a skill, the roll, the cap |
| `[combat]`, `[combat.damage_bonus]` | initiative cards, a Dragon on an attack, the evade skill, unarmed attacks, whether monster attacks can be parried, damage bonus by attribute |
| `[weapons.<id>]`, `[armor]` | every weapon's skill, damage, bonus attribute and whether it parries; armor and helmet ratings |
| `creation.toml` | the kin, profession (and its follow-ups), age tables, attributes roll and range, the key attribute swap, trained skills, `tracks`, `[ratings.*]` |

And from the solo rules, when the user has them, into the top `dragonbane` pack (each is optional; without them the engine's own likelihood oracle and random events run solo play):

| Key | From the solo rules |
|---|---|
| `[oracle]`, `[oracle.fortune]` | `chart = "fortune"`, `scene_checks = false`, the chart's `bands` and one list per column, `inspiration` naming its word tables |
| `[effects]` | the tables a Dragon or a Demon rolls outside a fight |
| `[threats]` | the counter's size, start, what advances it, the random threat table |
| `[search]`, `[scavenge]` | skill, table and time |
| `[npcs]`, `[npcs.templates.<id>]` | the NPC attack table and its role columns, the simple NPC templates |
| `[abilities.<id>]` | the lone hero's abilities the engine runs (`initiative`, `push`) |
| `creation.toml` `extra_abilities` | the extra heroic ability a lone hero starts with |
| `[rest.stretch] tend`, `[dying] self_rally`, `self_save` | healing alone and rallying alone |
| `tables/` | every table those name, and the booklet's others (harm, traps, areas, locations), exact |

A deck of cards that comes in the box (treasure cards) isn't in a PDF: type it into `tables/` only if the user hands you the cards' text, and mark the item `house` with where it came from. `tests/fixtures/house` shows every one of these keys in use, with made-up values: read it for the shapes, never for the numbers.

### 6. Rules pages the GM can find

A rules page is `rules/<topic>.md`, one topic per page, titled with the book's heading. The line after the title lists the words a GM would look it up by:

```markdown
# Journeys
Search: travel, travel time, journey, distance, kilometers, getting lost, pathfinder

(the book's text for this topic, or your faithful summary with every number)
```

GMs search by what they need in the moment, not by the book's headings: "prices", "inn", "travel time", "how far", "fear", "poison", "bartering". Give every page the words of the questions it answers. The GM reads one page at a time, so split a long chapter into pages of one topic each. Pages built from the book's text stay in the private pack.

### 7. Check it

```bash
solo validate --system <pack>
solo audit --system <pack>
```

The audit fails until everything is accounted for, both ways:

- Every item is decided, and every `to` names something in the pack (or in the pack it extends).
- Everything the pack itself holds (each section of `system.toml`, `gear.toml` and `creation.toml`, each table, monster, character and rules page) is claimed by an item. A reference claims what it names and everything under it: `system.toml:weapons` claims every weapon.
- Every page of the book with text is cited by an item.
- What a mapped item points at is on its pages: every result of a table, word for word; every dice expression, stat and price in its data. A line under "Not on the cited pages" means the pack says something the book doesn't. Copy it from the page (or its picture) or cite the right pages. A difference on purpose is a `house` item with a note.

"By file" shows each chapter file's progress. "Needs engine work" is the list for the user.

### 8. Play on it

```bash
solo new red-tusk --dir /tmp/check        # a campaign on the new pack
solo -C /tmp/check rule prices            # and the other questions a GM asks: inn, travel time, fear, poison
solo -C /tmp/check rule bestiary
solo -C /tmp/check commit '{"npc": {"wolf_1": {"name": "Wolf", "monster": "wolf"}}}'
solo -C /tmp/check fight wolf_1
```

Every page should come up from a GM's words, and a monster should fight from its table. For the risky rules, write a scenario in `tests/gm_eval/scenarios/` and run it with a real GM (tests/gm_eval/README.md).

### 9. Walk the user through it

What you mapped, chapter by chapter, with its pages; everything `house`, `skipped` and `engine`, with why; and anything you weren't sure how to read. They own the book. Engine work is theirs to decide: don't build it unasked, and never stand in for a missing mechanic with data that only looks right.

## Never

- Write a number or a table result from memory. If a page can't be read, say so and mark the item.
- Paste the book into the chat, or put its text, tables or numbers anywhere in the repository. The repository is public.
- Map an item to something the book doesn't say, to make the audit pass.
