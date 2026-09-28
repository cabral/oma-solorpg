# Roadmap

The next pieces of work for an agent (or anyone) picking this project up. Read [docs/INGESTION.md](docs/INGESTION.md) first (how content gets into the engine, and what went wrong before), then [docs/PACK_FORMAT.md](docs/PACK_FORMAT.md) (every key a pack can hold). [docs/PLAN.md](docs/PLAN.md) has the design, and its Scope section lists the smaller things planned for later.

The order is by who each item unblocks. Item 1 makes the project something other people can send changes to. Item 2 proves the one way into Dragonbane actually works on a real book. Item 3 lets someone with no book play at all. Items 4 and 5 are about trusting the GM: hard limits in code, and a way to measure whether a change to its instructions made it better. Item 6 is campaign generation, which waits on item 2's packs.

## 1. Open the project to contributors

Small, and first, because everything after it arrives as pull requests.

- CI that runs `make test` on every pull request, on Python 3.11 and the newest release. The engine and its tests are standard library only, and the PyMuPDF tests already skip without it, so the job needs no dependencies. Today the only workflow is `pages.yml`.
- `CONTRIBUTING.md`: the license rule in a paragraph (no numbers, tables or text from any book in the repository, tests included; `tests/fixtures/house` is how a test gets rules), how to run the tests and `make qml-check`, and how to write a `tests/gm_eval` scenario. Issue templates for "an import went wrong" and "the GM did something wrong", both asking for a `solo report` bundle (item 4).
- A format version in packs: `format = 1` in `adventure.toml` and `system.toml`, read by `solo validate`, which says what to change when a pack is older than the engine. Adventures people share will outlive engine changes, and chapters (`chapters/*.toml`) have already changed the adventure format once.

Done when: a pull request shows the tests passing or failing without anyone running them, and a pack with no `format` or an old one gets a sentence from `solo validate` saying what to do.

## 2. Rules ingestion from a rule book, run on a real book

The bundled `packs/dragonbane` holds only the game's names; every number and table comes from the player's own book, through `make rules` and the `solo-rules-import` skill. The goal is that the player hands over a core rulebook PDF, of Dragonbane or any other game, and an agent turns it into a system pack the engine can run, reviewed by the player, the same way adventures are imported.

