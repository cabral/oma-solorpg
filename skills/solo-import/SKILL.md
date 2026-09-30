---
name: solo-import
description: Build or enrich an adventure pack for the `solo` engine from a PDF or a Foundry VTT export, from a single adventure up to a whole book of them. Use when the user wants to import an adventure or official content, turn an adventure PDF into scenes, NPCs, tables and clocks, add clocks, gates, branches or NPC profiles to an imported adventure, play-test an import, or fix what `solo validate` reports.
---

# Building adventure packs

Read `docs/INGESTION.md` in the repository first: how earlier books were compiled, how a book's concepts map to pack features, and the mistakes play tests caught. Every key is in `docs/PACK_FORMAT.md`.

An adventure pack is a folder. The engine runs the game from it, and the GM agent reads its scene text one scene at a time. The source text stays close to the book. A thin structured layer on top holds only what has to be tracked or rolled.

## Two passes

1. Mechanical extraction, no judgement involved. From a Foundry export: `solo import foundry adventure <export files or folders> --out <pack>`. It writes `scenes.json`, `scenes/*.md`, `npcs/*.json` and `tables/*.json`. From a PDF, you do this pass yourself (below).
2. Structuring, by you, reviewed by the user. Write `adventure.toml` and `npcs/*.toml` with what the text implies: factions, clocks, branches, NPC profiles.

Never edit generated JSON: a re-import overwrites it. TOML files sit beside it and win on any key both set.

## Layout

```
adventure.toml   title, start, factions, clocks, scene extras and branches
scenes.json      generated: title, exits, npcs, tables per scene
scenes/<id>.md   scene text: read-aloud first, then GM material inside ::: gm fences
npcs/<id>.json   generated stat block
npcs/<id>.toml   profile: faction, attitude, wants, fears, voice, secrets
tables/<id>.*    name, formula, results with ranges
```

Scene text:

```markdown
The gate is shut. A torch gutters above it.

::: gm
Two guards watch from the platform. Sneaking past takes a SNEAKING roll; on a failure
they raise the alarm (fact hall.alarm).
:::
```

`adventure.toml`:

```toml
format = 1                           # the pack format this was written for; solo validate reads it
title = "The Red Tusk Hall"
start = "road"

[factions.orcs]
name = "Red Tusk orcs"
standing = -1                        # -2 hostile .. 2 allied

move_time = { stretch = 1 }          # game time every move takes unless its exit says otherwise

[clocks.dark_ritual]
label    = "The ritual below"
segments = 6
hidden   = true                      # not shown on the player's panel
advance  = ["time:shift", "fact:hall.alarm", "check:demon"]
stop     = ["npc:priest:dead"]       # stops it for good: what it counted down to can't happen now
on_tick  = "omens"                   # table rolled on every tick
at_full  = "ritual_completes"        # scene the GM runs when it fills
# while  = "fact.ritual.begun"       # optional: counts nothing until this holds

[[clocks.dark_ritual.stages]]        # something changes for good at a segment
at    = 4
text  = "The chanting below grows louder."          # what the player notices (shown unless hidden)
note  = "The priest's guards leave the gate: it's unguarded now."   # for the GM only
facts = { "gate.unguarded" = true }                 # set when it's reached
# clock = { other_clock = "+1" }                    # and other clocks moved

[scenes.hall]                        # adds to, or defines, a scene
title = "Chieftain's Hall"
npcs  = ["orc_leader"]
exits = { cellar = "The cellar stairs", gate = "Out through the gate" }
climax = false
source = "p. 12"                     # where it comes from in the book (solo outline shows it)

[scenes.hall.exits.throne_tunnel]    # a gated way: closed until its condition holds
label = "The smugglers' tunnel behind the throne"
when  = "fact.hall.tunnel_found"     # the GM commits this when the hero finds it
time  = { stretch = 1 }              # optional: game time the way takes

[[scenes.hall.branches]]
when = "fact.hall.alarm"
text = "The warband is awake and armed."
```

`npcs/<id>.toml`:

```toml
name = "Grukk Red Tusk"
role = "Chieftain of the Red Tusk orcs"
faction = "orcs"
attitude = "unfriendly"              # hostile, unfriendly, neutral, friendly, allied
wants = "..."
fears = "..."
voice = "..."

[[secrets]]
id = "tunnel"
text = "A smugglers' tunnel runs from behind the throne to the ritual cave."
reveal = "npc.orc_leader.attitude >= friendly"

[stats]                              # only if there's no generated stat block
hp = 16
armor = 2

[skills]
axes = 14

# Monsters also take: ferocity = 2 (two initiative cards: two turns a round), immune = "magic and fire"
# (weapons do nothing; the GM harms it with solo wound).
# A minor NPC can skip the stat block: template = "minion" (or "boss") and attacker = "melee"
# (ranged, sneaky, magic) fight by the solo rules' simple NPCs and NPC attack table, when the
# system pack built from the player's book has them.

# Anyone the hero may fight needs stats.hp and one of these, so `solo fight` can run them:
[attack]                             # a skill roll to hit (d20-under systems)
label = "Battleaxe"
skill = "axes"                       # read from [skills]; or value = 14
damage = "2d8"
# attacks = "tentacle_attacks"       # or: a monster's attack table, rolled instead
```

