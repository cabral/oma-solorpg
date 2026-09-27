"""Campaigns generated from a premise (`make campaign`, `solo campaign`).

The engine rolls a campaign's bones and an agent writes the flesh. `new` rolls a hub to come
back to, two factions, a hidden clock with omens, and the first mission as a path of
waypoints to its heart; `next` rolls the next mission of a campaign under way, and among
its parts, what the hero did that comes back. The dice decide what each waypoint holds, who
is there and what they want, from the system pack's own tables where it has them (its
threats, treasure, bestiary, simple NPCs, inspiration words) and from this module's
original lists where it doesn't.

Every roll that decides something goes into the pack's rolls.toml, numbered, and what it
decided cites it (`source = "rolled: #4"`), so a generated campaign is reviewed like an
imported one: `check` fails on a roll nothing uses and a citation of a roll that isn't
there. What was rolled is written as terse prompts, marked `rolled, not yet written`, for
the agent to write up with the solo-campaign skill; the pack plays even before it does.

Nothing here calls a model or reads the clock: the same premise, system and seed give the
same pack, file for file.
"""

import json
import math
import random
import re
from pathlib import Path

from . import SoloError, campaign, dice, library, oracle, packs
from .packs import slug, toml_string

PREMISE = "premise.toml"
ROLLS = "rolls.toml"
HUB = "hub"
# What every file the generator writes carries until the agent has written it up.
MARK = "rolled, not yet written"
# Waypoints a mission's path has before its heart.
WAYPOINTS = 3
MAX_MISSIONS = 12
_CITE = re.compile(r"rolled:((?:\s*,?\s*#\d+(?:\s*\([^)\n\"]*\))?)+)")
_MISSION = re.compile(r"^mission_(\d+)$")


# The original lists the dice pick from when the system pack has nothing of its own. ------

PLACE_START = ["Salt", "Grey", "Hollow", "Thorn", "Raven", "Ash", "Cold", "Iron", "Mire", "Wolf",
               "Stone", "Black", "Low", "High", "Old", "Bitter", "Red", "Frost", "Bone", "Reed"]
PLACE_END = ["ford", "watch", "mere", "barrow", "hollow", "gate", "fell", "stead", "moor", "wick",
             "cross", "haven", "tor", "holm", "marsh", "reach", "hythe", "combe", "rise", "well"]
BANDS = ["band", "crew", "circle", "company", "kin", "brood", "host", "lot"]
NAMES = ["Alder", "Brisk", "Corra", "Dunn", "Esk", "Fell", "Garrow", "Hesta", "Irn", "Juno",
         "Kell", "Lark", "Morrow", "Nim", "Orla", "Pike", "Quill", "Rook", "Sable", "Tamsin"]
ROLES = ["a trader with a cart and no guards", "a pilgrim who has lost the road", "a deserter in a stolen coat",
         "a hunter on a cold trail", "a healer on the way to a sickbed", "a courier who won't say for whom",
         "a scavenger picking over the dead", "an outcast from the next valley", "a child who shouldn't be out here",
         "a bard with a broken instrument", "a toll-keeper with no one left to pay", "a gravedigger far from any grave"]
VOICES = ["speaks slowly, as if every word costs a coin", "laughs at the wrong moments", "never looks you in the eye",
          "talks over you, then apologises", "whispers, as though someone is listening", "asks a question for every answer",
          "names every place by who died there", "hums between sentences", "swears by gods nobody else keeps",
          "is very polite and very frightened", "uses your name too often", "answers only what is asked, exactly"]
SIGHTS = ["The wind has dropped, and every sound carries.", "Birds went quiet a while back.",
          "Old wheel ruts run here, filled with rainwater.", "Someone has been here before you, not long ago.",
          "The light is going, sooner than it should.", "A cairn of stones marks the way, half kicked over.",
          "Smoke rises somewhere ahead, thin and grey.", "The ground is trampled, as if by many feet in a hurry."]
OMENS = ["Crows gather on every roof and make no sound.", "A cold wind comes from the wrong quarter.",
         "Milk sours overnight in every house you pass.", "Dogs howl at nothing, all at once, then stop.",
         "A bell rings somewhere far off, though no one rang it.", "Your dreams are of a door you have never seen.",
         "Every candle burns blue for a moment.", "Strangers on the road step aside and won't look at you.",
         "The water in the wells tastes of iron.", "A shooting star falls the wrong way, upward.",
         "Someone has scratched a mark on a door you know.", "Frost on the grass in the morning, out of season.",
         "An old woman spits when you pass and makes a sign.", "Fish float belly-up in the streams.",
         "The same black cat watches you from three villages.", "Children sing a rhyme you have never heard, about you."]
STAGE_TEXTS = ["Something has changed in the world: people talk in low voices, and doors are barred early.",
               "It is too late to stop what has begun. Everyone can feel it."]
FOE_WORDS = ["raider", "cutthroat", "brute", "scout", "zealot", "sellsword", "poacher", "marauder"]

# What a waypoint holds. Each has the skills that serve it, best first (the first the system
# has is used), and lines one of those skills might notice there, for its voice.
KINDS = [
    {"id": "passage", "label": "a way to get through",
     "voice": (["spot_hidden", "awareness", "observation", "bushcraft"],
               ["There's a better way across, a little upstream: someone has used it, and recently.",
                "The stones on the left are worn smooth by feet. The ones on the right aren't. Pick the left."])},
    {"id": "stranger", "label": "someone on the way",
     "voice": (["awareness", "observation", "persuasion", "insight"],
               ["They keep one hand hidden the whole time you talk.",
                "Whoever this is, they were waiting. For you, or for someone like you."])},
    {"id": "foes", "label": "a fight in the way",
     "voice": (["awareness", "spot_hidden", "observation", "hunting_fishing"],
               ["Fresh tracks, several sets, all going the way you are.",
                "Cold ashes of a fire for five or six, and bones picked clean. They ate well, and not long ago."])},
    {"id": "find", "label": "something to find",
     "voice": (["spot_hidden", "observation", "awareness", "sleight_of_hand"],
               ["Something here has been moved lately: the dust tells on it.",
                "A loose stone, darker at the edges than the rest. It has been lifted more than once."])},
    {"id": "hazard", "label": "a place that fights back",
     "voice": (["bushcraft", "awareness", "observation", "spot_hidden"],
               ["The air goes still and heavy here. Whatever this place is, it doesn't want you.",
                "No birds, no insects. Animals know better than to cross this."])},
    {"id": "signs", "label": "signs of the enemy",
     "voice": (["spot_hidden", "awareness", "observation", "myths_legends"],
               ["The same mark, scratched into three trees in a row. It points ahead.",
                "Somebody passed here in a hurry and dropped something they'll miss."])},
]
OBSTACLES = [
    ("a rope bridge over a gorge, half its slats gone", ["acrobatics", "mobility", "agility", "agl"]),
    ("a ford running high and fast with meltwater", ["swimming", "mobility", "strength", "str"]),
    ("a scree slope under a cliff that sheds stones", ["acrobatics", "mobility", "agility", "agl"]),
    ("a bog where the only path is a line of sunken stones", ["bushcraft", "survival", "wits", "int"]),
    ("a tunnel half fallen in, with a crawlway through", ["acrobatics", "mobility", "agility", "agl"]),
    ("a wall with a barred gate and a watchman who dozes", ["sneaking", "stealth", "mobility", "agl"]),
]
HAZARDS = [
    ("bad air pooled in a low place", ["con", "strength", "str"]),
    ("a floor of rotten boards over a deep drop", ["acrobatics", "mobility", "agl"]),
    ("a storm that comes in fast off the heights", ["bushcraft", "survival", "con"]),
    ("a swarm of biting flies from a stagnant pool", ["con", "strength", "str"]),
    ("a maze of fog where every way looks the same", ["bushcraft", "observation", "int"]),
    ("a silence that fills the head with old fears", ["wil", "empathy", "command"]),
]
SIGNS = ["a camp struck in a hurry", "a message left for someone else", "a body, and what was done to it",
         "a shrine defaced with their mark", "a trail of dropped coins", "a burned farmstead, still warm"]
