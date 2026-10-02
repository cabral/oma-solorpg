"""An adventure book's places as scenes and its people as NPCs.

The Dragonbane adventures are set out one way: a chapter for each site, a numbered section for each place in it (the words to read aloud set in
semibold italic, then what there is to find as bullets, then the ways on as bullets named for a direction), and under a place the people and monsters
there, each with a stat block. This reads that into the parts of an adventure pack: `[scenes.<id>]` with its exits, scenes/<id>.md, npcs/<id>.toml and
the tables the monsters' attacks and the site's random events are.

What the book leaves to its reader stays with the GM: a way the text calls locked, blocked or hidden is a gated exit the GM opens by committing a fact (the
scene says which), and a person with no stat block is a profile with no stats. The recipe says each place it had to choose.
"""

import re
from itertools import groupby

from .. import packs
from ..sections import paragraphs
from ..tomlwrite import Inline
from . import dice, read
from .dragonbane_core import bestiary
from .dragonbane_core.tables import _table

_NUMBERED = re.compile(r"^(\d+[A-Za-z]?)\.\s+(.+)$")
_PAIR = re.compile(r"^(\d+[A-Z]) & (\d+[A-Z])\s+(.+)$")
_DIRECTION = r"(?:NORTH|SOUTH|EAST|WEST|NORTHEAST|NORTHWEST|SOUTHEAST|SOUTHWEST|UP|DOWN)"
_WAY = re.compile(rf"^✦\s*({_DIRECTION}(?:,\s*{_DIRECTION})*):\s*(.*)$", re.S)
_BULLET = re.compile(r"^✦\s*([^:]{1,60}?):\s*(.*)$", re.S)
_PASSAGE = re.compile(r"portcullis|door|gate|trapdoor|hatch|passage|portal|opening|stairs|staircase|tunnel|bridge", re.I)
_SHUT = re.compile(r"\b(locked|blocked|barred|sealed|hidden|secret|concealed)\b", re.I)
_REFERENCE = re.compile(r"#(\d+[A-Za-z]?)")
_PERSON = re.compile(r"^(NPCs?|Monsters?|Animals?):\s*(.+)$")
_FIELD = re.compile(r"(Movement|Mov\.|Damage Bonus(?: [A-Z]{3})?|Dmg Bonus(?: [A-Z]{3})?|HP|WP|Armor|Skills|Spells|Abilities(?: [A-Z][a-z]+)?|Typical Weapons?|Weapons?|Attack|"
                    r"Gear(?: Adventurer \d| [A-Z][a-z]+)?|Inventory):\s*")
_WEAPON = re.compile(r"([A-Za-z][A-Za-z ]*?)\s*\(skill level (\d+), damage (\d*D\d+)")
_RULEBOOK = re.compile(r"[^.]*\bRulebook\b[^.]*\.?")
_INSTRUCTION = r"Read (?:the following|this)(?: text)? aloud(?: to the players)?:?"


class Place:
    """A numbered section of an adventure chapter: its numbers (one, or two for "6A & 6B"), its name, and the id of the scene it becomes."""

    def __init__(self, section, prefix):
        pair, one = _PAIR.match(section.title), _NUMBERED.match(section.title)
        self.section = section
        self.keys = [pair.group(1), pair.group(2)] if pair else [one.group(1)] if one else []
        self.name = pair.group(3) if pair else one.group(2) if one else section.title
        self.id = f"{prefix}_{packs.slug(self.name)}"


def places(chapter, prefix):
    """The places of a chapter, in the book's order: the numbered sections under its "Locations"."""
    return [Place(section, prefix) for section in chapter.find("Locations").children if _NUMBERED.match(section.title) or _PAIR.match(section.title)]


def clean(title):
    """A bookmark's title without the words that say what sort of section it is ("Sidebar: Leaving the Mound?")."""
    return re.sub(r"^(Sidebar|Monsters?|NPCs?|Animals?|Map|Table):\s*", "", title)


# What the words are -----------------------------------------------------------------------------

_WHITE = 16777215


def _aloud(line):
    return "SemiboldIt" in line["font"] and line["size"] >= 9.5


def after_title(lines):
    """The lines without headings (the one that starts them, and the next section's, which a bookmark placed below it leaves at the end) and without the white labels a
    map is lettered with."""
    return [line for line in lines if line.get("color") != _WHITE and not (line["font"].startswith("Hideout") and line["size"] >= 10)]


