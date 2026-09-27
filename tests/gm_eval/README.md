# GM play tests

The unit tests check the engine. These check the game master: a real agent runs an adventure through `solo gm turn`, exactly as the Book does, and the harness watches whether it holds the story together.

```bash
python3 tests/gm_eval/run.py red-tusk-opening              # one scenario
python3 tests/gm_eval/run.py                               # all of them
python3 tests/gm_eval/run.py red-tusk-memory --model claude-haiku-4-5-20251001 --turns 6
python3 tests/gm_eval/run.py red-tusk-cave-fight --no-judge # skip the review
python3 tests/gm_eval/run.py red-tusk-opening --effort low  # the GM's effort level (default: the normal pace's, medium)
```

It needs `claude` on PATH (or `--agent codex`), the Dragonbane rules built from your book (`make rules`: runs see your own `~/Games/solo` packs, and play in a throwaway home), and costs real model calls: a short scenario is a few minutes, a long run with an agent player half an hour or more. Each run writes a folder under `runs/` (git-ignored):

- `report.md`: the verdict. Expectations met or missed, problems found in code, refused commands, the judge's scores and issues, a line per turn.
- `transcript.md`: every message, with the engine's events between them (hidden ones marked).
- `trace.jsonl`: every `solo` command the GM ran, refused ones with the error (`SOLO_TRACE`).
- `campaign/`: the campaign itself. `solo -C <run>/campaign log -n 50` or `scene` to look around.

Every run also adds a line to `results.tsv` beside this file, which is checked in: the commit, the model and its effort level, the median seconds per turn, `solo` commands and model calls per turn, refused commands, the cost, the judge's six scores and the expectations met. It is how a change to the GM's instructions or the Book's prompt shows whether it made turns faster, cheaper or better. Claude Code reports model calls and cost; Codex reports neither. Under Codex's sandbox the trace file outside the campaign folder may not be writable, so its command counts can read low.

## What is checked

In code, after every GM message:

- Bookkeeping in the narration: `::: gm` fences, `solo` commands, JSON, engine ids (`hall.alarm`, `orc_leader`), Markdown headings.
- A message that doesn't end with a question or a prompt, or runs past 400 words.
- Spoilers: each scenario's `[[forbid]]` words, until their `unless` condition holds.
- Expectations: each `[[expect]]` condition (the engine's own condition language, read against the campaign state), or event that must have happened (a fortune-chart question, a search), and the turn it first held.

Over the whole run: commands the engine refused, moves forced past the exits, fight rounds where the hero attacked and no foe struck back, and GM messages recorded twice in a row (the Book would show them twice).

Then a judge (a tool-less agent) reads the adventure's text for the scenes reached and the whole transcript with its events, and scores rules, adventure, state, secrecy, narration and agency from 1 to 5, citing turns.

## Scenarios

`scenarios/<name>.toml`:

```toml
about = "What this tests, for the judge and for you."
adventure = "red-tusk"
character = "ragna"                 # pre-made id, choices ("human thief"), or a file
max_turns = 8
setup = [["move", "gate"]]         # solo commands run before the GM opens (start partway in)
fresh_session_at = [5]             # drop the agent's session before these turns: a new one must resume from the campaign

[player]
mode = "scripted"                  # the lines, in order
lines = ["I look at the carved tusk on the gate.", "..."]
# mode = "agent"                   # or a second agent plays toward a goal, seeing only what a player sees
# goal = "Find out why the orcs have grown bold, and live."
# persona = "Careful, curious, plays in character."
# model = "claude-haiku-4-5-20251001"

[[expect]]
when = "visited.gate"               # any condition: fact., visited., npc.<id>.fate, promise., clock., pc.hp ...
why = "the GM moves the hero up the hill"
by_turn = 5

[[expect]]
event = "search"                   # or an event happened: an event type, a table's id, a flag, a commit key ("consequence"), or "fortune"

[[forbid]]
text = "Deep Mother"               # a regular expression
unless = "visited.final_battle"
```

Scripted players test a specific part the same way every time (the GM's dice still vary). Agent players test the long haul: whether the GM keeps the clocks, the gates and the facts straight over many turns and lost sessions.

When a new adventure is imported, write scenarios for its riskiest parts (a puzzle gate, a fight with a strange monster, a timer) before playing it for real.