FINDS = ["a cache under a cairn", "a satchel on a dead mule", "a strongbox in a flooded cellar",
         "a bundle hidden in a hollow tree", "a purse sewn into an old coat", "a niche behind a loose stone"]
# How the people met on the way feel about the hero, on a D6.
ATTITUDE_ROLL = [(1, "hostile"), (2, "unfriendly"), (4, "neutral"), (6, "friendly")]


# Rolling ---------------------------------------------------------------------------------

class Roller:
    """The dice for one generation, and the record of every roll that decides something.
    `quiet` picks what only dresses a placeholder (a name, a line of scenery) and isn't
    recorded: the agent rewrites those."""

    def __init__(self, system, tables, rng, first=1):
        self.system, self.tables, self.rng = system, tables, rng
        self.rolls, self.next = [], first

    def pick(self, purpose, table, options, label=str):
        face = dice.pick(len(options), self.rng)
        return options[face - 1], self._record(purpose, table, f"1d{len(options)}", [face], label(options[face - 1]))

    def roll(self, purpose, expr):
        result = dice.roll(expr, self.rng)
        return result["total"], self._record(purpose, expr, expr, [result["total"]], str(result["total"]))

    def table(self, purpose, table_id):
        """A table of the system pack's or the adventure's, finishing itself the way a table
        rolled at the table does: `roll`, `choices`, `then`, `again`."""
        rolled = []
        text = self._resolve(table_id, rolled)
        name = self.tables[table_id].get("name", table_id)
        return text, self._record(purpose, table_id, self.tables[table_id]["formula"], rolled, text, name=name)

    def meaning(self, purpose):
        """Words to read an answer by: the system's inspiration columns, else meaning tables
        of the packs, else the oracle's own words."""
        columns = [t for t in self.system.get("oracle", {}).get("inspiration", []) if t in self.tables]
        rolled, words = [], []
        if columns:
            words = [self._resolve(column, rolled) for column in columns]
        else:
            for table_id, fallback in (("meaning_action", oracle.ACTIONS), ("meaning_subject", oracle.SUBJECTS)):
                if table_id in self.tables:
                    words.append(self._resolve(table_id, rolled))
                else:
                    face = dice.pick(len(fallback), self.rng)
                    rolled.append(face)
                    words.append(fallback[face - 1])
        words = [w.strip() for w in words if w.strip()]
        return words, self._record(purpose, "meaning", " ".join(columns) or "meaning words", rolled, " / ".join(words))

    def quiet(self, options):
        return options[dice.pick(len(options), self.rng) - 1]

    def _resolve(self, table_id, rolled, depth=0):
        table = self.tables[table_id]
        result = dice.roll(re.sub(r"@\w+", "0", table["formula"]), self.rng)
        rolled.append(result["total"])
        hit = next((r for r in table.get("results", []) if r["range"][0] <= result["total"] <= r["range"][1]), None) or {}
        text = hit.get("text", "") or f"(no result for {result['total']})"
        if hit.get("choices"):
            text = f"{text}: {hit['choices'][dice.pick(len(hit['choices']), self.rng) - 1]}"
        if hit.get("roll"):
            value = dice.roll(hit["roll"], self.rng)["total"]
            text = text.replace("{value}", str(value)) if "{value}" in text else f"{text} ({hit['roll']}: {value})"
        texts = [text]
        if depth < 5:
            follow = [hit["then"]] if isinstance(hit.get("then"), str) else list(hit.get("then", []))
            for next_id in follow + ([table_id] if hit.get("again") else []):
                if next_id in self.tables:
                    texts.append(self._resolve(next_id, rolled, depth + 1))
        return "; ".join(texts)

    def _record(self, purpose, table, expr, rolled, result, name=None):
        record = {"n": self.next, "for": purpose, "table": name or table, "dice": expr, "rolled": rolled, "result": result}
        self.rolls.append(record)
        self.next += 1
        return record


def cite(*records):
    """A source line citing rolls: "rolled: #3, #4"."""
    return "rolled: " + ", ".join(f"#{r['n']}" for r in records if r)


# Writing TOML ----------------------------------------------------------------------------

class Inline(dict):
    """A table written on one line: time = { shift = 1 }."""


def dump_toml(data, comments=()):
    lines = [f"# {line}".rstrip() for line in comments]
    _emit(lines, (), data)
    return "\n".join(lines).strip("\n") + "\n"


def _emit(lines, path, data):
    plain = [(k, v) for k, v in data.items() if not _is_table(v) and not _is_array(v)]
    tables = [(k, v) for k, v in data.items() if _is_table(v)]
    arrays = [(k, v) for k, v in data.items() if _is_array(v)]
    if path and (plain or not (tables or arrays)):
        lines += ["", f"[{'.'.join(map(_key, path))}]"]
    lines += [f"{_key(k)} = {_value(v)}" for k, v in plain]
    for key, value in tables:
        _emit(lines, (*path, key), value)
    for key, items in arrays:
        for item in items:
            lines += ["", f"[[{'.'.join(map(_key, (*path, key)))}]]"]
            lines += [f"{_key(k)} = {_value(v)}" for k, v in item.items()]


def _is_table(value):
    return isinstance(value, dict) and not isinstance(value, Inline)


def _is_array(value):
    return isinstance(value, list) and bool(value) and all(_is_table(v) for v in value)


def _key(key):
    return key if re.fullmatch(r"[A-Za-z0-9_-]+", key) else toml_string(key)


def _value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    elif isinstance(value, (int, float)):
        return str(value)
    elif isinstance(value, dict):
        return "{ " + ", ".join(f"{_key(k)} = {_value(v)}" for k, v in value.items()) + " }" if value else "{}"
    elif isinstance(value, list):
        return "[" + ", ".join(_value(v) for v in value) + "]"
    else:
        return toml_string(value)


