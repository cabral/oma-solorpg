---
name: solo-campaign
description: Write a campaign pack for the `solo` engine from a player's premise, and write each next mission from what their hero did. Use when the user runs `make campaign` or `make campaign-next`, wants a campaign or adventure generated from a pitch, a premise or a tone, wants the next mission of a generated campaign written, or asks to fix what `solo campaign check` reports.
---

# Writing a generated campaign

The player pitched a campaign (a premise, a tone, a number of missions) and the engine rolled its bones into an adventure pack in `~/Games/solo/adventures/<id>/`. You write the flesh: the prose, the people, the procedures a GM needs. The dice have already had their say, and you keep to what they said.

The generator writes campaigns for games of skills (Dragonbane and its like). A game of moves (Ironsworn, family `action-roll`) is refused with a sentence saying so: its waypoints would have to be written as moves and its oracle's odds, which is on the roadmap (ROADMAP.md, item 6).

Read `docs/PACK_FORMAT.md` in the repository first (every key a pack can hold, and chapters). The `solo-import` skill has the craft of a good pack (scene text, gates, voices, the exact commits a GM needs); this skill is what differs when there is no book.

## What was rolled

`solo campaign new` wrote a pack that already validates and plays:

```
premise.toml          what the player pitched, and the seed. Don't edit it.
rolls.toml            every roll made for the pack, numbered. Never change one.
adventure.toml        the title, the summary, the hub (safe), two factions (locals, rivals), the nemesis's hidden clock (plan) with omens
chapters/mission_1.toml   mission 1: the hub's way in and briefing, three waypoints m1_w1..m1_w3, the heart m1_heart
scenes/*.md           terse prompts: what the dice decided, the commands and commits
npcs/*.toml           the patron, the nemesis, the people and foes of mission 1
tables/omens.toml     what the hero feels when the plan moves
```

Each waypoint rolled what it holds (a way through, someone on the way, a fight, a find, a place that fights back, signs of the enemy), words for what is odd or at stake there, whether it is dark, and its specifics from the system pack: the solo rules' threat for the mission, foes from the bestiary or the simple NPC templates, treasure from the treasure table, inspiration words for wants, fears and secrets. `source = "rolled: #n"` on each scene, NPC, clock and faction says which rolls made it.

Every file you must write says `rolled, not yet written`. `draft = true` in `adventure.toml` keeps the campaign off the New adventure screen, and in a chapter keeps a mission out of a campaign under way.

## Writing it up

1. Read `premise.toml`, `rolls.toml` and `solo outline --adventure <id>` before writing anything. Decide what the campaign is about: who the nemesis is, what their plan is (the rolls for the rivals and the plan), why the patron needs the hero. Then read each rolled part as the answer to a question about this premise. Words like "Trick / Bright / Shell" are read, not quoted: the smugglers trick the lighthouse keepers with false lights.
2. Rename freely: titles, names, factions, places, the campaign's title. Keep every id (scene, NPC, clock, faction, fact): the conventions below and later missions depend on them.
3. Rewrite each scene: read-aloud first, then everything else inside `::: gm`, like an imported adventure. Keep the procedures the prompts give (the roll and its skill, the fight command, the commit on a failure) unless you replace them with better ones, and write every commit exactly.
4. Rewrite the NPCs: a role, wants, fears and a voice of their own, secrets that reveal on a fact or an attitude. Draw them in `art.toml` if you like (`[sprites.<id>]`, `[portraits.<id>]`).
5. Rewrite the omens as things the hero can see or feel, never the clock's name.
6. Write the hub's briefing (the branch in the chapter) so a GM who has read nothing else can run the mission: the goal, the waypoints in order, the threat and when to set it.
7. The summary in `adventure.toml` is the player's own pitch; tighten it if you like, and never spoil.
8. Delete each `rolled, not yet written` line as you finish its file, and the `draft` lines last.

### When to roll and when to choose