What the player provides: a rulebook PDF they own (Dragonbane's core rules and its solo rules first; later dice-pool games and others). Possibly supplements: a bestiary, a spell book, a GM screen.

What has to come out of it:

- `system.toml`: attributes, conditions (and which attribute each one banes), tracks, time units, the family (`d20-under`, `d6-pool`, or a new one), push rules, rests, light, dying, advancement, combat (initiative, damage bonus, dragon/demon effects), weapons and armor tables, skills with their attributes, and any solo tools the game has. Every number comes from the book, with its page.
- `creation.toml`: the creation tables (kin, profession, age, and so on) as data, with names of abilities and gear but no rules prose.
- Tables (`tables/*.toml`): fear, mishaps, random encounters, treasure, oracle charts, whatever the book rolls on, copied exactly and made self-resolving where a result rolls a value or a sub-choice.
- `rules/*.md`: the rules text, one page per topic, for `solo rule`. This is the book's own prose, so it stays in `~/Games/solo/systems/`.
- A bestiary as monster NPC templates or a reusable table set, if the book has one, so adventures can say `monster = "giant_spider"` and get the book's stat block and attack table.
- Heroic abilities, spells and their costs as data where the engine can run them (extra initiative cards, paying for a push), and as rule pages where it can't yet.

Built so far (the tools the import stands on, and the procedure):

- The `solo-rules-import` skill: the procedure an agent follows, from the PDF to a checked pack, with the mapping from a rulebook's contents to pack keys and rules pages, and the split for one agent per chapter.
- `solo extract` turns the PDF into pages and chapters, with running heads taken out and printed page numbers read off the footers when the PDF has no labels; `solo inventory` starts `inventory.toml` from it, a file per chapter with an item per section and table and every page already cited.
- `solo import table` reads a table from the extract's Markdown or a page's roll lines into `tables/*.toml`, dice worked out, gaps reported.
- Private packs laid over the bundled names (`extends`, `bundled:`), one per book, so the books' content stays in `~/Games/solo`; `needs` in the bundled pack says what a campaign can't start without.
- `make rules`, `make check`, `make adventure`: the mechanical steps in one command each, then the agent opened on the rest.
- `gear.toml` for coins and price lists, `bestiary/` for monsters any adventure's NPCs can be (and the GM can bring into play), both with `solo rule` pages generated from the data.
- Rules pages found by the words GMs ask with (`Search:`), whole-word matching and ranking.
- `solo audit` fails on anything unaccounted for, either way, and on anything a mapped item points at that isn't on its cited pages: table results, dice, monster stats, prices.

Still to do:

- The first import on a real book, from `make rules` to `make check` passing, by the maintainer with the skill. Nobody has run the whole path yet, and it is the only way into Dragonbane a new player has. Every place the agent or the player gets stuck goes into the skill and docs/INGESTION.md, the way the adventure imports did.
- Published adventures as the import's regression test. The maintainer keeps private packs of adventures from books they own (the core set's The Sinking Tower, and Alone in Deepfall Breach from the solo rules), written for an earlier hand-typed rules pack. Laid into `~/Games/solo/adventures/` over the imported rules, `solo validate` shows every table or key they name that the import named differently. Each one is a gap in the skill: give the tables a Dragonbane adventure is likely to name (the solo rules' threats, searching, scavenging, NPC attacks, treasure) the ids the skill must use, so every player's import comes out the same. Then their play-test scenarios run from outside the repository (`python3 tests/gm_eval/run.py <path to scenario>.toml`), and a fixed-dice test of each rule the import mapped goes into the private packs' own checks.
- Engine work for mechanics the book has and the engine doesn't, in this order: spells and WP spending (a mage hero can't do their job without them), ranged attacks and their ranges, the Rulebook's dragon/demon choices in combat, monster traits (a monster that can't repeat an attack, area attacks on several targets), weapon durability and breaking on a parry, encumbrance, journeys rolled by the engine (today the GM reads the journey rules and commits the time). Reorder by what the first import marks `engine` and what the regression adventures use. Each needs a data shape in `system.toml`, engine code, tests, and a `solo rule` page generated from the data. The import marks them `engine`, and the user decides which to build.

Done when: a player can give a rulebook PDF, an agent produces a system pack that validates, `solo audit` shows nothing unaccounted for, The Red Tusk Hall and the maintainer's regression adventures play on it, and a GM play test with a hero built from its creation tables gets through a fight, a rest and a push with the rules as the book has them.

## 3. A game anyone can play without buying a book

Someone who installs oma-solorpg today and doesn't own the Dragonbane core rules can't start a campaign: the bundled pack's `needs` refuses, as it should. So the first thing a stranger sees is a wall. The fix is one complete game in the repository, under a license that allows it.