# The world a campaign is rolled in ---------------------------------------------------------

class World:
    """What every part of a campaign reads: the system's skills, time, foes and names, and
    the campaign's own fixed points (the hub, the factions, who asks and who opposes)."""

    def __init__(self, system, roller, hub_title, locals_name, rivals_name, patron_name, nemesis_name, missions):
        self.system, self.roller = system, roller
        self.hub_title, self.locals_name, self.rivals_name = hub_title, locals_name, rivals_name
        self.patron_name, self.nemesis_name, self.missions = patron_name, nemesis_name, missions
        self.move, self.journey = time_units(system)
        npcs = system.get("npcs", {})
        self.templates, self.attackers = npcs.get("templates", {}), list(npcs.get("attackers", []))
        self.minion, self.boss = _template(self.templates, "minion", min), _template(self.templates, "boss", max)
        self.bestiary = sorted(system.get("bestiary", {}))
        tables = roller.tables
        threat_table = system.get("threats", {}).get("table")
        self.threat_table = threat_table if threat_table in tables else None
        self.treasure = "treasure" if "treasure" in tables else None

    def time(self, unit):
        return Inline({unit: 1}) if unit else None

    def skill(self, preferred):
        """The first of these the system has (a skill anyone can try, else an attribute),
        else its first such skill: a voice or a roll must name one the engine knows."""
        skills, attributes = self.system["skills"], self.system["attributes"]
        usable = [s for s, spec in skills.items() if spec.get("untrained", True)]
        found = next((s for s in preferred if s in usable), None) or next((a for a in preferred if a in attributes), None)
        return found or (usable[0] if usable else next(iter(attributes), None))

    def skill_label(self, key):
        spec = self.system["skills"].get(key)
        return (spec["name"] if spec else self.system["attributes"].get(key, key)).upper()

    def condition(self, key):
        """The condition that weighs on the same attribute as this skill, for a failure's cost."""
        attribute = self.system["skills"].get(key, {}).get("attribute", key)
        conditions = self.system["conditions"]
        return next((c for c, a in conditions.items() if a == attribute), next(iter(conditions), None))

    def person(self):
        """A name and a kin for someone, from the system's hero names when it has them."""
        names = self.system.get("creation", {}).get("names", {})
        kin = self.roller.quiet(sorted(names)) if names else None
        return (self.roller.quiet(names[kin]) if kin and names[kin] else self.roller.quiet(NAMES)), kin

    def foe(self, purpose, faction=None):
        """A kind of foe the hero meets again and again: a monster from the system's bestiary,
        else a simple NPC by the solo rules' template, else None (the system can't field one)."""
        if self.bestiary:
            monster, record = self.roller.pick(purpose, "bestiary", self.bestiary,
                                               label=lambda m: self.system["bestiary"][m].get("name", m))
            spec = self.system["bestiary"][monster]
            return {"name": spec.get("name", monster), "role": spec.get("role", "A creature from the bestiary"),
                    "monster": monster, "attitude": "hostile", "many": True, "source": cite(record)}, [record]
        elif self.minion:
            attacker, record = self.roller.pick(purpose, "attacker", self.attackers) if self.attackers else (None, None)
            word = self.roller.quiet(FOE_WORDS)
            npc = {"name": word.capitalize(), "role": f"One of {self.rivals_name}: a {word}", "attitude": "hostile",
                   "many": True, "template": self.minion, "source": cite(record)}
            npc.update({"faction": faction} if faction else {})
            npc.update({"attacker": attacker} if attacker else {})
            return npc, [r for r in [record] if r]
        return None, []

    def leader(self, purpose, name, role, faction):
        """Someone who leads foes: by the boss template when the system has one, else a
        bestiary monster, else a person with no stats (the GM plays it without a fight)."""
        npc = {"name": name, "role": role, "faction": faction, "attitude": "hostile"}
        records = []
        if self.boss:
            npc["template"] = self.boss
            if self.attackers:
                attacker, record = self.roller.pick(f"{purpose}: how they fight", "attacker", self.attackers)
                npc["attacker"] = attacker
                records.append(record)
        elif self.bestiary:
            monster, record = self.roller.pick(f"{purpose}: what they are", "bestiary", self.bestiary,
                                               label=lambda m: self.system["bestiary"][m].get("name", m))
            npc["monster"] = monster
            records.append(record)
        return npc, records

    def profile(self, npc, purpose, reveal):
        """Wants, fears and a secret, each read from rolled words."""
        wants, a = self.roller.meaning(f"{purpose}: what they want")
        fears, b = self.roller.meaning(f"{purpose}: what they fear")
        secret, c = self.roller.meaning(f"{purpose}: their secret")
        npc.update(wants=" / ".join(wants), fears=" / ".join(fears), voice=self.roller.quiet(VOICES))
        npc["secrets"] = [{"id": "secret", "text": " / ".join(secret), "reveal": reveal}]
        return [a, b, c]


def time_units(system):
    """(move, journey): the unit an ordinary move takes, the one nearest a quarter of an
    hour, and the one a journey out from the hub takes, the longest the system has."""
    time = {unit: seconds for unit, seconds in system.get("time", {}).items() if isinstance(seconds, (int, float)) and seconds > 0}
    if not time:
        return None, None
    return min(time, key=lambda u: abs(math.log(time[u] / 900))), max(time, key=time.get)


def _template(templates, word, choose):
    named = [t for t in templates if word in t]
    if named:
        return named[0]
    return choose(templates, key=lambda t: templates[t].get("hp", 0)) if templates else None


# A new campaign ----------------------------------------------------------------------------