def blocks(book, lines):
    """The words of some lines, in order, as (style, paragraph): "aloud" for what the book sets to be read out, "bullet" for a ✦ entry, "text" for the rest. What a map
    leaves among the words (a lone number, half a word at a line's end) is dropped."""
    out = []
    for aloud, run in groupby(after_title(lines), key=_aloud):
        run = list(run)
        found = paragraphs(run, book.glue).split("\n\n")
        # A run that ends at a soft hyphen is cut in a word: its last paragraph says so, for `mend`.
        found[-1] += "\u00ad" if run[-1]["text"].rstrip().endswith("\u00ad") else ""
        for paragraph in found:
            junk = (re.fullmatch(r"[\d\s,.]*", paragraph) or re.fullmatch(_INSTRUCTION, paragraph)
                    or (len(paragraph) < 14 and not paragraph.startswith("✦") and not re.search(r"[.!?:\"”]$", paragraph)))
            if paragraph and not junk:
                out.append(("aloud" if aloud else "bullet" if paragraph.startswith("✦") else "text", paragraph))
    return out


def gm_text(items):
    """Paragraphs for a GM fence: ✦ entries as a list, the rest as paragraphs."""
    out = []
    for style, text in items:
        found = _BULLET.match(text) if style == "bullet" else None
        line = f"- **{found.group(1)}:** {found.group(2)}" if found else f"- {text.lstrip('✦').strip()}" if style == "bullet" else text
        if style == "bullet" and out and out[-1].startswith("- "):
            out[-1] += f"\n{line}"
        else:
            out.append(line)
    return "\n\n".join(out)


def _first_sentence(text, limit=110):
    sentence = re.split(r"(?<=[.!?])\s", text.strip(), maxsplit=1)[0]
    return sentence if len(sentence) <= limit else sentence[:limit].rsplit(" ", 1)[0] + "…"


# People ------------------------------------------------------------------------------------------

def is_person(section):
    return _PERSON.match(section.title) is not None


def _lines_of(section):
    """A person's lines: the section's own and its Statblock's, in page order."""
    return sorted([*section.lines(own=True), *(line for child in section.children if child.title.startswith("Statblock") for line in child.lines(own=True))], key=lambda line: line["n"])


def _split(section):
    """(what is the person's, what is the place's): a ✦ entry starts what the place goes on with after the person."""
    lines = _lines_of(section)
    at = next((at for at, line in enumerate(lines) if line["text"].lstrip().startswith("✦")), len(lines))
    return lines[:at], lines[at:]


def leftover(section):
    return _split(section)[1]


class _Lines:
    """The lines of a table read from the middle of a section, for the readers that take a section."""

    def __init__(self, section, lines):
        self.page, self._lines = section.page, lines

    def lines(self, own=False):
        return self._lines


def _fields(text):
    found = list(_FIELD.finditer(text))
    return {match.group(1): text[match.end():after.start() if after else len(text)].strip() for match, after in zip(found, [*found[1:], None])}


def person(pack, section, prefix, ids):
    """A person or a monster of the book as npcs/<id>.toml (and the table of a monster's attacks): the stat block's numbers, the one weapon the engine fights with, and
    everything else the book says as the description. A monster the book gives by reference to the rulebook is that monster, with the numbers the book changes. Returns the
    NPC's id."""
    name = clean(section.title)
    npc_id = packs.slug(name)
    npc_id = npc_id if npc_id not in ids else f"{prefix}_{npc_id}"
    ids.add(npc_id)
    monster = section.title.startswith(("Monster", "Animal"))
    description, flat, table = _read(pack.book, section)
    entry = {"name": name, "role": _first_sentence(description) if description else "A monster" if monster else "A person", **({"description": description} if description else {}),
             "attitude": "hostile" if monster else "neutral", **({"many": True} if section.title.startswith(("NPCs:", "Monsters:", "Animals:")) else {})}
    made = []
    fields = _fields(flat)
    hp = re.search(bestiary._NUMBERS["hp"], flat) or re.match(r"(\d+)", fields.get("HP", ""))
    if hp:
        made = _fighter(pack, section, entry, npc_id, flat, fields, table, int(hp.group(1)))
    else:
        _by_reference(pack, section, entry, npc_id, description)
    entry["source"] = f"p. {section.page}"
    pack.toml(f"npcs/{npc_id}.toml", entry)
    pack.item(f"npc_{npc_id}", name, "creature" if monster else "npc", section.pages, [f"npcs/{npc_id}", *(f"tables/{table_id}" for table_id in made)])
    return npc_id