A monster's attack table is an ordinary table whose results carry `damage`, and `defend = false` for a hit that can't be dodged or parried, `parry = true` for one that can be parried (Dragonbane's monster attacks can't be, unless the book says so), `armor = false` when armor doesn't help. A result without `damage` is an effect for the GM to run (a fear attack, a condition): write what the GM should do in its text.

A table result can finish itself, so the GM gets an answer instead of instructions: `roll = "2d6x10"` rolls its value into the text where it says `{value}`; `choices = [...]` picks one; `then = "treasure"` (or a list) rolls other tables next; `again = true` rolls this one again. When the player's system pack has a `treasure` table (the core set's treasure deck, typed in from their cards), "a random treasure" in a book is `then = "treasure"`, or `solo table treasure` in the GM text.

`tables/<id>.toml`:

```toml
name = "Omens of the ritual"
formula = "1d6"                      # d66, 2d6, 1d6+@stress (@ reads a track) all work
results = [
  { range = [1, 2], text = "..." },
  { range = [3, 6], text = "..." },
]
```

Scenes can also carry what the Book shows the player:

```toml
[scenes.cellar]
dark = true                          # nothing lit, the GM hears "It's dark here"

[[scenes.cellar.voices]]             # the hero's skills speaking up on entering
skill = "spot_hidden"
text = "Chalk on the edge of the crack, still wet: a spiral with an eye in it."
clue = "chalk_spiral"                # optional: a clue the hero gains when it speaks
# when = "not fact.hall.alarm"       # optional: only while this holds
# boons = 1                          # optional
```

A place that asks something of the hero every round (holding their breath under water, keeping their footing on a sinking deck) says so in `each_round = "..."`: the GM reads it in every fight line there, so it isn't forgotten.

A voice is rolled quietly when the hero enters the scene. Only a success reaches the player, so write what the skill notices, in a voice of its own, never what the GM must do. Take them from what the book says a roll would find (SPOT HIDDEN finds...), and keep them to one or two per scene.

A clock with `omen = true` stays hidden, but what its `on_tick` table rolls reaches the player as an omen: write those results as things the hero can feel, never the clock's name.

Heroes that come with the adventure go in `characters/<id>.toml`, in the same shape as a system's pre-made heroes (`packs/dragonbane/characters/ragna.toml`). A pregenerated hero is offered on the New adventure screen. A replacement the story hands the player after a death (a prisoner freed, a survivor found) carries `replacement = true`: it isn't offered at the start, and `solo hero <id>` makes it the hero, taking that NPC out of the cast.

Rules the adventure leans on that the system pack may not have (fear, drowning, cold, scoring) go in `rules/<topic>.md`, found by `solo rule`. Write them in your own words, say which page of the book they stand in for, and never copy a rulebook. Tables that stand in for physical components (treasure cards, a deck) are ordinary tables, marked as stand-ins.

`art.toml` beside `adventure.toml` draws the NPCs in text: `[sprites.<npc id>]` is a small figure for fights (about 4 rows, 10 columns) and `[portraits.<npc id>]` a larger face for the codex (about 10 rows, 20 columns), each as `art = '''...'''`. An NPC without one gets the system pack's generic figure (`sprite = "beast"` in its profile picks another). Don't copy art from the book; draw it in characters.

`adventure.toml` can also set `chaos` (1-9, default 5), the oracle's chaos factor the campaign starts at, and `scene_checks = false` for an adventure that should never have its scenes altered or interrupted. A tight written adventure plays well at 3 or 4.

Conditions (branches, secret reveals) read state with `and`, `or`, `not`, comparisons and `in`:
`npc.<id>.fate`, `npc.<id>.attitude`, `npc.<id>.location`, `faction.<id>`, `promise.<id>`, `fact.<key>`, `clock.<id>`, `scene`, `visited.<scene>`, `pc.<track>`, `pc.conditions`, and the attitude names as numbers (hostile -2 .. allied 2).

Clock triggers: `time:<unit>` (units from the system pack), `fact:<key>` (set to something true), `scene:<id>` (entered), `check:dragon`, `check:demon`, `check:<pool trigger>`, `npc:<id>:<fate>`, `promise:<id>:<status>`, `clock:<id>:full`.

## From a PDF