def new(root, system_path, premise, tone="", missions=3, title=None, seed=None, system_name=None):
    """Roll a campaign into `root`: adventure.toml (the hub, the factions, the clock), the
    first mission as chapters/mission_1.toml, its scenes and people, the omens, premise.toml
    and rolls.toml. Marked draft until the agent has written it. Returns a summary."""
    root = Path(root).expanduser()
    premise = " ".join(str(premise or "").split())
    if not premise:
        raise SoloError("a campaign needs a premise: what it's about, in a sentence")
    elif not 1 <= int(missions) <= MAX_MISSIONS:
        raise SoloError(f"missions must be from 1 to {MAX_MISSIONS}")
    elif any((root / name).exists() for name in ("adventure.toml", "scenes.json", PREMISE)):
        raise SoloError(f"{root} already holds an adventure")
    system = packs.load_system(system_path)
    gaps = packs.missing(system)
    if gaps:
        raise SoloError(packs.missing_text(system, gaps))
    missions = int(missions)
    seed = int(seed) if seed is not None else random.SystemRandom().randrange(1_000_000)
    roller = Roller(system, dict(system["tables"]), random.Random(seed))
    hub_title = roller.quiet(PLACE_START) + roller.quiet(PLACE_END)
    patron_name, patron_kin = _person(system, roller)
    nemesis_name, nemesis_kin = _person(system, roller)
    rivals_name = f"{nemesis_name}'s {roller.quiet(BANDS)}"
    locals_name = f"The folk of {hub_title}"
    world = World(system, roller, hub_title, locals_name, rivals_name, patron_name, nemesis_name, missions)
    title = (title or "").strip() or f"The {hub_title} Campaign"

    rivals_want, rivals_roll = roller.meaning("the rivals: what they are after")
    patron = {"name": patron_name, "role": f"The one in {hub_title} who asks for your help" + (f" ({patron_kin})" if patron_kin else ""),
              "faction": "locals", "attitude": "friendly"}
    patron_rolls = world.profile(patron, "the patron", "npc.patron.attitude >= allied")
    patron["source"] = cite(*patron_rolls)
    nemesis, nemesis_rolls = world.leader("the nemesis", nemesis_name,
                                          f"Leader of {rivals_name}" + (f" ({nemesis_kin})" if nemesis_kin else ""), "rivals")
    nemesis_rolls += world.profile(nemesis, "the nemesis", "npc.nemesis.fate != 'alive'")
    nemesis["source"] = cite(*nemesis_rolls)

    segments = 3 * missions
    plan_words, plan_roll = roller.meaning("the nemesis's plan as it moves")
    omens = [roller.quiet(OMENS) for _ in range(6)]
    clock = {
        "label": f"{nemesis_name}'s plan", "segments": segments, "hidden": True, "omen": True,
        "advance": [f"time:{world.journey}", "check:demon"] if world.journey else ["check:demon"],
        "on_tick": "omens", "source": cite(rivals_roll, plan_roll),
        "stages": [
            *([{"at": segments // 2, "text": STAGE_TEXTS[0],
                "note": f"Halfway: {nemesis_name}'s plan is moving ({' / '.join(plan_words)}). Let the hero see it in the world."}]
              if segments >= 2 else []),
            {"at": segments, "text": STAGE_TEXTS[1], "facts": Inline({"plan.done": True}),
             "note": f"{nemesis_name}'s plan has come to pass ({' / '.join(rivals_want)}). The last mission's heart reads fact.plan.done."},
        ],
    }
    spec = {
        "title": title, "system": system_name or Path(system_path).name,
        "summary": _summary(premise, tone, missions),
        "start": HUB, "chaos": 4, "draft": True,
        **({"move_time": Inline({world.move: 1})} if world.move else {}),
        "factions": {
            "locals": {"name": locals_name, "standing": 0, "source": "the hub's people"},
            "rivals": {"name": rivals_name, "standing": -1, "source": cite(rivals_roll)},
        },
        "clocks": {"plan": clock},
        "scenes": {HUB: {"title": hub_title, "safe": True, "npcs": ["patron"], "source": "the campaign's hub"}},
    }
    files = {
        "adventure.toml": dump_toml(spec, [
            f"{MARK}: rewrite this file for the campaign, then delete this line.",
            f"Rolled by solo campaign new from premise.toml (seed {seed}). Every roll is in rolls.toml;",
            "what it decided cites it (source = \"rolled: #n\"). Missions are chapters/mission_<n>.toml.",
            "draft = true keeps it off the New adventure screen until it's written: delete it then.",
        ]),
        "scenes/hub.md": _hub_text(world, patron_name),
        "npcs/patron.toml": dump_toml(patron, [f"{MARK}: the patron, who gives the missions."]),
        "npcs/nemesis.toml": dump_toml(nemesis, [f"{MARK}: the nemesis, met at the heart of the last mission."]),
        "tables/omens.toml": dump_toml({"name": f"Omens of {nemesis_name}'s plan", "formula": "1d6",
                                        "results": [Inline({"range": [n, n], "text": text}) for n, text in enumerate(omens, 1)]},
                                       [f"{MARK}: what the hero feels when the plan moves. The player reads these as omens:",
                                        "things the hero can see or feel, never the clock's name."]),
        PREMISE: dump_toml({"title": title, "premise": premise, "tone": tone or "", "missions": missions,
                            "system": spec["system"], "seed": seed},
                           ["What the player pitched (make campaign). The generator reads it again for each mission."]),
    }
    mission_files, summary = _mission(world, 1, missions)
    files.update(mission_files)
    files[ROLLS] = _rolls_header() + _rolls_text(roller.rolls)
    _write(root, files)
    return {"dir": root, "title": title, "seed": seed, "missions": missions, "rolls": len(roller.rolls),
            "files": sorted(files), "mission": summary}


def _summary(premise, tone, missions):
    """The New adventure card: what the player pitched, which spoils nothing."""
    kind = f"{tone.strip()} campaign" if tone and tone.strip() else "campaign"
    article = "An" if kind[0].lower() in "aeiou" else "A"
    return f"{article} {kind} in {missions} mission{'s' if missions != 1 else ''}: {premise}"


def _person(system, roller):
    names = system.get("creation", {}).get("names", {})
    kin = roller.quiet(sorted(names)) if names else None
    return (roller.quiet(names[kin]) if kin and names[kin] else roller.quiet(NAMES)), kin


def _hub_text(world, patron_name):
    return "\n".join([
        f"{world.hub_title}. Smoke from a dozen chimneys, a well at the crossroads, and people who stop talking when a stranger passes.",
        "",
        "::: gm",
        f"({MARK}: the agent writing this campaign replaces this text.)",
        "",
        f"The campaign's home, and a safe place: the solo rules' threats don't close in here. {patron_name} is here "
        "and asks for the hero's help; each mission begins with them.",
        "",
        "Missions open from here one at a time, each once the one before is done (the facts mission_1.done, mission_2.done ...). "
        "What to tell the player about the mission at hand is under \"True now\". If no way into the next mission is listed "
        "under Exits or Closed for now, it hasn't been written yet: it's written between sessions from what the hero did. "
        "Close the session here (end-of-session marks with solo mark, solo advance, a chronicle entry) and tell the player "
        "the next chapter is on its way.",
        ":::",
        "",
    ])


# A mission ---------------------------------------------------------------------------------