def _read(book, section):
    """(what the book says of a person, their stat block as one line of words, the lines of their table of attacks): a stat block is set in a colour of its own, which is how it
    is told from the words, and the table starts at its header."""
    mine, rest = _split(section)
    start = next((line for line in mine if re.match(r"(Ferocity|Movement|Mov\.)", line["text"].strip())), None)
    marker = next((line for line in mine if re.match(r"D\d+\s+ATTACK", line["text"].strip())), None)
    cut = marker["n"] if marker else float("inf")
    stat = {line["n"] for line in mine if start and line.get("color") == start.get("color")}
    said = [line for line in mine if line["n"] not in stat and line["n"] < cut and line["text"].strip().upper() != "MONSTER ATTACKS"]
    description = " ".join(text for style, text in blocks(book, said) if style != "bullet")
    bullets = blocks(book, rest)
    if not description and bullets and bullets[0][0] == "bullet":
        description = re.sub(r"^✦[^:]{1,60}:\s*", "", bullets[0][1])
    flat = " ".join(line["text"] for line in mine if line["n"] in stat and line["n"] < cut)
    own = next((child.lines(own=True) for child in section.children if child.title == "Monster Attacks"), None) or ([line for line in mine if line["n"] >= cut] if marker else [])
    return description, re.sub(r"\s+", " ", flat.replace("\u00ad", "")), own


def _fighter(pack, section, entry, npc_id, flat, fields, table, hp):
    """What a person needs to fight, added to their entry: stats, a weapon or a table of attacks, skills, and the words of their abilities and gear. Returns the tables made."""
    numbers = {key: re.search(pattern, flat) for key, pattern in bestiary._NUMBERS.items()}
    weapon = _weapon(fields)
    entry["stats"] = {"hp": hp, "armor": _armor(numbers["armor"].group(1) if numbers["armor"] else _armor_words(flat))}
    if numbers["ferocity"]:
        entry["stats"]["ferocity"] = int(numbers["ferocity"].group(1))
    elif entry["attitude"] == "hostile":
        pack.note(f"{entry['name']} (p. {section.page}): its ferocity isn't a number in the book, so the engine's default (one card) is left")
    moves = numbers["movement"] or re.match(r"(\d+)", fields.get("Mov.", fields.get("Movement", "")))
    if moves:
        entry["stats"]["movement"] = int(moves.group(1))
    made = []
    if table:
        entry["attacks"] = f"{npc_id}_attacks"
        _, made = bestiary._attacks(pack, _Lines(section, table), entry["attacks"], f"{entry['name']} attacks", weapon[2] if weapon else None)
    elif weapon:
        bonus = re.search(r"\+(\d*D\d+)", " ".join(value for label, value in fields.items() if label.startswith(("Damage Bonus", "Dmg Bonus"))))
        entry["attack"] = Inline({"label": weapon[0], "value": weapon[1], "damage": read.roll(weapon[2]), **({"bonus": read.roll(bonus.group(1))} if bonus else {})})
    if fields.get("Skills"):
        entry["skills"] = bestiary._skills(fields["Skills"])
    said = [f"{label}: {fields[label]}." for label in ("Abilities", "Spells", "Typical Weapon", "Typical Weapons", "Weapons", "Weapon", "Attack", "Gear", "Inventory") if label in fields]
    said += [f"WP {fields['WP']}."] if "WP" in fields else []
    if said:
        entry["description"] = " ".join([entry.get("description", ""), *said]).strip()
    return made


def _by_reference(pack, section, entry, npc_id, description):
    """A person with no stat block: the rulebook's monster when the book says whose stats they have, else a profile with no stats, and a note either way."""
    name = entry["name"]
    spoken = re.sub(r"\s+", " ", f"{description} " + " ".join(line["text"] for line in _split(section)[0]).replace("\u00ad", ""))
    ref, candidates = _bestiary(pack.system_pack, name, spoken)
    if ref:
        entry["monster"] = ref
        pack.note(f"{name} (p. {section.page}): the book gives its stats by reference to the rulebook's: it is the rulebook's {ref}")
        over = {key: int(found.group(1)) for key, pattern in (("armor", r"armor rating (\d+)"), ("hp", r"\bwith (\d+) HP")) for found in [re.search(pattern, spoken, re.I)] if found}
        if over:
            entry["stats"] = over
    elif candidates:
        pack.note(f"{name} (p. {section.page}): the book says the rulebook has its stats, and more than one entry fits ({', '.join(candidates)}): pick one with monster = \"<id>\" in npcs/{npc_id}.toml, or the GM narrates it")
    else:
        pack.note(f"{name} (p. {section.page}): no stat block in the book, so no stats here: the GM narrates it, or gives it stats")


