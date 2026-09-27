"""Portraits and fight figures drawn in text, from the art in the packs.

The system pack's art.toml draws one head per kin with slots for the eyes, brows, mouth,
wounds and age, plus headgear per profession. The hero's state picks the mood, so the
face changes as the story does: angry, scared, hurt, dying, dead. An adventure's art.toml
adds figures and portraits for its own NPCs.

Everything here is presentation. It reads state and never changes it.
"""

from . import combat
from .packs import slug

_EYES, _BROWS = "LR", "lr"
MOOD_ORDER = ("exhausted", "sickly", "dazed", "angry", "scared", "disheartened")


def art(system, adventure, state):
    """What state.json carries for the Book: the hero's portrait, their small figure,
    a figure for every foe in a fight, and a picture for every NPC in the codex."""
    art_s, art_a = system.get("art", {}), adventure.get("art", {})
    pc = state["pc"]
    foes = (state["combat"] or {}).get("foes", {})
    return {
        "portrait": hero(art_s, pc, state),
        "figures": {
            "hero": sprite(art_s, art_a, hero_figure(system, art_s, art_a, pc)),
            "foes": {fid: sprite(art_s, art_a, "fallen") if foe["down"] else npc_sprite(art_s, art_a, adventure, foe["npc"])
                     for fid, foe in foes.items()},
        },
        "faces": {nid: npc_portrait(art_s, art_a, adventure, nid) for nid, npc in state["npcs"].items() if npc["met"]},
    }


# The hero's figure in a fight, by what they fight with best.
_RANGED = {"bows", "crossbows", "slings"}
_MAGIC = {"staves"}


def hero_figure(system, art_s, art_a, pc):
    """The sprite that fights for the hero: a bow for an archer, a staff for a mage, a
    blade and shield otherwise, from the carried weapon they have the best skill with.
    A pack without those figures has a single `hero`."""
    skills = pc.get("skills", {})
    carried = [w for w in combat.kit(system, pc)["weapons"] if w["id"] != "unarmed"]
    carried.sort(key=lambda w: -skills.get(w["skill"], {}).get("value", 0))
    skill = carried[0]["skill"] if carried else ""
    profession = slug(str(pc.get("info", {}).get("profession", "")))
    name = "hero_ranged" if skill in _RANGED else "hero_magic" if skill in _MAGIC or profession == "mage" else "hero"
    known = {**art_s.get("sprites", {}), **art_a.get("sprites", {})}
    return name if name in known else "hero"


def hero(art_s, pc, state):
    """{lines, ink, mood, wounds, tint}. Tint tells the Book how to colour it: normal, hurt,
    grave (dying, dead, badly hurt) or bright (a Dragon). Ink is the same shape as the
    lines, a letter per character for what it is (see INK), so the Book can colour the
    eyes, a wound, the hair and the helmet each their own way."""
    info = {slug(k): slug(str(v)) for k, v in pc.get("info", {}).items()}
    kin = art_s.get("kin", {}).get(info.get("kin", ""))
    if not kin:
        return None
    wounds = wound_level(pc, state)
    moods = art_s.get("moods", {})
    mood = mood_of(pc, state, moods, wounds)
    # An art pack may leave a mood out (no triumph face): the calm one stands in.
    spec = moods.get(mood) or moods.get("calm") or {}
    marks = art_s.get("wounds", {}).get("marks", [" ", "/", "#"])
    age = art_s.get("age", {}).get(info.get("age", ""), " ")
    head, ink = fill(kin["head"], spec, marks[min(wounds, len(marks) - 1)], age, kin.get("ink"))
    gear = art_s.get("gear", {}).get(info.get("profession", ""), {})
    tint = "grave" if mood in ("dead", "dying") or wounds >= 2 else "bright" if mood == "triumph" else "hurt" if wounds else "normal"
    lines, ink = compose(head, gear.get("top"), ink, gear.get("ink"))
    return {"lines": lines, "ink": ink, "mood": mood, "wounds": wounds, "tint": tint}


def mood_of(pc, state, moods, wounds=0):
    if pc.get("dead"):
        return "dead"
    elif pc.get("dying"):
        return "dying"
    held = [c for c in pc.get("conditions", []) if c in moods]
    if held:
        return held[-1]  # the newest condition shows
    last = state.get("last_check")
    if last and last["outcome"].get("dragon") and last["seq"] >= state["seq"] - 2:
        return "triumph"
    return "hurt" if wounds >= 2 and "hurt" in moods else "calm"


def wound_level(pc, state):
    """0 unhurt (above half), 1 at half or less, 2 at a quarter or less, on the track the
    system calls for in fights (hp)."""
    track = pc["tracks"].get((state.get("labels", {}).get("dying") or {}).get("track", "hp")) or next(iter(pc["tracks"].values()), None)
    if not track or not track["max"]:
        return 0
    share = track["value"] / track["max"]
    return 2 if share <= 0.25 else 1 if share <= 0.5 else 0


# What each character of a portrait is, for the Book to colour: e eyes, b brows, m mouth,
# w a wound, a age, h hair (fur, feathers, a beard: the shaded blocks), g headgear, o gold
# (a jewel, a bead), . the line of the face. A space is nothing.
INK = "ebmwahgo."
_HAIR = set("░▒▓@")
_GOLD = set("◆")