def _mission(world, n, missions, threads=(), people=None):
    """Mission n as files: its chapter (scenes, the hub's way in and briefing, a clock when
    the system has no threats), scene texts and people. `threads` are what the hero did,
    rolled to come back (see `next_mission`); `people` their NPC files to add."""
    roller, last = world.roller, n == missions
    prefix = f"m{n}"
    goal, goal_roll = roller.meaning(f"mission {n}: what the hero must do")
    threat, threat_roll = roller.table(f"mission {n}: the threat", world.threat_table) if world.threat_table else (None, None)
    kinds, kind_rolls = [], []
    for i in range(1, WAYPOINTS + 1):
        kind, record = roller.pick(f"mission {n}, waypoint {i}: what it holds", "waypoint", KINDS, label=lambda k: k["label"])
        kinds.append(kind)
        kind_rolls.append(record)
    ids = [f"{prefix}_w{i}" for i in range(1, WAYPOINTS + 1)] + [f"{prefix}_heart"]
    scenes, texts, npcs = {}, {}, dict(people or {})
    titles = {}
    for i, kind in enumerate(kinds):
        sid = ids[i]
        place = roller.quiet(PLACE_START) + roller.quiet(PLACE_END)
        titles[sid] = _waypoint_title(kind["id"], place)
    titles[ids[-1]] = f"The Heart of It, at {roller.quiet(PLACE_START) + roller.quiet(PLACE_END)}"
    chapter_clocks = {}
    if not world.threat_table and world.move:
        chapter_clocks[f"{prefix}_time"] = {
            "label": f"Mission {n}: time running out", "segments": 6, "hidden": True,
            "advance": [f"time:{world.move}"], "source": cite(goal_roll),
            "stages": [{"at": 6, "note": f"Time's up for mission {n}: what the hero came to do is harder now (fact mission_{n}.late).",
                        "facts": Inline({f"mission_{n}.late": True})}],
        }
    payoff = {ids[min(1, WAYPOINTS - 1)]: threads[0]} if threads else {}
    if len(threads) > 1:
        payoff[ids[-1]] = threads[1]
    for i, kind in enumerate(kinds):
        sid = ids[i]
        onward, back = ids[i + 1], (ids[i - 1] if i else HUB)
        exits = {onward: f"On to {titles[onward]}"}
        exits[back] = {"label": f"Back to {world.hub_title}", "time": world.time(world.journey)} if back == HUB else f"Back to {titles[back]}"
        if back == HUB and not world.journey:
            exits[back] = f"Back to {world.hub_title}"
        scene, text, extra = _waypoint(world, n, i + 1, sid, kind, kind_rolls[i], titles[sid], payoff.get(sid))
        scene["exits"] = exits
        scenes[sid] = scene
        texts[f"scenes/{sid}.md"] = text
        npcs.update(extra)
    heart, heart_text, heart_npcs = _heart(world, n, last, ids[-1], titles[ids[-1]], goal, goal_roll, payoff.get(ids[-1]))
    heart["exits"] = {HUB: {"label": f"Back to {world.hub_title}", "time": world.time(world.journey)} if world.journey else f"Back to {world.hub_title}"}
    heart["exits"][ids[-2]] = f"Back to {titles[ids[-2]]}"
    scenes[ids[-1]] = heart
    texts[f"scenes/{ids[-1]}.md"] = heart_text
    npcs.update(heart_npcs)
    for sid, thread in payoff.items():
        if thread.get("npc") and thread["npc"] not in scenes[sid].get("npcs", []):
            scenes[sid].setdefault("npcs", []).append(thread["npc"])

    way_in = {"label": f"Set out: {titles[ids[0]]}", "source": cite(goal_roll, threat_roll)}
    if n > 1:
        way_in["when"] = f"fact.mission_{n - 1}.done"
    if world.journey:
        way_in["time"] = world.time(world.journey)
    route = " -> ".join(f"{titles[sid]} ({sid})" for sid in ids)
    briefing = [f"Mission {n} of {missions}, the one at hand: {' / '.join(goal)} (rolled: what the hero must do; "
                f"{world.patron_name} asks it of them). The way: {route}."]
    if threat:
        briefing.append(f'Its threat (rolled from the solo rules): {threat} When the hero sets out, set it: '
                        f'solo threat add "{_quote(threat)}" --id {prefix}_threat --recurring.')
    elif chapter_clocks:
        briefing.append(f"A hidden clock ({prefix}_time) counts the time it takes: every {world.move} spent brings it closer.")
    if threads:
        briefing.append("What the hero did comes back in it: " + "; ".join(t["text"] for t in threads) + ".")
    when = f"not fact.mission_{n}.done" if n == 1 else f"fact.mission_{n - 1}.done and not fact.mission_{n}.done"
    hub = {"exits": {ids[0]: way_in}, "branches": [{"when": when, "text": " ".join(briefing)}]}
    chapter = {"draft": True, "scenes": {HUB: hub, **scenes}}
    if chapter_clocks:
        chapter["clocks"] = chapter_clocks
    comments = [f"{MARK}: rewrite this mission for the campaign, then delete this line.",
                f"Mission {n} of {missions}: the hub's way in and briefing, then {WAYPOINTS} waypoints and the heart.",
                "draft = true keeps it out of a campaign under way until it's written: delete it then."]
    rolls = [goal_roll, threat_roll, *kind_rolls]
    files = {f"chapters/mission_{n}.toml": dump_toml(chapter, comments), **texts}
    for nid, npc in npcs.items():
        # Someone met in play arrives already written (see _met_in_play); the rest are rolled.
        files[f"npcs/{nid}.toml"] = npc["_text"] if "_text" in npc else dump_toml(npc, [f"{MARK}: someone in mission {n}."])
    return files, {"mission": n, "scenes": ids, "goal": " / ".join(goal), "threat": threat,
                   "threads": [t["text"] for t in threads], "rolls": [r["n"] for r in rolls if r]}


def _waypoint_title(kind, place):
    return {
        "passage": f"The Crossing at {place}", "stranger": f"The Road by {place}", "foes": f"The Ambush at {place}",
        "find": f"The Ruin at {place}", "hazard": f"The Bad Ground at {place}", "signs": f"The Camp at {place}",
    }[kind]


