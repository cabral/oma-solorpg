"""A campaign folder: the event log, the state derived from it, and every action that appends to it.

events.jsonl is the source of truth. state.json is fold(packs, events), rewritten after
each command for the panel, and safe to delete: `solo rebuild` recreates it.
"""

import copy
import fcntl
import json
import os
import re
import unicodedata
from collections import Counter
from contextlib import contextmanager
from datetime import datetime
from difflib import get_close_matches
from pathlib import Path

from . import SoloError, combat, creation, dice, library, mechanics, oracle, packs, portrait
from .packs import ATTITUDES, FATES, PROMISE_STATUSES, slug

LIKELIHOOD = {
    "impossible": 5, "very unlikely": 15, "unlikely": 30, "even": 50,
    "likely": 70, "very likely": 85, "certain": 95,
}
_ODDS = ["very unlikely", "unlikely", "even", "likely", "very likely"]
SPEAKERS = ("gm", "player")
_COMMIT_KEYS = {"note", "facts", "npc", "faction", "promise", "pc", "clock", "time", "clue", "chronicle", "override", "chaos", "end", "learn", "consequence"}
# What the GM writes down about someone it made up, so the next session meets the same person.
# An adventure's own NPCs have these already; what changes about them is a memory.
PROFILE_FIELDS = ("role", "description", "voice", "wants", "fears")
_NPC_FIELDS = {"name", "faction", "attitude", "fate", "location", "memory", "template", "attacker", "monster", *PROFILE_FIELDS}
# What a player can learn about an NPC besides its secrets (by id): the codex blanks them out until then.
LEARNABLE = ("wants", "fears")
# A consequence is something the hero did coming back later: open until the story pays it
# off (done), or until it can't happen any more (dropped).
CONSEQUENCE_STATUSES = ("open", "done", "dropped")
_CONSEQUENCE_KEYS = {"id", "text", "npc", "at", "when", "after", "status"}
_PROMISE_KEYS = {"id", "npc", "terms", "text", "status"}
# Commit keys GMs write in the plural or singular by mistake: read as meant.
_KEY_ALIASES = {"npcs": "npc", "fact": "facts", "factions": "faction", "promises": "promise",
                "consequences": "consequence", "clues": "clue"}
# The GM is reminded to write a chronicle entry after this many of its messages without one.
CHRONICLE_EVERY = 12
# State the GM reads through `solo`, never the panel: it stays out of state.json.
_GM_ONLY = ("consequences", "hidden", "problems")
# The event log's format, written into `created`, so a later change to what events hold can
# tell the logs written before it apart.
FORMAT = 1
# Words a GM reaches for when it means an item: the refusal says how to write it.
_MONEY = {"gear", "silver", "gold", "copper", "money", "coins", "coin", "treasure", "inventory", "equipment"}
_LOG_SIZE = 40
# The Book's feed: speech and what the player saw happen, oldest first.
_STORY_SIZE = 150


def find(start=None):
    """The campaign folder at or above `start`, or else at or above the working directory,
    falling back to the current campaign recorded by `solo use`. A folder named on purpose
    (-C) never falls back: a stale path must not roll dice in some other game."""
    here = Path(start or Path.cwd()).expanduser().resolve()
    found = next((f for f in (here, *here.parents) if (f / "campaign.toml").exists()), None)
    if found is None and not start:
        found = library.current()
    if found is not None:
        return found
    elif start:
        raise SoloError(f"{here} isn't a campaign folder (no campaign.toml): pick one with `solo use <dir>`, or start one with `solo new <adventure>`")
    else:
        raise SoloError("no campaign here: start one with `solo new <adventure>` or pick one with `solo use <dir>`")


def set_current(root):
    pointer = library.state_home() / "current"
    pointer.parent.mkdir(parents=True, exist_ok=True)
    pointer.write_text(f"{Path(root).resolve()}\n", encoding="utf-8")


def create(root, system_path, adventure_path, character, title=None, prefs=None):
    """Start a campaign in `root` with `character`, a sheet or the path to one, and the
    player's table settings (tone, lines, veils). Refuses a folder that already holds a campaign."""
    root = Path(root).resolve()
    system = packs.load_system(system_path)
    adventure = packs.load_adventure(adventure_path, drafts=False)
    problems = packs.validate(system, adventure)
    if (root / "campaign.toml").exists():
        raise SoloError(f"{root} already holds a campaign")
    elif packs.missing(system):
        raise SoloError(packs.missing_text(system, packs.missing(system)))
    elif problems:
        raise SoloError("the packs need fixing first (solo validate):\n  " + "\n  ".join(problems))
    else:
        data = dict(character) if isinstance(character, dict) else packs.load_data(character)
        # A hero from an earlier campaign brings their story: what happened there, and the
        # hero.* facts the player gave them (see `hero`).
        past, carried = data.pop("past", None), data.pop("facts", None)
        pc = character_sheet(data, system)
        root.mkdir(parents=True, exist_ok=True)
        config = {
            "title": title or adventure["title"],
            "system": str(Path(system_path).resolve()),
            "adventure": str(Path(adventure_path).resolve()),
        }
        (root / "campaign.toml").write_text("".join(f"{k} = {packs.toml_string(v)}\n" for k, v in config.items()), encoding="utf-8")
        with session(root) as campaign:
            event = campaign.append("created", format=FORMAT, title=config["title"], pc=pc, scene=adventure["start"],
                                    past=past or None, facts=carried or None)
            campaign._follow([f"scene:{adventure['start']}"], cause=event["seq"])
            campaign._voices(event["seq"])
            if prefs and any(prefs.values()):
                campaign.set_prefs(**prefs)
        # The Book watches the GM's turn file, and a watch set on a file that isn't there yet
        # never fires: it waits here, idle, before the first turn writes it.
        (root / ".solo").mkdir(exist_ok=True)
        (root / ".solo" / "turn.json").write_text('{"status": "idle"}\n', encoding="utf-8")
        set_current(root)
        return root


def hero(root, name=None):
    """The hero of an earlier campaign, as they stand now, to carry into a new adventure:
    skills and gear as they were earned, rested (tracks full, conditions gone). Their story
    comes too: each earlier adventure in a few lines (`past`), and the hero.* facts."""
    with session(root) as c:
        pc = copy.deepcopy(c.state["pc"])
        past = [*c.state["past"], _looking_back(c)]
        facts = {k: v for k, v in c.state["facts"].items() if k.startswith("hero.")}
    if pc["dead"]:
        raise SoloError(f"{pc['name']} died in {Path(root).name}; the dead stay in the Hall of the Fallen")
    return {
        "name": name or pc["name"], "info": pc["info"], "attributes": pc["attributes"], "skills": pc["skills"],
        "tracks": {k: {"value": t["max"], "max": t["max"]} for k, t in pc["tracks"].items()},
        "conditions": [], "items": pc["items"], "abilities": pc["abilities"], "ratings": pc["ratings"],
        "past": past, "facts": facts,
    }


def _looking_back(c):
    """One adventure as the hero carries it into the next: how it ended, the last chronicle
    entries, what was left open, and the people who will remember them."""
    state = c.state
    people = [
        f"{npc['name']} ({_attitude_word(npc['attitude'])}" + (f", {npc['fate']}" if npc["fate"] != "alive" else "") + ")"
        + (f": {npc['memories'][-1]}" if npc["memories"] else "")
        for nid, npc in state["npcs"].items()
        if npc["met"] and npc["memories"] and not profile_of(c.adventure, state, nid).get("many")
    ]
    loose = [f"{p['terms']} (a promise, {state['npcs'].get(p['npc'], {}).get('name', p['npc'])})"
             for p in state["promises"].values() if p["status"] == "open"]
    loose += [k["text"] for k in state["consequences"].values() if k["status"] == "open"]
    return {
        "title": c.config["title"], "ended": (state["ended"] or {}).get("text"),
        "chronicle": [entry["text"] for entry in state["chronicle"][-3:]],
        "loose_ends": loose, "people": people[-12:],
    }


def character_sheet(data, system):
    """Normalise a pc.toml / pc.json into the sheet the engine keeps in state."""
    tracks = {}
    for name, value in data.get("tracks", {}).items():
        if isinstance(value, dict):
            top = value.get("max", value.get("value", 0))
            tracks[name] = {"value": int(value.get("value", top)), "max": int(top)}
        else:
            tracks[name] = {"value": int(value), "max": int(value)}
    attributes = {k: int(v) for k, v in data.get("attributes", {}).items()}
    skills = {}
    for key, value in data.get("skills", {}).items():
        entry = value if isinstance(value, dict) else {"value": value}
        known = system["skills"].get(slug(key), {})
        skills[slug(key)] = {
            "value": int(entry.get("value", 0)),
            "attribute": entry.get("attribute") or known.get("attribute"),
            "name": entry.get("name") or known.get("name") or key,
            "trained": bool(entry.get("trained", True)),
        }
    # Every skill the system knows goes on the sheet, so the panel can offer it:
    # ones the sheet leaves out are untrained, at their base chance.
    for key, skill in system["skills"].items():
        if key not in skills and skill["untrained"]:
            value = packs.base_chance(system, attributes.get(skill["attribute"], 0))
            skills[key] = {"value": value, "attribute": skill["attribute"], "name": skill["name"], "trained": False}
    sheet = {
        "name": data.get("name", "The hero"),
        "info": data.get("info", {}),
        "attributes": attributes,
        "skills": skills,
        "tracks": tracks,
        "conditions": [slug(c) for c in data.get("conditions", [])],
        "items": list(data.get("items", [])),
        "abilities": list(data.get("abilities", [])),
        "ratings": dict(data.get("ratings", {})),
    }
    attributes = system["attributes"]
    problems = (
        [f"missing attribute {a}" for a in attributes if a not in sheet["attributes"]]
        + [f"unknown attribute {a}" for a in sheet["attributes"] if a not in attributes]
        + [f"missing track {t}" for t in system["tracks"] if t not in tracks]
        + [f"unknown track {t}" for t in tracks if t not in system["tracks"]]
        + [f"unknown condition {c}" for c in sheet["conditions"] if c not in system["conditions"]]
        + [f"skill {k} has no attribute (add it to the system pack or give the skill an attribute)"
           for k, s in skills.items() if s["attribute"] not in attributes]
    )
    if problems:
        raise SoloError("character sheet: " + "; ".join(problems))
    else:
        return sheet