def fill(head, mood, wound, age, marked=None):
    """Put a mood into a head: eyes, brows and a four-wide mouth, wound and age marks.
    Returns the lines and their ink. `marked` is the head's own ink, the same shape as the
    head: a letter there says what that stroke is (h hair, o gold), where the shape of a
    character can't (a strand of hair is a / like a jaw is)."""
    eyes, brows, mouth = mood.get("eyes", ["o", "o"]), mood.get("brows", [" ", " "]), mood.get("mouth", "----")
    marked = _lines(marked) if marked else []
    out, inks = [], []
    for number, line in enumerate(_lines(head)):
        given = marked[number] if number < len(marked) else ""
        chars, ink, mouth_at = [], [], 0
        for char in line:
            if char in _EYES:
                chars.append(eyes[_EYES.index(char)])
                ink.append("e")
            elif char in _BROWS:
                chars.append(brows[_BROWS.index(char)])
                ink.append("b")
            elif char == "m":
                chars.append(mouth[mouth_at % len(mouth)])
                ink.append("m")
                mouth_at += 1
            elif char == "w":
                chars.append(wound)
                ink.append("w")
            elif char == "a":
                chars.append(age)
                ink.append("a")
            else:
                chars.append(char)
                mark = given[len(ink)] if len(ink) < len(given) else " "
                ink.append(mark if mark in INK and mark != " " else _ink_of(char))
        out.append("".join(chars))
        inks.append("".join(i if c != " " else " " for c, i in zip(chars, ink)))
    return out, inks


def _ink_of(char, line="."):
    return " " if char == " " else "h" if char in _HAIR else "o" if char in _GOLD else line


def compose(head, gear=None, ink=None, gear_ink=None):
    """Headgear over a head: its last row (the brim) replaces the head's first (the crown),
    centred on it, so a hat sits the same on a wolfkin's ears as on a mallard's bill.
    Without headgear the same rows stay blank, so every portrait is the same height.
    Returns the lines and their ink (a head given without ink is all line)."""
    head = list(head)
    ink = list(ink) if ink is not None else ["".join(_ink_of(c) for c in row) for row in head]
    top = _lines(gear) if gear else []
    marked = _lines(gear_ink) if gear and gear_ink else []
    top_ink = []
    for number, row in enumerate(top):
        given = marked[number] if number < len(marked) else ""
        top_ink.append("".join(" " if c == " " else given[i] if i < len(given) and given[i] in INK and given[i] != " "
                               else "o" if c in _GOLD else "g" for i, c in enumerate(row)))
    height = 3
    left, right = _extent(head[:1])
    if top:
        g_left, g_right = _extent(top[-1:])
        shift = (left + right) // 2 - (g_left + g_right) // 2
        top = [(" " * shift + row) if shift >= 0 else row[-shift:] for row in top]
        top_ink = [(" " * shift + row) if shift >= 0 else row[-shift:] for row in top_ink]
    top = [""] * (height - len(top)) + top
    top_ink = [""] * (height - len(top_ink)) + top_ink
    canvas = top[:-1] + [_merge(row, top[-1] if index == 0 else "") for index, row in enumerate(head)]
    canvas_ink = top_ink[:-1] + [_merge(row, top_ink[-1] if index == 0 else "") for index, row in enumerate(ink)]
    return _tidy(canvas, canvas_ink)


def _merge(row, overlay):
    """The overlay's characters over the row's; a space in the overlay shows the row."""
    width = max(len(row), len(overlay))
    row, overlay = row.ljust(width), overlay.ljust(width)
    return "".join(o if o != " " else r for r, o in zip(row, overlay, strict=True))


def sprite(art_s, art_a, name):
    spec = art_a.get("sprites", {}).get(name) or art_s.get("sprites", {}).get(name)
    return _tidy(_lines(spec["art"]))[0] if spec else []


def npc_sprite(art_s, art_a, adventure, npc_id):
    """An NPC's figure: its own in the adventure's art, the one its profile names
    (`sprite = "beast"`), or a humanoid (a monster when it attacks from a table)."""
    profile = adventure["npcs"].get(npc_id, {})
    for name in (npc_id, profile.get("sprite"), "monster" if profile.get("attacks") else "humanoid"):
        if name and (art_a.get("sprites", {}).get(name) or art_s.get("sprites", {}).get(name)):
            return sprite(art_s, art_a, name)
    return []


def npc_portrait(art_s, art_a, adventure, npc_id):
    spec = art_a.get("portraits", {}).get(npc_id)
    return _tidy(_lines(spec["art"]))[0] if spec else npc_sprite(art_s, art_a, adventure, npc_id)


def _lines(text):
    lines = (text or "").split("\n")
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _extent(lines):
    filled = [line for line in lines if line.strip()]
    if not filled:
        return 0, 0
    return min(len(line) - len(line.lstrip()) for line in filled), max(len(line.rstrip()) for line in filled)


def _tidy(lines, ink=None):
    """Drop the shared left margin and pad every row to the same width; the ink, if any,
    the same way. Returns (lines, ink)."""
    rows = [line.rstrip() for line in lines]
    margin = min((len(r) - len(r.lstrip()) for r in rows if r.strip()), default=0)
    width = max((len(r) - margin for r in rows), default=0)
    rows = [r[margin:].ljust(width) for r in rows]
    inks = [i[margin:margin + width].ljust(width) for i in ink] if ink is not None else None
    return rows, inks