def _waypoint(world, n, i, sid, kind, kind_roll, title, thread):
    """One waypoint: its scene (title, voice, people), its text and its people."""
    roller, system = world.roller, world.system
    twist, twist_roll = roller.meaning(f"mission {n}, waypoint {i}: what is odd or at stake here")
    rolls, npcs, gm = [kind_roll, twist_roll], {}, []
    scene = {"title": title}
    dark, dark_roll = roller.roll(f"mission {n}, waypoint {i}: dark? (1 on a D6)", "1d6")
    rolls.append(dark_roll)
    if dark == 1:
        scene["dark"] = True
    skill_for = lambda preferred: world.skill(preferred)  # noqa: E731
    read = roller.quiet(SIGHTS)
    kid = kind["id"]
    if kid == "passage":
        (obstacle, preferred), record = roller.pick(f"mission {n}, waypoint {i}: the obstacle", "obstacle", OBSTACLES, label=lambda o: o[0])
        rolls.append(record)
        skill = skill_for(preferred)
        read = f"The way ahead runs to {obstacle}. {read}"
        gm.append(f"Getting across takes a {world.skill_label(skill)} roll (solo check {skill}). On a failure it costs time: "
                  f"describe the delay and run {_commit({'time': {world.move: 1}}) if world.move else 'a commit of what it costs'}"
                  + ("; the mission's threat draws closer (solo threat advance)." if world.threat_table else "."))
    elif kid == "stranger":
        name, kin = world.person()
        nid = f"{sid}_stranger"
        role, role_roll = roller.pick(f"mission {n}, waypoint {i}: who they are", "stranger", ROLES)
        attitude, attitude_roll = _attitude(roller, f"mission {n}, waypoint {i}: how they take to the hero")
        npc = {"name": name, "role": role[0].upper() + role[1:] + (f" ({kin})" if kin else ""), "attitude": attitude}
        profile_rolls = world.profile(npc, f"{name}, met at waypoint {i} of mission {n}", f"npc.{nid}.attitude >= friendly")
        npc["source"] = cite(role_roll, attitude_roll, *profile_rolls)
        npcs[nid] = npc
        scene["npcs"] = [nid]
        read = f"Someone is on the road ahead: {role}. {read}"
        gm.append(f"{name} ({nid}) is here, {attitude} toward the hero; what they want, fear and hide is in their profile "
                  f"(solo npc {nid}). How they react to what the hero does: solo ask --npc {nid}.")
    elif kid == "foes":
        foe, foe_rolls = world.foe(f"mission {n}, waypoint {i}: the foes", faction="rivals")
        if foe:
            nid = f"{sid}_foe"
            count, count_roll = roller.roll(f"mission {n}, waypoint {i}: how many", "1d3")
            npcs[nid] = foe
            rolls += [*foe_rolls, count_roll]
            scene["npcs"] = [nid]
            read = f"{read} Voices ahead, and the scrape of steel."
            gm.append(f"{count} × {foe['name']} ({nid}) hold the way. Sneaking past is a roll; a fight is "
                      f"solo fight {' '.join([nid] * count)}. Talking works only if the rolled words above give them a reason.")
        else:
            gm.append("Foes hold the way, but the system pack has no foes to roll (no bestiary, no simple NPCs): "
                      "the hero must get past them by a roll, a trick or a bargain.")
    elif kid == "find":
        spot, record = roller.pick(f"mission {n}, waypoint {i}: where it is", "find", FINDS)
        rolls.append(record)
        found = None
        if world.treasure:
            found, treasure_roll = roller.table(f"mission {n}, waypoint {i}: what is there", world.treasure)
            rolls.append(treasure_roll)
        how = "a careful search (solo search) finds it" if system.get("search") else \
            f"a {world.skill_label(world.skill(['spot_hidden', 'observation', 'awareness']))} roll finds it"
        read = f"{read} Something about this place says it has been used, and left in a hurry."
        gm.append(f"Hidden here: {spot}; {how}. It holds {found or 'what the rolled words above suggest'}. "
                  f"Give it with a commit ({_commit({'pc': {'items': {'add': ['...']}}})}); a clue it holds is "
                  f"{_commit({'clue': f'{sid}_find'})}.")
    elif kid == "hazard":
        (hazard, preferred), record = roller.pick(f"mission {n}, waypoint {i}: the hazard", "hazard", HAZARDS, label=lambda h: h[0])
        rolls.append(record)
        skill = skill_for(preferred)
        condition = world.condition(skill)
        read = f"{read} Ahead: {hazard}."
        cost = (f"the hero takes the {condition} condition: {_commit({'pc': {'conditions': {'add': [condition]}}})}"
                if condition else "it costs the hero something they carry, or time")
        gm.append(f"Getting through {hazard} takes a {world.skill_label(skill)} roll (solo check {skill}). On a failure {cost}.")
    elif kid == "signs":
        sign, record = roller.pick(f"mission {n}, waypoint {i}: the sign", "signs", SIGNS)
        rolls.append(record)
        skill = world.skill(["spot_hidden", "observation", "awareness", "bushcraft"])
        read = f"{read} Here: {sign}."
        gm.append(f"Signs of {world.rivals_name}: {sign}. A {world.skill_label(skill)} roll reads them: on a success the hero "
                  f"learns what they are about (the rolled words above), and gains a clue: {_commit({'clue': f'{sid}_signs'})}. "
                  f"Lingering here lets them get ahead: {_commit({'clock': {'plan': '+1'}})}.")
    preferred, lines = kind["voice"]
    voice_skill = world.skill(preferred)
    if voice_skill:
        scene["voices"] = [{"skill": voice_skill, "text": roller.quiet(lines)}]
    if thread:
        gm.append(_thread_text(thread, sid))
        if thread.get("record"):
            rolls.append(thread["record"])
    scene["source"] = cite(*rolls)
    text = "\n".join([
        read, "", "::: gm", f"({MARK}: the agent writing this campaign replaces this text.)", "",
        f"Mission {n}, waypoint {i} of {WAYPOINTS}: {kind['label']}. Rolled: {' / '.join(twist)} "
        "(what is odd or at stake here: make it mean something for this campaign).", "",
        *[line for part in gm for line in (part, "")],
        ":::", "",
    ])
    return scene, text, npcs


def _heart(world, n, last, sid, title, goal, goal_roll, thread):
    """Where a mission ends: what the hero came to do, who stands in the way, the reward,
    and the exact commit that closes the mission (and the campaign, after the last)."""
    roller = world.roller
    rolls, npcs, fight = [goal_roll], {}, []
    if last:
        boss_id, boss_name = "nemesis", world.nemesis_name
        leads = f"{boss_name} (nemesis) is here: this is where the campaign ends"
    else:
        boss_id = f"{sid}_lieutenant"
        boss_name, kin = world.person()
        boss, boss_rolls = world.leader(f"mission {n}: the lieutenant", boss_name,
                                        f"One of {world.nemesis_name}'s lieutenants" + (f" ({kin})" if kin else ""), "rivals")
        boss_rolls += world.profile(boss, f"{boss_name}, the lieutenant of mission {n}", f"npc.{boss_id}.fate != 'alive'")
        boss["source"] = cite(*boss_rolls)
        npcs[boss_id] = boss
        rolls += boss_rolls
        leads = f"{boss_name} ({boss_id}), one of {world.nemesis_name}'s lieutenants, holds it"
    scene = {"title": title, "climax": True, "npcs": [boss_id]}
    foe, foe_rolls = world.foe(f"mission {n}, the heart: who stands with them", faction="rivals")
    fighters = [boss_id] if world.boss or world.bestiary else []
    if foe:
        foe_id = f"{sid}_foe"
        count, count_roll = roller.roll(f"mission {n}, the heart: how many stand with them", "1d3")
        npcs[foe_id] = foe
        scene["npcs"].append(foe_id)
        rolls += [*foe_rolls, count_roll]
        fighters += [foe_id] * count
        leads += f", with {count} × {foe['name']} ({foe_id})"
    if fighters:
        fight.append(f"If it comes to a fight: solo fight {' '.join(fighters)}.")
    reward = None
    if world.treasure:
        reward, reward_roll = roller.table(f"mission {n}, the heart: the reward", world.treasure)
        rolls.append(reward_roll)
    done = {"facts": {f"mission_{n}.done": True}, "chronicle": f"<what the hero did in mission {n}, and how it ended>"}
    if last:
        done["end"] = "<how the campaign ends, in a sentence>"
    lines = [
        f"The heart of mission {n}: {' / '.join(goal)} (rolled: what the hero came to do). {leads}.",
        *fight,
        *([f"The reward (rolled): {reward}."] if reward else []),
        f"When it's done, won, bargained or lost for good, run {_commit(done)}"
        + (", then bring the hero back." if not last else ". The campaign is over."),
        f"If {world.nemesis_name}'s plan came to pass first (fact.plan.done), it shows here: see True now.",
    ]
    if thread:
        lines.append(_thread_text(thread, sid))
        if thread.get("record"):
            rolls.append(thread["record"])
    scene["branches"] = [{"when": "fact.plan.done", "text": f"{world.nemesis_name}'s plan has come to pass: what the hero came to do "
                                                             "is harder now, and the place shows it."}]
    if not world.threat_table and world.move:  # the mission's own clock (see _mission) sets it
        scene["branches"].append({"when": f"fact.mission_{n}.late", "text": "The hero took too long: those here were ready for them."})
    scene["source"] = cite(*rolls)
    text = "\n".join([
        "This is it: the place everything on the way pointed to.", "", "::: gm",
        f"({MARK}: the agent writing this campaign replaces this text.)", "",
        *[line for part in lines for line in (part, "")],
        ":::", "",
    ])
    return scene, text, npcs