_STOP = {"the", "of", "a", "in", "as", "per", "but", "like", "stat", "have", "with", "page", "rulebook", "for", "see"}


def _singular(word):
    return word[:-3] + "y" if word.endswith("ies") else word.rstrip("s")


def _words(text):
    return {_singular(word) for word in re.findall(r"[a-z]+", text.lower())}


def _bestiary(system, name, text):
    """(the rulebook's monster a person has the stats of, the entries that might be): only for a person whose words send the reader to the Rulebook. Their name says which
    ("Okvid the Troll"), or else the sentence that sends the reader (and the one before it) names it. An entry fits when all its
    words are there; the one with the most words wins, and a tie is no answer."""
    sentences = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", text))
    near = " ".join(" ".join(sentences[max(0, at - 1):at + 1]) for at, sentence in enumerate(sentences) if "Rulebook" in sentence)
    entries = {id_: set(map(_singular, id_.split("_"))) for id_ in system.get("bestiary", {})}
    for said in (_words(name), _words(near)) if near else ():
        whole = [id_ for id_, words in entries.items() if words <= said]
        best = [id_ for id_ in whole if len(entries[id_]) == max(len(entries[other]) for other in whole)]
        if len(best) == 1:
            return best[0], best
    said = _words(name) | _words(near)
    some = [id_ for id_, words in entries.items() if near and words & said - _STOP]
    return (some[0], some) if len(some) == 1 else (None, some)


def _armor_words(flat):
    """What a stat block says after "Armor:" up to its next field. The words of a column beside it can come in the middle ("Studded leather WP: 14 and open helmet (3)")."""
    found = re.search(r"Armor:\s*(.*?)(?=\s*(?:Skills|Abilities|Spells|Weapons?|Typical Weapons?|Gear|Inventory|Attack):|$)", flat)
    return re.sub(r"\b[A-Z]{2}: \d+", "", found.group(1)) if found else ""


def _armor(text):
    """The armor rating a stat block gives: "Leather (1)", "4", "—"."""
    found = re.search(r"\((\d+)\)", text) or re.match(r"^(\d+)$", text.strip())
    return int(found.group(1)) if found else 0


def _weapon(fields):
    """(label, skill, damage) of the first weapon a stat block names."""
    found = _WEAPON.search(" ".join(value for label, value in fields.items() if label.startswith(("Typical Weapon", "Weapon", "Attack", "Gear"))))
    return (found.group(1).strip().capitalize(), int(found.group(2)), found.group(3)) if found else None


# Places ------------------------------------------------------------------------------------------

def ways(place, by_key):
    """Where a place leads: [(target place, label, shut)], from the bullets named for a direction, and the bullets named for a door or a passage that give a
    place's number. A way the text calls locked, blocked, barred or hidden is `shut`: the GM opens it."""
    found = {}
    for style, paragraph in blocks(place.section.book, place.section.lines(own=True)):
        if style != "bullet":
            continue
        way, bullet = _WAY.match(paragraph), _BULLET.match(paragraph)
        through = way or (bullet and _PASSAGE.search(bullet.group(1)))
        body = (way or bullet).group(2) if (way or bullet) else ""
        for key in dict.fromkeys(_REFERENCE.findall(body)):
            target = by_key.get(key.lower())
            if through and target is not None and target is not place and target.id not in found:
                lead = way.group(1).capitalize() if way else bullet.group(1)
                found[target.id] = (target, f"{lead}: {_first_sentence(_without_references(body))}".rstrip(" ,;"), bool(_SHUT.search(paragraph)))
    return list(found.values())