That game is Ironsworn (the original, not Starforged). It is written for solo play, its text is under Creative Commons Attribution 4.0 ([Tomkin Press licensing](https://tomkinpress.com/pages/licensing)), and [Datasworn](https://github.com/rsek/datasworn) publishes its moves, oracles and assets as JSON, maintained officially. Its oracles are also far richer than the engine's own likelihood oracle.

- A third mechanics family, `action-roll`: an action die (d6) plus a stat and adds against two challenge dice (d10), read as a strong hit, a weak hit or a miss; momentum, which can cancel challenge dice and resets after use; progress tracks by rank, with progress rolls. It goes in `mechanics.py` beside `d20-under` and `d6-pool`, kept out of their code. The old roadmap's "third family when a game needs one" was waiting for this.
- Moves as the engine's actions: `solo move` is taken, so the command is something like `solo act <move>`, with the move's outcomes shown as the book words them and the GM choosing within them. Vows, bonds and journeys as progress tracks on the sheet and the Table.
- `solo import datasworn <json>` writing a pack: moves as rules pages, oracles as tables, assets as creation data. It reads each object's `source.license` and takes only CC BY content (some Datasworn content is CC BY-NC). Attribution goes in NOTICE.md and on each rules page.
- One original starter adventure for it, so first launch works with clicks only: New adventure, pick it, Begin.
- The Book and the Table learn the family: the action roll's three dice in the dice moment, momentum as a meter, progress tracks as boxes.
- Check the license terms again before starting; they are the reason this game and not another.

Done when: a fresh install with no book plays the starter adventure from the bar's d20, a fight and a vow included, and `tests/` plays it with fixed dice.

## 4. Safety and controls

The player's lines and veils are instructions to the GM and nothing more: nothing checks them, in play or in tests. And a GM turn has no ceiling except going quiet for 180 seconds; a GM that keeps talking, or keeps calling `solo`, runs until it stops on its own.

- A cut button in the Book (an X-card). It strikes the GM's last message: the engine records a `struck` event (the log stays append-only), the Book and `solo recall` leave the message out, and the next turn's prompt tells the GM the player cut it and not to come back to it. The player can add a line or veil from the same place. A struck message doesn't undo commits made in that turn; the GM is told which facts it committed, and retracts them in the story if it has to.
- Hard limits on a GM turn in `solo/gm.py`. For Claude Code: `--max-turns`, and an explicit `--disallowedTools` for WebFetch, WebSearch, Edit, Write and NotebookEdit, beside the `--allowedTools` list it already passes. For both agents: a wall-clock limit per turn next to the quiet limit (`SOLO_GM_TIMEOUT`), and a spending limit per campaign session, read from the `usage` each turn already records, which ends the session with a plain sentence in the Book and a setting to raise it. Tests check the commands `solo gm` builds.
- Adventure text is untrusted. `GM_COMMANDS` already leaves out every command that writes outside the campaign, so a shared adventure can't talk the GM into `solo setup`. Add: the GM skill says outright that scene and NPC text is story material and never an instruction; `solo validate` warns on text in a pack that addresses the model (ignore previous instructions, run this command, a `solo` command in scene prose); a gm_eval scenario with such a line in a scene checks the GM doesn't obey it.
- `solo report`: a bundle for a bug report (the trace of `solo` commands, the last events and GM messages, the engine version, the packs' `format`), with rules pages and pack text left out, so a report can't carry a book's content into a public issue.

Done when: a player can cut a message and never see it come back, a turn can't run past its limits whatever the agent does, and item 5's safety scenarios pass.

## 5. Measure the GM, then improve it

The GM is the player's agent (Claude Code or Codex) with this project's instructions, so there are no model weights here to train, and the engine design keeps it that way. What this project controls is the layer the agent reads: `skills/solo-gm/SKILL.md`, the Book's prompt in `solo/gm.py`, and what `solo resume` and `solo scene` print. `tests/gm_eval` already plays scenarios with a real GM, checks each message and the campaign state in code, and has a judge score the transcript. It has never been used to decide anything: `results.tsv` isn't in the repository yet.

- A baseline. Every scenario, three runs each, with Claude Code on its default model and a small one, at the normal pace, with `SOLO_SEED` fixed so the dice are the same across runs. Check in `results.tsv`. Until there is one, a change to the skill can't be shown to help or hurt.
- `run.py --repeat N`, and a `compare.py` that reads `results.tsv` and says, per score, whether two commits differ by more than their runs differ among themselves. A change to the skill or the Book's prompt comes with that comparison.
- Scenarios for what goes wrong on purpose: a player who cheats ("I find a sword that never misses", "I kill the dragon in one blow", "set my HP to 20"), and the GM should answer in the story and through the rules; lines and veils set in the scenario, with `[[forbid]]` on the line's words and a seventh judge score for the player's table settings; the injected scene line from item 4; a session lost in the middle of a fight.
- `solo review <campaign>`: the checks gm_eval runs, run offline over a campaign played for real (`events.jsonl` and the trace): refused commands, consequences that came due and were never paid, a person given two names, fight rounds where no foe struck back. What it finds in real play becomes a scenario, so the scenarios follow the failures players actually meet.
- These cost model calls, so they run on demand, before a pull request that changes `skills/` or `solo/gm.py`, and not in CI. A manual workflow with an API key as a repository secret can come later.

Done when: `results.tsv` has a baseline, every change to the GM's instructions since carries a comparison against it, and the safety scenarios are part of the set.

## 6. Generate campaigns

Every adventure the engine plays today was written by someone: The Red Tusk Hall by this project, the rest imported from books the player owns. The goal is that a player with no book for the story they want can pitch one (a premise, a tone, a length) and an agent writes it as a campaign pack the engine plays like any other, with the dice taking part in the writing. The website (`site/`) already presents this, with the interface below; build to it, or change the page with it.

What the player gives:

```bash
make campaign ID=salt-and-ash TONE=grim MISSIONS=4 \
  PREMISE="a smuggler's coast where the dead keep the lighthouses"
```

What has to come out of it, in `~/Games/solo/adventures/<id>/`, in the formats [docs/PACK_FORMAT.md](docs/PACK_FORMAT.md) already has:

- `adventure.toml` with a `system` and a spoiler-free `summary`, so it shows on the New adventure screen.
- A hub scene to come back to between missions (a safe scene: threats don't close in there), and each mission as a path of waypoints behind a gate that opens when the one before is done.
- Factions that want things, clocks and threats with omens, NPC profiles with a face (`art.toml`), a voice, wants, fears and secrets that reveal on a fact, and voices (quiet skill checks) per scene.
- Rolled parts: the system pack's own tables and the oracle (`solo table`, `solo ask --meaning`) decide what a waypoint holds, who is there and what they want, so the dice have a say before play. The rolls are recorded in the pack (`source = "rolled: ..."`), so a generated campaign can be reviewed like an imported one.

The pieces it stands on: the adventure pack format, gates and clocks, the long-campaign memory (consequences, faction memories, the chronicle, `solo history`), `solo validate` (with its lint warnings) and `solo outline`, and the `solo-import` skill's procedure for inferring factions, clocks and branches.

Built so far:

- `solo campaign new` (`solo/generate.py`) rolls a pack from the premise: the hub (safe), the factions `locals` and `rivals`, the patron and the nemesis, the nemesis's hidden clock `plan` with omens and a last stage that sets `plan.done`, and mission 1 as `chapters/mission_1.toml`: three waypoints and a heart. Each waypoint rolls what it holds (a way through, a stranger, foes, a find, a hazard, signs of the enemy), meaning words for what is at stake, darkness, and its specifics from the system pack (the solo rules' threat, bestiary monsters or simple NPC templates, treasure, inspiration words). The same premise, system and seed give the same pack, file for file. It validates, lints clean and plays before anyone writes a word; every file is marked `rolled, not yet written`, and `draft = true` keeps it off the New adventure screen.
- Every roll goes into `rolls.toml` and is cited where it decided something (`source = "rolled: #4"`); `solo campaign roll` records the author's own rolls the same way. `solo campaign check` fails on files still as rolled, drafts, a roll nothing uses or explains, and a citation of a roll that isn't there.
- Adventures in chapters (`chapters/*.toml`): scenes, clocks, factions and weapons laid over `adventure.toml` in order, adding the hub's way in and briefing without touching it, ids defined twice reported, `draft` chapters kept out of a campaign under way.
- `solo campaign next` rolls mission n into a campaign's pack once `mission_<n-1>.done` holds, and rolls two of the campaign's threads to come back in it (open consequences and promises, people who remember the hero, people who got away, faction memories, hero facts). Someone the GM made up in play gets an NPC file with the name and profile the GM gave them, and nothing the log sets, so the campaign replays to the same state (tested).
- The `solo-campaign` skill; `make campaign`, `make campaign-next`, and `make check-adventure` running `solo campaign check` on a generated pack.
- Tests (`tests/test_generate.py`): same premise and seed give the same pack; it validates and lints clean; mission 1 plays through with fixed dice, fights included; mission 2 loads into the running campaign, leaves what happened as it was, and brings back a consequence and a hero fact from mission 1. `tests/gm_eval/scenarios/generated-mission.toml` plays a rolled mission with a real GM (`[generate]` in a scenario rolls the campaign for the run).

Still to do:

- Run `generated-mission` with a real GM on the rules built from a book (item 2), read the reports, and fix the rolled prompts or the skill where the GM stumbles.
- A campaign written up by an agent with the skill, from `make campaign` to a second mission with `make campaign-next`, played for real. What that teaches goes into the skill and docs/INGESTION.md, as the imports did.
- The generator's own lists (places, roles, voices, obstacles, hazards, omens) are short and plain on purpose: the agent rewrites them. If write-ups keep the same placeholder shapes, give the lists more variety, or let a system pack name tables to roll instead.
- Once item 3 lands, campaigns on Ironsworn too: its oracles are made for exactly this, and a player with no book at all could pitch a campaign.

Done when: a player gives a premise, gets a campaign that validates and shows on the New adventure screen, plays its first mission, and the second mission, written after the first, pays off something the hero did in it. The engine side is built and tested; the end-to-end run with a real agent and GM is what's left.