def _attitude(roller, purpose):
    face, record = roller.roll(purpose, "1d6")
    return next(name for top, name in ATTITUDE_ROLL if face <= top), record


def _commit(payload):
    """A commit as the GM writes it in a scene's text."""
    return f"solo commit '{json.dumps(payload, ensure_ascii=False)}'"


def _quote(text):
    return str(text).replace("\\", "").replace('"', "'").strip()


# The next mission of a campaign under way -----------------------------------------------

def threads(c):
    """What the hero did that can come back, from the campaign: open consequences and
    promises, people who remember the hero, people who got away, what word has reached a
    faction, and what the player said about their hero. In the order they happened."""
    state, adventure = c.state, c.adventure
    name = lambda nid: state["npcs"].get(nid or "", {}).get("name", nid)  # noqa: E731
    found, used = [], set()
    for cid, k in state["consequences"].items():
        if k["status"] == "open":
            found.append({"kind": "consequence", "id": cid, "npc": k["npc"], "text": f"a consequence ({cid}): {k['text']}"})
            used.add(k["npc"])
    for pid, p in state["promises"].items():
        if p["status"] == "open":
            found.append({"kind": "promise", "id": pid, "npc": p["npc"], "text": f"a promise to {name(p['npc'])} ({pid}): {p['terms']}"})
            used.add(p["npc"])
    for nid, npc in state["npcs"].items():
        if nid in used or not npc["met"] or campaign.profile_of(adventure, state, nid).get("many"):
            continue
        if npc["fate"] in ("fled", "captured"):
            found.append({"kind": "fate", "npc": nid, "text": f"{npc['name']} ({nid}), who {npc['fate'] == 'fled' and 'got away' or 'was taken'}"})
        elif npc["fate"] == "alive" and npc["memories"]:
            found.append({"kind": "person", "npc": nid, "text": f"{npc['name']} ({nid}), who remembers: {npc['memories'][-1]}"})
    for fid, faction in state["factions"].items():
        if faction.get("memories"):
            found.append({"kind": "faction", "faction": fid, "text": f"{faction['name']} ({fid}), who heard: {faction['memories'][-1]}"})
    for key, value in state["facts"].items():
        if key.startswith("hero.") and value not in (None, False, ""):
            found.append({"kind": "hero", "text": f"the hero's own story ({key}): {value}"})
    return found


def next_mission(root, rng=None):
    """Roll the next mission into the adventure pack a campaign plays: once the mission
    before it is done, from what the hero did in it. Two of the campaign's threads are rolled
    to come back (see `threads`), and the people in them join the mission; someone the GM made
    up in play gets an NPC file of their own, their name and profile as the GM wrote them."""
    root = Path(root).expanduser()
    with campaign.session(root) as c:
        pack = Path(c.adventure["dir"])
        system, state = c.system, c.state
        found = threads(c)
        live = {nid: dict(campaign.profile_of(c.adventure, state, nid), name=npc["name"]) for nid, npc in state["npcs"].items()}
        live_factions = {fid: f["name"] for fid, f in state["factions"].items()}
    if not (pack / PREMISE).exists():
        raise SoloError(f"{pack.name} wasn't generated (no {PREMISE}): only a generated campaign gets its missions written as it goes")
    premise = packs.load_data(pack / PREMISE)
    adventure = packs.load_adventure(pack)
    written = sorted(int(m.group(1)) for m in map(_MISSION.match, adventure["chapters"]) if m)
    n, missions = (written[-1] if written else 0) + 1, int(premise.get("missions", 1))
    drafts = [p.stem for p in (pack / "chapters").glob("mission_*.toml") if packs.load_data(p).get("draft")]
    if written != list(range(1, n)):
        raise SoloError(f"{pack.name}'s missions should be chapters/mission_1.toml, mission_2.toml ... in order; it has {', '.join(map(str, written))}")
    elif drafts:
        raise SoloError(f"{', '.join(sorted(drafts))} is still a draft: write it up (and delete its draft line) before rolling the next")
    elif n > missions:
        raise SoloError(f"all {missions} missions of {premise.get('title', pack.name)} are written")
    elif state["ended"]:
        raise SoloError(f"this campaign has ended: {state['ended']['text']}")
    elif state["pc"]["dead"]:
        raise SoloError(f"{state['pc']['name']} is dead: take on another hero first (solo hero)")
    elif not state["facts"].get(f"mission_{n - 1}.done"):
        raise SoloError(f"mission {n - 1} isn't done in this campaign yet: the next is written once the GM commits "
                        f'{{"facts": {{"mission_{n - 1}.done": true}}}}')
    rng = rng or random.Random(f"{premise.get('seed', 0)}:{n}")
    roller = Roller(system, {**system["tables"], **adventure["tables"]}, rng, first=_last_roll(pack) + 1)
    world = _world_of(system, roller, adventure, missions)
    chosen, people = [], {}
    pool = list(found)
    for label in ("what comes back", "what else comes back"):
        if not pool:
            break
        thread, record = roller.pick(f"mission {n}: {label} (from what the hero did)", "threads", pool, label=lambda t: t["text"])
        pool.remove(thread)
        chosen.append({**thread, "record": record})
    for thread in chosen:
        nid = thread.get("npc")
        if nid and nid not in adventure["npcs"] and nid in live and not (pack / "npcs" / f"{nid}.toml").exists():
            people[nid] = {"_text": _met_in_play(nid, live[nid], root, thread["record"])}
        if thread.get("faction") and thread["faction"] not in adventure["factions"]:
            thread["new_faction"] = live_factions.get(thread["faction"], thread["faction"])
    files, summary = _mission(world, n, missions, threads=chosen, people=people)
    new_factions = {t["faction"]: t["new_faction"] for t in chosen if t.get("new_faction")}
    if new_factions:
        chapter = files[f"chapters/mission_{n}.toml"]
        files[f"chapters/mission_{n}.toml"] = chapter + "".join(
            f"\n[factions.{fid}]\nname = {toml_string(name)}\nstanding = 0\nsource = \"met in play\"\n" for fid, name in new_factions.items())
    clash = [path for path in files if (pack / path).exists()]
    if clash:
        raise SoloError(f"{pack.name} already has {', '.join(clash)}: move it aside first")
    _write(pack, files)
    with open(pack / ROLLS, "a", encoding="utf-8") as log:
        log.write(_rolls_text(roller.rolls))
    return {"dir": pack, "campaign": root, "mission": n, "missions": missions, "rolls": len(roller.rolls),
            "files": sorted(files), "threads": [t["text"] for t in chosen], **summary}


