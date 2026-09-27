# Roadmap

The next piece of work for an agent picking this project up. Read [docs/INGESTION.md](docs/INGESTION.md) first (how content gets into the engine, and what went wrong before), then [docs/PACK_FORMAT.md](docs/PACK_FORMAT.md) (every key a pack can hold). [docs/PLAN.md](docs/PLAN.md) has the design.

## 1. Develop rules ingestion from a rule book

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

Still to build:

- Engine work for mechanics the book has and the engine doesn't. Known gaps for Dragonbane: spells and WP spending, weapon durability and breaking on a parry, ranged attacks and their ranges, monster traits (a monster that can't repeat an attack, area attacks on several targets), the Rulebook's dragon/demon choices in combat, encumbrance, journeys rolled by the engine (today the GM reads the journey rules and commits the time). Each needs a data shape in `system.toml`, engine code, tests, and a `solo rule` page generated from the data. The import marks them `engine`, and the user decides which to build.
- A third mechanics family when a game needs one (a percentile or D&D-style d20-over), kept out of the other families' code as `mechanics.py` does now.
- Imports by players with the skill, and what they teach: fixed-dice tests of the book's rules, and `tests/gm_eval` scenarios that exercise each rule with a real GM.

Done when: a player can give a rulebook PDF, an agent produces a system pack that validates, `solo audit` shows nothing unaccounted for, The Red Tusk Hall plays on it (for Dragonbane), and a GM play test with a hero built from its creation tables gets through a fight, a rest and a push with the rules as the book has them.

## 2. Generate campaigns

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

- Run `generated-mission` with a real GM on the rules built from a book, read the reports, and fix the rolled prompts or the skill where the GM stumbles. It hasn't been run yet: it needs `claude` and the player's Dragonbane packs.
- A campaign written up by an agent with the skill, from `make campaign` to a second mission with `make campaign-next`, played for real. What that teaches goes into the skill and docs/INGESTION.md, as the imports did.
- The generator's own lists (places, roles, voices, obstacles, hazards, omens) are short and plain on purpose: the agent rewrites them. If write-ups keep the same placeholder shapes, give the lists more variety, or let a system pack name tables to roll instead.

Done when: a player gives a premise, gets a campaign that validates and shows on the New adventure screen, plays its first mission, and the second mission, written after the first, pays off something the hero did in it. The engine side is built and tested; the end-to-end run with a real agent and GM is what's left.