def mend(book, items):
    """A paragraph a column or a page cut off in the middle of a word or a sentence has the rest of it elsewhere (a sidebar stands between them in the page's order, and
    the rest comes first or last): a paragraph that begins in lower case is joined to the nearest one that stops without a full stop, with no space where the first half is
    not a word the book spells."""
    out = list(items)
    at = 0
    while at < len(out):
        style, text = out[at]
        cut = [i for i in range(len(out)) if i != at and out[i][0] != "aloud" and re.search(r"[\w\u00ad]$", out[i][1])]
        head = next((i for i in reversed(cut) if i < at), None)
        head = head if head is not None else next((i for i in cut if i > at), None)
        if style == "text" and text[:1].islower() and head is not None:
            half = out[head][1]
            out[head] = (out[head][0], (half[:-1] if half.endswith("\u00ad") else f"{half} ") + text)
            del out[at]
            at -= at < head
        else:
            at += 1
    return out


def _without_references(text):
    """A bullet's words without the places it gives by number: "(#4)" and "#4" go, and the space before them."""
    return re.sub(r"\s+([.,;:])", r"\1", re.sub(r"\s*\([^()]*#\d+[A-Za-z]?[^()]*\)|\s*#\d+[A-Za-z]?", "", text)).strip()


def table_pages(pack):
    """{printed page: [ids]} of the tables made so far, for the words that send the reader to "the table on page 34"."""
    book = pack.book
    found = {}
    for number, table_id in pack.facts.get("tables_made", {}).items():
        found.setdefault(book.printed(book.sections[number].page), []).append(table_id)
    return found


def _name_tables(paragraph, pages):
    """A paragraph that sends the reader to a table of the adventure by its page ("the table on page 34", not "... in the Rulebook") says which: `solo table <id>`. A page with
    two tables is the one named like the event the paragraph is about, else nobody's."""
    def named(found):
        ids = pages.get(int(found.group(2)), [])
        pick = ids if len(ids) == 1 else [i for i in ids if re.search(r"random event", paragraph, re.I) and i.endswith("random_events")]
        return f"{found.group(1)} (solo table {pick[0]})" if len(pick) == 1 else found.group(0)
    return re.sub(r"(table on page (\d+))(?! in the Rulebook)", named, paragraph)


def scene_file(blocks_, shut, titles, pages=None):
    """scenes/<id>.md: what to read aloud, then the rest inside a GM fence, a place's number turned into its name where the text refers to it and a table sent to by its page
    named."""
    blocks_ = [(style, _name_tables(text, pages or {})) for style, text in blocks_]
    aloud = [text for style, text in blocks_ if style == "aloud"]
    rest = gm_text([item for item in blocks_ if item[0] != "aloud"] + [("text", f"Shut: {label.rstrip('.')}. When the heroes get through, commit {{\"facts\": {{\"{key}\": true}}}}.") for _, label, key in shut])
    text = ("\n\n".join(aloud) + ("\n\n" if aloud else "") + (f"::: gm\n{rest}\n:::" if rest else "")).replace("\u00ad", "")
    return re.sub(r"#(\d+[A-Za-z]?)", lambda found: f"#{found.group(1)} {titles[found.group(1).lower()]}" if found.group(1).lower() in titles else found.group(0), text)


def child_blocks(pack, section):
    """The words of what stands under a place that isn't a person, a table made or a map (a sidebar, a scene within it), each with its heading, to follow the place's own."""
    out = []
    for child in section.children:
        if is_person(child) or child.number in pack.facts.get("tables_made", {}) or child.title.startswith(("Map:", "Statblock")) or child.title == "Monster Attacks":
            continue
        out.append(("text", f"**{clean(child.title)}**"))
        out += blocks(pack.book, child.lines(own=True)) + child_blocks(pack, child)
    return out


def _within(section):
    return {part.number for part in (section, *section.subtree())}


def background(pack, section, prefix, ids):
    """What a chapter says before its places: (the words, the people and monsters under it), for the first scene to hold."""
    book = pack.book
    words = [("text", f"**{clean(section.title)}**"), *blocks(book, section.lines(own=True)), *child_blocks(pack, section)]
    return words, [person(pack, child, prefix, ids) for child in _persons(section)]


def _linked(first, plan):
    """The ids of the places that can be reached from the first by the exits planned so far."""
    seen, todo = {first.id}, [first.id]
    while todo:
        for target in plan[todo.pop()][0]:
            if target in plan and target not in seen:
                seen.add(target)
                todo.append(target)
    return seen


