# Ingesting content

How books become packs the engine can run, what has been done so far, and what went wrong along the way. Written for the agent doing the next import. The formats are in [PACK_FORMAT.md](PACK_FORMAT.md); the step-by-step skills are `skills/solo-import` (adventures) and `skills/solo-rules-import` (rulebooks).

## What imports have taught the engine

Only The Red Tusk Hall ships here. Everything else below was imported from books the maintainer owns, into a private `~/Games/solo`, and each import left features in the engine that any book can use.

| Imported | What it forced into the engine |
|---|---|
| The Red Tusk Hall (original, `examples/red-tusk`) | The adventure format itself: scenes, clocks, branches, NPC profiles, voices |
| A tournament adventure with a real-time limit | Gated and timed exits, clock stages and `while`, round time, ferocity, immunity, monster parry/armor flags, `solo wound`, replacement heroes (`solo hero`), adventure `rules/` pages, `each_round` |
| A solo rules booklet | `[oracle]`, `[effects]`, `[threats]`, `[search]`, `[scavenge]`, `[npcs]`, `[abilities]`, `tend`, `self_rally`, `self_save`: a chart oracle, inspiration words, dragon/demon effects, threats, search and scavenge, simple NPCs with attacker roles, abilities for a lone hero, healing alone, ferocity as initiative cards |
| A solo campaign of missions from a hub | Missions in order, generated waypoints, adventure weapons, `defend resist`, safe scenes, kinds of foes |
| A deck of treasure cards | Dice multipliers (`2d6x10`) and self-resolving table results (`roll`, `choices`, `then`, `again`) |
| A core rulebook | Packs laid over packs, `gear.toml`, `bestiary/`, rules pages found by `Search:` words, running heads kept to the page edges, soft hyphens in the audit's page check, a guard against inventorying the extract itself |

## The process

1. Get the text. `solo extract <pdf>` writes it to `~/Games/solo/sources/<book>/`: a file per page, a file per chapter with its page range and size, `book.md` for grep, and every table as Markdown and as a picture of the page. Running heads and page numbers are taken out of the text (`manifest.json` lists them under `running`), and when the PDF has no page labels the printed numbers are read off the footers (`labels`, `labels_from`). It needs PyMuPDF (`uv pip install --system pymupdf`); nothing else in solo does. The PDF never has to go through a chat upload, whatever its size. If it says pages are scans, run `ocrmypdf` on the PDF and extract again. If the PDF has no bookmarks, `toc.json` is a guess from font sizes: check it against the contents page. Read a chapter at a time from `chapters/`; for a table, look at the page's picture in `tables/` when the text has scrambled its columns.
2. Read all of it before writing anything, and write the inventory as you go: `inventory.toml` in the pack (PACK_FORMAT.md), one item per mechanic, table, creature, place, set piece, clock-like thing and component, each with its pages and `status = "todo"`. Note what the book assumes about the table (a party, a GM, real time). Set `extract` to the extract folder so the audit checks pages. `solo inventory <pack> --extract <folder>` starts one: a file per chapter under `inventory/`, an item per section and table found, every page with text already cited. On a long book, one agent per chapter file refines its items; ids are shared, and the audit reports one used twice.
3. Map each thing to the engine (the table below) and record it on its item: `mapped` with `to`, `engine` with what the engine needs, `skipped` with why. What maps to nothing is engine work: note it, decide with the user, build it with tests, then use it.
4. Decide what belongs where. Rules of the game go in the system pack. Rules one adventure leans on go in the adventure's `rules/`. Components that the engine can simulate (a deck, a timer) become tables and clocks.
5. Write the pack. Tables come in with `solo import table` (from the extract's Markdown or a page's roll lines), never retyped. For many similar pieces (a few dozen waypoints), a throwaway script that renders the files from a data list saves time and mistakes; the files it writes are the source afterwards, and the script isn't kept.
6. `solo validate --adventure <pack>` until ok and nothing is worth a look; `solo outline --adventure <pack>` and check every gate, stage, branch and read fact against the book. `solo audit --adventure <pack>` (or `--system`) until everything is accounted for: no `todo`, no reference to something that isn't there, nothing in the pack that no item claims, no page with text that no item cites, and nothing a mapped item points at that isn't on its pages (table results, dice, stats, prices).
7. Fixed-dice tests of the routes that matter (see `tests/test_playtest.py`). Tests of a private pack stay private with it: this repository's tests run on made-up rules and its own adventures.
8. GM play tests (`tests/gm_eval`): scenarios for the risky parts and one long run with an agent player. Read the reports, fix the text or the engine, run again. Several rounds is normal.
9. Walk the user through every inference and translation with its page. Put the translations at the top of `adventure.toml` so they travel with the pack.

## Mapping a book to the engine