def _world_of(system, roller, adventure, missions):
    npcs, factions = adventure["npcs"], adventure["factions"]
    return World(system, roller, adventure["scenes"].get(HUB, {}).get("title", "the hub"),
                 factions.get("locals", {}).get("name", "the locals"), factions.get("rivals", {}).get("name", "the rivals"),
                 npcs.get("patron", {}).get("name", "the patron"), npcs.get("nemesis", {}).get("name", "the nemesis"), missions)


def _met_in_play(nid, profile, root, record):
    """An NPC file for someone the GM made up in play, so the next mission can bring them
    back: their name and what the GM wrote about them, nothing the campaign's log sets
    (attitude, faction, fate, where they are), so replaying it changes nothing."""
    keep = {k: profile[k] for k in ("name", *campaign.PROFILE_FIELDS) if profile.get(k)}
    keep["source"] = f"met in play in {root.name}; {cite(record)}"
    return dump_toml(keep, [f"Met in play in the campaign {root.name}: their name and profile as the GM made them up there.",
                            "Keep what's here; add what the next mission needs (secrets, stats)."])


def _thread_text(thread, sid):
    line = f"What comes back here (rolled from what the hero did): {thread['text']}."
    if thread.get("npc"):
        line += (f" {thread['npc']} is here: if solo scene doesn't list them, the story put them elsewhere; bring them with "
                 f"{_commit({'npc': {thread['npc']: {'location': sid}}})}.")
    if thread["kind"] == "consequence":
        line += f" Pay it off here, then run {_commit({'consequence': {'id': thread['id'], 'status': 'done'}})}."
    elif thread["kind"] == "promise":
        line += f" The hero keeps it or breaks it here: {_commit({'promise': {'id': thread['id'], 'status': 'kept'}})} (or broken)."
    return line


# Rolls the author makes, and the check -----------------------------------------------------

def roll(pack, what, purpose, rng=None):
    """A roll the agent makes while writing a campaign (a table of the packs, meaning words,
    or dice), recorded in rolls.toml like the generator's own, to cite where it's used."""
    pack = Path(pack)
    if not (pack / PREMISE).exists():
        raise SoloError(f"{pack.name} wasn't generated (no {PREMISE})")
    elif not str(purpose or "").strip():
        raise SoloError("say what the roll is for (--for): a waypoint's danger, who is at the inn ...")
    premise = packs.load_data(pack / PREMISE)
    adventure = packs.load_adventure(pack)
    system = packs.load_system(library.find_system(premise.get("system") or adventure["system"]))
    tables = {**system["tables"], **adventure["tables"]}
    roller = Roller(system, tables, rng or random.Random(), first=_last_roll(pack) + 1)
    if what == "meaning":
        roller.meaning(purpose)
    elif what in tables or slug(what) in tables:
        roller.table(purpose, what if what in tables else slug(what))
    else:
        try:
            dice.parse(what)
        except SoloError:
            raise SoloError(f"{what!r} is neither a table ({', '.join(sorted(tables)) or 'none'}), meaning, nor dice") from None
        roller.roll(purpose, what)
    with open(pack / ROLLS, "a", encoding="utf-8") as log:
        log.write(_rolls_text(roller.rolls))
    return roller.rolls[-1]


def load_rolls(pack):
    path = Path(pack) / ROLLS
    return packs.load_data(path).get("rolls", []) if path.exists() else []


def check(pack):
    """What stands between a generated campaign and play, as {problems, notes}: files still
    as rolled, draft marks, rolls cited that aren't in rolls.toml, and rolls nothing uses
    (a roll the author didn't take says why in its `note`)."""
    pack = Path(pack)
    if not (pack / PREMISE).exists():
        raise SoloError(f"{pack.name} wasn't generated (no {PREMISE})")
    premise = packs.load_data(pack / PREMISE)
    adventure = packs.load_adventure(pack)
    rolls = {r["n"]: r for r in load_rolls(pack)}
    problems, cited = [], set()
    files = sorted(p for pattern in ("*.toml", "chapters/*.toml", "npcs/*.toml", "tables/*.toml", "scenes/*.md", "rules/*.md")
                   for p in pack.glob(pattern) if p.name not in (PREMISE, ROLLS))
    for path in files:
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(pack).as_posix()
        if MARK in text:
            problems.append(f"{rel}: still as rolled: write it up for the campaign, then delete the \"{MARK}\" line")
        for match in _CITE.finditer(text):
            cited |= {int(n) for n in re.findall(r"#(\d+)", match.group(1))}
    if adventure["draft"]:
        problems.append("adventure.toml: draft = true: delete it when the campaign is written, and it shows on the New adventure screen")
    for path in sorted((pack / "chapters").glob("*.toml")):
        if packs.load_data(path).get("draft"):
            problems.append(f"chapters/{path.name}: draft = true: delete it when the mission is written, and a campaign under way gets it")
    problems += [f"a source cites roll #{n}, which isn't in {ROLLS}" for n in sorted(cited - set(rolls))]
    problems += [f"roll #{n} ({r.get('for', '')}: {r.get('result', '')}) is used by nothing: cite it where it's used "
                 "(source = \"rolled: #n\"), or give it a note saying why it wasn't"
                 for n, r in sorted(rolls.items()) if n not in cited and not str(r.get("note", "")).strip()]
    written = sorted(int(m.group(1)) for m in map(_MISSION.match, adventure["chapters"]) if m)
    notes = [f"{premise.get('title', pack.name)}: {len(written)} of {premise.get('missions', '?')} missions written, {len(rolls)} rolls"]
    return {"problems": problems, "notes": notes}


def _last_roll(pack):
    return max((int(r.get("n", 0)) for r in load_rolls(pack)), default=0)


def _rolls_header():
    return ("# Every roll made for this campaign, in order: what it was for, the dice, what came up.\n"
            "# What each decided cites it (source = \"rolled: #n\"); solo campaign check fails on one nothing uses.\n"
            "# Never change a roll. One you didn't take gets a note saying why (note = \"...\").\n")


def _rolls_text(records):
    return "".join("\n" + dump_toml({"rolls": [record]}).lstrip("\n") for record in records)


def _write(root, files):
    for relative, text in files.items():
        path = Path(root) / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
