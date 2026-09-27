"""The oracle's surprises: random events and meaning words.

The yes/no oracle lives in campaign.py. This module adds what keeps a solo game from
running on rails: a random event when an oracle roll comes up doubles within the chaos
factor, a scene check when the hero enters a scene, and a pair of words for questions a
yes or no can't answer ("what does the priest want?"). The GM interprets; the dice pick.

The word lists are original. An adventure or system pack can replace them with tables
named meaning_action and meaning_subject.
"""

from . import dice

CHAOS_RANGE = (1, 9)

ACTIONS = [
    "abandon", "accuse", "ambush", "arrive", "bargain", "betray", "block", "break",
    "bury", "call", "capture", "change", "chase", "conceal", "corrupt", "decay",
    "deceive", "defend", "delay", "demand", "destroy", "discover", "divide", "escape",
    "expose", "fail", "follow", "gather", "guard", "heal", "hunt", "imprison",
    "inspect", "lose", "mourn", "oppose", "promise", "protect", "pursue", "release",
    "reveal", "ruin", "seek", "steal", "summon", "surrender", "threaten", "trade",
    "wake", "warn",
]

SUBJECTS = [
    "a debt", "a secret", "an old wound", "a stranger", "the dead", "a map", "the weather",
    "a rival", "an oath", "food", "a weapon", "a child", "a message", "blood", "a door",
    "the law", "fire", "a beast", "gold", "a ritual", "an illness", "a home", "the past",
    "a lie", "a leader", "an ally", "a road", "a trap", "faith", "a tool", "fear",
    "a name", "hunger", "a gift", "the river", "a prisoner", "power", "a song",
    "a hiding place", "the gods", "a trail", "family", "a mistake", "darkness", "a ruin",
    "a bargain", "shelter", "a relic", "pride", "the future",
]

# What a random event is about, on a d100. The hero's side of the story is the "thread".
FOCUS = [
    (7, "remote", "Something happens away from the hero that they'll hear about or see the signs of"),
    (28, "npc_acts", "Someone the hero knows acts on their own wants"),
    (35, "new_npc", "Someone new enters the story"),
    (45, "thread_forward", "An open thread moves toward its end"),
    (52, "thread_back", "An open thread slips further away"),
    (55, "thread_closes", "An open thread closes, for good or ill"),
    (67, "pc_trouble", "Trouble for the hero"),
    (75, "pc_fortune", "A stroke of luck for the hero"),
    (83, "ambiguous", "Something strange that could go either way"),
    (92, "npc_trouble", "Trouble for someone the hero knows"),
    (100, "npc_fortune", "Luck for someone the hero knows"),
]

_ABOUT_NPC = {"npc_acts", "npc_trouble", "npc_fortune"}
_ABOUT_THREAD = {"thread_forward", "thread_back", "thread_closes"}


def is_event(roll, chaos):
    """A d100 roll of 11, 22 ... 99 is an event when its digit is within the chaos factor."""
    return roll % 11 == 0 and roll // 11 <= chaos


def random_event(state, tables, rng=None):
    """What the event is about, who or what it touches (picked from the tracked state so it
    lands on this story), and two words to read it by."""
    roll = dice.roll("1d100", rng)["total"]
    focus_id = next(fid for top, fid, _ in FOCUS if roll <= top)
    people = [n["name"] for n in state["npcs"].values() if n["met"] and n["fate"] == "alive"]
    if focus_id in _ABOUT_NPC and not people:
        # Nobody known yet: the event brings someone in instead.
        focus_id = "new_npc"
    text = next(text for _, fid, text in FOCUS if fid == focus_id)
    event = {"roll": roll, "focus": focus_id, "text": text}
    if focus_id in _ABOUT_NPC:
        event["about"] = _pick(people, rng)
    elif focus_id in _ABOUT_THREAD:
        threads = [f"promise {pid}: {p['terms']}" for pid, p in state["promises"].items() if p["status"] == "open"]
        threads += [f"clue {clue}" for clue in state["clues"]]
        event["about"] = _pick(threads, rng) or "the hero's current goal"
    event["meaning"] = meaning(tables, rng)
    return event


def scene_check(chaos, rng=None):
    """Entering a scene: a d10 within the chaos factor changes it. Odd, the scene is
    altered (one detail differs from what the hero expects); even, it is interrupted
    by a random event."""
    roll = dice.roll("1d10", rng)["total"]
    if roll > chaos:
        result = "expected"
    elif roll % 2:
        result = "altered"
    else:
        result = "interrupted"
    return {"roll": roll, "result": result}


def meaning(tables, rng=None):
    """An action and a subject. Pack tables named meaning_action / meaning_subject win."""
    return [_word(tables.get("meaning_action"), ACTIONS, rng), _word(tables.get("meaning_subject"), SUBJECTS, rng)]


def describe_event(event):
    about = f" ({event['about']})" if event.get("about") else ""
    return f"{event['text']}{about}: {' / '.join(event['meaning'])}"


def _word(table, fallback, rng):
    if table:
        total = dice.roll(table["formula"], rng)["total"]
        hit = next((r for r in table.get("results", []) if r["range"][0] <= total <= r["range"][1]), None)
        if hit:
            return hit.get("text", "")
    return fallback[dice.pick(len(fallback), rng) - 1]


def _pick(options, rng):
    return options[dice.pick(len(options), rng) - 1] if len(options) > 1 else (options[0] if options else None)