| The book says | Encode it as |
|---|---|
| A door, stair or passage that appears when something is done | A gated exit (`when = "fact.x.y"`), and the exact commit that sets the fact in the scene's GM text |
| After an hour, at midnight, on the third day | A clock advancing on `time:<unit>`, with a stage at that segment (text for the player, note for the GM, facts it sets) |
| Once it starts, every round X | A clock with `while` and `advance = ["time:round"]` |
| Every round in this place, the hero must X | `each_round` on the scene: it shows in every fight line there |
| Moving takes time; the tournament has a timer | `move_time`, and `time` on particular exits |
| Roll on this table | A table copied exactly; results that roll a value or pick a sub-option use `roll`/`choices`/`then` |
| A random treasure | `solo table treasure` (when the pack has the core set's deck) or `then = "treasure"` |
| A monster's stat block and attack table | `npcs/<id>.toml` with `[stats]` (hp, armor, ferocity, immune) and `attacks` naming its table; result flags `defend`, `parry`, `armor` |
| A creature named with no stats | `template` (minion, boss) and `attacker` (melee, ranged, sneaky, magic) |
| A person with skills who may fight beside the hero | `[attack]` and `[skills]` in the profile; `solo ally` runs them |
| A pregenerated character | `characters/<id>.toml` |
| If a character dies, the player takes over X | `characters/<id>.toml` with `replacement = true`; `solo hero <id>` |
| A relic weapon | `[weapons]` in `adventure.toml` |
| A rule the adventure relies on (fear, drowning, scoring) | `rules/<topic>.md` in the adventure, in your own words, marked as a stand-in if the book doesn't give it |
| Something the hero's skills might notice | A voice (`[[scenes.x.voices]]`), one or two per scene |
| Missions from a hub, in order | A hub scene with branches per mission, and gated exits into each mission's first scene on the previous mission's done fact |
| Places generated at the table | A placeholder scene whose GM text is the generation procedure (which tables to roll) |
| "The players", "a player character" | The hero; attacks on everyone nearby hit the hero |

## Rules and system packs

A rulebook is imported with the `solo-rules-import` skill, and `make rules` starts it. The pieces it stands on:

- The bundled `packs/dragonbane` holds only the game's names (attributes, conditions, tracks, skills, hero names) and a `needs` list. The engine won't start a campaign until the packs laid over it hold every key there.
- A pack from a book the player owns lives in `~/Games/solo/systems/`. For Dragonbane, `make rules` makes two: `dragonbane-rulebook` over the bundled names (`extends = "bundled:dragonbane"`), and `dragonbane` over that, the one campaigns use, which holds the solo rules when the player has that book. Each has its own inventory, so each audits against its own book.
- The data the engine runs goes in `system.toml`, `creation.toml` and the tables. Price lists and coins go in `gear.toml`; monsters in `bestiary/`, which every adventure's NPCs can be (`monster = "wolf"`) and the GM can bring into play by a commit.
- Everything the GM rules on itself (travel, fear, poison, spells, the book's own words on anything the engine runs) goes in rules pages, one topic each, with a `Search:` line of the words a GM will ask with. Play tests showed GMs asking `solo rule prices`, `bartering`, `inn`: they search by the question, not by the book's headings.
- A rule the engine runs should also be explainable: `packs.engine_rules` writes `solo rule` pages from the system pack's data (and the price pages and the bestiary), so the GM gets exactly what the engine does. Add a page there for each new data-driven mechanic. The book's own page of the same title replaces the engine's.
- A solo booklet maps cleanly because each of its rules is either a table (copied), a procedure with a roll and a table (search, scavenge), a counter (threats), a modifier on existing mechanics (more initiative cards, paying for a push, tending wounds at a rest), or advice for the GM (resolving failures, avoiding combat), which belongs in the GM skill.
- Nothing from a book is committed here, not its prose, tables or numbers. The tests use made-up rules (`tests/fixtures/house`) in the same shapes.

## Lessons learned

In the data and the engine:

- An agent transcribing a book writes plausible numbers when it half-remembers the game. Coverage can't see that; the audit now reads each mapped table, dice expression, stat and price back against the cited pages.
- Search by substring found "inn" in "beginning" and answered "prices" with nothing, because no page was titled so. Rules pages carry the words GMs ask with, and matching is by whole words.

- TOML reads `facts = { hall.flooded = true }` as a nested table. The engine flattens stage facts, but quoting the key (`"hall.flooded" = true`) is safer anywhere else.
- Names collide. NPC profiles already had `role` (a description), so the NPC attack role became `attacker`. Grep for a key before giving it a new meaning.
- A GM writes `{"hp": -1}` meaning a loss. A number sets a value, so the engine now reads negative numbers on tracks as losses. It also accepts one name where a list is expected (`"add": "dazed"`).
- Time that passed before a clock started must not count on it: the stretch whose stage starts a countdown in rounds holds 90 rounds.
- Read the rule instead of guessing it. Ferocity is the number of initiative cards, not actions on one card; the first version had it wrong.
- A rule change shifts the dice of every older fixed-dice test. Freeze a fixture (`tests/fixtures/ragna.toml`) rather than rewriting dozens of tests, and give new behaviour its own tests.
- A `str.replace` on code can hit two places; check the count.
- The extract took a line for a running head when it sat at a page's edge on enough pages. On two-column pages a spell's "Rank: 1" or a table's "D6" often comes out first, so they vanished from the text; a running head now has to be at the edge nearly everywhere it appears. Compare the manifest's `running` list against the book.
- Soft hyphens split words ("market\u00adplace"), and the audit read them as two. The page check drops them now.
- The Markdown grids lose ligatures ("sufer") and scramble columns; the page text is clean. Roll lines built from the page text (a row number alone on its line joined to what follows, a number with text only when it is the next row) import best. Tables of six side-by-side columns (random NPCs, quests, journeys, sites) had to be read from the picture, a column to a table, chained with `then` so one roll reads as the book's sentence.
- Numbers typed from memory of a game were wrong in several places, weapons among them. Nothing is typed from memory now: every number cites a page, and the audit reads it back.
- A kit offering a choice of three weapons becomes a kit per weapon, the book's other kits repeated so each keeps its one in three.
- Whole-word search still matches the start of a word: "inn" found "innate" on every kin page before any page about inns. A GM's question needs a page carrying it as a search term.

In compiling adventures:

- Don't close a way the book leaves open. A flooded room could still be swum through; closing it stranded a hero.
- Keep the book's resets. A creature that the book sends back to what it was doing needs the fact that angered it cleared.
- Give the GM procedures, not only outcomes: "a torch is a skill roll, then `solo wound <foe> 1d6 --through-armor`".
- Every fact a condition reads needs its exact commit in the GM text of the scene where it becomes true. `solo outline` lists them all.
- Don't invent names or numbers. Where the book is silent and a number is needed, say so in the text ("the book gives no number: D6").
- Stand-in rules shape play. A made-up fear result ("must attack") forced a fight the player was avoiding.
- Long procedures repeated in every scene cost the GM attention on every turn. Put them in a rule page and point to it.

In what GMs do (from the play tests):

- They guess skill names from other games (search, insight). The scene digest lists the hero's skills, and an unknown skill lists the system's.
- They forget what a place asks every round (holding a breath). `each_round` puts it in the fight lines.
- They skip a monster result that is an effect rather than damage. The engine says "run this now".
- They offer choices the rules don't allow (evading while dying) when the engine's own lines suggest them. The lines now say what's allowed.
- They think aloud in the final message, and once copied a `::: gm` block into it. The Book drops both; the harness flags them.
- They drift into third person. `AGENTS.md` carries the rule in one line.
- They write the dice into the story ("(Sneaking, 14 vs 5, failed)") though the Book shows them. `AGENTS.md` and the skill forbid it by example; the harness flags it.
- They reach for money as its own thing (`"silver": 30`, `"gear"`, `pc.tracks.silver`). Coins are items; the refusal now says so. They also nest tracks (`{"pc": {"tracks": {"hp": 3}}}`), which the engine now reads.
- They want to hurt the hero outside a fight (a fall, a trap) and tried `solo wound pc`. `solo wound hero` now does it, with armor. They also guess table names (`table danger`); the refusal suggests the near ones.
- They set a threat and then forget it: over a whole mission, failed rolls never advanced the goblins. A failed check out of a fight now names the live threat and the command.
- A hub scene has to carry what the GM must say there. A mission briefing skipped the waypoints and the threat until the hub's text listed them for each mission.
- They answer from the text or a skill roll before the oracle, as the ladder says. Scenarios meant to test the oracle need questions nothing else answers.
- A resumed session picks the story up from the campaign well, but the first turn is slow (several minutes).

In solo play:

- Content written for a party kills a lone hero. The system's own solo rules (two turns a round, pushing for willpower, healing alone) fixed that without touching the adventure's numbers. Prefer the book's solo rules to ad-hoc scaling.

## Play-testing an ingestion

Runs cost real usage: one long run can take half an hour, and a usage limit can cut a run off mid-way (the harness stops after two failed GM turns in a row). Run the short scenarios first, and the long one once they pass.

Write scenarios in `tests/gm_eval/scenarios/` for: the opening, each gate or puzzle, each unusual monster, any timer, and one long run with an agent player and a dropped session. Expectations can be state conditions (`when`) or events (`event = "search"`). A short scenario costs a few minutes; a long run half an hour. The judge varies between runs, so read its issues rather than only the scores, and trust what the code checks find.

## Legal and privacy

This repository is public. Free League's Dragonbane Third-Party Tabletop Module License lets a supplement use Dragonbane's terminology and cite its pages, and forbids carrying a copy of its rules or any of its text or art (see [NOTICE.md](../NOTICE.md)). So:

- Nothing from a book goes into this repository: no prose, tables, numbers or adventure text, free adventures included. It stays in `~/Games/solo`.
- Page references are fine (`source = "p. 58"`), and so are the game's terms (skill names, conditions, kin).
- Tests use made-up rules and this project's own adventures.
- Every pack says where its content comes from (`source`, and the header of `adventure.toml`).