@contextmanager
def session(root):
    """Open a campaign under an exclusive lock, so the agent and the panel never write
    at the same time. state.json is rewritten on the way out if anything changed."""
    root = Path(root)
    with open(root / ".lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        campaign = Campaign(root)
        count = len(campaign.events)
        try:
            yield campaign
        except BaseException:
            # What a failed command wrote before it failed stands (a roll is never taken back),
            # but the state it was changing may be half changed: take it from the log again.
            if len(campaign.events) != count:
                campaign.state = fold(campaign.system, campaign.adventure, campaign.events)
            raise
        finally:
            if len(campaign.events) != count:
                # Whatever changed (a move, time passing, a click on the panel) may be the
                # moment a consequence was waiting for.
                campaign.come_due()
            if len(campaign.events) != count or not (root / "state.json").exists():
                campaign.save()


class Campaign:
    def __init__(self, root):
        self.root = Path(root)
        self.config = packs.load_data(self.root / "campaign.toml")
        self.system = packs.load_system(_pack(self.root, self.config["system"], library.find_system))
        self.adventure = packs.with_system(self.system, packs.load_adventure(_pack(self.root, self.config["adventure"], library.find_adventure), drafts=False))
        if self.adventure.get("weapons"):
            self.system["weapons"] = {**self.system.get("weapons", {}), **self.adventure["weapons"]}
        self.events = _read_events(self.root / "events.jsonl")
        # Where this session's own events begin: what one command did, whatever came first.
        self.opened = len(self.events)
        self.state = fold(self.system, self.adventure, self.events)
        self._chronology = None

    @property
    def problems(self):
        """What's wrong with the packs this campaign plays on, and events the replay passed over.
        The packs are read afresh every time, so an edit to one (a book's import laid over the
        bundled pack) reaches a campaign already under way: this says when it broke something."""
        return packs.validate(self.system, self.adventure) + self.state["problems"]

    def append(self, event_type, /, **data):
        event = {
            "seq": len(self.events) + 1,
            "at": datetime.now().isoformat(timespec="seconds"),
            "type": event_type,
            **{k: v for k, v in data.items() if v is not None},
        }
        # Dice fixed by SOLO_SEED say so in the log (and the Book shows it): otherwise a GM
        # could try seeds on a copy of the campaign and roll the one that lands well here.
        seed = dice.fixed_seed()
        if seed is not None:
            event["seed"] = seed
        # Applied before it is written: an event the state can't take is refused, never left
        # in the log for every later replay to trip over.
        apply(self.state, event, self.adventure)
        with open(self.root / "events.jsonl", "a", encoding="utf-8") as log:
            log.write(json.dumps(event, ensure_ascii=False) + "\n")
        self.events.append(event)
        return event

    def chronology(self):
        """The campaign replayed as moments with where and when (see `chronology`), kept
        until the log grows."""
        if self._chronology is None or self._chronology[0] != len(self.events):
            self._chronology = (len(self.events), chronology(self.system, self.adventure, self.events))
        return self._chronology[1]

    def come_due(self):
        """Consequences whose moment has just come (the hero walked back into the smithy, two
        shifts went by) are announced once, as a `due` event the GM reads and the player never
        sees. The GM pays it off in the story and commits it done."""
        for consequence_id, consequence in self.state["consequences"].items():
            if not consequence["due"] and ready(self.adventure, self.state, consequence):
                self.append("due", consequence=consequence_id, text=consequence["text"], npc=consequence["npc"])

    def save(self):
        path = self.root / "state.json"
        temporary = path.with_name("state.json.tmp")
        temporary.write_text(json.dumps(snapshot(self.system, self.state, self.adventure), ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(temporary, path)

    # Rolls -----------------------------------------------------------------------

    def check(self, name, boons=0, banes=0, rng=None, pushable=True, **extra):
        """Roll a skill or attribute. A condition tied to the roll's attribute adds a bane.
        `extra` marks what the roll is for (an attack, a defence) in the log."""
        self._able("roll")
        kind, key, label, attribute = self._stat(name)
        auto = self._condition_banes(attribute)
        outcome = self._resolve(kind, key, attribute, boons, banes + len(auto), rng)
        if not pushable:
            outcome["pushable"] = False
        event = self.append(
            "check", stat=key, kind=kind, label=label, attribute=attribute,
            boons=boons, banes=banes + len(auto), condition_banes=auto or None, outcome=outcome, **extra,
        )
        self._after_roll(event, rng)
        return event

    def push(self, condition=None, rng=None, sole_survivor=False):
        """Push the last check once. The cost comes from the system pack: a condition the
        character doesn't have yet (Dragonbane) or a track increase (stress in Alien). A hero
        with Sole Survivor may pay willpower instead of a condition."""
        self._able("push a roll")
        last = self.state["last_check"]
        cost = self.system["push"].get("cost", "condition")
        pc = self.state["pc"]
        if sole_survivor:
            ability = self._ability("push")
            if ability is None:
                raise SoloError(f"{pc['name']} doesn't have a heroic ability to push without a condition (Sole Survivor)")
            cost = {t: int(v) for t, v in ability["push"].items()}
            short = [t for t, v in cost.items() if pc["tracks"][t]["value"] < v]
            if short:
                raise SoloError(f"{ability.get('name', 'that')} costs {', '.join(f'{v} {t}' for t, v in cost.items())}, and {pc['name']} has too little {short[0]}")
            cost = {t: -v for t, v in cost.items()}
        available = [c for c in self.system["conditions"] if c not in pc["conditions"]]
        if last is None:
            raise SoloError("nothing to push: make a check first")
        elif last["type"] == "push":
            raise SoloError("that roll was already pushed")
        elif not last["outcome"]["pushable"]:
            raise SoloError("that roll can't be pushed: it succeeded or it was a Demon")
        elif cost == "condition" and not available:
            raise SoloError("every condition is already taken, so the roll can't be pushed")
        elif cost == "condition" and slug(condition or "") not in available:
            raise SoloError(f"choose the condition to take: {', '.join(available)}")
        else:
            if cost == "condition":
                changes = {"pc": {"conditions_add": [slug(condition)]}}
            else:
                tracks = {t: _clamp(pc["tracks"][t]["value"] + d, 0, pc["tracks"][t]["max"]) for t, d in cost.items()}
                changes = {"pc": {"tracks": tracks, "tracks_was": {t: pc["tracks"][t]["value"] for t in cost}}}
            if self.system["family"] == "d20-under":
                outcome = mechanics.d20_under(last["outcome"]["target"], last["boons"], last["banes"], rng)
            else:
                add = self.system["push"].get("add_dice", {})
                outcome = mechanics.d6_pool_push(last["outcome"], add, self.system.get("success", 6), rng)
            outcome["pushable"] = False
            event = self.append(
                "push", of=last["seq"], stat=last["stat"], kind=last["kind"], label=last["label"],
                attribute=last["attribute"], boons=last["boons"], banes=last["banes"],
                changes=changes, outcome=outcome, attack=last.get("attack"), search=last.get("search"), quiet=last.get("quiet"),
            )
            self._after_roll(event, rng)
            if last.get("search"):
                self._searched(event, rng)
            # A pushed attack that now hits deals its damage, if the target still stands.
            target = (self.state["combat"] or {}).get("foes", {}).get((last.get("attack") or {}).get("target"))
            if outcome["success"] and target and not target["down"]:
                self._strike(event, rng)
            return event

    def roll(self, expr, reason=None, rng=None):
        """Any dice expression; @track reads a track, as in 1d6+@stress."""
        return self.append("roll", expr=expr, reason=reason, result=dice.roll(self._substitute(expr), rng))

    def table(self, table_id, rng=None, cause=None, depth=0):
        """Roll on a table. A result can finish itself: `roll` (its value, put where the text
        says {value}: "{value} silver coins"),
        `choices` (one picked: the dagger or the longsword), `then` (another table to roll,
        like a treasure card) and `again` (roll this table once more)."""
        key, table, rolled, hit = self._roll_table(table_id, rng)
        hit = hit or {}
        text = hit.get("text", "") if hit else f"(the table has no result for {rolled['total']})"
        extra = {}
        if hit.get("choices"):
            extra["choice"] = hit["choices"][dice.pick(len(hit["choices"]), rng) - 1]
            text = f"{text}: {extra['choice']}"
        if hit.get("roll"):
            value = dice.roll(hit["roll"], rng)
            extra.update(value=value["total"], value_roll=value)
            text = text.replace("{value}", str(value["total"])) if "{value}" in text else f"{text} ({hit['roll']}: {value['total']})"
        event = self.append("table", table=key, name=table.get("name", key), roll=rolled, total=rolled["total"], text=text, cause=cause, **extra)
        if depth < 5:
            follow = [hit["then"]] if isinstance(hit.get("then"), str) else list(hit.get("then", []))
            for next_id in follow + ([key] if hit.get("again") else []):
                self.table(next_id, rng=rng, cause=event["seq"], depth=depth + 1)
        return event

    def ask(self, question, likely=None, npc=None, rng=None, kind=None):
        """Oracle for questions neither the adventure nor the rules answer. Likelihood is
        given, or read from an NPC's attitude and promises; it is never chosen to please.
        A system with a fortune chart (Dragonbane's solo rules) reads it; otherwise the
        likelihood oracle, where doubles within the chaos factor set off a random event."""
        if npc is not None and npc not in self.state["npcs"]:
            raise SoloError(f"unknown npc {npc!r}")
        level = (likely or (self._odds_for(npc) if npc else "even")).replace("_", " ")
        if self._chart():
            return self._fortune(question, level, kind or ("reaction" if npc and not likely else "yes_no"), npc, rng)
        elif kind:
            raise SoloError(f"{self.system['name']} has no fortune chart, so questions are yes or no (or --meaning)")
        if level in LIKELIHOOD:
            chance = LIKELIHOOD[level]
            roll = dice.roll("1d100", rng)["total"]
            if roll <= chance // 5:
                answer = "yes, and"
            elif roll <= chance:
                answer = "yes"
            elif roll > 100 - (100 - chance) // 5:
                answer = "no, and"
            else:
                answer = "no"
            surprise = self._random_event(rng) if oracle.is_event(roll, self.state["chaos"]) else None
            return self.append("oracle", question=question, likely=level, chance=chance, roll=roll, answer=answer, npc=npc, random_event=surprise)
        else:
            raise SoloError(f"likelihood must be one of: {', '.join(LIKELIHOOD)}")

    def meaning(self, question=None, rng=None):
        """Words for a question a yes or no can't answer: the system's inspiration columns
        (Dragonbane: an action, an attribute and a thing), or an action and a subject."""
        columns = self.system.get("oracle", {}).get("inspiration")
        tables = self._tables()
        if columns:
            words = [self._roll_table(column, rng)[3].get("text", "") for column in columns]
        else:
            words = oracle.meaning(tables, rng)
        return self.append("meaning", question=(question or "").strip() or None, words=words)

    def _chart(self):
        return self.system.get("oracle", {}).get("fortune") if self.system.get("oracle", {}).get("chart") == "fortune" else None

    def _fortune(self, question, level, kind, npc, rng):
        """The fortune chart: a D6 read in the column that fits the question. Likely high
        results roll 2D6 and keep the highest, likely low ones keep the lowest."""
        chart = self._chart()
        columns = {k: v for k, v in chart.items() if k != "bands"}
        kind = slug(kind)
        if kind not in columns:
            raise SoloError(f"the fortune chart reads {', '.join(columns)}; not {kind!r}")
        if level not in LIKELIHOOD:
            raise SoloError(f"likelihood must be one of: {', '.join(LIKELIHOOD)}")
        tilt = "high" if LIKELIHOOD[level] > 50 else "low" if LIKELIHOOD[level] < 50 else None
        formula = {"high": "2d6kh1", "low": "2d6kl1", None: "1d6"}[tilt]
        rolled = dice.roll(formula, rng)
        band = next(i for i, (low, high) in enumerate(chart["bands"]) if low <= rolled["total"] <= high)
        return self.append("oracle", question=question, chart="fortune", kind=kind, likely=level, tilt=tilt, dice=rolled,
                           roll=rolled["total"], answer=columns[kind][band], extreme=rolled["total"] in (1, 6), npc=npc)

    # Story ------------------------------------------------------------------------

    def say(self, text, by="gm"):
        """Record what the GM told the player, or what the player said, word for word, so a
        closed session reopens exactly where it stopped. The same words twice in a row from
        the same speaker are recorded once (a hook and a GM can both report a reply)."""
        text = (text or "").strip()
        if by not in SPEAKERS:
            raise SoloError(f"a speaker is one of: {', '.join(SPEAKERS)}")
        elif not text:
            raise SoloError("nothing to record: the text is empty")
        last = next((e for e in reversed(self.events) if e["type"] == "said"), None)
        if last is not None and last["by"] == by and last["text"] == text:
            return None
        else:
            return self.append("said", by=by, text=text, scene=self.state["scene"])

    def move(self, target, force=None, rng=None):
        """Take an exit (by scene id or label). `force` jumps to any scene and records why.
        An ordinary move rolls a scene check against the chaos factor: the scene may be
        altered, or interrupted by a random event. Forced moves (a clock filled) aren't checked."""
        self._able("move")
        here = self.state["scene"]
        every = packs.exits(self.adventure, here)
        key = slug(target)
        destination = key if key in every else self._exit_by_label(every, key, target)
        if destination is None and force and key in self.adventure["scenes"]:
            destination = key
        if destination is None:
            listed = ", ".join(f"{sid} ({spec['label']})" for sid, spec in every.items() if packs.is_open(spec, self.state)) or "none"
            raise SoloError(f"no exit {target!r} from {here}; exits: {listed}")
        elif not force and destination in every and not packs.is_open(every[destination], self.state):
            # A gated way (hidden stairs, a locked door) stays shut until the story opens it.
            raise SoloError(f"the way to {destination} isn't open yet (it opens when {every[destination]['when']}); "
                            "if the hero opened it, commit that first")
        else:
            check = None
            if not force and self.adventure["scene_checks"] and self.system.get("oracle", {}).get("scene_checks", True):
                check = oracle.scene_check(self.state["chaos"], rng)
                if check["result"] == "interrupted":
                    check["event"] = self._random_event(rng)
            spent = {} if force else (every[destination]["time"] if destination in every and every[destination]["time"] else self.adventure["move_time"])
            seconds = self._seconds(spent)
            before = self.state["time"]
            event = self.append("move", to=destination, forced=force, scene_check=check, time=seconds or None, **{"from": here})
            self._follow([f"scene:{destination}"] + self._time_triggers(before, before + seconds), cause=event["seq"], rng=rng)
            if seconds:
                self._burn(event["seq"])
            self._voices(event["seq"], rng)
            return event

    def _exit_by_label(self, every, key, target):
        """An exit by its label, or a word of it: a whole label first, then the one exit it
        fits, the open ones before those still shut. A word that fits two ways is refused
        rather than guessed, because a move can't be taken back."""
        fits = [sid for sid, spec in every.items() if key and key in slug(spec["label"])]
        whole = [sid for sid in fits if slug(every[sid]["label"]) == key]
        picks = whole or [sid for sid in fits if packs.is_open(every[sid], self.state)] or fits
        if len(picks) > 1:
            named = ", ".join(f"{sid} ({every[sid]['label']})" for sid in picks)
            raise SoloError(f"{target!r} could be {named}: name the exit")
        return picks[0] if picks else None

    # Voices ---------------------------------------------------------------------------
    #
    # The hero's skills speak up, the way they do in Disco Elysium. A scene lists voices
    # (a skill and what it notices); entering the scene rolls each one quietly. A success
    # puts the line in the Book and in `solo scene`; a failure stays silent, so the player
    # never learns what they missed. The GM can raise one too with `solo voice`.

    def voice(self, skill, text, rng=None):
        """The GM offers a thought one of the hero's skills might have; the dice decide
        whether the hero has it. The line is recorded (and shown) only on a success."""
        self._able("notice anything")
        text = (text or "").strip()
        if not text:
            raise SoloError("a voice needs the line the skill would say")
        return self._voice(skill, text, source="gm", rng=rng)

    def _voices(self, cause, rng=None):
        scene_id = self.state["scene"]
        if self.state["pc"]["dead"] or self.state["pc"]["dying"]:
            return
        for index, spec in enumerate(self.adventure["scenes"][scene_id].get("voices", [])):
            if not spec.get("when") or packs.evaluate(spec["when"], self.state):
                self._voice(spec["skill"], spec["text"], source="scene", rng=rng, cause=cause, index=index,
                            clue=spec.get("clue"), boons=int(spec.get("boons", 0)), banes=int(spec.get("banes", 0)))

    def _voice(self, skill, text, source, rng=None, cause=None, index=None, clue=None, boons=0, banes=0):
        kind, key, label, attribute = self._stat(skill)
        auto = self._condition_banes(attribute)
        outcome = self._resolve(kind, key, attribute, boons, banes + len(auto), rng)
        outcome["pushable"] = False
        heard = bool(outcome["success"])
        return self.append(
            "voice", stat=key, label=label, text=text, heard=heard, outcome=outcome, source=source,
            scene=self.state["scene"], cause=cause, index=index, clue=slug(clue) if clue and heard else None,
        )

    # Searching and scavenging -------------------------------------------------------------

    def search(self, rng=None):
        """Search an area with care (the solo rules, p. 10): it takes a stretch, so active
        threats advance, then SPOT HIDDEN. A Dragon rolls the search table twice (the player
        picks one), a success once, a failure finds nothing, and a Demon finds nothing and
        brings a new danger."""
        self._able("search")
        spec = self.system.get("search")
        if not spec:
            raise SoloError(f"{self.system['name']} has no [search] in its system pack")
        self._record("commit", {"note": "a careful search", "time": spec.get("time", {})}, rng)
        event = self.check(spec["skill"], rng=rng, search=True, quiet=True)
        self._searched(event, rng)
        return event

    def _searched(self, event, rng):
        outcome, table = event["outcome"], self.system["search"]["table"]
        if outcome.get("success"):
            for _ in range(2 if outcome.get("dragon") else 1):
                self.table(table, rng=rng, cause=event["seq"])

    def scavenge(self, again=False, rng=None):
        """Rummage through something specific (p. 9): a minute or two, but scavenging the same
        place again takes a stretch, and active threats advance."""
        self._able("scavenge")
        spec = self.system.get("scavenge")
        if not spec:
            raise SoloError(f"{self.system['name']} has no [scavenge] in its system pack")
        if again:
            self._record("commit", {"note": "scavenging again", "time": spec.get("again_time", {})}, rng)
        return self.table(spec["table"], rng=rng)

    # Light ----------------------------------------------------------------------------
    #
    # A torch burns down as game time passes (the system pack says for how long). The Book
    # draws it; the GM reads "It's dark here" in `solo scene` when the scene is dark and
    # nothing burns.

    def light(self, source=None, rng=None):
        """Light a carried light source: one comes off the hero's gear."""
        self._able("light anything")
        sources = self.system.get("light", {})
        key = slug(source) if source else next(iter(sources), None)
        spec = sources.get(key or "")
        if not sources:
            raise SoloError(f"{self.system['name']} has no [light] section in its system pack")
        elif spec is None:
            raise SoloError(f"no light source {source!r}; the system has {', '.join(sources)}")
        elif self.state["light"]:
            raise SoloError(f"{self.state['light']['label'].lower()} is already burning")
        item = spec.get("item", key)
        carried = next((i for i in self.state["pc"]["items"] if _count_of(i, item) is not None), None)
        if carried is None:
            raise SoloError(f"{self.state['pc']['name']} isn't carrying a {item}")
        left = _count_of(carried, item) - 1
        items = {"remove": [carried], "add": [f"{left} {_plural(item)}" if left > 1 else item] if left else []}
        burns = sum(int(self.system["time"][unit] * amount) for unit, amount in spec.get("lasts", {"shift": 1}).items())
        label = spec.get("label", key.capitalize())
        return self._record("light", {"note": f"lit a {label.lower()}", "pc": {"items": items}}, rng, source=key, label=label, lit=True, burns=burns)

    def snuff(self):
        lit = self.state["light"]
        if lit is None:
            raise SoloError("nothing is burning")
        return self.append("light", source=lit["source"], label=lit["label"], lit=False, reason="put out", changes={})

    def _burn(self, cause):
        """A light that has burned its time goes out (called after time passes)."""
        lit = self.state["light"]
        if lit and self.state["time"] >= lit["lit_at"] + lit["burns"]:
            self.append("light", source=lit["source"], label=lit["label"], lit=False, reason="burned out", cause=cause, changes={})

    def commit(self, payload, rng=None):
        """Apply the consequences the agent proposes, after checking them against the packs."""
        return self._record("commit", payload, rng)

    def rest(self, rest_id, heal=None, rng=None, tend=False):
        """A rest from the system pack: recover tracks, heal conditions, let time pass (which
        may tick clocks). A `limit` allows one per time unit: Dragonbane's round and stretch
        rests are once per shift. `heal` names the condition to heal first."""
        self._able("rest")
        key = slug(rest_id)
        spec = self.system["rest"].get(key)
        pc = self.state["pc"]
        if self.state["combat"]:
            raise SoloError("no resting in the middle of a fight")
        elif spec is None:
            raise SoloError(f"no rest {rest_id!r}; rests: {', '.join(self.system['rest']) or 'none'}")
        label = spec.get("label", key.capitalize())
        unit = self.system["time"].get(spec.get("limit"))
        taken = self.state["rests"].get(key)
        if unit and taken is not None and taken // unit == self.state["time"] // unit:
            raise SoloError(f"you've already taken a {label.lower()} this {spec['limit']}")
        elif heal and not spec.get("heal"):
            raise SoloError(f"a {label.lower()} heals no conditions; {self._healing_rests()}")
        elif heal and slug(heal) not in pc["conditions"]:
            raise SoloError(f"you don't have {heal}; conditions: {', '.join(pc['conditions']) or 'none'}")
        else:
            tracks, rolls = {}, {}
            recover = dict(spec.get("recover", {}))
            tended = None
            if tend:
                # The solo hero tends their own wounds: a skill roll, and more back on a success.
                if not spec.get("tend"):
                    raise SoloError(f"a {label.lower()} has no tending in {self.system['name']}'s rules")
                tended = self.check(spec["tend"]["skill"], rng=rng, quiet=True)
                if tended["outcome"]["success"]:
                    recover.update(spec["tend"].get("recover", {}))
                pc = self.state["pc"]
            for track, amount in recover.items():
                current = pc["tracks"][track]
                if amount == "max":
                    value = current["max"]
                else:
                    rolls[track] = dice.roll(amount, rng)["total"]
                    value = min(current["max"], current["value"] + rolls[track])
                if value != current["value"]:
                    tracks[track] = value
            held = ([slug(heal)] if heal else []) + [c for c in pc["conditions"] if c != slug(heal or "")]
            count = len(held) if spec.get("heal") == "all" else int(spec.get("heal", 0))
            payload = {"note": label, "pc": {**tracks, "conditions": {"remove": held[:count]}}, "time": spec.get("time", {})}
            return self._record("rest", payload, rng, rest=key, rolls=rolls or None, tended=tended and tended["seq"])

    def _healing_rests(self):
        healing = [r.get("label", rid.capitalize()).lower() for rid, r in self.system["rest"].items() if r.get("heal")]
        return f"a {' or a '.join(healing)} does" if healing else "no rest does"

    # Fights -------------------------------------------------------------------------
    #
    # The minimum a fight needs to run from code: who acts when, whether a blow lands,
    # and how much gets through armor. Tactics, morale and what a hit looks like stay
    # with the GM. Foes need stats.hp (and armor) in the adventure's NPC files, plus an
    # `attack` (a skill roll) or `attacks` (a monster table whose results carry damage).

    def fight(self, foes, rng=None):
        """Start a fight with these NPCs (repeat an id for several of the same kind) and
        deal initiative for the first round."""
        self._able("start a fight")
        if self.state["combat"]:
            raise SoloError("a fight is already on: solo fight --round for the next round, or solo fight --end")
        elif not self.system.get("combat"):
            raise SoloError(f"{self.system['name']} has no [combat] section, so fights are narrated and committed")
        elif not foes:
            raise SoloError("name who the hero fights: solo fight <npc> [<npc> ...]")
        roster = self._roster(foes, {})
        return self.append("fight", foes=roster, round=1, order=self._initiative(roster, rng))

    def join(self, foes, rng=None):
        """More foes enter the fight. They draw from the cards left this round."""
        fight = self._fight()
        joining = self._roster(foes, fight["foes"])
        used = {f["card"] for f in fight["order"]}
        left = [c for c in range(1, int(self.system["combat"].get("initiative", 10)) + 1) if c not in used]
        if len(joining) > len(left):
            raise SoloError("not enough initiative cards left this round; join them next round")
        if sum(self._cards(fid, foe) for fid, foe in joining.items()) > len(left):
            raise SoloError("not enough initiative cards left this round; join them next round")
        order = []
        for foe_id, foe in joining.items():
            for _ in range(self._cards(foe_id, foe)):
                card = left.pop(dice.pick(len(left), rng) - 1)
                order.append({"id": foe_id, "name": foe["name"], "card": card})
        order = sorted(fight["order"] + order, key=lambda f: f["card"])
        return self.append("join", foes=joining, order=order)

    def next_round(self, rng=None):
        """A new round: every fighter still standing draws a new initiative card."""
        fight = self._fight()
        # A round is game time too (ten seconds in Dragonbane), so a clock can count rounds.
        seconds = int(self.system["time"].get("round", 0))
        before = self.state["time"]
        event = self.append("round", round=fight["round"] + 1, order=self._initiative(fight["foes"], rng), time=seconds or None)
        if seconds:
            self._follow(self._time_triggers(before, before + seconds), event["seq"], rng)
            self._burn(event["seq"])
        return event

    def end_fight(self):
        fight = self._fight()
        standing = [f["name"] for f in fight["foes"].values() if not f["down"]]
        return self.append("fight_end", rounds=fight["round"], standing=standing)

    def attack(self, target=None, weapon=None, boons=0, banes=0, rng=None):
        """The hero attacks a foe with a carried weapon: a skill check, then on a hit the
        weapon's damage (plus the hero's damage bonus) minus the foe's armor."""
        if self._fight()["incoming"]:
            raise SoloError("answer the hit coming at the hero first: defend evade, parry or take")
        foe_id = self._foe(target)
        arm = combat.weapon(self.system, self.state["pc"], weapon, "attack")
        turns = sum(1 for f in self._fight()["order"] if f["id"] == "pc")
        if self._count_this_round(lambda e: e["type"] == "check" and e.get("attack")) >= turns:
            raise SoloError(f"{self.state['pc']['name']} has already attacked this round; the next round comes with solo fight --round")
        attack = {"weapon": arm["id"], "label": arm["label"], "target": foe_id}
        event = self.check(arm["skill"], boons, banes, rng, attack=attack)
        if event["outcome"]["success"]:
            self._strike(event, rng)
        return event

    def enemy(self, foe=None, rng=None):
        """A foe attacks the hero. A monster rolls on its attack table; anyone else rolls
        their attack skill. A hit waits as `incoming` until the hero defends or takes it."""
        fight = self._fight()
        if self.state["pc"]["dead"]:
            raise SoloError(f"{self.state['pc']['name']} is dead")
        elif fight["incoming"]:
            raise SoloError(f"{fight['incoming']['name']}'s attack is still waiting: defend evade, defend parry or defend take")
        foe_id = self._foe(foe)
        foe = fight["foes"][foe_id]
        profile = self._profile(foe["npc"])
        dragon_rule = self.system["combat"].get("dragon")
        attacker = profile.get("attacker")
        roles = attacker if isinstance(attacker, list) else [attacker] if attacker else []
        pending = (fight.get("pending") or {}).get(foe_id)
        if (roles or pending) and self.system.get("npcs", {}).get("attacks"):
            return self._npc_turn(foe_id, foe, profile, roles, pending, rng)
        elif profile.get("attacks"):
            key, table, rolled, hit = self._roll_table(profile["attacks"], rng)
            hit = hit or {}
            damage = hit.get("damage")
            # Monster attacks can be evaded but, in Dragonbane, not parried unless the attack says so.
            parry = hit.get("parry", table.get("parry", self.system["combat"].get("monster_parry", True)))
            incoming = {"damage": damage, "can_defend": hit.get("defend", True), "can_parry": bool(parry)} if damage else None
            if incoming and hit.get("armor") is False:
                incoming["armor"] = False  # a ghost's hand through the chest: armor doesn't help
            detail = {"table": key, "total": rolled["total"], "text": hit.get("text", ""), "label": _attack_name(hit.get("text", ""), table.get("name", key))}
        elif profile.get("attack"):
            spec = profile["attack"]
            if self.system["family"] != "d20-under":
                raise SoloError("skill attacks for foes are only built for d20-under systems; give the foe an attack table")
            value = int(spec.get("value") or profile.get("skills", {}).get(spec.get("skill", ""), 0))
            outcome = mechanics.d20_under(value, rng=rng)
            outcome["pushable"] = False
            damage = combat.damage_expression(spec["damage"], spec.get("bonus", ""), outcome["dragon"], dragon_rule)
            incoming = {"damage": damage, "can_defend": True} if outcome["success"] else None
            detail = {"outcome": outcome, "label": spec.get("label", "attack")}
        else:
            raise SoloError(f"{foe['name']} has no attack or attacks in the adventure pack; narrate it and commit the harm")
        if incoming:
            incoming.update({"from": foe_id, "name": foe["name"], "label": detail["label"]})
        return self.append("enemy", foe=foe_id, name=foe["name"], incoming=incoming, **detail)

    def _npc_turn(self, foe_id, foe, profile, roles, pending, rng):
        """A notable NPC's turn, from the solo rules' NPC attack table (p. 4): its role's
        column says what it does. An attack is a skill roll (it doesn't hit by itself), with
        the result's boons, banes and extra damage; anything else is for the GM to run."""
        if pending:
            role, entry, total = pending["role"], pending["entry"], pending["total"]
        else:
            role = roles[dice.pick(len(roles), rng) - 1] if len(roles) > 1 else roles[0]
            key, table, rolled, hit = self._roll_table(self.system["npcs"]["attacks"], rng)
            entry, total = (hit or {}).get(role, {}), rolled["total"]
        detail = {"table": "npc_attacks", "total": total, "text": entry.get("text", ""), "label": f"{role} attacker", "role": role}
        incoming, queued = None, None
        if entry.get("attack"):
            spec = profile.get("attack", {})
            value = int(spec.get("value") or profile.get("skills", {}).get(spec.get("skill", ""), 0))
            outcome = mechanics.d20_under(value, int(entry.get("boons", 0)), int(entry.get("banes", 0)), rng)
            outcome["pushable"] = False
            base = entry.get("damage") or spec.get("damage", "1d6")
            damage = combat.damage_expression(base, spec.get("bonus", "") if not entry.get("damage") else "", outcome["dragon"], self.system["combat"].get("dragon"))
            if entry.get("extra"):
                damage += f"+{entry['extra']}"
            incoming = {"damage": damage, "can_defend": True, "from": foe_id, "name": foe["name"], "label": detail["label"]} if outcome["success"] else None
            detail["outcome"] = outcome
            if int(entry.get("times", 1)) > 1 and not pending:
                # A volley: the second attack comes as the same result, without a new roll.
                queued = {"role": role, "entry": {**entry, "times": 1}, "total": total}
        return self.append("enemy", foe=foe_id, name=foe["name"], incoming=incoming, queued=queued, **detail)

    def ally(self, npc, target=None, rng=None):
        """An NPC fighting on the hero's side (Grukk, once he keeps his promise) attacks a foe
        with its own attack skill, once a round: the dice decide what an ally does, as they
        do for the hero. It isn't dealt initiative; the GM runs it when the story says."""
        fight = self._fight()
        npc_id = slug(npc)
        npc_state, profile = self.state["npcs"].get(npc_id), self._profile(npc_id)
        spec = profile.get("attack")
        if npc_state is None:
            raise SoloError(f"unknown npc {npc!r}; npcs: {', '.join(self.state['npcs']) or 'none'}")
        elif npc_state["fate"] != "alive":
            raise SoloError(f"{npc_state['name']} is {npc_state['fate']}")
        elif any(f["npc"] == npc_id and not f["down"] for f in fight["foes"].values()):
            raise SoloError(f"{npc_state['name']} is fighting against the hero in this fight")
        elif not spec or self.system["family"] != "d20-under":
            raise SoloError(f"{npc_state['name']} has no attack skill in the adventure pack; narrate what they do and commit it")
        elif self._this_round(lambda e: e["type"] == "ally" and e["npc"] == npc_id):
            raise SoloError(f"{npc_state['name']} has already attacked this round")
        foe_id = self._foe(target)
        foe = fight["foes"][foe_id]
        value = int(spec.get("value") or profile.get("skills", {}).get(spec.get("skill", ""), 0))
        outcome = mechanics.d20_under(value, rng=rng)
        outcome["pushable"] = False
        blow = {}
        if outcome["success"]:
            expr = combat.damage_expression(spec["damage"], spec.get("bonus", ""), outcome["dragon"], self.system["combat"].get("dragon"))
            rolled = dice.roll(expr, rng)
            dealt = max(0, rolled["total"] - foe["armor"])
            hp = max(0, foe["hp"] - dealt)
            blow = {"expr": expr, "roll": rolled, "armor": foe["armor"], "dealt": dealt, "hp": hp, "hp_was": foe["hp"], "down": hp == 0}
        event = self.append("ally", npc=npc_id, name=npc_state["name"], label=spec.get("label", "attack"),
                            target=foe_id, target_name=foe["name"], outcome=outcome, **blow)
        self._settle()
        return event

    def wound(self, target, amount, why, armor=True, double=False, rng=None):
        """Harm to a foe that isn't a weapon blow: fire, a spell, a falling bookcase, one
        creature turned on another, or a power that ends it where it stands ("all").
        The GM rules that it happens; the dice (or the adventure's number) say how much."""
        if not (why or "").strip():
            raise SoloError("say what does the harm: --why \"the torch sets it alight\"")
        if slug(target) in ("hero", "pc", slug(self.state["pc"]["name"])):
            return self._hurt(amount, why, armor, double, rng)
        foe_id = self._foe(target)
        foe = self._fight()["foes"][foe_id]
        text = str(amount).strip().lower()
        if text == "all":
            rolled, dealt = None, foe["hp"]
        else:
            rolled = dice.roll(text, rng)
            dealt = max(0, rolled["total"] * (2 if double else 1) - (foe["armor"] if armor else 0))
        hp = max(0, foe["hp"] - dealt)
        event = self.append("wound", target=foe_id, name=foe["name"], why=why.strip(), expr=None if rolled is None else text,
                            roll=rolled, armor=foe["armor"] if armor and rolled else 0, double=double or None,
                            dealt=dealt, hp=hp, hp_was=foe["hp"], down=hp == 0)
        self._settle()
        return event

    def _hurt(self, amount, why, armor, double, rng):
        """Harm to the hero that no foe's attack brings: a fall, a trap, a vent of steam.
        The dice are rolled here; the hero's armor helps unless the harm goes through it."""
        self._able("be hurt") if not self.state["pc"]["dying"] else None
        rolled = dice.roll(str(amount), rng)
        worn = combat.kit(self.system, self.state["pc"])["armor"] if armor else 0
        dealt = max(0, rolled["total"] * (2 if double else 1) - worn)
        track = (self.system.get("combat") or {}).get("track", "hp")
        payload = {"note": why.strip(), **({"pc": {track: f"-{dealt}"}} if dealt else {})}
        return self._record("harm", payload, rng, expr=str(amount), roll=rolled, armor=worn, dealt=dealt, by=why.strip())

    def defend(self, how, weapon=None, rng=None):
        """Answer an incoming hit: evade or parry (a roll that can't be pushed; it stops
        the hit on a success) or take it. A failed defence takes the hit."""
        incoming = self._fight()["incoming"]
        how = slug(how)
        if incoming is None:
            raise SoloError("nothing is coming at the hero right now")
        elif how == "take":
            return self.take(rng)
        elif how == "resist":
            # Something the adventure grants against a kind of attack (a WIL roll that nullifies a
            # demon's blow): a roll with the named stat, and the hit is gone on a success.
            if not weapon:
                raise SoloError("resist with what? defend resist --with wil")
            event = self.check(weapon, rng=rng, pushable=False, defend={"how": "resist", "weapon": None, "against": incoming["from"]})
            if not event["outcome"]["success"]:
                self.take(rng, cause=event["seq"])
            return event
        elif how not in ("evade", "parry"):
            raise SoloError("defend with evade, parry, resist or take")
        elif not incoming.get("can_defend", True):
            raise SoloError(f"{incoming['label']} can't be dodged or parried: defend take")
        elif how == "parry" and not incoming.get("can_parry", True):
            raise SoloError(f"{incoming['label']} can't be parried: defend evade, or take")
        if how == "evade":
            skill, arm = self.system["combat"].get("evade", "evade"), None
        else:
            arm = combat.weapon(self.system, self.state["pc"], weapon, "parry")
            skill = arm["skill"]
        event = self.check(skill, rng=rng, pushable=False, defend={"how": how, "weapon": arm and arm["label"], "against": incoming["from"]})
        if not event["outcome"]["success"]:
            self.take(rng, cause=event["seq"])
        return event

    def take(self, rng=None, cause=None):
        """The incoming hit lands: roll its damage, subtract the hero's armor."""
        incoming = self._fight()["incoming"]
        if incoming is None:
            raise SoloError("nothing is coming at the hero right now")
        track = self.system["combat"].get("track", "hp")
        armor = combat.kit(self.system, self.state["pc"])["armor"] if incoming.get("armor", True) else 0
        rolled = dice.roll(incoming["damage"], rng)
        dealt = max(0, rolled["total"] - armor)
        payload = {"note": f"hit by {incoming['name']} ({incoming['label']})"}
        if dealt:
            payload["pc"] = {track: f"-{dealt}"}
        return self._record("harm", payload, rng, expr=incoming["damage"], roll=rolled, armor=armor, dealt=dealt, cause=cause,
                            by=incoming["name"], source=incoming["from"])

    # Dying ----------------------------------------------------------------------------

    def death_roll(self, rng=None):
        """At 0 HP the hero is dying and rolls each turn. Successes and failures count up
        to the pack's limits: enough successes and they rally, enough failures and they die.
        A Dragon counts as two successes, a Demon as two failures."""
        spec, pc = self.system.get("dying"), self.state["pc"]
        if not spec:
            raise SoloError(f"{self.system['name']} has no death rolls ([dying] in system.toml)")
        elif pc["dead"]:
            raise SoloError(f"{pc['name']} is dead")
        elif not pc["dying"]:
            raise SoloError(f"{pc['name']} isn't dying")
        elif self._this_round(lambda e: e["type"] in ("death_roll", "save_self")):
            raise SoloError(f"{pc['name']} has already made a death roll this round (or tried to save themselves); the next comes with solo fight --round")
        elif self._this_round(lambda e: e["type"] == "check" and e.get("attack")):
            # The death roll is the hero's turn: a hero struck down after attacking rolls next round.
            raise SoloError(f"{pc['name']} has already had their turn this round; the first death roll comes with solo fight --round")
        kind, key, label, attribute = self._stat(spec["roll"])
        auto = self._condition_banes(attribute)
        outcome = self._resolve(kind, key, attribute, 0, len(auto), rng)
        outcome["pushable"] = False
        successes = 2 if outcome.get("dragon") else int(outcome["success"])
        failures = 2 if outcome.get("demon") else int(not outcome["success"])
        payload, result = {}, None
        if pc["dying"]["successes"] + successes >= int(spec.get("rally", 3)):
            recovered = dice.roll(str(spec.get("recover", "1")), rng)["total"]
            payload = {"note": f"{pc['name']} rallies", "pc": {spec["track"]: f"+{recovered}"}}
            result = "rallies"
        elif pc["dying"]["failures"] + failures >= int(spec.get("die", 3)):
            result = "dies"
        return self._record(
            "death_roll", payload, rng, label=label, outcome=outcome, condition_banes=auto or None,
            successes=successes, failures=failures, result=result,
        )

    # A new hero -----------------------------------------------------------------------

    def take_over(self, character, name=None, seed=None):
        """The hero is dead but the story goes on: the player takes up another character
        where it stands (a written replacement like the dwarf in the trapdoor, a pre-made,
        or a new roll). The dead hero stays in the story's memory and the Hall of the Fallen.
        An NPC the adventure offered as the replacement leaves the cast: they are the hero now."""
        pc = self.state["pc"]
        if not pc["dead"]:
            raise SoloError(f"{pc['name']} is still alive; a new hero takes over only after a death")
        sheet = character_sheet(creation.character(self.system, character, name=name, seed=seed, adventure=self.adventure), self.system)
        npc = slug(character) if slug(character) in self.state["npcs"] else None
        return self.append("hero", pc=sheet, npc=npc)

    def rally(self, rng=None):
        """Alone at zero HP, the hero rallies themselves (the solo rules, p. 5): a roll with no
        bane, and on a success they may act again, still making death rolls each round."""
        spec, pc = (self.system.get("dying") or {}).get("self_rally"), self.state["pc"]
        if not spec:
            raise SoloError(f"{self.system['name']} has no self_rally under [dying]")
        elif not pc["dying"]:
            raise SoloError(f"{pc['name']} isn't dying")
        elif pc["dying"].get("rallied"):
            raise SoloError(f"{pc['name']} has already rallied")
        kind, key, label, attribute = self._stat(spec["skill"])
        outcome = self._resolve(kind, key, attribute, 0, len(self._condition_banes(attribute)), rng)
        outcome["pushable"] = False
        return self.append("rally", label=label, outcome=outcome, rallied=bool(outcome["success"]))

    def save_self(self, rng=None):
        """Alone at zero HP, the hero tries to save their own life (p. 5): a HEALING roll that
        stops the dying and brings a little HP back on a success. It is their turn."""
        spec, pc = (self.system.get("dying") or {}).get("self_save"), self.state["pc"]
        if not spec:
            raise SoloError(f"{self.system['name']} has no self_save under [dying]")
        elif not pc["dying"]:
            raise SoloError(f"{pc['name']} isn't dying")
        elif self._this_round(lambda e: e["type"] in ("death_roll", "save_self")):
            raise SoloError(f"{pc['name']} has already had their turn this round; the next comes with solo fight --round")
        kind, key, label, attribute = self._stat(spec["skill"])
        outcome = self._resolve(kind, key, attribute, 0, len(self._condition_banes(attribute)), rng)
        outcome["pushable"] = False
        payload = {}
        if outcome["success"]:
            recovered = dice.roll(str(spec.get("recover", "1")), rng)["total"]
            payload = {"note": f"{pc['name']} saves their own life", "pc": {self.system["dying"]["track"]: f"+{recovered}"}}
        return self._record("save_self", payload, rng, label=label, outcome=outcome, saved=bool(outcome["success"]))

    # Advancement ------------------------------------------------------------------------

    def mark(self, skill, reason=None):
        """Mark a skill for advancement (the end-of-session questions award these; Dragons
        and Demons on skill rolls mark them by themselves)."""
        if not self.system.get("advancement"):
            raise SoloError(f"{self.system['name']} has no [advancement] section")
        elif self.state["pc"]["dead"]:
            raise SoloError(f"{self.state['pc']['name']} is dead, so there is nothing left to learn")
        kind, key, label, _ = self._stat(skill)
        if kind != "skill":
            raise SoloError(f"only skills are marked, and {label} is an attribute")
        elif key not in self.state["pc"]["skills"]:
            raise SoloError(f"{label} can't be learned by marking it")
        elif key in self.state["pc"]["marks"]:
            raise SoloError(f"{label} is already marked")
        else:
            return self.append("mark", skill=key, label=label, reason=reason)

    def advance(self, rng=None):
        """Roll for every marked skill: above its value, it goes up one (to the pack's max).
        Every mark is used up either way."""
        spec, pc = self.system.get("advancement"), self.state["pc"]
        if not spec:
            raise SoloError(f"{self.system['name']} has no [advancement] section")
        elif pc["dead"]:
            raise SoloError(f"{pc['name']} is dead, so there is nothing left to learn")
        elif not pc["marks"]:
            raise SoloError("no skills are marked")
        results = []
        for key in pc["marks"]:
            skill = pc["skills"][key]
            total = dice.roll(spec.get("roll", "1d20"), rng)["total"]
            improves = total > skill["value"] and skill["value"] < int(spec.get("max", 18))
            results.append({"skill": key, "name": skill["name"], "roll": total, "was": skill["value"], "now": skill["value"] + improves})
        return self.append("advance", results=results)

    # Table settings ---------------------------------------------------------------------

    def set_prefs(self, tone=None, lines=None, veils=None, clear=False):
        """The player's table settings: the tone they want, lines (never in the story) and
        veils (happen off screen). The GM reads them at the start of every session."""
        now = {"tone": "", "lines": [], "veils": []} if clear else copy.deepcopy(self.state["prefs"])
        if tone is not None:
            now["tone"] = tone.strip()
        now["lines"] += [t.strip() for t in lines or [] if t.strip() and t.strip() not in now["lines"]]
        now["veils"] += [t.strip() for t in veils or [] if t.strip() and t.strip() not in now["veils"]]
        return self.append("prefs", **now)

    # Internals ----------------------------------------------------------------------

    def _able(self, action):
        pc = self.state["pc"]
        if pc["dead"]:
            raise SoloError(f"{pc['name']} is dead, so there is nothing left to {action}")
        elif pc["dying"] and not pc["dying"].get("rallied"):
            raise SoloError(f"{pc['name']} is dying and can't {action}: make a death roll (solo death-roll), rally (solo rally), or be healed")

    def _condition_banes(self, attribute):
        return [c for c in self.state["pc"]["conditions"] if self.system["conditions"].get(c) == attribute]

    def _resolve(self, kind, key, attribute, boons, banes, rng):
        family = self.system["family"]
        if family == "d20-under":
            return mechanics.d20_under(self._target(kind, key, attribute), boons, banes, rng)
        elif family == "d6-pool":
            return mechanics.d6_pool(self._pool(kind, key, attribute, boons - banes), self.system.get("success", 6), rng)
        else:
            raise SoloError(f"unknown mechanics family {family!r}")

    def _tables(self):
        return {**self.system["tables"], **self.adventure["tables"]}

    def _roll_table(self, table_id, rng):
        tables = self._tables()
        key = table_id if table_id in tables else slug(table_id)
        if key not in tables:
            close = [t for t in tables if key and key in t] or get_close_matches(key, list(tables), n=3)
            hint = f"; did you mean {', '.join(close)}?" if close else ""
            raise SoloError(f"no table {table_id!r}{hint}; tables: {', '.join(sorted(tables)) or 'none'}")
        table = tables[key]
        rolled = dice.roll(self._substitute(table["formula"]), rng)
        hit = next((r for r in table.get("results", []) if r["range"][0] <= rolled["total"] <= r["range"][1]), None)
        return key, table, rolled, hit

    def _random_event(self, rng):
        return oracle.random_event(self.state, self._tables(), rng)

    def _fight(self):
        if self.state["combat"] is None:
            raise SoloError("there is no fight on: start one with solo fight <npc> ...")
        return self.state["combat"]

    def to_act(self):
        """Who hasn't acted yet this round, in initiative order: the hero until they attack
        (or roll against death), each standing foe until it attacks. Anything else the hero
        does in their turn the engine can't see, so it only ever says who may still be owed one."""
        fight = self.state["combat"]
        if fight is None:
            return []
        acted = Counter()
        for event in reversed(self.events):
            if event["type"] in ("fight", "round"):
                break
            elif event["type"] == "enemy" and not event.get("queued"):
                acted[event["foe"]] += 1
            elif event["type"] == "death_roll" or (event["type"] == "check" and event.get("attack")):
                acted["pc"] += 1
        # Each card is a turn: a monster with ferocity 2, or a hero with Army of One, holds two.
        standing = {"pc", *(fid for fid, foe in fight["foes"].items() if not foe["down"])}
        waiting = []
        for f in fight["order"]:
            if f["id"] not in standing:
                continue
            elif acted[f["id"]]:
                acted[f["id"]] -= 1
            else:
                waiting.append(f["name"])
        return waiting

    def _count_this_round(self, test):
        count = 0
        for event in reversed(self.events) if self.state["combat"] else []:
            if event["type"] in ("fight", "round"):
                break
            count += bool(test(event))
        return count

    def _this_round(self, test):
        """Whether an event of this round of the fight passes `test`. The hero acts once a
        round: without this, a button clicked again would attack (or roll against death)
        as often as the player likes. Outside a fight there are no rounds to count."""
        if self.state["combat"] is None:
            return False
        for event in reversed(self.events):
            if event["type"] in ("fight", "round"):
                return False
            elif test(event):
                return True
        return False

    def _profile(self, npc_id):
        """An NPC as it fights: the adventure's profile, with a template and a role set in play
        (the solo rules' simple NPCs: a minion or a boss; an attacker: melee, ranged, sneaky, magic)."""
        profile = copy.deepcopy(profile_of(self.adventure, self.state, npc_id))
        live = self.state["npcs"].get(npc_id, {})
        profile.update({k: live[k] for k in ("template", "attacker") if live.get(k)})
        template = self.system.get("npcs", {}).get("templates", {}).get(profile.get("template") or "")
        if template:
            profile["stats"] = {"hp": template["hp"], "armor": template.get("armor", 0), **profile.get("stats", {})}
            profile.setdefault("attack", {"label": "attack", "value": template["skill"], "damage": template["damage"]})
        return profile

    def _foe(self, name):
        """A standing foe by id or name; with none given, the only one left standing."""
        foes = self._fight()["foes"]
        standing = [fid for fid, f in foes.items() if not f["down"]]
        if name is None:
            if len(standing) == 1:
                return standing[0]
            raise SoloError(f"which foe? {', '.join(standing) or 'none are standing'}")
        key = slug(name)
        found = key if key in foes else next((fid for fid, f in foes.items() if slug(f["name"]) == key), None)
        if found is None:
            raise SoloError(f"no foe {name!r} in this fight; foes: {', '.join(foes)}")
        elif foes[found]["down"]:
            raise SoloError(f"{foes[found]['name']} is already down")
        return found

    def _roster(self, names, present):
        """Foes by NPC id, with their stats from the adventure. Repeating an id brings
        several of that kind: cultist, cultist_2 ..."""
        roster = {}
        for name in names:
            npc_id = slug(name)
            npc, profile = self.state["npcs"].get(npc_id), self._profile(npc_id)
            stats = profile.get("stats", {})
            if npc is None:
                raise SoloError(f"unknown npc {name!r}; npcs: {', '.join(self.state['npcs']) or 'none'}")
            elif npc["fate"] != "alive" and not profile.get("many"):
                # A kind of foe (cultists, skeletons) is never used up: every fight brings new ones.
                raise SoloError(f"{npc['name']} is {npc['fate']}")
            elif "hp" not in stats:
                raise SoloError(f"{npc_id} has no stats.hp in the adventure pack, so it can't be fought here: narrate it, or give it stats")
            count = sum(1 for foe in [*present.values(), *roster.values()] if foe["npc"] == npc_id)
            foe_id = npc_id if count == 0 else f"{npc_id}_{count + 1}"
            roster[foe_id] = {
                "npc": npc_id, "name": npc["name"] + (f" {count + 1}" if count else ""),
                "hp": int(stats["hp"]), "max": int(stats["hp"]), "armor": int(stats.get("armor", 0)), "down": False,
            }
            # A monster with ferocity 2 acts twice a round; an immune one shrugs off weapons.
            if int(stats.get("ferocity", 1)) > 1:
                roster[foe_id]["ferocity"] = int(stats["ferocity"])
            if stats.get("immune"):
                roster[foe_id]["immune"] = stats["immune"] if isinstance(stats["immune"], str) else "weapons"

        return roster

    def _cards(self, fighter_id, foe=None):
        """Initiative cards a fighter draws: a monster's ferocity; the hero's Army of One, two."""
        if fighter_id == "pc":
            return int((self._ability("initiative") or {}).get("initiative", 1))
        return int(foe.get("ferocity", 1))

    def _ability(self, key):
        """The system's heroic ability that does `key` (initiative, push), if the hero has it."""
        held = {slug(a) for a in self.state["pc"]["abilities"]}
        return next((spec for aid, spec in self.system.get("abilities", {}).items()
                     if key in spec and (aid in held or slug(spec.get("name", "")) in held)), None)

    def _initiative(self, foes, rng):
        fighters = [("pc", self.state["pc"]["name"])] * self._cards("pc")
        fighters += [(fid, f["name"]) for fid, f in foes.items() if not f["down"] for _ in range(self._cards(fid, f))]
        cards = combat.deal(int(self.system["combat"].get("initiative", 10)), len(fighters), rng)
        return sorted(({"id": fid, "name": name, "card": card} for (fid, name), card in zip(fighters, cards)), key=lambda f: f["card"])

    def _strike(self, event, rng):
        """Damage from an attack that hit: weapon dice (twice on a Dragon, if the pack says
        so) plus the damage bonus, minus the target's armor."""
        attack = event["attack"]
        arm = combat.weapons(self.system)[attack["weapon"]]
        foe = self.state["combat"]["foes"][attack["target"]]
        bonus = combat.damage_bonus(self.system, self.state["pc"], arm["bonus"])
        expr = combat.damage_expression(arm["damage"], bonus, event["outcome"].get("dragon", False), self.system["combat"].get("dragon"))
        rolled = dice.roll(expr, rng)
        dealt = 0 if foe.get("immune") else max(0, rolled["total"] - foe["armor"])
        hp = max(0, foe["hp"] - dealt)
        damage = self.append(
            "damage", of=event["seq"], target=attack["target"], name=foe["name"], weapon=arm["label"],
            expr=expr, roll=rolled, armor=foe["armor"], dealt=dealt, hp=hp, hp_was=foe["hp"], down=hp == 0,
            immune=foe.get("immune"),
        )
        self._settle()
        return damage

    def _settle(self):
        """A fight whose last foe is down, or whose hero is dead, is over: close it, so the
        hero can rest, the GM isn't asked to deal another round against nobody, and a hero
        who takes up the story doesn't walk into the blow that killed the last one."""
        fight = self.state["combat"]
        if fight and (all(foe["down"] for foe in fight["foes"].values()) or self.state["pc"]["dead"]):
            standing = [foe["name"] for foe in fight["foes"].values() if not foe["down"]]
            self.append("fight_end", rounds=fight["round"], standing=standing)

    def _record(self, kind, payload, rng=None, **extra):
        """Validate a commit-shaped payload, log it, move the clocks it names, and follow
        the triggers it sets off (facts, fates, promises, time passing)."""
        changes, clock_moves, warnings = self._normalize(payload)
        before = self.state["time"]
        event = self.append(kind, changes=changes, warnings=warnings or None, **extra)
        for clock_id, delta in clock_moves:
            for _ in range(abs(delta)):
                self._tick(clock_id, 1 if delta > 0 else -1, event["seq"], rng)
        self._follow(self._commit_triggers(changes, before), event["seq"], rng)
        if changes.get("time"):
            self._burn(event["seq"])
        self._settle()
        return event

    def _stat(self, name):
        """(kind, key, label, attribute) for a skill or attribute as the player typed it."""
        key = slug(name)
        attributes = self.system["attributes"]
        by_label = {slug(label): k for k, label in attributes.items()}
        skills = {**self.system["skills"], **self.state["pc"]["skills"]}
        if key in attributes or key in by_label:
            attribute = key if key in attributes else by_label[key]
            return "attribute", attribute, attributes[attribute], attribute
        elif key in skills:
            return "skill", key, skills[key]["name"], skills[key]["attribute"]
        else:
            close = get_close_matches(key, [*skills, *attributes], n=3, cutoff=0.75)
            hint = (f"; did you mean {', '.join(close)}?" if close
                    else f"; {self.system['name']} has: {', '.join([*attributes, *sorted(skills)])}")
            raise SoloError(f"no skill or attribute called {name!r}{hint}")

    def _target(self, kind, key, attribute):
        pc = self.state["pc"]
        if kind == "attribute":
            return pc["attributes"][attribute]
        elif key in pc["skills"]:
            return pc["skills"][key]["value"]
        elif self.system["skills"].get(key, {}).get("untrained", True):
            return packs.base_chance(self.system, pc["attributes"].get(attribute, 0))
        else:
            raise SoloError(f"{self.system['skills'][key]['name']} can't be used without training")

    def _pool(self, kind, key, attribute, modifier):
        """Dice groups for a d6-pool check. Boons add dice to the last pool group, banes
        remove dice from the last groups first; extra groups (stress) are never reduced."""
        pc = self.state["pc"]
        pool = []
        for name, spec in self.system.get("pool", {"base": "attribute", "skill": "skill"}).items():
            source, mode = (spec, "count") if isinstance(spec, str) else (spec["source"], spec.get("mode", "count"))
            if source == "attribute":
                value = pc["attributes"].get(attribute, 0)
            elif source == "skill":
                value = pc["skills"].get(key, {}).get("value", 0) if kind == "skill" else 0
            else:
                value = pc["tracks"].get(source, {}).get("value", 0)
            if mode == "step":
                pool.append({"name": name, "count": 1 if value >= 2 else 0, "sides": max(value, 2), "on_one": None})
            else:
                pool.append({"name": name, "count": value, "sides": 6, "on_one": None})
        if modifier > 0 and pool:
            pool[-1]["count"] += modifier
        remaining = max(0, -modifier)
        for group in reversed(pool):
            taken = min(group["count"], remaining)
            group["count"] -= taken
            remaining -= taken
        extra = []
        for name, spec in self.system.get("extra_dice", {}).items():
            count = spec.get("count", 0)
            value = pc["tracks"].get(count, {}).get("value", 0) if isinstance(count, str) else int(count)
            extra.append({"name": name, "count": value, "sides": int(spec.get("sides", 6)), "on_one": spec.get("on_one")})
        return pool + extra

    def _after_roll(self, event, rng):
        """Dragons, Demons and pool triggers (panic) roll their tables and move clocks.
        Outside a fight, a Dragon or a Demon also rolls the system's effect for it."""
        outcome = event["outcome"]
        triggers = [f"check:{name}" for name in ("dragon", "demon") if outcome.get(name)]
        effects = self.system.get("effects", {})
        if not self.state["combat"] and not event.get("attack") and not event.get("defend") and not event.get("quiet"):
            for name in ("dragon", "demon"):
                if outcome.get(name) and effects.get(name):
                    self.table(effects[name], rng=rng, cause=event["seq"])
        for name in outcome.get("triggers", []):
            triggers.append(f"check:{name}")
            table = self.system.get("triggers", {}).get(name, {}).get("table")
            if table:
                self.table(table, rng=rng, cause=event["seq"])
        self._follow(triggers, event["seq"], rng)

    def _odds_for(self, npc_id):
        """An NPC's attitude sets the odds; a kept or open promise raises them a step,
        a broken one lowers them."""
        step = self.state["npcs"][npc_id]["attitude"] + 2
        for promise in self.state["promises"].values():
            if promise["npc"] == npc_id:
                step += -1 if promise["status"] == "broken" else 1
        return _ODDS[_clamp(step, 0, len(_ODDS) - 1)]

    def _substitute(self, expr):
        tracks = (self.state["pc"] or {}).get("tracks", {})
        unknown = [name for name in re.findall(r"@(\w+)", expr) if name not in tracks]
        if unknown:
            raise SoloError(f"unknown track @{unknown[0]} in {expr!r}")
        else:
            return re.sub(r"@(\w+)", lambda m: str(tracks[m.group(1)]["value"]), expr)

    def _follow(self, triggers, cause, rng=None):
        """Advance every clock listening to these triggers. A clock that fills up fires
        clock:<id>:full, which other clocks may listen to in turn."""
        pending = Counter(triggers)
        rounds = 0
        while pending and rounds < 10:
            fired = Counter()
            # Which clocks run is settled before this batch: time that passed before a clock
            # started (the stretch whose stage set the tower sinking) doesn't count on it.
            specs = self._clock_specs()
            running = {cid for cid, spec in specs.items()
                       if not spec.get("while") or packs.evaluate(spec["while"], self.state)}
            for clock_id, spec in specs.items():
                clock = self.state["clocks"][clock_id]
                if not clock["stopped"] and any(pending[t] for t in spec.get("stop", [])):
                    # What the clock counted down to can't happen any more (the priest is dead).
                    self.append("clock", clock=clock_id, label=clock["label"], value=clock["value"],
                                segments=clock["segments"], full=clock["full"], stopped=True, cause=cause)
                if clock["stopped"]:
                    continue
                elif clock_id not in running:
                    # Not running yet (or any more): the sinking only counts rounds once it has begun.
                    continue
                times = sum(pending[t] for t in spec.get("advance", []))
                for _ in range(min(times, int(spec.get("segments", 1)))):
                    fired.update(self._tick(clock_id, 1, cause, rng))
            pending = fired
            rounds += 1

    def _clock_specs(self):
        """The adventure's clocks and the threats set in play, each with what advances it.
        A threat looms where the danger is: in a scene the adventure marks safe (the chapel,
        the village) time passes without bringing it closer. It waits for the hero's return."""
        threats = self.system.get("threats", {})
        safe = self.adventure["scenes"].get(self.state["scene"], {}).get("safe", False)
        live = {cid: {"advance": [] if safe else threats.get("advance", []), "segments": clock["segments"]}
                for cid, clock in self.state["clocks"].items() if clock.get("threat") and not clock["stopped"]}
        return {**self.adventure["clocks"], **live}

    def _clock_spec(self, clock_id):
        return self._clock_specs().get(clock_id) or self.adventure["clocks"].get(clock_id, {})

    def _tick(self, clock_id, delta, cause, rng=None):
        clock, spec = self.state["clocks"][clock_id], self._clock_spec(clock_id)
        value = _clamp(clock["value"] + delta, 0, clock["segments"])
        if value == clock["value"] or clock["stopped"]:
            return []
        else:
            was_full = clock["full"]
            full = value >= clock["segments"]
            event = self.append(
                "clock", clock=clock_id, label=clock["label"], value=value,
                segments=clock["segments"], full=full, cause=cause,
            )
            if delta > 0 and spec.get("on_tick"):
                self.table(spec["on_tick"], rng=rng, cause=event["seq"])
            if delta > 0:
                for stage in spec.get("stages", []):
                    if stage.get("at") == value:
                        self._stage(clock_id, stage, event["seq"], rng)
            if full and clock.get("threat"):
                self._threat_comes(clock_id, event["seq"])
            return [f"clock:{clock_id}:full"] if full and not was_full else []

    # Threats -------------------------------------------------------------------------
    #
    # The solo rules' looming dangers: a D6 counter from 1 that advances on delays, failures
    # and time spent (a stretch or more). At 6 it comes to pass. A threat inherent to the
    # mission resets to 1; any other is gone once it has happened.

    def threat(self, text=None, threat_id=None, recurring=False, rng=None, label=None):
        spec = self.system.get("threats")
        if not spec:
            raise SoloError(f"{self.system['name']} has no [threats] in its system pack")
        if not text:
            text = self._roll_table(spec["table"], rng)[3].get("text", "") if spec.get("table") else ""
        text = (text or "").strip()
        if not text:
            raise SoloError("a threat needs what happens when it triggers")
        key = slug(threat_id or " ".join(text.split()[:4]))
        if key in self.state["clocks"] and not self.state["clocks"][key]["stopped"]:
            raise SoloError(f"there is already a threat {key}")
        # The table shows the label ("Goblin scouts"); the text is what happens when it triggers.
        short = (label or "").strip() or key.replace("_", " ").capitalize()
        return self.append("threat", action="add", clock=key, label=short, text=text, recurring=recurring,
                           value=int(spec.get("start", 1)), segments=int(spec.get("segments", 6)))

    def advance_threat(self, threat_id=None, by=1, rng=None):
        """A delay, or an opening the hero gave it: the threat draws closer."""
        key = self._looming(threat_id)
        return self._record("commit", {"note": "the threat draws closer", "clock": {key: f"+{int(by)}"}}, rng)

    def end_threat(self, threat_id=None):
        key = self._looming(threat_id)
        return self.append("threat", action="end", clock=key, label=self.state["clocks"][key]["label"])

    def _looming(self, threat_id):
        """A threat still looming, by id; with none given, the only one. Only threats: an
        adventure's clocks (hidden ones too) move by their own triggers or by a commit."""
        live = [cid for cid, c in self.state["clocks"].items() if c.get("threat") and not c["stopped"]]
        key = slug(threat_id or "")
        if key in live:
            return key
        elif not key and len(live) == 1:
            return live[0]
        elif not key:
            raise SoloError(f"which threat? {', '.join(live) or 'none is looming'}")
        else:
            raise SoloError(f"no threat {threat_id!r}; threats: {', '.join(live) or 'none'}")

    def _threat_comes(self, clock_id, cause):
        clock = self.state["clocks"][clock_id]
        self.append("threat", action="triggered", clock=clock_id, label=clock["label"], text=clock["threat"].get("text"), cause=cause,
                    note="it happens now, before anything else: run it in this reply (a fight, a hazard), then go on")
        if clock["threat"]["recurring"]:
            start = int(self.system.get("threats", {}).get("start", 1))
            self.append("clock", clock=clock_id, label=clock["label"], value=start, segments=clock["segments"], full=False, cause=cause)
        else:
            self.append("threat", action="end", clock=clock_id, label=clock["label"], cause=cause)

    def _stage(self, clock_id, stage, cause, rng=None):
        """A clock reached one of its stages: what the player notices (text), what the GM
        must do (note), and what changes for good (facts, other clocks)."""
        moves = {c: v for c, v in stage.get("clock", {}).items() if not self.state["clocks"][c]["stopped"]}
        payload = {"facts": packs.flat_facts(stage.get("facts")), "clock": moves}
        clock = self.state["clocks"][clock_id]
        return self._record("stage", payload, rng, clock=clock_id, label=clock["label"], at=stage["at"],
                            segments=clock["segments"], text=stage.get("text"), note=stage.get("note"), cause=cause)

    def _commit_triggers(self, changes, before):
        triggers = [f"fact:{key}" for key, value in changes.get("facts", {}).items() if value]
        triggers += [f"npc:{nid}:{c['fate']}" for nid, c in changes.get("npc", {}).items() if "fate" in c]
        triggers += [
            f"promise:{pid}:{p['status']}" for pid, p in changes.get("promise", {}).items()
            if p["status"] != p.get("status_was")
        ]
        return triggers + self._time_triggers(before, before + changes.get("time", 0))

    def _time_triggers(self, before, after):
        """time:<unit> once for every boundary of that unit crossed between two moments."""
        return [f"time:{unit}" for unit, seconds in self.system["time"].items() for _ in range(int(after // seconds - before // seconds))]

    def _seconds(self, spent):
        """{ stretch = 2 } in seconds, in the system's own time units."""
        seconds = 0
        for unit, amount in (spent or {}).items():
            if unit in self.system["time"]:
                seconds += int(self.system["time"][unit] * amount)
            else:
                raise SoloError(f"unknown time unit {unit}; the system has {', '.join(self.system['time']) or 'none'}")
        return seconds

    def _normalize(self, payload):
        """Check a commit against the packs and the current state. Returns absolute changes
        (so the log reads without context), clock moves, and warnings about clamping."""
        if not isinstance(payload, dict):
            raise SoloError("a commit is a JSON object")
        warnings = []
        payload = dict(payload)
        for alias, key in _KEY_ALIASES.items():
            # "npcs" for "npc": the meaning is plain, so it is read and said, not refused.
            if alias in payload and key not in payload:
                payload[key] = payload.pop(alias)
                warnings.append(f"read {alias} as {key}")
        unknown = sorted(set(payload) - _COMMIT_KEYS)
        if unknown:
            money = "; coins and gear are items: {\"pc\": {\"items\": {\"add\": [\"30 silver\"]}}}" if set(unknown) & _MONEY else ""
            memory = ('; a memory belongs to someone: {"npc": {"<id>": {"memory": "..."}}}, or to a faction: '
                      '{"faction": {"<id>": {"memory": "..."}}}') if set(unknown) & {"memory", "memories"} else ""
            raise SoloError(f"unknown commit keys: {', '.join(unknown)} (allowed: {', '.join(sorted(_COMMIT_KEYS))}){money}{memory}")
        override = payload.get("override")
        changes = {}
        for key in ("note", "chronicle", "end"):
            if payload.get(key):
                changes[key] = str(payload[key])
        if payload.get("chaos") is not None:
            low, high = oracle.CHAOS_RANGE
            chaos = _clamp(_shift(payload["chaos"], self.state["chaos"]), low, high)
            if chaos != self.state["chaos"]:
                changes["chaos"] = {"value": chaos, "was": self.state["chaos"]}
        if override:
            changes["override"] = str(override)
        facts = self._facts(payload.get("facts", {}))
        npcs = self._npc_changes(payload.get("npc", {}), override)
        factions = self._faction_changes(payload.get("faction", {}), override)
        promises = self._promise_changes(payload.get("promise", []), npcs)
        pc, pc_warnings = self._pc_changes(payload.get("pc", {}), override)
        warnings += pc_warnings
        clues = payload.get("clue", [])
        clues = [slug(c) for c in ([clues] if isinstance(clues, str) else clues)]
        learn = self._learn(payload.get("learn", []), npcs)
        consequences = self._consequence_changes(payload.get("consequence", []), npcs)
        seconds = self._seconds(payload.get("time", {}))
        clock_moves = []
        for clock_id, value in payload.get("clock", {}).items():
            if clock_id in self.state["clocks"] and self.state["clocks"][clock_id]["stopped"]:
                raise SoloError(f"clock {clock_id} has stopped for good; it doesn't move any more")
            elif clock_id in self.state["clocks"]:
                clock = self.state["clocks"][clock_id]
                target = _clamp(_shift(value, clock["value"]), 0, clock["segments"])
                clock_moves.append((clock_id, target - clock["value"]))
            else:
                raise SoloError(f"unknown clock {clock_id}; clocks: {', '.join(self.state['clocks']) or 'none'}")
        parts = {"facts": facts, "npc": npcs, "faction": factions, "promise": promises, "pc": pc, "clues": clues, "learn": learn,
                 "consequence": consequences, "time": seconds}
        changes.update({key: value for key, value in parts.items() if value})
        return changes, clock_moves, warnings

    def _facts(self, facts):
        for key, value in facts.items():
            if not packs.FACT_KEY.match(key):
                raise SoloError(f"fact {key!r}: use lowercase words joined by dots, like hall.alarm")
            elif value is not None and not isinstance(value, (bool, int, float, str)):
                raise SoloError(f"fact {key!r}: a value must be true/false, a number or text")
        return dict(facts)

    def _learn(self, items, new_npcs=None):
        """What the player has found out about an NPC: `<npc>.wants`, `<npc>.fears` or
        `<npc>.<secret id>`. The codex shows these; everything else stays blanked out.
        An NPC the GM made up can be learned about too, from what the GM wrote down."""
        result = []
        if isinstance(items, dict):
            # {"gudrun": "wants"} or {"gudrun": ["wants", "fears"]}: the same as "gudrun.wants".
            items = [f"{npc_id}.{what}" for npc_id, whats in items.items() for what in _listed(whats)]
        for item in [items] if isinstance(items, str) else items:
            npc_id, _, what = str(item).partition(".")
            profile = None
            if npc_id in self.state["npcs"] or npc_id in (new_npcs or {}):
                profile = {**profile_of(self.adventure, self.state, npc_id), **(new_npcs or {}).get(npc_id, {}).get("profile", {})}
            secrets = [s.get("id") for s in (profile or {}).get("secrets", [])]
            if profile is None:
                raise SoloError(f"learn {item!r}: unknown npc {npc_id!r}")
            elif not (what in LEARNABLE and profile.get(what)) and what not in secrets:
                known = [k for k in LEARNABLE if profile.get(k)] + secrets
                raise SoloError(f"learn {item!r}: {npc_id} has {', '.join(known) or 'nothing to learn'}")
            elif f"{npc_id}.{what}" not in self.state["learned"] + result:
                result.append(f"{npc_id}.{what}")
        return result

    def _npc_changes(self, updates, override):
        result = {}
        for npc_id, fields in updates.items():
            current = self.state["npcs"].get(npc_id)
            authored = self.adventure["npcs"].get(npc_id, {})
            if not isinstance(fields, dict):
                raise SoloError(f'npc {npc_id}: give the fields as an object, like {{"attitude": "+1", "memory": "..."}}')
            unknown = sorted(set(fields) - _NPC_FIELDS)
            if unknown:
                place = "; where someone is, is location (a scene id)" if set(unknown) & {"at", "place", "scene"} else ""
                raise SoloError(f"npc {npc_id}: unknown fields {', '.join(unknown)} (allowed: {', '.join(sorted(_NPC_FIELDS))}){place}")
            elif current is None and not fields.get("name"):
                raise SoloError(f"npc {npc_id!r} isn't in the adventure; give it a name to add it")
            is_new = current is None
            change = {"name": fields["name"], "new": True} if is_new else {}
            current = current or {"attitude": 0, "fate": "alive"}
            if "attitude" in fields:
                attitude = _clamp(_shift(fields["attitude"], current["attitude"], ATTITUDES), -2, 2)
                if not is_new and abs(attitude - current["attitude"]) > 1 and not override:
                    raise SoloError(
                        f"npc {npc_id}: attitude moves one step per commit ({current['attitude']} -> {attitude}); "
                        'add "override": "<reason>" if the adventure says otherwise'
                    )
                change.update(attitude=attitude, attitude_was=current["attitude"])
            if "fate" in fields:
                if fields["fate"] not in FATES:
                    raise SoloError(f"npc {npc_id}: fate must be one of {', '.join(FATES)}")
                elif authored.get("many"):
                    raise SoloError(
                        f"npc {npc_id} is a kind of foe the hero meets again and again ({authored.get('name', npc_id)}), "
                        f"so no one fate covers them all: say what became of these ones with a fact "
                        f'({{"facts": {{"{self.state["scene"]}.{npc_id}": "two fled"}}}}), or give one a name of their own to follow them')
                elif current["fate"] == "dead" and fields["fate"] != "dead" and not override:
                    raise SoloError(f'npc {npc_id} is dead; add "override": "<reason>" to change that')
                change.update(fate=fields["fate"], fate_was=current["fate"])
            if "location" in fields and fields["location"] not in (None, *self.adventure["scenes"]):
                raise SoloError(f"npc {npc_id}: unknown location {fields['location']}")
            if "faction" in fields and fields["faction"] not in self.state["factions"]:
                raise SoloError(f"npc {npc_id}: unknown faction {fields['faction']}")
            npcs = self.system.get("npcs", {})
            if "template" in fields and fields["template"] not in npcs.get("templates", {}):
                raise SoloError(f"npc {npc_id}: template must be one of {', '.join(npcs.get('templates', {})) or 'none'}")
            if "attacker" in fields and fields["attacker"] not in npcs.get("attackers", []):
                raise SoloError(f"npc {npc_id}: attacker must be one of {', '.join(npcs.get('attackers', [])) or 'none'}")
            if "monster" in fields and fields["monster"] not in self.system.get("bestiary", {}):
                known = ", ".join(self.system.get("bestiary", {})) or "none: the system pack has no bestiary"
                raise SoloError(f"npc {npc_id}: monster must be one of the bestiary's ({known})")
            change.update({k: fields[k] for k in ("location", "faction", "memory", "template", "attacker", "monster") if k in fields})
            profile = {k: str(fields[k]).strip() for k in PROFILE_FIELDS if str(fields.get(k) or "").strip()}
            written = [k for k in profile if authored.get(k)]
            if written:
                raise SoloError(f"npc {npc_id}: the adventure already gives their {', '.join(written)}; "
                                "what changed about them goes in a memory")
            elif profile:
                change["profile"] = profile
            result[npc_id] = change
        return result

    def _faction_changes(self, updates, override):
        result = {}
        for faction_id, value in updates.items():
            current = self.state["factions"].get(faction_id)
            spec = value if isinstance(value, dict) else {"standing": value}
            unknown = sorted(set(spec) - {"name", "standing", "memory"})
            if unknown:
                raise SoloError(f"faction {faction_id}: unknown fields {', '.join(unknown)} (allowed: memory, name, standing)")
            elif current is None and not spec.get("name"):
                raise SoloError(f'faction {faction_id!r} isn\'t in the adventure; add it with {{"name": ..., "standing": 0}}')
            old = current["standing"] if current else 0
            standing = _clamp(_shift(spec.get("standing", old), old, ATTITUDES), -2, 2)
            if current is not None and abs(standing - old) > 1 and not override:
                raise SoloError(
                    f"faction {faction_id}: standing moves one step per commit ({old} -> {standing}); "
                    'add "override": "<reason>" if the adventure says otherwise'
                )
            result[faction_id] = {"standing": standing, "standing_was": old}
            if current is None:
                result[faction_id]["name"] = spec["name"]
            if str(spec.get("memory") or "").strip():
                # Word spreads: what the faction has heard of the hero, for the next of them they meet.
                result[faction_id]["memory"] = str(spec["memory"]).strip()
        return result

    def _consequence_changes(self, items, new_npcs):
        """Something the hero did that will come back: when the hero is somewhere (`at`),
        meets someone (`npc`, when nothing else says when), a condition holds (`when`), or
        game time has passed (`after`). Given several, all must hold. Updates by id: a
        status (done, dropped), new words or new triggers."""
        result = {}
        for item in _by_id(items, _CONSEQUENCE_KEYS):
            if not isinstance(item, dict):
                raise SoloError('a consequence is an object: {"id": ..., "text": "what will happen", "npc": ..., "at": ..., "when": ..., "after": {"shift": 1}}')
            unknown = sorted(set(item) - _CONSEQUENCE_KEYS)
            text = str(item.get("text") or "").strip()
            consequence_id = slug(str(item.get("id") or " ".join(text.split()[:4])))
            if not item.get("id") and consequence_id:
                # An id made from the words is a new consequence, never an old one that began alike.
                base, number = consequence_id, 1
                while consequence_id in self.state["consequences"] or consequence_id in result:
                    number += 1
                    consequence_id = f"{base}_{number}"
            current = self.state["consequences"].get(consequence_id)
            status = item.get("status", current["status"] if current else "open")
            if unknown:
                raise SoloError(f"consequence: unknown fields {', '.join(unknown)} (allowed: {', '.join(sorted(_CONSEQUENCE_KEYS))})")
            elif not consequence_id:
                raise SoloError("a consequence needs an id, or its text to make one from")
            elif current is None and not text:
                known = ", ".join(self.state["consequences"]) or "none yet"
                raise SoloError(f"consequence {consequence_id}: a new one needs its text (what will happen, and to whom); consequences: {known}")
            elif status not in CONSEQUENCE_STATUSES:
                raise SoloError(f"consequence {consequence_id}: status must be one of {', '.join(CONSEQUENCE_STATUSES)}")
            change = {"status": status, "status_was": current["status"] if current else None}
            if text:
                change["text"] = text
            if item.get("npc") is not None:
                if item["npc"] not in self.state["npcs"] and item["npc"] not in new_npcs:
                    raise SoloError(f"consequence {consequence_id}: unknown npc {item['npc']}; someone new goes in the same commit's "
                                    f'npc with a name: {{"npc": {{"{item["npc"]}": {{"name": "..."}}}}}}')
                change["npc"] = item["npc"]
            if item.get("at") is not None:
                places = [slug(p) for p in _listed(item["at"])]
                strange = [p for p in places if p not in self.adventure["scenes"]]
                if strange:
                    raise SoloError(f"consequence {consequence_id}: unknown scene {strange[0]}; at names scene ids, like {self.state['scene']}")
                change["at"] = places
            if item.get("when"):
                try:
                    packs.compile_condition(str(item["when"]))
                except SoloError as error:
                    raise SoloError(
                        f"consequence {consequence_id}: {error}. `when` is a condition the engine can check, like "
                        "fact.hall.alarm or clock.dark_ritual >= 4. To wait for something that happens in the story, "
                        "leave when out and give at, npc or after, or no trigger at all (a loose end you bring in)") from None
                change["when"] = str(item["when"])
            if item.get("after"):
                seconds = self._seconds(item["after"])
                if seconds <= 0:
                    raise SoloError(f'consequence {consequence_id}: after is game time from now, like {{"shift": 1}}')
                change["due_at"] = self.state["time"] + seconds
            if current is None or {"npc", "at", "when", "due_at"} & set(change):
                # Waiting starts now: `at` and `npc` wait for the hero's next arrival, so one
                # made in front of the smith comes due when the hero comes back to him.
                change.update(arrivals=self.state["arrivals"], due=False)
            result[consequence_id] = change
        return result

    def _promise_changes(self, items, new_npcs):
        """Promises by id: a new one needs npc and terms (`text` reads as terms), and an id,
        made from the terms when none is given; an update needs only its status."""
        result = {}
        for item in _by_id(items, _PROMISE_KEYS):
            if not isinstance(item, dict):
                raise SoloError('a promise is an object: {"id": ..., "npc": ..., "terms": "what was promised", "status": "open"}')
            item = {**item, "terms": item.get("terms") or item.get("text")} if item.get("text") else item
            promise_id = slug(str(item.get("id") or ""))
            if not promise_id and item.get("terms"):
                base = promise_id = slug(" ".join(str(item["terms"]).split()[:4]))
                number = 1
                while promise_id in self.state["promises"] or promise_id in result:
                    number += 1
                    promise_id = f"{base}_{number}"
            current = self.state["promises"].get(promise_id)
            status = item.get("status", current["status"] if current else "open")
            npc = item.get("npc", current["npc"] if current else None)
            terms = item.get("terms", current["terms"] if current else None)
            if not promise_id:
                raise SoloError("a promise needs an id, or its terms to make one from")
            elif status not in PROMISE_STATUSES:
                raise SoloError(f"promise {promise_id}: status must be one of {', '.join(PROMISE_STATUSES)}")
            elif not (npc and terms):
                raise SoloError(f"promise {promise_id}: a new promise needs npc and terms")
            elif npc not in self.state["npcs"] and npc not in new_npcs:
                raise SoloError(f"promise {promise_id}: unknown npc {npc}")
            else:
                result[promise_id] = {
                    "npc": npc, "terms": terms, "status": status,
                    "status_was": current["status"] if current else None,
                }
        return result

    def _pc_changes(self, updates, override=None):
        pc = self.state["pc"]
        dying = self.system.get("dying") or {}
        result, warnings = {}, []
        if updates and pc["dead"] and not override:
            raise SoloError(f'{pc["name"]} is dead; add "override": "<reason>" to change that')
        if isinstance(updates.get("tracks"), dict):
            # {"pc": {"tracks": {"hp": 3}}} can only mean the tracks themselves.
            updates = {**{k: v for k, v in updates.items() if k != "tracks"}, **updates["tracks"]}
        for key, value in updates.items():
            if key in pc["tracks"]:
                track = pc["tracks"][key]
                if isinstance(value, (int, float)) and not isinstance(value, bool) and value < 0:
                    # A track is never set below zero, so -3 can only mean "lose 3". Setting HP to 0
                    # instead would leave the hero dying over a scratch (a GM wrote exactly this).
                    warnings.append(f"read {key} {value} as a loss of {-int(value)}; write \"{int(value)}\" as text to move a value")
                    value = str(int(value))
                wanted = _shift(value, track["value"])
                result.setdefault("tracks", {})[key] = _clamp(wanted, 0, track["max"])
                result.setdefault("tracks_was", {})[key] = track["value"]
                if key == dying.get("track") and pc["dying"] and wanted < 0:
                    # Harm while dying: one failed death roll.
                    result["death_failures"] = 1
                elif result["tracks"][key] != wanted:
                    warnings.append(f"{key} stops at {result['tracks'][key]} (range 0-{track['max']})")
            elif key == "conditions":
                # One name is a list of one: {"add": "dazed"} is dazed, not d, a, z, e, d.
                add = [slug(c) for c in _listed(value.get("add"))]
                remove = [slug(c) for c in _listed(value.get("remove"))]
                unknown = [c for c in add + remove if c not in self.system["conditions"]]
                if unknown:
                    raise SoloError(f"unknown conditions {', '.join(unknown)}; the system has {', '.join(self.system['conditions'])}")
                result["conditions_add"] = [c for c in add if c not in pc["conditions"]]
                result["conditions_remove"] = [c for c in remove if c in pc["conditions"]]
            elif key == "items":
                result["items_add"] = _listed(value.get("add"))
                result["items_remove"] = [i for i in _listed(value.get("remove")) if i in pc["items"]]
                warnings += [f"{i} isn't carried" for i in _listed(value.get("remove")) if i not in pc["items"]]
            else:
                money = " (coins and gear are items: {\"pc\": {\"items\": {\"add\": [\"30 silver\"]}}})" if key in _MONEY else ""
                raise SoloError(f"pc has no {key!r}; use a track ({', '.join(pc['tracks'])}), conditions or items{money}")
        return {k: v for k, v in result.items() if v}, warnings


# Folding events into state --------------------------------------------------------

def fold(system, adventure, events):
    state = initial_state(system, adventure)
    for event in events:
        _replay(state, event, adventure)
    return state


def _replay(state, event, adventure):
    """`apply` for an event already in the log. The packs are read afresh each time, and one
    edited since (a clock renamed, an NPC taken out) may no longer hold what an old event
    names: that event is passed over and said so, rather than locking the player out."""
    try:
        apply(state, event, adventure)
    except KeyError as error:
        state["problems"].append(f"#{event['seq']} {event['type']} was passed over: the packs no longer have {error}")


def snapshot(system, state, adventure=None):
    """state.json: the folded state plus what the panel and the Book need derived from the
    packs (the weapons the hero carries, the codex, the route, the art), so they compute no
    rules. Nothing here is GM-only: unknown things are counted, never shown."""
    view = {**{k: v for k, v in state.items() if k not in _GM_ONLY}, "kit": combat.kit(system, state["pc"]) if state["pc"] else None}
    if adventure is not None:
        # Counted, not listed: what they name would give the adventure away (`solo validate` says).
        view["pack_problems"] = len(packs.validate(system, adventure)) + len(state["problems"])
    if adventure is not None and state["pc"]:
        lit = state["light"]
        view.update(
            codex=codex(adventure, state),
            route=route(adventure, state),
            dark=bool(adventure["scenes"].get(state["scene"], {}).get("dark")),
            light=lit and {**lit, "left": max(0, lit["lit_at"] + lit["burns"] - state["time"])},
            **portrait.art(system, adventure, state),
        )
    return view


def codex(adventure, state):
    """The people the hero has met, as the player knows them. Wants, fears and secrets
    stay blanked out (counted under `unknown`) until a commit's `learn` reveals them;
    a foe's numbers show once the hero has fought it."""
    entries = []
    for npc_id, npc in state["npcs"].items():
        if not npc["met"]:
            continue
        profile = profile_of(adventure, state, npc_id)
        learned = set(state["learned"])
        known = {k: profile[k] for k in LEARNABLE if profile.get(k) and f"{npc_id}.{k}" in learned}
        secrets = [s.get("text", "") for s in profile.get("secrets", []) if f"{npc_id}.{s.get('id')}" in learned]
        knowable = sum(1 for k in LEARNABLE if profile.get(k)) + len(profile.get("secrets", []))
        stats = profile.get("stats", {})
        entries.append({
            "id": npc_id, "name": npc["name"], "role": profile.get("role", ""),
            "faction": state["factions"].get(npc.get("faction") or "", {}).get("name", ""),
            "attitude": next((name for name, value in ATTITUDES.items() if value == npc["attitude"]), str(npc["attitude"])),
            "fate": npc["fate"], "memories": npc["memories"], "known": known, "secrets": secrets,
            "unknown": knowable - len(known) - len(secrets),
            "fought": npc.get("fought", False),
            "stats": {"hp": stats.get("hp"), "armor": stats.get("armor", 0)} if npc.get("fought") and "hp" in stats else None,
        })
    return entries


def chronology(system, adventure, events):
    """The campaign as it happened, replayed from the log: one entry per event, with where the
    hero was and the game time after it, and the moments in it that matter to the story later
    (arrivals, people met and what they now think, fates, promises, consequences, gear won and
    lost, fights, deaths, the chronicle). The GM's long memory is read from this, so it holds
    for campaigns begun before it existed, and needs no one to have written anything down."""
    state = initial_state(system, adventure)
    entries = []
    for event in events:
        seen = set(state["visited"])
        was_dead = bool(state["pc"] and state["pc"]["dead"])
        _replay(state, event, adventure)
        entries.append({"seq": event["seq"], "event": event, "time": state["time"], "scene": state["scene"],
                        "title": state["scene_title"], "moments": _moments(event, state, adventure, seen, was_dead)})
    return entries


def moments(entries, after=0, kinds=None):
    """The moments of a chronology after a seq, flat, oldest first: {seq, time, scene, title,
    kind, text, npcs}."""
    return [{"seq": e["seq"], "time": e["time"], "scene": e["scene"], "title": e["title"], **m}
            for e in entries if e["seq"] > after for m in e["moments"] if kinds is None or m["kind"] in kinds]


def _moments(event, state, adventure, seen, was_dead):
    kind, changes = event["type"], event.get("changes") or {}
    name = lambda npc_id: state["npcs"].get(npc_id, {}).get("name", npc_id)
    found = []

    def say(what, text, npcs=()):
        found.append({"kind": what, "text": text, "npcs": list(npcs)})

    if kind == "created":
        say("begin", f"{event['pc']['name']} begins {event['title']}")
    if kind in ("created", "move"):
        back = state["scene"] in seen
        say("return" if back else "arrive", f"{'came back to' if back else 'reached'} {state['scene_title']}", people_here(adventure, state))
    elif kind == "hero":
        say("hero", f"{event['pc']['name']} takes up the story")
    elif kind == "commit":
        if changes.get("note"):
            say("note", changes["note"], changes.get("npc", {}))
        if changes.get("chronicle"):
            say("chronicle", changes["chronicle"])
        if changes.get("end"):
            say("end", f"the adventure ends: {changes['end']}")
    elif kind == "stage":
        say("stage", f"{event['label']} reached {event['at']}/{event['segments']}: {event.get('text') or event.get('note') or ''}".rstrip(": "))
    elif kind in ("fight", "join"):
        say("fight", ("a fight: " if kind == "fight" else "joining the fight: ") + ", ".join(f["name"] for f in event["foes"].values()),
            {f["npc"] for f in event["foes"].values()})
    elif kind in ("damage", "wound", "ally") and event.get("down"):
        say("fight", f"{event.get('name') or event.get('target_name')} down")
    elif kind == "fight_end" and event.get("standing"):
        say("fight", f"the fight ends; still standing: {', '.join(event['standing'])}")
    elif kind == "threat" and event["action"] in ("add", "triggered"):
        say("threat", f"a threat looms: {event['label']}" if event["action"] == "add" else f"a threat came to pass: {event.get('text') or event['label']}")
    elif kind == "clock" and event.get("full") and not event.get("stopped"):
        say("clock", f"{event['label']} filled")
    elif kind == "advance" and any(r["now"] > r["was"] for r in event["results"]):
        say("advance", "grew: " + ", ".join(f"{r['name']} {r['now']}" for r in event["results"] if r["now"] > r["was"]))
    elif kind == "due":
        say("due", f"a consequence came due: {event['text']}", [event["npc"]] if event.get("npc") else [])
    if kind in ("commit", "stage"):
        for npc_id, change in changes.get("npc", {}).items():
            bits = []
            if "fate" in change and change["fate"] != change.get("fate_was"):
                bits.append(change["fate"])
            if "attitude" in change and change["attitude"] != change.get("attitude_was"):
                bits.append(f"now {_attitude_word(change['attitude'])}")
            if change.get("location"):
                bits.append(f"now at {adventure['scenes'].get(change['location'], {}).get('title', change['location'])}")
            if change.get("memory"):
                bits.append(f"remembers: {change['memory']}")
            if change.get("new"):
                role = (change.get("profile") or {}).get("role")
                say("npc", "; ".join([f"met {name(npc_id)}" + (f", {role}" if role else ""), *bits]), [npc_id])
            elif bits:
                say("npc", f"{name(npc_id)}: {'; '.join(bits)}", [npc_id])
        for faction_id, change in changes.get("faction", {}).items():
            bits = [f"now {_attitude_word(change['standing'])}"] if change["standing"] != change["standing_was"] else []
            bits += [f"heard: {change['memory']}"] if change.get("memory") else []
            if bits:
                say("faction", f"{state['factions'].get(faction_id, {}).get('name', faction_id)}: {'; '.join(bits)}")
        for promise in changes.get("promise", {}).values():
            if promise["status"] != promise.get("status_was"):
                say("promise", f"a promise to {name(promise['npc'])} ({promise['status']}): {promise['terms']}", [promise["npc"]])
        for consequence_id, change in changes.get("consequence", {}).items():
            if change["status"] != change.get("status_was"):
                text = state["consequences"].get(consequence_id, {}).get("text", "")
                say("consequence", f"consequence {consequence_id} ({change['status']}): {text}",
                    [state["consequences"][consequence_id]["npc"]] if state["consequences"].get(consequence_id, {}).get("npc") else [])
        pc = changes.get("pc", {})
        if pc.get("items_add") or pc.get("items_remove"):
            say("gear", "; ".join(filter(None, [pc.get("items_add") and "gained " + ", ".join(pc["items_add"]),
                                                pc.get("items_remove") and "lost " + ", ".join(pc["items_remove"])])))
        if changes.get("learn"):
            say("learn", "found out " + ", ".join(changes["learn"]), {k.partition(".")[0] for k in changes["learn"]})
    if state["pc"] and state["pc"]["dead"] and not was_dead:
        say("death", f"{state['pc']['name']} died" + (f" ({state['last_blow']})" if state.get("last_blow") else ""))
    return found


def recall(entries, state, query, limit=8):
    """Everything the campaign holds that mentions these words: every message said at the
    table, the GM's notes, facts, memories, what word has spread, consequences, oracle
    answers, table results, the chronicle, and the hero's earlier adventures. Best matches
    first (the most words found), newest first among equals. Accents and case don't count."""
    words = [w for w in _fold(query).split() if len(w) > 2] or _fold(query).split()
    if not words:
        raise SoloError("recall what? give a word or two: solo recall smith hammer")
    found = []
    for entry in entries:
        for label, text in _recallable(entry["event"], state):
            folded = _fold(text)
            # The label counts too: "Bram remembers" is about Bram, whatever he remembers.
            hits = sum(1 for w in words if w in folded or w in _fold(label))
            if hits:
                found.append({"hits": hits, "seq": entry["seq"], "time": entry["time"], "title": entry["title"],
                              "label": label, "text": _snippet(text, folded, words)})
    for number, record in enumerate(state.get("past") or [], 1):
        for label, text in [("the ending", record.get("ended") or ""), *[("chronicle", t) for t in record.get("chronicle", [])],
                            *[("left open", t) for t in record.get("loose_ends", [])], *[("people", t) for t in record.get("people", [])]]:
            folded = _fold(text)
            hits = sum(1 for w in words if w in folded)
            if hits:
                found.append({"hits": hits, "seq": 0, "time": None, "title": record.get("title", f"adventure {number}"),
                              "label": f"before this adventure, {label}", "text": _snippet(text, folded, words)})
    found.sort(key=lambda f: (-f["hits"], -f["seq"]))
    best = found[0]["hits"] if found else 0
    # When some matches hold every word, the ones that hold only a few are noise.
    return [f for f in found if f["hits"] == best or best < len(words)][:limit]


def _recallable(event, state):
    """(label, text) for what an event put into the story in words."""
    kind, changes = event["type"], event.get("changes") or {}
    npc_name = lambda npc_id: state["npcs"].get(npc_id, {}).get("name", npc_id)
    if kind == "said":
        return [("you said" if event["by"] == "gm" else "the player said", event["text"])]
    elif kind in ("oracle", "meaning"):
        answer = event.get("answer") or " / ".join(event.get("words", []))
        return [("the oracle", f"{event.get('question') or 'meaning'}: {answer}")]
    elif kind == "table":
        return [(event["name"], event["text"])]
    elif kind == "voice" and event["heard"]:
        return [(event["label"], event["text"])]
    elif kind == "threat" and event["action"] in ("add", "triggered"):
        return [("threat", event.get("text") or event["label"])]
    elif kind == "due":
        return [("came due", event["text"])]
    items = []
    if kind == "stage":
        items += [(event["label"], " ".join(filter(None, [event.get("text"), event.get("note")])))]
    if kind in ("commit", "stage"):
        items += [(key, changes[key]) for key in ("note", "chronicle", "end") if changes.get(key)]
        items += [("fact", f"{k}: {v}") for k, v in changes.get("facts", {}).items()]
        for npc_id, change in changes.get("npc", {}).items():
            items += [(f"{npc_name(npc_id)} remembers", change["memory"])] if change.get("memory") else []
            items += [(f"{npc_name(npc_id)}, {field}", text) for field, text in (change.get("profile") or {}).items()]
            items += [("met", f"{npc_name(npc_id)} ({npc_id})")] if change.get("new") else []
        for faction_id, change in changes.get("faction", {}).items():
            items += [(f"{state['factions'].get(faction_id, {}).get('name', faction_id)} heard", change["memory"])] if change.get("memory") else []
        for promise_id, promise in changes.get("promise", {}).items():
            items += [(f"promise {promise_id} ({promise['status']})", f"{npc_name(promise['npc'])}: {promise['terms']}")]
        for consequence_id, change in changes.get("consequence", {}).items():
            items += [(f"consequence {consequence_id}", change["text"])] if change.get("text") else []
        items += [("gained", item) for item in changes.get("pc", {}).get("items_add", [])]
    return items


def _fold(text):
    """Lowercase, accents gone, one character for one, so a match found in the folded text
    points at the same place in the original: Kjölvik is kjolvik."""
    return "".join((unicodedata.normalize("NFKD", ch)[:1] or ch).lower()[:1] for ch in str(text))


def _snippet(text, folded, words, before=90, after=170):
    at = min((folded.find(w) for w in words if w in folded), default=0)
    start, end = max(0, at - before), min(len(text), at + after)
    while start > 0 and not text[start - 1].isspace():
        start -= 1
    while end < len(text) and not text[end].isspace():
        end += 1
    return ("..." if start else "") + " ".join(text[start:end].split()) + ("..." if end < len(text) else "")


def _attitude_word(value):
    return next((name for name, number in ATTITUDES.items() if number == value), str(value))


def route(adventure, state):
    """The scenes visited, in order, each with how many of its ways on are still unexplored
    (never where they lead: that would spoil scenes the hero hasn't reached). A way that
    hasn't opened yet (hidden stairs) isn't counted, or the map would give it away."""
    visited = state["visited"]
    return [
        {"id": sid, "title": adventure["scenes"][sid].get("title", sid), "here": sid == state["scene"],
         "unexplored": sum(1 for target, spec in packs.exits(adventure, sid).items()
                           if target not in visited and packs.is_open(spec, state))}
        for sid in visited if sid in adventure["scenes"]
    ]


def initial_state(system, adventure):
    return {
        "seq": 0,
        "title": adventure["title"],
        "system": system["name"],
        "family": system["family"],
        "labels": {
            "attributes": system["attributes"],
            "tracks": system["tracks"],
            "conditions": list(system["conditions"]),
            "push": system["push"].get("cost", "condition"),
            # limit: seconds per time unit, so the panel can tell a rest taken this shift
            "rests": {
                rid: {"label": r.get("label", rid.capitalize()), "limit": system["time"].get(r.get("limit")), **({"tend": True} if r.get("tend") else {})}
                for rid, r in system["rest"].items()
            },
            # A heroic ability that pays for a push instead of a condition (Sole Survivor): name and cost.
            "push_ability": next(({"name": a.get("name", aid), "cost": ", ".join(f"{v} {t.upper()}" for t, v in a["push"].items())}
                                  for aid, a in system.get("abilities", {}).items() if a.get("push")), None),
            "likelihood": ["unlikely", "even", "likely"] if system.get("oracle", {}).get("chart") == "fortune" else list(LIKELIHOOD),
            # The fortune chart's columns (yes_no, number, scale ...), when the system has one.
            "fortune": [k for k in system.get("oracle", {}).get("fortune", {}) if k != "bands"] or None,
            # Death rolls and advancement, when the system has them.
            "dying": _dying_rules(system),
            "advancement": list(system.get("advancement", {}).get("mark_on", [])) if system.get("advancement") else None,
        },
        "scene": None,
        "scene_title": None,
        "visited": [],
        "time": 0,
        "pc": None,
        "npcs": {
            nid: {
                "name": npc.get("name", nid), "faction": npc.get("faction"), "fate": npc.get("fate", "alive"),
                "attitude": _attitude(npc.get("attitude", 0)), "location": npc.get("location"),
                "met": False, "fought": False, "memories": [],
            }
            for nid, npc in adventure["npcs"].items()
        },
        "factions": {
            fid: {"name": f.get("name", fid), "standing": int(f.get("standing", 0)), "memories": []}
            for fid, f in adventure["factions"].items()
        },
        "promises": {},
        # What the hero did that will come back: {id: text, npc, at, when, due_at, status, due ...}. GM only.
        "consequences": {},
        # How many times the hero has come into a scene, so a consequence can wait for the next time.
        "arrivals": 0,
        # The hero's earlier adventures, when they came from another campaign (see `hero`).
        "past": [],
        "clocks": {
            cid: {
                "label": c.get("label", cid), "value": 0, "segments": int(c.get("segments", 1)),
                "full": False, "hidden": bool(c.get("hidden", False)), "stopped": False,
            }
            for cid, c in adventure["clocks"].items()
        },
        "facts": {},
        "clues": [],
        "chronicle": [],
        "rests": {},
        "last_check": None,
        # 1-9: how likely surprises are. The GM raises it when the story runs away from the hero.
        "chaos": int(adventure.get("chaos", 5)),
        "combat": None,
        # The player's table settings, read by the GM every session.
        "prefs": {"tone": "", "lines": [], "veils": []},
        # Set when the hero dies or the GM commits an "end".
        "ended": None,
        # The GM's last words to the player, and whether the player has answered them.
        "last_said": None,
        "awaiting_player": False,
        # The torch (or other light) burning now: {source, label, lit_at, burns}.
        "light": None,
        # What the player has found out about NPCs (learn in a commit), for the codex.
        "learned": [],
        # Lines the hero's skills said in this scene (voices heard).
        "voices": [],
        # For the epitaph: the player's last words and who dealt the last blow.
        "last_player_said": None,
        "last_blow": None,
        "fallen": None,
        # Heroes who came before this one in the same story (a death, then a replacement).
        "heroes": [],
        "story": [],
        "log": [],
        # Every event the player never saw, by seq: the log keeps only the last few.
        "hidden": [],
        # Events the replay passed over, because the packs no longer hold what they name.
        "problems": [],
    }


def apply(state, event, adventure):
    kind = event["type"]
    state["seq"] = event["seq"]
    if kind == "said":
        # Speech stays out of the dice log: the panel shows it in its own card, the Book in its story.
        if event["by"] == "gm":
            state["last_said"] = {k: event[k] for k in ("seq", "at", "scene", "text")}
        else:
            state["last_player_said"] = event["text"]
        state["awaiting_player"] = event["by"] == "gm"
        _tell(state, {"seq": event["seq"], "kind": event["by"], "text": event["text"]})
        return
    fight = state["combat"]
    if kind == "created":
        state["pc"] = {**copy.deepcopy(event["pc"]), "marks": [], "dying": None, "dead": False}
        state["past"] = copy.deepcopy(event.get("past") or [])
        state["facts"].update(event.get("facts") or {})
        _enter(state, event["scene"], adventure)
    elif kind == "hero":
        old = state["pc"]
        state["heroes"].append({"name": old["name"], "info": old["info"], "fate": "died" if old["dead"] else "stepped aside",
                                "fallen": state["fallen"]})
        state["pc"] = {**copy.deepcopy(event["pc"]), "marks": [], "dying": None, "dead": False}
        state.update(ended=None, fallen=None, last_blow=None, last_check=None, voices=[])
        if event.get("npc") in state["npcs"]:
            state["npcs"][event["npc"]].update(fate="gone", location=None)
    elif kind == "move":
        state["time"] += event.get("time") or 0
        _enter(state, event["to"], adventure)
    elif kind == "check":
        state["last_check"] = event
        _mark(state, event)
        if event.get("defend") and event["outcome"]["success"] and fight:
            fight["incoming"] = None
    elif kind == "push":
        _apply_changes(state, event["changes"], event)
        state["last_check"] = event
        _mark(state, event)
    elif kind == "stage":
        _apply_changes(state, event["changes"], event)
    elif kind in ("commit", "harm"):
        if kind == "harm":
            state["last_blow"] = event.get("by")
            if fight:
                # Only the blow that was coming (it has a source) is answered by this; a stone
                # falling on the hero mid-fight leaves the foe's axe still on its way.
                if event.get("source"):
                    fight["incoming"] = None
                fight["last"] = {"seq": event["seq"], "from": event.get("source"), "to": "pc", "hit": True, "dealt": event["dealt"], "text": describe(event)}
        _apply_changes(state, event["changes"], event)
    elif kind == "rally":
        if event["rallied"] and state["pc"]["dying"]:
            state["pc"]["dying"]["rallied"] = True
    elif kind == "save_self":
        _apply_changes(state, event["changes"], event)
    elif kind == "death_roll":
        _dying(state, event, successes=event["successes"], failures=event["failures"])
        _apply_changes(state, event["changes"], event)
    elif kind == "fight":
        state["combat"] = {"round": event["round"], "foes": copy.deepcopy(event["foes"]), "order": event["order"], "incoming": None}
    elif kind == "join" and fight:
        fight["foes"].update(copy.deepcopy(event["foes"]))
        fight["order"] = event["order"]
    elif kind == "round" and fight:
        fight.update(round=event["round"], order=event["order"])
        state["time"] += event.get("time") or 0
    elif kind == "fight_end":
        state["combat"] = None
    elif kind == "damage" and fight:
        fight["foes"][event["target"]].update(hp=event["hp"], down=event["down"])
        fight["last"] = {"seq": event["seq"], "from": "pc", "to": event["target"], "hit": True, "dealt": event["dealt"], "text": describe(event)}
    elif kind == "wound" and fight:
        fight["foes"][event["target"]].update(hp=event["hp"], down=event["down"])
        fight["last"] = {"seq": event["seq"], "from": "pc", "to": event["target"], "hit": True, "dealt": event["dealt"], "text": describe(event)}
    elif kind == "ally" and fight:
        if "dealt" in event:
            fight["foes"][event["target"]].update(hp=event["hp"], down=event["down"])
        # Drawn from the hero's side of the tableau, like the hero's own blows.
        fight["last"] = {"seq": event["seq"], "from": "pc", "to": event["target"], "hit": "dealt" in event, "dealt": event.get("dealt", 0), "text": describe(event)}
        state["npcs"][event["npc"]]["met"] = True
    elif kind == "enemy" and fight:
        fight["incoming"] = event.get("incoming")
        pending = fight.setdefault("pending", {})
        if event.get("queued"):
            pending[event["foe"]] = event["queued"]
        else:
            pending.pop(event["foe"], None)
        if not event.get("incoming"):
            fight["last"] = {"seq": event["seq"], "from": event["foe"], "to": "pc", "hit": False, "dealt": 0, "text": describe(event)}
    elif kind == "voice":
        if event["heard"]:
            state["voices"].append({"label": event["label"], "text": event["text"]})
            if event.get("clue") and event["clue"] not in state["clues"]:
                state["clues"].append(event["clue"])
    elif kind == "light":
        _apply_changes(state, event.get("changes", {}), event)
        state["light"] = {"source": event["source"], "label": event["label"], "lit_at": state["time"], "burns": event["burns"]} if event["lit"] else None
    elif kind == "mark":
        state["pc"]["marks"].append(event["skill"])
    elif kind == "advance":
        for result in event["results"]:
            state["pc"]["skills"][result["skill"]]["value"] = result["now"]
        state["pc"]["marks"] = []
    elif kind == "prefs":
        state["prefs"] = {k: event[k] for k in ("tone", "lines", "veils")}
    elif kind == "rest":
        state["rests"][event["rest"]] = state["time"]
        _apply_changes(state, event["changes"], event)
    elif kind == "clock":
        state["clocks"][event["clock"]].update(value=event["value"], full=event["full"], stopped=bool(event.get("stopped")))
    elif kind == "threat" and event["action"] == "add":
        state["clocks"][event["clock"]] = {
            "label": event["label"], "value": event["value"], "segments": event["segments"], "full": False,
            "hidden": False, "stopped": False, "threat": {"recurring": bool(event.get("recurring")), "text": event.get("text") or event["label"]},
        }
    elif kind == "threat" and event["action"] == "end":
        state["clocks"][event["clock"]]["stopped"] = True
    elif kind == "due" and event["consequence"] in state["consequences"]:
        state["consequences"][event["consequence"]]["due"] = True
    if kind in ("fight", "join"):
        for foe in event["foes"].values():
            if foe["npc"] in state["npcs"]:
                state["npcs"][foe["npc"]].update(met=True, fought=True)
    if kind in ("check", "push") and fight and (event.get("attack") or event.get("defend")) and not event["outcome"]["success"]:
        attack = event.get("attack")
        fight["last"] = ({"seq": event["seq"], "from": "pc", "to": attack["target"], "hit": False, "dealt": 0, "text": describe(event)} if attack
                         else fight.get("last"))
    entry = {"seq": event["seq"], "type": kind, "text": describe(event)}
    if kind == "clock":
        entry["clock"] = event["clock"]
    # The player's panel skips hidden clocks and the tables their ticks roll, unless the
    # clock is an omen clock: then what its tick rolls is felt, though the clock stays hidden.
    cause = next((e for e in state["log"] if e["seq"] == event.get("cause")), None) if kind == "table" else None
    omen = cause is not None and bool(adventure["clocks"].get(cause.get("clock", ""), {}).get("omen"))
    hidden_clock = kind == "clock" and state["clocks"][event["clock"]]["hidden"]
    hidden_cause = cause is not None and cause.get("hidden") and not omen
    if kind == "stage":
        # A stage of a hidden clock stays hidden, unless it is an omen clock with something to feel.
        spec = adventure["clocks"].get(event["clock"], {})
        omen = bool(spec.get("omen") and event.get("text"))
        hidden_clock = state["clocks"][event["clock"]]["hidden"] and not omen or not event.get("text")
    # A consequence coming due is the GM's, and so is a commit with nothing the player can see
    # (facts, a consequence): the table's log would only say "commit".
    gm_only = kind == "due" or (kind == "commit" and entry["text"] == "commit")
    if hidden_clock or hidden_cause or gm_only or (kind == "voice" and not event["heard"]):
        entry["hidden"] = True
        state["hidden"].append(event["seq"])
    elif omen:
        entry["omen"] = True
    state["log"] = (state["log"] + [entry])[-_LOG_SIZE:]
    if not entry.get("hidden"):
        _tell(state, _story_entry(state, event, entry))


def _enter(state, scene_id, adventure):
    scene = adventure["scenes"].get(scene_id, {})
    state["scene"] = scene_id
    state["scene_title"] = scene.get("title", scene_id)
    state["voices"] = []
    state["arrivals"] = state.get("arrivals", 0) + 1
    if scene_id not in state["visited"]:
        state["visited"].append(scene_id)
    for npc_id in people_here(adventure, state):
        state["npcs"][npc_id]["met"] = True


def people_here(adventure, state):
    """Who is in the current scene: the people its text lists, unless the story has since put
    them somewhere else (a committed location wins over the adventure's lists), and anyone the
    story has put here."""
    scene_id = state["scene"]
    listed = [nid for nid in adventure["scenes"].get(scene_id, {}).get("npcs", []) if nid in state["npcs"]]
    here = [nid for nid in listed if state["npcs"][nid].get("location") in (None, scene_id)]
    return here + [nid for nid, npc in state["npcs"].items() if npc.get("location") == scene_id and nid not in here]


def profile_of(adventure, state, npc_id):
    """An NPC as the GM knows them: the adventure's profile (a bestiary monster under it, when
    it names one), what a commit made them in play (a monster), and what the GM wrote down
    about one it made up (role, looks, voice, wants, fears)."""
    live = state["npcs"].get(npc_id, {})
    profile = adventure["npcs"].get(npc_id, {})
    monster = (adventure.get("bestiary") or {}).get(live.get("monster") or "")
    if monster:
        profile = packs._layered(monster, profile)
    return {**profile, **(live.get("profile") or {})}


def ready(adventure, state, consequence):
    """Whether a consequence's moment has come. `at`, `when` and `after` must all hold, those
    it names; with none of them, `npc` alone says when: the next time the hero meets them.
    `at` and `npc` count only from the hero's next arrival somewhere, so a consequence made
    in front of the smith waits for the hero to come back. With no trigger at all it is a
    loose end the GM keeps in mind, never announced."""
    if consequence["status"] != "open":
        return False
    later = state["arrivals"] > consequence["arrivals"]
    timed = [consequence.get(k) for k in ("at", "when", "due_at") if consequence.get(k) not in (None, [])]
    if consequence["at"] and not (later and state["scene"] in consequence["at"]):
        return False
    elif consequence["due_at"] is not None and state["time"] < consequence["due_at"]:
        return False
    elif consequence["when"]:
        try:
            if not packs.evaluate(consequence["when"], state):
                return False
        except SoloError:
            return False
    if timed:
        return True
    npc = state["npcs"].get(consequence["npc"] or "")
    return bool(npc and later and npc["fate"] == "alive" and consequence["npc"] in people_here(adventure, state))


def _apply_changes(state, changes, event):
    state["facts"].update(changes.get("facts", {}))
    for npc_id, change in changes.get("npc", {}).items():
        if change.get("new") and npc_id in state["npcs"] and "location" not in change:
            # Someone the GM made up in play whom the pack has written down since (a generated
            # campaign's next mission brings them back): met here, as when the GM made them up.
            state["npcs"][npc_id]["location"] = state["scene"]
        npc = state["npcs"].setdefault(npc_id, {
            "name": change.get("name", npc_id), "faction": None, "fate": "alive", "attitude": 0,
            "location": state["scene"], "met": True, "memories": [],
        })
        npc.update({k: change[k] for k in ("name", "faction", "fate", "attitude", "location", "template", "attacker", "monster") if k in change})
        npc["met"] = True
        if change.get("memory"):
            npc["memories"].append(change["memory"])
        if change.get("profile"):
            npc["profile"] = {**npc.get("profile", {}), **change["profile"]}
    for faction_id, change in changes.get("faction", {}).items():
        faction = state["factions"].setdefault(faction_id, {"name": change.get("name", faction_id), "standing": 0, "memories": []})
        faction["standing"] = change["standing"]
        if change.get("memory"):
            faction.setdefault("memories", []).append(change["memory"])
    for promise_id, promise in changes.get("promise", {}).items():
        state["promises"][promise_id] = {k: promise[k] for k in ("npc", "terms", "status")}
    for consequence_id, change in changes.get("consequence", {}).items():
        consequence = state["consequences"].setdefault(consequence_id, {
            "text": "", "npc": None, "at": [], "when": None, "due_at": None, "status": "open",
            "made": event["seq"], "scene": state["scene"], "arrivals": 0, "due": False,
        })
        consequence.update({k: v for k, v in change.items() if k != "status_was"})
    pc = state["pc"]
    update = changes.get("pc", {})
    for track, value in update.get("tracks", {}).items():
        pc["tracks"][track]["value"] = value
    pc["conditions"] = [c for c in pc["conditions"] if c not in update.get("conditions_remove", [])]
    pc["conditions"] += [c for c in update.get("conditions_add", []) if c not in pc["conditions"]]
    for item in update.get("items_remove", []):
        if item in pc["items"]:
            pc["items"].remove(item)
    pc["items"] += update.get("items_add", [])
    state["time"] += changes.get("time", 0)
    state["clues"] += [c for c in changes.get("clues", []) if c not in state["clues"]]
    state["learned"] += [k for k in changes.get("learn", []) if k not in state["learned"]]
    if changes.get("chronicle"):
        state["chronicle"].append({"seq": event["seq"], "at": event["at"], "text": changes["chronicle"]})
    if changes.get("chaos"):
        state["chaos"] = changes["chaos"]["value"]
    if changes.get("end"):
        state["ended"] = {"seq": event["seq"], "at": event["at"], "text": changes["end"]}
    if pc["dead"] and changes.get("override") and update.get("tracks"):
        pc["dead"] = False
        state["ended"] = None
        state["fallen"] = None
    _dying(state, event, failures=update.get("death_failures", 0))


def _tell(state, entry):
    if entry:
        state["story"] = (state["story"] + [entry])[-_STORY_SIZE:]


# What each event looks like in the Book. Commits are the GM's bookkeeping and stay out:
# the GM narrates them. Everything here is already in the player's log.
_STORY_KINDS = {
    "check": "roll", "push": "roll", "death_roll": "roll", "rally": "roll", "save_self": "roll", "voice": "voice", "damage": "hit", "wound": "hit", "harm": "hurt",
    "enemy": "foe", "ally": "hit", "oracle": "oracle", "meaning": "oracle", "fight": "fight", "join": "fight", "round": "fight",
    "fight_end": "fight", "rest": "event", "light": "light", "advance": "event", "mark": "event", "roll": "event",
    "table": "event", "clock": "clock", "threat": "event",
}


def _story_entry(state, event, entry):
    kind = event["type"]
    if kind in ("created", "move"):
        story = {"kind": "scene", "scene": state["scene"], "title": state["scene_title"]}
    elif kind == "hero":
        story = {"kind": "event", "text": entry["text"]}
    elif kind == "commit" and event["changes"].get("end"):
        story = {"kind": "end", "text": event["changes"]["end"]}
    elif kind in ("table", "stage") and entry.get("omen"):
        story = {"kind": "omen", "text": event["text"]}
    elif kind == "stage":
        story = {"kind": "event", "text": event["text"]}
    elif kind in _STORY_KINDS:
        story = {"kind": _STORY_KINDS[kind], "text": entry["text"]}
    else:
        return None
    if kind in ("check", "push", "death_roll", "voice", "rally", "save_self"):
        outcome = event["outcome"]
        story.update(label=event["label"], pushed=kind == "push", death=kind in ("death_roll", "save_self"),
                     outcome={k: outcome[k] for k in ("result", "target", "success", "dragon", "demon", "rolls", "successes", "groups", "triggers") if k in outcome},
                     boons=event.get("boons", 0), banes=event.get("banes", 0))
        if kind == "voice":
            story["text"] = event["text"]
        elif event.get("attack"):
            foe = ((state["combat"] or {}).get("foes") or {}).get(event["attack"]["target"], {})
            story["purpose"] = f"{event['attack']['label']} at {foe.get('name', event['attack']['target'])}"
        elif event.get("defend"):
            story["purpose"] = event["defend"]["how"]
    elif kind in ("damage", "wound", "harm"):
        story.update(dealt=event["dealt"], down=event.get("down", False))
    if "seed" in event:
        story["seed"] = event["seed"]
    return {"seq": event["seq"], **story}


def _attack_name(text, fallback):
    """What a monster's attack is called, from its result: "Furious Bite! The eel sinks
    its fangs into you." is a Furious Bite. Otherwise the table's name."""
    name, bang, _ = text.partition("!")
    return name.strip() if bang and 0 < len(name.strip()) <= 32 else fallback


def _count_of(item, name):
    """How many of `name` an item line holds: "torch" is 1, "3 torches" is 3, anything else None."""
    words = item.strip().split(" ", 1)
    number, rest = (int(words[0]), words[1]) if len(words) == 2 and words[0].isdigit() else (1, item)
    wanted = slug(name)
    return number if slug(rest) in (wanted, slug(_plural(name))) else None


def _plural(word):
    return word + ("es" if word.endswith(("ch", "sh", "s", "x")) else "s")


def _dying_rules(system):
    spec = system.get("dying")
    if spec:
        return {"track": spec["track"], "rally": int(spec.get("rally", 3)), "die": int(spec.get("die", 3)),
                "self_rally": bool(spec.get("self_rally")), "self_save": bool(spec.get("self_save"))}
    else:
        return None


def _dying(state, event, successes=0, failures=0):
    """At 0 on the dying track the hero starts dying; above it they stop. Counts past the
    pack's limits end it one way or the other (a rally restores the track in the same event)."""
    rules, pc = state["labels"]["dying"], state["pc"]
    if not rules or pc["dead"]:
        return
    elif pc["tracks"][rules["track"]]["value"] > 0:
        pc["dying"] = None
    elif pc["dying"] is None:
        pc["dying"] = {"successes": 0, "failures": 0}
    else:
        pc["dying"]["successes"] += successes
        pc["dying"]["failures"] += failures
        if pc["dying"]["failures"] >= rules["die"]:
            pc.update(dying=None, dead=True)
            state["ended"] = {"seq": event["seq"], "at": event["at"], "text": f"{pc['name']} died."}
            state["fallen"] = {"at": event["at"], "scene": state["scene_title"], "by": state["last_blow"], "epitaph": state["last_player_said"]}


def _mark(state, event):
    """A Dragon or Demon on a skill roll marks the skill for advancement."""
    mark_on = state["labels"]["advancement"]
    outcome = event["outcome"]
    if mark_on and event["kind"] == "skill" and any(outcome.get(m) for m in mark_on) and event["stat"] not in state["pc"]["marks"]:
        state["pc"]["marks"].append(event["stat"])


def describe(event):
    """One line per event, for the log and the panel."""
    kind = event["type"]
    if kind == "created":
        return f"{event['pc']['name']} begins {event['title']}"
    elif kind == "move":
        text = f"moved to {event['to']}" + (f" (forced: {event['forced']})" if event.get("forced") else "")
        check = event.get("scene_check") or {}
        if check.get("result") == "altered":
            text += f" (scene check {check['roll']}: altered)"
        elif check.get("result") == "interrupted":
            text += f" (scene check {check['roll']}: interrupted. {oracle.describe_event(check['event'])})"
        return text
    elif kind in ("check", "push"):
        attack, defend = event.get("attack"), event.get("defend")
        purpose = f" (attack {attack['target']} with {attack['label']})" if attack else f" ({defend['how']})" if defend else ""
        text = ("pushed " if kind == "push" else "") + f"{event['label']}{purpose}: {_outcome_text(event)}"
        return text + (_push_cost(event.get("changes") or {}) if kind == "push" else "")
    elif kind == "roll":
        return f"rolled {event['expr']} = {event['result']['total']}" + (f" ({event['reason']})" if event.get("reason") else "")
    elif kind == "table":
        return f"{event['name']} ({event['total']}): {event['text']}"
    elif kind == "oracle" and event.get("chart") == "fortune":
        tilt = {"high": ", likely high", "low": ", likely low"}.get(event.get("tilt"), "")
        text = f"asked \"{event['question']}\" (fortune, {event['kind'].replace('_', '/')}{tilt}, rolled {event['roll']}): {event['answer']}"
        return text + (" (an extreme result, or a twist)" if event.get("extreme") else "")
    elif kind == "oracle":
        text = f"asked \"{event['question']}\" ({event['likely']}, rolled {event['roll']}): {event['answer']}"
        return text + (f". Random event: {oracle.describe_event(event['random_event'])}" if event.get("random_event") else "")
    elif kind == "meaning":
        return (f"meaning of \"{event['question']}\"" if event.get("question") else "meaning") + f": {' / '.join(event['words'])}"
    elif kind == "fight":
        return "fight: " + _order_text(event["order"])
    elif kind == "join":
        return f"{', '.join(f['name'] for f in event['foes'].values())} join the fight: " + _order_text(event["order"])
    elif kind == "round":
        return f"round {event['round']}: " + _order_text(event["order"])
    elif kind == "fight_end":
        return "the fight ends" + (f"; still standing: {', '.join(event['standing'])}" if event["standing"] else "")
    elif kind == "damage" and event.get("immune"):
        return f"{event['weapon']} hits {event['name']}: no effect (only {event['immune']} can harm it)"
    elif kind == "damage":
        text = f"{event['weapon']} hits {event['name']}: {event['roll']['total']} - armor {event['armor']} = {event['dealt']} damage"
        return text + (", down!" if event["down"] else f", HP {event['hp']}")
    elif kind == "wound":
        if event.get("roll") is None:
            return f"{event['why']}: {event['name']} is down!"
        amount = f"{event['roll']['total']}" + (" x2" if event.get("double") else "") + (f" - armor {event['armor']}" if event["armor"] else "")
        return f"{event['why']}: {amount} = {event['dealt']} damage to {event['name']}" + (", down!" if event["down"] else f", HP {event['hp']}")
    elif kind == "enemy":
        if "outcome" in event:
            outcome = event["outcome"]
            verdict = "Dragon!" if outcome["dragon"] else "Demon!" if outcome["demon"] else "hits" if outcome["success"] else "misses"
            text = f"{event['name']} attacks ({event['label']}, {outcome['result']} vs {outcome['target']}): {verdict}"
            return text + (f"; {event['incoming']['damage']} damage coming" if event.get("incoming") else "")
        text = f"{event['name']} ({event['total']}): {event['text']}"
        return text.rstrip(". ") + (f" ({event['incoming']['damage']} damage coming)" if event.get("incoming") else "")
    elif kind == "ally":
        outcome = event["outcome"]
        verdict = "Dragon!" if outcome["dragon"] else "Demon!" if outcome["demon"] else "hits" if outcome["success"] else "misses"
        text = f"{event['name']} attacks {event['target_name']} ({event['label']}, {outcome['result']} vs {outcome['target']}): {verdict}"
        if "dealt" in event:
            text += f"; {event['roll']['total']} - armor {event['armor']} = {event['dealt']} damage" + (", down!" if event["down"] else f", HP {event['hp']}")
        return text
    elif kind == "harm":
        sums = f"{event['roll']['total']} - armor {event['armor']} = " if event["armor"] else ""
        return f"{event['changes'].get('note', 'hit')}: {sums}{event['dealt']} damage"
    elif kind == "death_roll":
        tally = f"{event['successes']} success{'es' * (event['successes'] != 1)}, {event['failures']} failure{'s' * (event['failures'] != 1)}"
        after = {"rallies": ": rallies!", "dies": ": dies."}.get(event.get("result"), "")
        return f"death roll ({event['label']}, {_outcome_text(event)}): {tally}{after}"
    elif kind == "rally":
        return f"rallies alone ({event['label']}, {_outcome_text(event)})" + (": back on their feet, still dying" if event["rallied"] else "")
    elif kind == "save_self":
        return f"tries to save their own life ({event['label']}, {_outcome_text(event)})" + (": saved!" if event["saved"] else "")
    elif kind == "mark":
        return f"marked {event['label']} for advancement" + (f" ({event['reason']})" if event.get("reason") else "")
    elif kind == "advance":
        return "advancement: " + "; ".join(
            f"{r['name']} {r['was']} -> {r['now']} (rolled {r['roll']})" if r["now"] > r["was"] else f"{r['name']} stays {r['was']} (rolled {r['roll']})"
            for r in event["results"]
        )
    elif kind == "prefs":
        return "table settings changed"
    elif kind == "hero":
        return f"{event['pc']['name']} takes up the story"
    elif kind == "threat":
        if event["action"] == "triggered":
            return "the threat comes to pass: " + (event.get("text") or event["label"])
        return {"add": "a threat looms: ", "end": "the threat is gone: "}[event["action"]] + event["label"]
    elif kind == "stage":
        # Only what the player notices: the GM's note travels separately (gm_line).
        return event.get("text") or f"{event['label']} {event['at']}/{event['segments']}"
    elif kind == "clock" and event.get("stopped"):
        return f"{event['label']} stops at {event['value']}/{event['segments']}"
    elif kind == "clock":
        return f"{event['label']} {event['value']}/{event['segments']}" + (", full" if event["full"] else "")
    elif kind in ("commit", "rest"):
        return _commit_text(event["changes"])
    elif kind == "voice":
        return f"{event['label']} ({_outcome_text(event)}): " + (event["text"] if event["heard"] else "stays silent")
    elif kind == "light":
        label = event["label"].lower()
        return f"lit a {label}" if event["lit"] else f"put out the {label}" if event.get("reason") == "put out" else f"the {label} burns out"
    elif kind == "said":
        first = " ".join(event["text"].split())
        return ("GM" if event["by"] == "gm" else "Player") + f': "{first[:77] + "..." if len(first) > 80 else first}"'
    elif kind == "due":
        return f"a consequence comes due ({event['consequence']}): {event['text']}"
    else:
        return kind


def gm_line(event):
    """An event as the GM reads it: the player's line, plus what only the GM should read (what
    a clock's stage asks of them, facts, consequences, what word has spread)."""
    notes = [event["note"]] if event.get("note") else []
    changes = event.get("changes") or {}
    if changes.get("facts"):
        notes.append("facts " + ", ".join(f"{k} = {json.dumps(v, ensure_ascii=False)}" for k, v in changes["facts"].items()))
    for faction_id, change in changes.get("faction", {}).items():
        if change.get("memory"):
            notes.append(f"{faction_id} heard: {change['memory']}")
    for consequence_id, change in changes.get("consequence", {}).items():
        notes.append(f"consequence {consequence_id} {change['status']}" + (f": {change['text']}" if change.get("text") else ""))
    return describe(event) + "".join(f" [for the GM: {note}]" for note in notes)


def _outcome_text(event):
    outcome = event["outcome"]
    extras = []
    if event.get("boons"):
        extras.append(f"boons {event['boons']}")
    if event.get("banes"):
        extras.append(f"banes {event['banes']}")
    if "result" in outcome:
        verdict = "Dragon!" if outcome["dragon"] else "Demon!" if outcome["demon"] else "success" if outcome["success"] else "failure"
        text = f"{outcome['result']} vs {outcome['target']}, {verdict}"
    else:
        hits = outcome["successes"]
        text = f"{hits} success{'es' * (hits != 1)}" + (f", {', '.join(outcome['triggers'])}!" if outcome["triggers"] else "")
    return text + (f" ({', '.join(extras)})" if extras else "")


def _push_cost(changes):
    """What pushing took: "; took angry", "; paid 3 WP" (Sole Survivor) or "; STRESS +1"
    (Alien). A push recorded before the old value was kept says what the track came to."""
    pc = changes.get("pc", {})
    was = pc.get("tracks_was", {})
    parts = [f"took {c}" for c in pc.get("conditions_add", [])]
    for track, now in pc.get("tracks", {}).items():
        if track not in was:
            parts.append(f"{track.upper()} now {now}")
        elif now < was[track]:
            parts.append(f"paid {was[track] - now} {track.upper()}")
        else:
            parts.append(f"{track.upper()} +{now - was[track]}")
    return f"; {', '.join(parts)}" if parts else ""


def _commit_text(changes):
    parts = [changes["note"]] if changes.get("note") else []
    for npc_id, change in changes.get("npc", {}).items():
        if "attitude" in change:
            parts.append(f"{npc_id} attitude {change['attitude_was']} -> {change['attitude']}")
        if "fate" in change:
            parts.append(f"{npc_id} {change['fate']}")
    for faction_id, change in changes.get("faction", {}).items():
        if change["standing"] != change["standing_was"]:
            parts.append(f"{faction_id} standing {change['standing_was']} -> {change['standing']}")
    for promise_id, promise in changes.get("promise", {}).items():
        parts.append(f"promise {promise_id} {promise['status']}")
    pc = changes.get("pc", {})
    for track, value in pc.get("tracks", {}).items():
        parts.append(f"{track} {pc['tracks_was'][track]} -> {value}")
    parts += [f"+{c}" for c in pc.get("conditions_add", [])] + [f"-{c}" for c in pc.get("conditions_remove", [])]
    parts += [f"+{i}" for i in pc.get("items_add", [])] + [f"-{i}" for i in pc.get("items_remove", [])]
    if changes.get("time"):
        parts.append(f"{_duration(changes['time'])} pass")
    if changes.get("learn"):
        parts.append(f"learned {', '.join(changes['learn'])}")
    if changes.get("chronicle"):
        parts.append("chronicle entry")
    if changes.get("chaos"):
        parts.append(f"chaos {changes['chaos']['was']} -> {changes['chaos']['value']}")
    if changes.get("end"):
        parts.append("the adventure ends")
    return "; ".join(parts) or "commit"


def _order_text(order):
    return ", ".join(f"{f['name']} ({f['card']})" for f in order)


def _duration(seconds):
    if seconds % 3600 == 0:
        return f"{seconds // 3600} h"
    elif seconds % 60 == 0:
        return f"{seconds // 60} min"
    else:
        return f"{seconds} s"


def _pack(root, recorded, find):
    """A pack path from campaign.toml. If the pack moved (the plugin was reinstalled
    somewhere else), find it again in the library by its folder name."""
    path = root / recorded
    return path if path.exists() else find(Path(recorded).name)


def _read_events(path):
    events = []
    if path.exists():
        _mend_tail(path)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.strip():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as error:
                    raise SoloError(f"{path} line {number} is damaged: {error}") from None
    return events


def _mend_tail(path):
    """Every event is written as one line ending in a newline, so a last line without one
    was cut off mid-write (a crash, a power cut). Nothing has read it yet: set it aside in
    events.jsonl.torn and carry on. A complete event that only lost its newline gets it
    back, or the next event would be written onto the same line."""
    data = path.read_bytes()
    if not data or data.endswith(b"\n"):
        return
    cut = data.rfind(b"\n") + 1
    try:
        json.loads(data[cut:].decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        with open(path.with_name(path.name + ".torn"), "ab") as torn:
            torn.write(data[cut:] + b"\n")
        with open(path, "r+b") as log:
            log.truncate(cut)
    else:
        with open(path, "ab") as log:
            log.write(b"\n")


def _shift(value, old, names=None):
    """ "+1" / "-2" move from the old value; a number or a name sets it outright."""
    text = value.strip() if isinstance(value, str) else None
    if isinstance(value, bool) or value is None:
        raise SoloError(f"can't use {value!r} as an amount")
    elif isinstance(value, (int, float)):
        return int(value)
    elif text and re.fullmatch(r"[+-]\d+", text):
        return old + int(text)
    elif text and names and text in names:
        return names[text]
    else:
        raise SoloError(f"can't use {value!r}: write \"+1\", \"-1\" or a number" + (f", or one of {', '.join(names)}" if names else ""))


def _by_id(items, fields):
    """Records given as a list, as one object, or keyed by their ids, the way npc and faction
    are ({"hrok_talks": {"status": "done"}}): always a list of objects with their id inside."""
    if isinstance(items, dict):
        if items and not set(items) & fields and all(isinstance(v, dict) for v in items.values()):
            return [{"id": key, **value} for key, value in items.items()]
        return [items]
    return list(items) if isinstance(items, list) else [items]


def _listed(value):
    return [] if value is None else [value] if isinstance(value, str) else list(value)


def _attitude(value):
    return ATTITUDES[value] if isinstance(value, str) else int(value)


def _clamp(value, low, high):
    return max(low, min(high, value))