def _plan(pack, chapter, found, hub):
    """{place id: (its exits, the ways that are shut)}: the ways the book gives, and for each place none of them leads to, a way from the place before it in the book and one
    back, the recipe saying so."""
    by_key = {key.lower(): place for place in found for key in place.keys}
    plan = {}
    for place in found:
        exits, shut = {}, []
        for target, label, closed in ways(place, by_key) + _map_ways(place, by_key) + _hub_ways(place, found, hub):
            if target.id not in exits:
                fact = f"{place.id}.to_{packs.slug(target.name)}"
                exits[target.id] = Inline({"label": label, "when": f"fact.{fact}"}) if closed else label
                shut += [(target, label, fact)] if closed else []
        plan[place.id] = (exits, shut)
    lost = []
    for before, place in zip(found, found[1:]):
        if place.id not in _linked(found[0], plan):
            plan[before.id][0][place.id] = f"To {place.name}"
            plan[place.id][0].setdefault(before.id, f"Back to {before.name}")
            lost.append(place.name)
    if lost:
        pack.note(f"{clean(chapter.title)}: the book's text gives no way on to {', '.join(lost)}, so each is linked from the place before it in the book, and back (change them if the map says otherwise)")
    return plan


def _place_lines(section):
    """A place's own lines, and the lines of its maps' bookmarks that aren't labels: a map's bookmark sits above the words set beside the map, so the lines of a list in the
    middle of the place's text can be left in it."""
    maps = [line for child in section.children if child.title.startswith("Map:") for line in child.lines()]
    return sorted([*section.lines(own=True), *maps], key=lambda line: line["n"])


def _scene_words(pack, section):
    """The words of a place: its own, what stands under it (sidebars), and what its people's sections hold that goes on with the place."""
    book = pack.book
    return (blocks(book, _place_lines(section)) + child_blocks(pack, section)
            + [item for child in section.children if is_person(child) for item in blocks(book, leftover(child))])


def _each_round(words):
    """What a place asks of the hero every round, in the book's words: the sentences of its bullets that say "each round" or "every round", for the GM to read in every fight
    there."""
    sentences = [re.sub(r"^✦[^:]{1,60}:\s*", "", sentence) for style, text in words if style != "aloud" for sentence in re.split(r"(?<=[.!?])\s+", text)
                 if re.search(r"\b(?:each|every|per) round\b", sentence, re.I)]
    return " ".join(sentences[:2])


def scenes(pack, chapter_id, chapter, prefix, hub=None, situation=True):
    """The scenes of one chapter of places: a scene, its file and its inventory item for each, the people and monsters under them, the ways on, the tables (those not
    under a place on every scene of the chapter), and the chapter's situation on its first. `hub` is the number of the place the others all open on and out of (a
    village). Returns the places."""
    book, spec = pack.book, pack.chapter(chapter_id)
    spec.setdefault("scenes", {})
    found = places(chapter, prefix)
    titles = {key.lower(): place.name for place in found for key in place.keys}
    ids = pack.facts.setdefault("npc_ids", set())
    made = tables_under(pack, chapter, prefix)
    wide = [table_id for number, table_id in made.items() if not any(number in _within(place.section) for place in found)]
    opening = next((child for child in chapter.children if child.title == "The Situation"), None) if situation else None
    first, crowd = background(pack, opening, prefix, ids) if opening else ([], [])
    plan = _plan(pack, chapter, found, hub)
    for number, place in enumerate(found):
        section, (exits, shut) = place.section, plan[place.id]
        words = _scene_words(pack, section) + (first if number == 0 else [])
        people = [person(pack, child, prefix, ids) for child in _persons(section)] + (crowd if number == 0 else [])
        here = _within(section)
        scene = {"title": place.name, "source": f"p. {section.page}"}
        if people:
            scene["npcs"] = people
        if wide or any(table in here for table in made):
            scene["tables"] = [*wide, *(table_id for table, table_id in made.items() if table in here)]
        if exits:
            scene["exits"] = Inline(exits)
        if _each_round(words):
            scene["each_round"] = _each_round(words)
        spec["scenes"][place.id] = scene
        pack.file(f"scenes/{place.id}.md", scene_file(mend(book, words), shut, titles, table_pages(pack)))
        pack.item(f"place_{place.id}", place.name, "place", [*section.pages, *(opening.pages if opening and number == 0 else [])], [f"scenes/{place.id}"])
        if shut:
            pack.note(f"{place.name} (p. {section.page}): " + "; ".join(f"the way to {target.name} is shut by what the text says, so it is a gated exit" for target, _, _ in shut))
    return found


