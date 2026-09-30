# Pack format

Every key a system pack or an adventure pack can hold, as the engine reads it. Hand-written files are TOML; files an importer generates are JSON (or, for `solo import datasworn`, TOML marked as generated), and a TOML file beside a JSON one wins on any key both set. `solo validate` checks all of this; `solo outline` shows an adventure on one page. Worked examples: `examples/red-tusk` and `examples/bell-under-the-hill` for adventures; `packs/dragonbane` for a game's names; `packs/ironsworn` for a whole game of the `action-roll` family; `tests/fixtures/house` for every system section of the skill families, with made-up values.

## System pack: `packs/<system>/` or `~/Games/solo/systems/<system>/`

```
system.toml      the game's rules as data (below)
creation.toml    character creation tables
gear.toml        coins and price lists (below)
characters/      pre-made heroes (<id>.toml)
bestiary/        monsters any adventure can use (<id>.toml, below)
moves/           action-roll games: the moves a hero can make (<id>.toml, below)
assets/          action-roll games: what a hero can take (<id>.toml, below)
art.toml         the hero's portrait parts and generic figures
tables/          <id>.toml tables (hand-written) and <id>.json (imported)
skills.json      imported skills (extends [skills])
rules/           <topic>.md rule pages for `solo rule` (imported prose: git-ignored)
inventory.toml   what the book holds and where it went (below); inventory/*.toml, a file per chapter
checks/          unittest files with fixed-dice tests of the rules the import mapped; `make check` runs them (private, like the rest)
```