Roll when the answer should surprise you, too: who is at the inn, what the ruin holds, how a stranger takes to the hero, what a faction wants. `solo campaign roll <id> <table> --for "what it decides"` rolls a table of the system pack or the adventure (the solo rules' threats, the treasure deck, a random encounter table), `meaning` rolls inspiration words, and dice roll dice (`1d6`). Each goes into `rolls.toml`; cite it where you use it (`source = "rolled: #41"`).

Choose when the campaign needs it to hold together: names, how the pieces connect, what the nemesis's plan is, which clue points where. A roll that doesn't fit the premise gets read harder before it's rejected. If you don't take a roll, give it `note = "why"` in `rolls.toml`; never delete or change one. `solo campaign check` fails on a roll nothing cites and nothing explains.

### What each mission needs to be playable alone

- A way in from the hub, open once the mission before is done (`when = "fact.mission_<n-1>.done"`), and a briefing branch under the same condition.
- A path of waypoints, each with a way on and a way back, each giving the hero something to do: a roll, a person, a fight, a find, a choice. One or two voices per scene, in the voice of the skill.
- A heart that ends it, with the exact commit: `{"facts": {"mission_<n>.done": true}, "chronicle": "..."}`, and after the last mission an `"end"`.
- Every fact a condition reads, committed in the text of the scene where it becomes true (`solo outline` lists them).
- Foes the engine can fight: the simple NPC templates, bestiary monsters (`monster = "<id>"`), or stat blocks from the player's book. Never invent numbers for a system: take them from the system pack.

### The conventions to keep

- The hub is `hub`, marked `safe`. Its GM text keeps the paragraph on what to do when no way into the next mission is listed: the next one hasn't been written yet, so the GM closes the session and tells the player.
- Mission `n` lives in `chapters/mission_<n>.toml`; its scenes are `m<n>_...`; it is done when `mission_<n>.done` is true.
- The factions `locals` and `rivals`, the NPCs `patron` and `nemesis`, and the clock `plan` keep their ids. Its last stage sets `plan.done`, which the last heart reads.

## The next mission

After a session ends a mission, `make campaign-next CAMPAIGN=<campaign folder>` runs `solo campaign next`: it checks that the mission before is done, rolls the next one into `chapters/mission_<n>.toml` (draft), and rolls two of the campaign's threads to come back in it: open consequences and promises, people who remember the hero, people who got away, what word reached a faction, what the player said about their hero. Someone the GM made up in play gets an NPC file with the name and profile the GM gave them.

1. Read what happened: `solo -C <campaign> history`, `solo -C <campaign> resume`, and `solo -C <campaign> recall <words>` for anything you'll bring back. `solo -C <campaign> npc <id>` for each person who comes back.
2. Write the mission as above, around what the dice picked to come back. The mission must pay off something the hero did: a consequence arriving, a promise called in, a person returning with what they remember. Say so in the briefing.
3. Never contradict the campaign. A name, a place, a face the player has read stays as it is. People met in play keep their id and what the GM wrote about them: add to their file (secrets, stats), never change it. Leave attitude, fate, faction and location out of their file: the campaign's log already sets those.
4. Don't touch what is already written and played: earlier chapters, `adventure.toml`'s hub, the scenes the hero has seen. A chapter may add to the hub (its way in, its briefing) and bring new factions; it can't redefine a clock or faction another file holds.
5. Delete the chapter's `draft` line when it's done. Only then does the campaign under way see the new mission; until then the hub has no way into it, and the GM knows to wait.

## Finish

1. `make check-adventure ID=<id>` in the repository until it's clean: `solo validate`, `solo outline` and `solo campaign check`. Read what `validate` lists as worth a look.
2. Play the first mission's riskiest waypoint in your head against `solo outline`: can a GM who has read only this pack run it?
3. Walk the player through the campaign without spoiling what they'll play: the tone, the hub, who asks for help. Tell them what you chose where the dice didn't decide, if they want to know. For a next mission, tell them it's ready.

Generated campaigns are the player's: they live in `~/Games/solo/adventures`, never in this repository. When the rules come from their book, so do the threats, treasure and monsters in the pack.