def scene_of(pack, chapter_id, scene_id, title, sections, prefix, first=(), after=None, tables=(), crowd=()):
    """One scene from one or more sections of a chapter that aren't numbered places (an opening, an arrival, a conclusion): their words in order, each under its title when
    there are several, their people, `first` more words before them, `tables` and `crowd` (people more). It is one scene because it is one place and one stretch of play: the
    story goes on in it without the hero going anywhere, and a GM that isn't asked to move would never see the rest. `after` is (the id, the title) of the scene it leads on to.
    Returns the scene's id."""
    book, spec = pack.book, pack.chapter(chapter_id)
    spec.setdefault("scenes", {})
    ids = pack.facts.setdefault("npc_ids", set())
    words = list(first)
    for section in sections:
        words += ([("text", f"**{clean(section.title)}**")] if len(sections) > 1 else []) + _scene_words(pack, section)
    people = [person(pack, child, prefix, ids) for section in sections for child in _persons(section)] + list(crowd)
    spec["scenes"][scene_id] = {"title": title, "source": f"p. {sections[0].page}", **({"npcs": people} if people else {}), **({"tables": list(tables)} if tables else {}),
                                **({"exits": Inline({after[0]: f"Onward, to {after[1]}"})} if after else {})}
    pack.file(f"scenes/{scene_id}.md", scene_file(mend(book, words), [], {}, table_pages(pack)))
    pack.item(f"place_{scene_id}", title, "place", sorted({page for section in sections for page in section.pages}), [f"scenes/{scene_id}"])
    return scene_id


def _persons(section):
    """The people and monsters under a place, however deep in its sidebars."""
    return [child for child in section.subtree() if is_person(child)]


def _map_ways(place, by_key):
    """The ways a place's map gives, as the labels it is lettered with: "To #3", and "(hidden)" or "Hidden door" beside it for a way that has to be found. A label can be
    broken ("To" over "#5")."""
    section = place.section
    labels = [line for line in section.lines(own=True) if line.get("color") == _WHITE] + [line for child in section.children if child.title.startswith("Map:") for line in child.lines(own=True)]
    marks = [(line["x0"], line["y0"], line["text"].strip()) for line in labels]
    hidden = [(x, y) for x, y, text in marks if re.search(r"\(hidden\)|hidden door", text, re.I) and not re.search(r"#\d", text)]
    found = []
    for x, y, text in marks:
        broken = text.upper() == "TO"
        key = next((re.match(r"#(\d+[A-Za-z]?)", other).group(1) for ox, oy, other in marks if broken and re.match(r"#\d", other) and abs(ox - x) <= 10 and 0 <= oy - y <= 12), None) if broken else None
        given = re.match(r"To #(\d+[A-Za-z]?)\s*(\(hidden\))?", text, re.I)
        key, shut = (given.group(1), bool(given.group(2))) if given else (key, False)
        target = by_key.get(key.lower()) if key else None
        if target is not None and target is not place:
            near = shut or any(abs(hx - x) <= 40 and 0 <= hy - y <= 14 for hx, hy in hidden)
            found.append((target, f"To {target.name}", near))
    return found


def _hub_ways(place, found, hub):
    """In a hub (a village), the places all open on the hub and the hub on all of them."""
    centre = next((other for other in found if hub and hub.lower() in map(str.lower, other.keys)), None)
    if centre is None:
        return []
    return [(centre, f"Back to {centre.name}", False)] if place is not centre else [(other, f"To {other.name}", False) for other in found if other is not centre]


def tables_under(pack, section, prefix):
    """The tables under a section (its "Table:" sections, however deep), as tables/<prefix>_<title>.toml: {the table's section number: its id}. A table's header may
    have no die, or two ("D6/D10"): it rolls as high as it has rows. A section called a table whose rows aren't numbered (First, Second ...) is words, left to the scene."""
    done = pack.facts.setdefault("tables_made", {})
    for child in section.subtree():
        if child.title.startswith("Table:") and child.number not in done:
            lines = child.lines(own=True)
            marked = [line["text"] for line in lines if dice.is_marker(line)]
            if dice.read(lines, pack.book.glue, 100)["rows"]:
                table_id = f"{prefix}_{packs.slug(clean(child.title))}"
                _table(pack, child, table_id, f"{re.sub(r'^[0-9]+[.] ', '', clean(section.title))}: {clean(child.title)}", 100 if not marked or "/" in marked[0] else None)
                done[child.number] = table_id
    return {number: table_id for number, table_id in done.items() if number in _within(section)}