A pack can be laid over another: `extends = "dragonbane"` in `system.toml` (a folder relative to the pack, or a pack's name, never the pack itself, so `~/Games/solo/systems/dragonbane` can extend the bundled `dragonbane` it hides). `extends` can also be a list, `extends = ["dragonbane-rulebook", "dragonbane-treasure-cards"]`, laid down in that order with the last one winning where they set the same key: one pack per book, each audited against its own book, and a supplement never has to sit under another. A pack that several of them extend (the rulebook) is laid down once, first. `extends = "bundled:dragonbane"` names the bundled pack only, for a layer that sits under the player's own `dragonbane` (`make rules` puts the rulebook's pack there, and the solo rules' pack over it). Its `system.toml`, `creation.toml`, `gear.toml` and `art.toml` are merged over the base's table by table (a key it sets wins, lists are replaced); its tables, characters, bestiary entries and rules pages are added over the base's by id or title. A pack built from a book the player owns stays in `~/Games/solo`, never in this repository.

### `system.toml`

| Key | Meaning |
|---|---|
| `format` | The pack format this file was written for (see [Format versions](#format-versions)) |
| `name`, `family` | Display name; mechanics family: `d20-under`, `d6-pool` or `action-roll` (an action die and a stat against two challenge dice: Ironsworn) |
| `credit` | A line every generated rules page of the pack ends with: the attribution a licensed pack owes (`packs/ironsworn` says its Creative Commons credit here) |
| `extends` | The pack this one is laid over (above) |
| `needs` | Keys a campaign can't start without (a dotted key reads into a section: `creation.choose`). The bundled Dragonbane lists what the player's book must supply; `solo validate` and `solo new` name what's missing |
| `untrained` | d20-under: base chance by attribute, `[[top, chance], ...]` |
| `success`, `[pool]`, `[extra_dice.<id>]`, `[triggers.<id>]` | d6-pool: success face, dice groups, extra dice (stress) with `on_one`, trigger tables (panic) |
| `[attributes]` | `id = "Label"` |
| `[conditions]` | `condition = "attribute"`: a bane on rolls with that attribute. In an `action-roll` system an impact instead names the track it keeps from rising while it is marked (`wounded = "health"`), or `""` for one that only weighs on momentum |
| `[tracks]` | `id = "Label"`: resources with value and max (hp, wp, stress) |
| `[time]` | `unit = seconds`; clocks advance on `time:<unit>`; a fight round passes `round` |
| `[push]` | `cost = "condition"` or `{ track = n }`; `add_dice` for d6-pool |
| `[rest.<id>]` | `label`, `recover = { track = "1d6" or "max" }`, `heal` (a number or `"all"`), `time`, `limit` (once per unit), `tend = { skill, recover }` (the hero tends their own wounds: `--tend`) |
| `[light.<id>]` | `label`, `item` (carried item used up), `lasts = { unit = n }` |
| `[dying]` | `track`, `roll` (attribute or skill), `rally`, `die` (counts), `recover`; `self_rally = { skill }` (`solo rally`), `self_save = { skill, recover }` (`solo death-roll --heal`; `recover` is `[dying]`'s own when it isn't given) |
| `[advancement]` | `mark_on = ["dragon", "demon"]`, `roll`, `max` |
| `[combat]` | `initiative` (cards), `dragon = "double"`, `evade` (skill), `track`, `unarmed = { label, skill, damage, bonus }`, `monster_parry` (can monster attacks be parried by default), `[combat.damage_bonus]` `attribute = [[top, "dice"], ...]` |
| `[weapons.<id>]` | `label`, `skill`, `damage`, `bonus` (attribute), `parry = false`, `attack = false`; matched to carried items by slug |
| `[armor]` | `item_id = rating` |
| `[skills]` | `id = "attribute"` or `{ attribute, name, untrained = false }` |
| `[oracle]` | `chart = "fortune"` (the fortune chart replaces the likelihood oracle) or `"odds"` (a d100 against the chance of a yes at each of five odds: `[oracle.odds]` `"50/50" = 50`, one level at 50; a double is a twist), `scene_checks = false`, `inspiration = [table ids]` for `--meaning`, `[oracle.fortune]` with `bands` and one list per column |
| `[momentum]` | `action-roll`: `min` (below 0), `max`, `reset`. Momentum is a track (`[tracks]` names it) that may go below zero; each impact the hero has takes one off its ceiling and its reset (never below 0) |
| `[progress]` | `action-roll`: `boxes` and `ticks` (a track's length and a box's), `[progress.ranks]` (`rank = ticks one mark fills`), `kinds = { vow = "Vow" }` (the tracks a game keeps, started with `solo track add`), `unranked = { bonds = "Bonds" }` (tracks every hero has from the start, with no rank: a mark is one tick) |
| `[effects]` | `dragon`, `demon`: tables rolled on a Dragon or Demon outside a fight |
| `[threats]` | `segments`, `start`, `advance` (triggers), `table` (random threats) |
| `[search]` | `skill`, `table`, `time` |
| `[scavenge]` | `table`, `again_time` |
| `[npcs]` | `attacks` (the NPC attack table), `attackers` (role columns), `[npcs.templates.<id>]` with `hp`, `armor`, `damage`, `skill`, `other`, `movement`, `attributes` |
| `[abilities.<id>]` | Heroic abilities the engine runs: `name`, and `initiative = n` (cards drawn) or `push = { track = n }` (pay instead of a condition) |
| `[foundry]` | Where a Foundry actor keeps values, for the character importer |

### `gear.toml`

```toml
[money]
coins = { gold = 100, silver = 10, copper = 1 }   # each coin's worth in the smallest
aliases = { gc = "gold", sc = "silver" }           # optional: abbreviations the book uses

[gear.rope]
name = "Rope, 10 meters"
category = "Equipment"          # the book's heading: a page per category in `solo rule prices <category>`
price = "1 silver"              # as the book writes it: "1 gold 5 silver", "3 gold coins", "12 sc", a number in the smallest coin, or "varies"
weight = 1                      # optional, in the book's own unit
supply = "common"               # optional: how easy it is to find
note = ""                       # optional, short, in your words
source = "p. 58"
```

A weapon's or armor's price sits here under the same id as its `[weapons]` or `[armor]` entry, and the price pages show its stats beside it. `solo rule prices` lists the categories; `solo rule <item>` finds an item's category page.

### Moves: `moves/<id>.toml`

The moves of an `action-roll` game, by id (`solo act <id>`); the folder is read from every layer of the pack, and the moves keep the book's order (`order`).

| Key | Meaning |
|---|---|
| `name`, `category`, `order` | The move's name; the group the book puts it in (the Table's palette shows it); where the book puts it |
| `kind` | `action` (rolls an action die and a stat), `progress` (a progress roll on a track) or `none` (a move with no roll: its words are the rule) |
| `stats` | An action move: what it can roll `+`, attributes or tracks (`["edge", "iron"]`, `["health", "iron"]`). `--stat` picks one; a move with one needs no flag; `--stat highest` or `lowest` takes the better or worse of them |
| `pick` | `highest` or `lowest`: the move says whichever is higher or lower, so the engine takes it (Endure Harm) |
| `track` | A progress move: the kind of track it reads (`vow`, `journey`, `combat`, `bonds`) |
| `oracle` | Tables the move sends you to (`solo table <id>`) |
| `text`, `[outcomes]` | The move in the book's words, and `strong_hit`, `weak_hit`, `miss`: what `solo act` says back for the result |
| `source` | Where in the book |

### Assets: `assets/<id>.toml`

`name`, `category`, `requirement`, `health` (a companion's), `source`, and `abilities = [{ name, text, enabled }]` (`enabled` marks the one a new hero has). A hero's `abilities` list on the sheet names them; `solo rule <asset>` gives the page. Nothing in the engine runs an ability: the GM reads it and adds what it gives to a move.

`moves/`, `tables/` and `assets/` of a pack that comes from a licensed source are generated (`solo import datasworn`), start with a `# Generated by ...` line and are not edited by hand: the import runs again and rewrites them. A file without that line is the pack's author's own and is never touched.

### Bestiary: `bestiary/<id>.toml`

A monster as an adventure's NPC profile has it: `name`, `role`, `description`, `[stats]` (`hp`, `armor`, `ferocity`, `immune`), `attacks = "<table>"` (its attack table, in the pack's `tables/`) or `[attack]` and `[skills]`. An adventure's NPC becomes one with `monster = "<id>"`, its own keys laid over the monster's (a name, secrets, more hit points); in play the GM commits one (`{"npc": {"wolf_1": {"name": "Wolf", "monster": "wolf"}}}`). `solo rule bestiary` lists them. Whether a kind of foe is met again and again (`many`) is the adventure's to say, not the bestiary's.

### `creation.toml`

Top level: `attributes` (dice per attribute, or a list of numbers dealt out across the attributes at random: Ironsworn's `[3, 2, 2, 1, 1]`), `attribute_range`, `key_swap`, `trained_multiplier`, `tracks = { track = "attribute" }` (a track starts at an attribute's value) or `{ track = number }` (at a number), `extra_abilities = { count, from = [...] }` (picked last, so a seed stays stable; without `from`, from every asset of the pack), `[ratings.<id>]` with `label`, `attribute`, `table = [[top, value], ...]`. A game with no `[choose]` tables still builds a random hero when it has `attributes`.

`[names]`: `<option id> = [names]`, a list of hero names for a kin (or any option) without `names` of its own; `any` for a hero with no options. The bundled Dragonbane pack has one per kin.

`[choose.<table>]`: `label`, `roll` (dice), and `[choose.<table>.options.<id>]` with `label`, `range`, `attributes` (modifiers), `key` (key attribute), `skills` and `train` (how many trained), `always`, `extra`, `abilities`, `ratings`, `names`, `gear` (text; `{1d8}` rolls), `kits` (one picked), `then` (a follow-up table).

### Characters: `characters/<id>.toml` (system or adventure)

`name`, `info` (kin, profession, age...), `[attributes]`, `[skills]` (value; listed means trained), `[tracks]` (max or `{ value, max }`), `conditions`, `items`, `abilities`, `[ratings]`. In an adventure, `replacement = true` keeps a hero off the start screen for `solo hero` after a death.

### `art.toml` (system)

`[moods.<mood>]` (`eyes`, `brows`, `mouth`), `[kin.<kin>]` heads with slots, `[gear.<profession>]` headgear, `[wounds]`, `[age]`, `[sprites.<id>]` generic figures. The comments in `packs/dragonbane/art.toml` explain the slots.

## Adventure pack: `examples/<id>/` or `~/Games/solo/adventures/<id>/`

```
adventure.toml   everything below that isn't text
chapters/<id>.toml  more scenes, clocks, factions and weapons, laid on in order (below)
scenes/<id>.md   read-aloud first, GM-only text inside ::: gm fences
npcs/<id>.toml   profiles (npcs/<id>.json from an importer)
tables/<id>.toml
characters/      pregenerated and replacement heroes
rules/<topic>.md rules the adventure leans on
checks/          unittest files with fixed-dice tests of the adventure's routes; `make check-adventure` runs them (private, like the pack)
art.toml         [sprites.<npc>] and [portraits.<npc>], each art = '''...'''
scenes.json      from an importer: titles, exits, npcs, tables
```

### `adventure.toml`

| Key | Meaning |
|---|---|
| `format` | The pack format this was written for (see [Format versions](#format-versions)) |
| `title`, `system`, `summary` (player-safe), `start`, `source` | The card on the New adventure screen, and where it comes from |
| `draft` | `true` while it's still being written: the New adventure screen leaves it out (and says so) and `solo new` refuses it |
| `chaos`, `scene_checks` | The likelihood oracle's settings (ignored by a system with a fortune chart) |
| `move_time` | Game time every move takes unless its exit says otherwise |
| `[weapons.<id>]` | Weapons the adventure brings; they join the system's |
| `[factions.<id>]` | `name`, `standing` (-2..2) |
| `[clocks.<id>]` | `label`, `segments`, `hidden`, `omen` (hidden, but tick results and stage texts reach the player), `advance` and `stop` (triggers), `while` (a condition: counts nothing until it holds), `on_tick` (table), `at_full` (scene), `source`; `[[clocks.<id>.stages]]` with `at`, `text` (player), `note` (GM), `facts`, `clock` (moves) |
| `[scenes.<id>]` | `title`, `npcs`, `tables`, `climax`, `ending`, `dark`, `safe` (the solo rules' threats don't advance there: a hub, a village), `each_round` (read in every fight line there), `file`, `source` |
| `exits` | `target = "Label"`, or `[scenes.<id>.exits.<target>]` with `label`, `when` (closed until it holds), `time` |
| `[[scenes.<id>.voices]]` | `skill`, `text`, `clue`, `when`, `boons`, `banes` |
| `[[scenes.<id>.branches]]` | `when`, `text` (shown to the GM under "True now") |

### Chapters: `chapters/<id>.toml`

An adventure can come in parts. Each chapter file holds `scenes`, `clocks`, `factions` and `weapons` in the same shape as `adventure.toml`, and they are laid over it in natural order (`mission_2` before `mission_10`). A chapter can add to a scene defined before it: its `exits` join the scene's, and its `branches` and `voices` are added after the scene's own, so a new mission gives the hub its way in and its briefing without anyone editing the hub. Any other key of a scene set again replaces it. A clock, faction or weapon defined in two files is a problem (`solo validate` names both), and so is any other top-level key in a chapter. `draft = true` in a chapter keeps it out of a campaign under way until the line comes off; `solo validate --adventure` and `solo outline` show drafts to their author. A generated campaign keeps each mission in `chapters/mission_<n>.toml`.

### Generated campaigns: `premise.toml` and `rolls.toml`

`solo campaign new` (`make campaign`) writes both beside `adventure.toml`, and `solo campaign check` reads them:

- `premise.toml`: what the player pitched: `title`, `premise`, `tone`, `missions`, `system`, `seed`. The generator reads it again for each mission.
- `rolls.toml`: every roll made for the pack, in order, as `[[rolls]]` with `n`, `for` (what it decided), `table`, `dice`, `rolled` (the dice) and `result`. The generator and `solo campaign roll` append to it; nothing else writes it. A roll the author chose not to use gets `note = "why"`.

What a roll decided cites it anywhere in the pack's files, most often in a `source`: `source = "rolled: #4, #7"`. The check fails on a roll nothing cites and nothing explains, on a citation of a roll that isn't there, on a file still marked `rolled, not yet written`, and on `draft` marks.

### NPCs: `npcs/<id>.toml`

`name`, `role` (a description), `faction`, `attitude` (hostile .. allied), `fate`, `location`, `wants`, `fears`, `voice`, `description`, `source`, `sprite`, `monster` (a bestiary entry of the system pack this NPC is, its keys laid over the monster's), `many` (true for a kind of foe met again and again, like cultists or skeletons: fights never run out of them, and no commit gives them a fate); `[[secrets]]` with `id`, `text`, `reveal` (a condition). To fight: `[stats]` with `hp`, `armor`, `ferocity` (initiative cards), `immune` (text: what alone harms it); and either `[attack]` (`label`, `skill` or `value`, `damage`, `bonus`), or `attacks = "<table>"` (a monster), or `template` + `attacker` (a simple NPC: minion or boss; melee, ranged, sneaky or magic, or a list). `[skills]` for any skill values.

### Tables: `tables/<id>.toml`

`name`, `formula` (dice; `@track` reads a track), `parry` (default for a monster table), `results = [...]`, each with `range = [low, high]`, `text`, and optionally:

- `damage`, `defend = false`, `parry = true`, `armor = false`: a monster attack
- `roll = "2d6x10"`: a value, written where the text says `{value}`
- `choices = [...]`: one picked
- `then = "table"` or `[...]`: rolled next
- `again = true`: roll this table once more
- per-role entries (`melee = { text, attack, damage, boons, banes, extra, times, effect }`): the NPC attack table
- `page = 44`: the PDF page the result is on. A deck of cards is a page each; with `page`, `solo audit` reads that result (its text, `choices`, numbers and dice, a multiplier such as `2d6x10` included) against that page alone, instead of against everything the item cites, so a value that's right for another card can't pass for this one

`solo validate` checks that the ranges cover every result the formula can roll.

### Scene text: `scenes/<id>.md`

```markdown
Read-aloud text: what the hero perceives on arriving.

::: gm
GM-only: rolls with their skills and banes, the exact commits for facts that conditions
read, fights with their commands, what's hidden and when it's revealed.
:::
```

## Rules pages: `rules/<topic>.md` in either kind of pack

Markdown, titled on its first line (`# Journeys`). The line after it can list the words a GM would look the page up by: `Search: travel, travel time, distance, getting lost`. `solo rule <topic>` finds a page by its title or one of those words (whole, or as the start of a word), else by the topic's words in the text, best first; with no topic it lists every page. Pages are looked up in the pack first, then the packs it is laid over, then the adventure; when two share a title, the first answers a search for it. An imported page hides the engine's own page of the same title (`packs.engine_rules`).

## Inventory: `inventory.toml` in either kind of pack

What the book holds, item by item, with its pages, and where each item went in the pack. `solo audit` reads it both ways: every item has to be accounted for, and everything in the pack has to be claimed by an item. Names and page numbers only, no rules prose. Items can also live in `inventory/*.toml`, a file per chapter (what `solo inventory <pack> --extract <folder>` starts): ids are shared by all of them, and one used twice is reported.

```toml
source  = "Dragonbane Core Rules"
extract = "~/Games/solo/sources/dragonbane-core-rules"   # solo extract's folder, so the audit can check pages

[items.boons_and_banes]
name   = "Boons and banes"            # default: from the id
kind   = "mechanic"
pages  = [30, "31-32"]                 # PDF pages, as solo extract numbers them
status = "mapped"
to     = ["system.toml:untrained", "rules/boons_and_banes.md"]
note   = ""
```

| Key | Meaning |
|---|---|
| `kind` | `mechanic`, `table`, `creature`, `npc`, `spell`, `ability`, `gear`, `place`, `event`, `component`, `advice`, `other` |
| `pages` | Where it is in the book. Required, except for `house` |
| `status` | `mapped`: in the pack where `to` says. `house`: in the pack but not from the book, a stand-in (`note` says so). `engine`: the engine can't run it yet (`note`: what it needs). `skipped`: left out on purpose (`note`: why). `todo`: not decided (the default) |
| `to` | What in the pack holds it: `tables/fear`, `npcs/priest`, `characters/ragna` (a file by its stem), `rules/fear.md`, `scenes/cellar` (a scene, wherever it is defined), `system.toml:combat.damage_bonus` (a key in a TOML or JSON file), `skill:solo-gm` (GM advice that went into a skill) |

What an item must claim: in a system pack, each top-level key of `system.toml`, `creation.toml` and `gear.toml` (each entry, for a section whose entries are all tables, like `[weapons]`, `[rest]` or `[gear]`; `name`, `family`, `extends` and `[foundry]` are exempt), each table, monster, character and rules page. Only the pack's own files count: a pack laid over another claims what it adds, and an item's `to` may name something the base holds (the book confirming it). In an adventure, each scene, NPC, table, character, rules page, and each clock, faction and weapon in `adventure.toml`. A reference claims what it names and anything under it: `system.toml:weapons` claims every weapon, `system.toml:weapons.dagger` only the dagger.

With `extract` set, the audit also reads a mapped item's pack data back against its pages: each result of a table must be there word for word (order aside), and each dice expression, stat (a monster's hp, armor, ferocity) and price in its data must appear on them. What doesn't is listed under "Not on the cited pages" and fails the audit.

## Extracted books: `~/Games/solo/sources/<book>/`

What `solo extract <pdf>` writes. Outside every pack and the repository: it is the book's own text.

A card deck or a book of art keeps some of its words in the pictures (a card's value, a title), and the PDF's text layer has none of them, or some. OCR of a decorated card is unreliable, so an agent reads such a page's picture and writes what it says into `picture/<page>.txt` (the same number as `pages/`, in a folder a new extract leaves alone). `solo audit` reads it after the page's own text, and says which pages it came from, since the pack is then checked against a reading, not against the PDF.

```
manifest.json      source file and sha256, page count, printed page labels (`labels`, and `labels_from`: pdf, footers or none), pages that need OCR, `running` (headers and footers taken out of the text)
toc.json           [{ level, title, start, end, chars, file }]: from the PDF's bookmarks, else guessed from font sizes
book.md            every page, after a ===== PAGE n (printed m) ===== marker
pages/0042.txt     one page, columns read left then right, running heads taken out
chapters/03-combat.md   one chapter's pages, the unit an agent reads in one go
tables/index.json  [{ page, kind: grid | roll, file, image }]
tables/p0042-1.md  a ruled table as Markdown; p0042.png the page as a picture, for tables the text scrambles
picture/0042.txt   yours, not the extract's: what you read off page 42's picture where the PDF has no text there
```

## Conditions and triggers

Conditions (branches, exits, voices, secrets, `while`): `and`, `or`, `not`, comparisons, `in`, over `npc.<id>.<fate|attitude|location>`, `faction.<id>`, `promise.<id>`, `fact.<key>`, `clock.<id>`, `scene`, `visited.<scene>`, `pc.<track>`, `pc.conditions`, and the attitude names as numbers.

Clock triggers: `time:<unit>`, `fact:<key>`, `scene:<id>`, `check:dragon`, `check:demon`, `check:<pool trigger>`, `check:strong_hit`, `check:weak_hit`, `check:miss` and `check:match` (an `action-roll` move's result), `npc:<id>:<fate>`, `promise:<id>:<status>`, `clock:<id>:full`. A move's result is final when no burn of momentum could still change it; a roll one could change holds its triggers back until the story goes on (the next commit, move or roll), or the burn.

## Commits (what the GM writes)

`solo commit '<json>'`, every key optional: `note`, `facts` (`hero.<key>` facts follow the hero into later adventures), `npc` (`name`, `faction`, `attitude`, `fate`, `location`, `memory`, `template`, `attacker`, `monster`; for an NPC the adventure doesn't have, also `role`, `description`, `voice`, `wants`, `fears`). A person keeps their name: a different `name` for someone who already has one is refused, unless the commit has an `override` with the reason (they give their name at last), and `solo review` lists it, `faction` (a standing, or `standing`, `memory`, `name`), `promise` (`id`, `npc`, `terms`, `status`), `consequence` (`id`, `text`, `npc`, `at` (scene ids), `when` (a condition), `after` (game time), `status`: open, done, dropped), `pc` (tracks as `"+n"`/`"-n"` or a number to set; a negative number is a loss; `conditions`, `items` and `abilities` (what the hero has learned: heroic abilities, assets) with `add`/`remove`, a name or a list. A track stops at its own range: momentum runs from `min` to what impacts leave of `max`; in an `action-roll` system an impact keeps its track from rising), `clock`, `time`, `clue`, `chaos`, `learn` (`npc.wants`, `npc.fears`, `npc.<secret>`), `chronicle`, `end`, `override`.

## Format versions

`format = 1` at the top of `system.toml` and `adventure.toml` says which pack format the file was written for. Adventures people share outlive engine changes, and chapters (`chapters/*.toml`) have already changed the adventure format once, so the engine reads the number and tells the author what to do. `solo validate` (and `make check`) reads it:

- No `format`: one sentence, `add format = 1`. The pack was written before formats had numbers, so it reads as format 1 and plays as it always did.
- Older than the engine's: what to change to bring the pack up, one sentence for each format it has to cross, then the number to set. The engine says it once, to the author; the pack is theirs to change.
- Newer than the engine's: `solo validate` fails, `solo new` refuses it, and the New adventure screen leaves it out with the reason: update oma-solorpg, or use a copy of the pack written for this engine.
- Not a whole number: an error.

Each layer of a system pack answers for its own file (`dragonbane-rulebook/system.toml`, then `dragonbane/system.toml`). A chapter, an inventory or a table has no format of its own: it belongs to the pack. `solo campaign new`, `solo import foundry adventure` and `make rules` start their packs at the current format.

The engine raises `packs.FORMAT` only for a change that would break a pack written for the one before (a key renamed or given another meaning), never for a key older packs simply don't use, and writes what an author must do into `packs.UPGRADES` in the same change. The history:

| Format | What it holds |
|---|---|
| 1 | Everything in this document: chapters, packs laid over packs (`extends`), `gear.toml`, `bestiary/`, inventories, generated campaigns. The first numbered format; a pack with no `format` is this one. |