Read the book, not your memory of it. Start with `solo extract <pdf>`: it writes the text to `~/Games/solo/sources/<book>/`, a file per page and per chapter, with every table as Markdown and as a picture of its page (`tables/`). Read chapter by chapter from `chapters/`. Cite pages as the extract numbers them (the PDF's).

1. Read the whole adventure before writing anything, and write `inventory.toml` in the pack as you go (docs/PACK_FORMAT.md): one item per location, set piece, NPC and creature, table, timer or alarm, puzzle or key, ending, and rule it leans on, each with its pages, `status = "todo"`, and `extract` set to the extract folder. When the pack is written, every item says where it went (`mapped` and `to`) or why it isn't there, and `solo audit --adventure <pack>` passes.
2. Make one scene per location or set piece. Ids are short snake_case. Put read-aloud text first and everything else inside `::: gm`. Keep the book's wording for rules-relevant GM text (rolls, damage, consequences); trim flavor you don't need.
3. Give each scene its exits, the NPCs present and the tables it uses. A way that only opens when something happens (hidden stairs, a locked door, a secret passage) is a gated exit with `when`, never a plain exit the GM is told not to use.
4. Write the GM text so a GM who has never read the book can run it. For every fact a condition reads, the scene where it becomes true says so with the exact commit: `commit {"facts": {"gallery.stairs_open": true}}`. Name the fights with their command (`solo fight skeleton skeleton skeleton`), the rolls with their skill and banes, the tables to roll.
5. Copy tables exactly, with `solo import table <extract>/tables/pNNNN-1.md --out <pack>/tables/<id>.toml` (or a page's roll lines on stdin: `solo import table - ...`); check each against its page's picture. `solo validate` checks that the ranges cover every result the formula can roll, and `solo audit` that every result is on the page it cites. Add monster attack tables' damage and flags by hand.
6. Put stat blocks in `npcs/<id>.toml` under `[stats]` (and `[skills]`). Give every foe an `[attack]` or an `attacks` table, and its ferocity and immunities. A creature the system's bestiary has (an imported rulebook's) is `monster = "<id>"` in the NPC's profile instead: it fights with the book's stat block and attack table, and the profile adds a name, secrets, or a stronger one's hit points.
7. Mark dark places `dark = true`, and add voices where the book gives a skill something to notice.
8. Tag scenes, NPCs and clocks with `source = "p. N"`.

## Official adventures: what to translate

A published adventure is written for a table of players and a human GM. Solo play needs some of it restated in the engine's terms; say what you changed at the top of `adventure.toml`.

- Real-time limits become game time. A clock that advances on time (`time:stretch`), `move_time` so moving costs time, and stages for what the book says happens at a given moment. The GM commits time for long activities; moves spend it by themselves.
- "Two floors a round once it starts" is a clock with `while` (it counts nothing until it starts) that advances on `time:round`.
- Puzzles become gated exits plus the fact the solution sets. The clue can be a voice.
- "The players" becomes the hero. Attacks on everyone nearby hit the hero. Party-sized fights stay as written: the hero can take allies (`solo ally`), and the fight is meant to be hard.
- Replacement characters become `characters/` with `replacement = true`. Pregenerated heroes become `characters/` too.
- Scoring, if any, goes in `rules/scoring.md`, with the facts that count.

## A book of adventures

A book of linked adventures (a starter set's adventure book) is imported one adventure at a time, each its own pack, each playable and play-tested before the next. The hero carries from one to the next with `solo new <next> --character <campaign folder>`, with the skills and gear they earned. Keep ids stable across the book (the same NPC is the same id in every pack), and write each pack's summary for a player who hasn't read the rest. What the world remembers between packs (who lives, promises) isn't carried yet: note in each pack's `adventure.toml` what an earlier adventure could have changed, so it can be carried when the engine does.

## What to encode, and what to leave

Encode only the state that later content depends on: who is alive, who is allied, which promises were made, what is on a countdown, which alarms went off, which ways are open. Leave the rest to the text and the GM. The orc leader's fate matters; the color of his banner doesn't.

For each clock, gate, branch or secret you infer, write down the page or paragraph it came from (`source`).

## Finish

1. `solo validate --system <system pack> --adventure <pack>` until it prints ok, and read what it lists as worth a look (scenes nobody can reach, dead ends, NPCs no scene brings in).
2. `solo outline --adventure <pack>`: the whole pack in one page. Check every gate, stage and branch against the book. Under "Facts the story reads", every fact that no stage sets must be committed somewhere in a scene's GM text; find each one.
3. Play the tricky parts with fixed dice in a test (`tests/test_playtest.py` shows how), and with a real GM: write scenarios for the riskiest scenes (a puzzle, a fight, a timer) in `tests/gm_eval/scenarios/` and run them (`python3 tests/gm_eval/run.py <scenario>`, see tests/gm_eval/README.md). Fix the text where the GM stumbles.
4. Walk the user through every clock, gate, branch and secret you inferred, with its source, and let them correct you. They own the book; you are compiling it for them.

Packs built from books stay private, free adventures included: they live in `~/Games/solo/adventures`, never in this repository, and their contents never go anywhere public. The repository is public, and the publisher's license lets it use a game's terms, not copy its books.
