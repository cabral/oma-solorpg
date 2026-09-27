"""System and adventure packs: loading, validation, and the branch-condition language.

Hand-written files are TOML, generated files are JSON. When both exist for the same
thing (npcs/grukk.json from an import, npcs/grukk.toml written by hand), the TOML
keys win, so re-running an import never clobbers authored content.
"""

import ast
import json
import re
import tomllib
import unicodedata
from pathlib import Path

from . import SoloError, dice

FAMILIES = ("d20-under", "d6-pool")
ATTITUDES = {"hostile": -2, "unfriendly": -1, "neutral": 0, "friendly": 1, "allied": 2}
FATES = ("alive", "dead", "fled", "captured", "gone")
PROMISE_STATUSES = ("open", "kept", "broken")
FACT_KEY = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)*$")


def slug(text):
    """"Hunting & Fishing" -> "hunting_fishing", "Chieftain's Hall" -> "chieftains_hall"."""
    plain = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().replace("'", "")
    return re.sub(r"[^a-z0-9]+", "_", plain.lower()).strip("_")


def toml_string(value):
    """A TOML basic string. JSON's escapes are TOML's, except that JSON writes characters
    outside the BMP (emoji) as surrogate pairs, which TOML rejects, so those stay literal."""
    return json.dumps(str(value), ensure_ascii=False)


def load_data(path):
    """Read a .toml or .json file."""
    path = Path(path)
    try:
        if path.suffix == ".toml":
            with open(path, "rb") as f:
                return tomllib.load(f)
        else:
            return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SoloError(f"missing file: {path}") from None
    except (tomllib.TOMLDecodeError, json.JSONDecodeError, UnicodeDecodeError) as error:
        raise SoloError(f"can't parse {path}: {error}") from None


def load_system(path):
    """A system pack, with every pack it extends under it. A pack built from a book the
    player owns (~/Games/solo/systems/dragonbane) can say `extends = "dragonbane"` and hold
    only what the book adds or corrects: its system.toml, creation.toml, art.toml and
    gear.toml are laid over the base's section by section, and its tables, characters,
    bestiary and rules pages over the base's by id. Nothing of the book lands in the
    repository, and the bundled pack keeps its updates."""
    layers = _system_layers(Path(path))
    spec, creation_data, art, gear, skill_files = {}, {}, {}, {}, {}
    tables, characters, bestiary = {}, {}, {}
    for root in layers:
        own = load_data(root / "system.toml")
        own.pop("extends", None)
        spec = _layered(spec, own)
        creation_data = _layered(creation_data, _optional(root / "creation.toml"))
        art = _layered(art, _optional(root / "art.toml"))
        gear = _layered(gear, _optional(root / "gear.toml"))
        skill_files.update(_optional(root / "skills.json"))
        tables.update(_load_folder(root / "tables"))
        characters.update(_load_folder(root / "characters"))
        bestiary.update(_load_folder(root / "bestiary"))
    root = layers[-1]
    skills = {}
    for source in (skill_files, spec.get("skills", {})):
        for key, value in source.items():
            entry = value if isinstance(value, dict) else {"attribute": value}
            skills[slug(key)] = {
                "attribute": entry["attribute"],
                "name": entry.get("name") or key.replace("_", " ").capitalize(),
                # false for skills nobody can try without training (Dragonbane's magic schools)
                "untrained": entry.get("untrained", True),
            }
    return {
        **spec,
        "dir": root,
        # Every layer, this pack first: where rules pages are looked up, in that order.
        "dirs": list(reversed(layers)),
        "name": spec.get("name", root.name),
        "attributes": spec.get("attributes", {}),
        "conditions": spec.get("conditions", {}),
        "tracks": spec.get("tracks", {}),
        "time": spec.get("time", {}),
        "push": spec.get("push", {}),
        "rest": spec.get("rest", {}),
        "skills": skills,
        "tables": tables,
        "creation": creation_data,
        "characters": characters,
        "art": art,
        # What things cost (gear.toml): the coins, and every item with its price.
        "money": gear.get("money", {}),
        "gear": gear.get("gear", {}),
        # Creatures with their stat blocks, for any adventure's NPCs to be (`monster = "<id>"`).
        "bestiary": bestiary,
    }


def _system_layers(root):
    """The packs under this one, base first, ending with this one."""
    chain = [root.resolve()]
    while True:
        base = load_data(chain[-1] / "system.toml").get("extends")
        if not base:
            return list(reversed(chain))
        found = _base_pack(chain[-1], str(base))
        if found in chain:
            raise SoloError(f"{chain[-1].name} extends {base!r}, which extends it back")
        chain.append(found)


def _base_pack(root, name):
    """What `extends` names: a folder relative to the pack, else a player's pack, else a
    bundled one. Never the pack itself, so ~/Games/solo/systems/dragonbane can extend the
    bundled dragonbane its name hides. `bundled:dragonbane` names the bundled pack only, for
    a layer under the player's own dragonbane (the core rules under the solo rules)."""
    from . import library  # library loads packs, so it can't be imported at the top
    if name.startswith("bundled:"):
        name, places = name.split(":", 1)[1], (library.REPO / "packs",)
    else:
        places = (root, library.home() / "systems", library.REPO / "packs")
    for candidate in (place / name for place in places):
        candidate = candidate.expanduser().resolve()
        if candidate != root and (candidate / "system.toml").exists():
            return candidate
    raise SoloError(f"{root.name} extends {name!r}, and there's no system pack by that name (a folder, or one in the library)")


def _layered(base, over):
    """`over` laid on `base`: tables merged key by key, anything else replaced."""
    merged = dict(base)
    for key, value in over.items():
        merged[key] = _layered(merged[key], value) if isinstance(value, dict) and isinstance(merged.get(key), dict) else value
    return merged


def with_system(system, adventure):
    """The adventure as it plays on this system: an NPC that names a monster
    (`monster = "wolf"`) is the bestiary's wolf with the adventure's own keys laid over it
    (a name, a secret, more hit points). The bestiary rides along for NPCs a commit makes
    from a monster in play."""
    bestiary = system.get("bestiary", {})
    npcs = {nid: _layered(bestiary[npc["monster"]], npc) if npc.get("monster") in bestiary else npc
            for nid, npc in adventure["npcs"].items()}
    return {**adventure, "npcs": npcs, "bestiary": bestiary}


def price(text, money):
    """A price as the book writes it, in the smallest coin: "1 gold 5 silver" is 105 with
    gold 100, silver 10, copper 1. A bare number is already in the smallest coin. None
    when it can't be read ("varies")."""
    coins, aliases = (money or {}).get("coins", {}), (money or {}).get("aliases", {})
    text = re.sub(r"\b(coins?|pieces?|and)\b|,", " ", str(text).lower())
    if text.strip().isdigit():
        return int(text)
    pairs = _PRICE.findall(text)
    if not pairs or _PRICE.sub("", text).strip():
        return None
    total = 0
    for amount, coin in pairs:
        coin = aliases.get(coin, coin)
        coin = coin if coin in coins else coin[:-1] if coin.endswith("s") and coin[:-1] in coins else None
        if coin is None:
            return None
        total += int(amount) * int(coins[coin])
    return total


_PRICE = re.compile(r"(\d+)\s*([a-z]+)")


# What a chapter file (chapters/<id>.toml) may hold: the parts of adventure.toml that grow
# with the story. The title, the start and the rest stay in adventure.toml.
CHAPTER_KEYS = ("scenes", "clocks", "factions", "weapons")


def load_adventure(path, drafts=True):
    """An adventure pack: adventure.toml over an importer's scenes.json, then each chapter
    file in chapters/ in order (chapter_2 before chapter_10). A chapter adds scenes, clocks,
    factions and weapons, and can add to a scene defined before it (the hub's way into the
    new mission, its briefing), so a campaign that grows a mission at a time never has to
    rewrite what was written before. An id defined twice is a problem, never a silent
    override: `conflicts` lists them for `validate`.

    A chapter marked `draft = true` is still being written: its author sees it (the default),
    a campaign plays on without it (drafts=False) until the mark comes off."""
    root = Path(path)
    spec = _optional(root / "adventure.toml")
    scenes = {sid: dict(scene) for sid, scene in _optional(root / "scenes.json").items()}
    sections = {key: dict(spec.get(key, {})) for key in CHAPTER_KEYS if key != "scenes"}
    defined = {key: dict.fromkeys(sections[key], "adventure.toml") for key in sections}
    conflicts, chapters = [], []
    for part, name in [(spec, "adventure.toml"), *_chapters(root)]:
        if name != "adventure.toml":
            if part.get("draft") and not drafts:
                continue
            chapters.append(Path(name).stem)
            conflicts += [f"{name}: a chapter holds only {', '.join(CHAPTER_KEYS)} and draft ({key} goes in adventure.toml)"
                          for key in part if key not in (*CHAPTER_KEYS, "draft")]
            for key in sections:
                for item_id, value in part.get(key, {}).items():
                    if item_id in defined[key]:
                        conflicts.append(f"{name}: {key[:-1]} {item_id} is already defined in {defined[key][item_id]}")
                    else:
                        sections[key][item_id], defined[key][item_id] = value, name
        for sid, extra in part.get("scenes", {}).items():
            scene = scenes.setdefault(sid, {})
            for key, value in extra.items():
                if key == "exits":
                    scene["exits"] = {**scene.get("exits", {}), **value}
                elif key in ("npcs", "tables"):
                    scene[key] = list(dict.fromkeys(scene.get(key, []) + list(value)))
                elif key in ("branches", "voices"):
                    scene[key] = scene.get(key, []) + list(value)
                else:
                    scene[key] = value
    if scenes:
        return {
            "dir": root,
            "title": spec.get("title", root.name),
            "system": spec.get("system"),
            "summary": spec.get("summary", ""),
            "start": spec.get("start") or next(iter(scenes)),
            "factions": sections["factions"],
            "clocks": sections["clocks"],
            # Still being written (make campaign): the New adventure screen leaves it out.
            "draft": bool(spec.get("draft")),
            # chapters/*.toml, in the order they were laid on, and ids they defined twice.
            "chapters": chapters,
            "conflicts": conflicts,
            # The oracle's chaos factor to start at, and whether entering a scene rolls a scene check.
            "chaos": spec.get("chaos", 5),
            "scene_checks": spec.get("scene_checks", True),
            # Game time an ordinary move takes, unless the exit says otherwise: { stretch = 1 }.
            "move_time": spec.get("move_time", {}),
            # Weapons the adventure brings (a named blade, a relic): they join the system's.
            "weapons": sections["weapons"],
            "characters": _load_folder(root / "characters"),
            "scenes": scenes,
            "npcs": _load_folder(root / "npcs"),
            "tables": _load_folder(root / "tables"),
            "art": _optional(root / "art.toml"),
        }
    else:
        raise SoloError(f"{root} has no scenes: expected scenes.json or [scenes.<id>] in adventure.toml")


def _chapters(root):
    """chapters/*.toml as (data, name), in natural order: chapter_2 before chapter_10."""
    order = lambda p: [int(part) if part.isdigit() else part for part in re.split(r"(\d+)", p.stem)]  # noqa: E731
    return [(load_data(p), f"chapters/{p.name}") for p in sorted((root / "chapters").glob("*.toml"), key=order)]


def flat_facts(facts, prefix=""):
    """TOML reads { hall.flooded = true } as nested tables; facts are dotted keys."""
    flat = {}
    for key, value in (facts or {}).items():
        if isinstance(value, dict):
            flat.update(flat_facts(value, f"{prefix}{key}."))
        else:
            flat[f"{prefix}{key}"] = value
    return flat


def exit_spec(value):
    """An exit as {label, when, time}. Written as a plain label it is always open; written
    as a table it can wait on a condition (stairs that unfold once a puzzle is solved) and
    take game time to cross (a swim to the wreck)."""
    if isinstance(value, dict):
        return {"label": str(value.get("label", "")), "when": value.get("when"), "time": dict(value.get("time", {}))}
    else:
        return {"label": str(value), "when": None, "time": {}}


def exits(adventure, scene_id):
    """Every exit of a scene, open or not, as {scene id: exit_spec}."""
    return {sid: exit_spec(value) for sid, value in adventure["scenes"].get(scene_id, {}).get("exits", {}).items()}


def is_open(spec, state):
    return not spec["when"] or evaluate(spec["when"], state)


def missing(system):
    """What the pack says it needs (`needs`) and doesn't hold yet. A bundled pack ships only
    a game's names; the numbers and tables come from a pack built from the player's book,
    laid over it. Dotted keys read into a section: creation.choose is creation.toml's tables."""
    def held(key):
        value = system
        for part in key.split("."):
            value = value.get(part) if isinstance(value, dict) else None
        return bool(value)
    return [key for key in system.get("needs", []) if not held(key)]


def missing_text(system, gaps):
    return (f"{system['name']} has only its names so far. Its rules come from your own book: "
            f"build them with `make rules BOOK=<your PDF>` (see the README). Missing: {', '.join(gaps)}")


def base_chance(system, value):
    """A skill's chance without training for an attribute value, from the system's
    `untrained` table (d20-under). Systems without one start untrained skills at 0."""
    return next((chance for top, chance in system.get("untrained", []) if value <= top), 0)


def scene_text(adventure, scene_id):
    """The scene's full text, GM-only blocks included."""
    scene = adventure["scenes"][scene_id]
    path = scene_path(adventure, scene_id)
    return path.read_text(encoding="utf-8") if path.exists() else scene.get("text", "")


def scene_path(adventure, scene_id):
    """Where a scene's Markdown lives. It must be inside the adventure folder: the GM reads
    whatever this points at, and adventure packs get shared."""
    root = Path(adventure["dir"]).resolve()
    path = (root / adventure["scenes"][scene_id].get("file", f"scenes/{scene_id}.md")).resolve()
    if path.is_relative_to(root):
        return path
    else:
        raise SoloError(f"scene {scene_id}: its file must be inside the adventure folder")


def engine_rules(system):
    """The rules the engine itself runs, written out from the system pack, so `solo rule`
    answers the basics (conditions, pushing, rests, dying, fights) even when no rulebook
    has been imported. Generated from data: it can't disagree with what the engine does."""
    note = "(The rules the engine runs, from the system pack. An imported rulebook says more.)"
    attributes, time = system["attributes"], system["time"]
    pages = []
    if system["conditions"]:
        lines = [f"- {c}: a bane on every roll that uses {attributes.get(a, a)} ({a})" for c, a in system["conditions"].items()]
        pages.append(("Conditions", [
            "A condition stays until a rest heals it. The engine adds its bane to rolls by itself; don't add it again.", *lines,
            'Gain one with a commit: {"pc": {"conditions": {"add": ["dazed"]}}}. Heal: {"pc": {"conditions": {"remove": ["dazed"]}}}.']))
    cost = system["push"].get("cost")
    if cost == "condition":
        pages.append(("Pushing a roll", [
            "A failed roll that isn't a Demon can be pushed once: roll again, and take a condition the hero doesn't have yet.",
            "The player picks the condition: solo push --condition <name>. A pushed roll can't be pushed again; defences and death rolls can't be pushed."]))
    elif isinstance(cost, dict):
        pages.append(("Pushing a roll", [f"A failed roll can be pushed once, at a cost: {', '.join(f'{k} +{v}' for k, v in cost.items())}. solo push."]))
    for rest_id, rest in system["rest"].items():
        recover = ", ".join(f"{t} {v}" for t, v in rest.get("recover", {}).items()) or "nothing"
        pages.append((rest.get("label", rest_id.capitalize()), [
            f"Recovers {recover}; heals {rest.get('heal', 0)} condition(s); takes {spent_text(rest.get('time', {}))}"
            + (f"; once per {rest['limit']}" if rest.get("limit") else "") + f". solo rest {rest_id}."]))
    dying = system.get("dying")
    if dying:
        pages.append(("Dying", [
            f"At 0 {dying['track']} the hero is dying: no other rolls. On each of the hero's turns, a death roll on {dying['roll']} (solo death-roll).",
            f"{dying.get('rally', 3)} successes: they rally with {dying.get('recover', '1')} {dying['track']}. {dying.get('die', 3)} failures: they die.",
            "A Dragon counts as two successes, a Demon as two failures. Any hit while dying is a failure; a dying hero can't evade or parry (solo defend take).",
            "Healing from someone else, or an elixir, ends it: commit the track back up."]))
    fight = system.get("combat")
    if fight:
        pages.append(("Fights", [
            f"Initiative: cards 1-{fight.get('initiative', 10)} dealt each round (solo fight, solo fight --round); lowest acts first. A round is {time.get('round', '?')} seconds of game time.",
            "The hero attacks with a carried weapon's skill (solo attack <foe> --with <weapon>). A hit deals the weapon's damage plus the damage bonus, minus the foe's armor."
            + (" A Dragon on an attack rolls the weapon's dice twice." if fight.get("dragon") == "double" else "") + " A Demon (a fumble) misses and can't be pushed.",
            "Foes attack with solo enemy <foe>: a skill roll, or a monster's attack table. A monster with ferocity acts that many times a round.",
            f"A hit waits until the player answers: evade ({fight.get('evade', 'evade')}), parry with a weapon, or take it. A failed defence takes the hit, minus the hero's armor."
            + (" Monster attacks can be evaded but not parried, unless the attack says so." if fight.get("monster_parry") is False else ""),
            "Not modelled (a grapple or a hold like a monster's embrace, shoving, fleeing, morale): rule them with a check (BRAWLING or STR to break free, EVADE to slip away) and commit the harm.",
            "Harm that isn't a weapon blow (fire, spells, traps): solo wound <foe> <dice> --why <what>."]))
    advancement = system.get("advancement")
    if advancement:
        pages.append(("Advancement", [
            f"A {' or '.join(advancement.get('mark_on', []))} on a skill roll marks the skill; so do the end-of-session questions (solo mark <skill>).",
            f"solo advance rolls {advancement.get('roll', '1d20')} for each mark: over the skill's value, it goes up one (to {advancement.get('max', 18)})."]))
    oracle = system.get("oracle", {})
    if oracle.get("chart") == "fortune":
        chart = oracle["fortune"]
        bands = [f"{low}" if low == high else f"{low}-{high}" for low, high in chart["bands"]]
        pages.append(("Fortune chart", [
            "The oracle: a question a GM would answer. solo ask \"<question>\" [--kind <column>] [--likely unlikely|likely]",
            "Roll a D6 and read the column. If a low result is likely, 2D6 keep the lowest; if a high one is, keep the highest.",
            *[f"- {column}: " + ", ".join(f"{b} {v}" for b, v in zip(bands, values)) for column, values in chart.items() if column != "bands"],
            "A 1 or a 6 is an extreme result or an interesting twist. If an answer is almost certain, or one is more interesting, don't roll: decide.",
            "Open questions: solo ask --meaning rolls the inspiration table (an action, an attribute, a thing) to interpret."]))
    threats = system.get("threats")
    if threats:
        pages.append(("Threats", [
            f"A looming danger on a counter from {threats.get('start', 1)} to {threats.get('segments', 6)}: solo threat add \"<what happens when it triggers>\" [--recurring], or solo threat random.",
            "It advances on a significant delay, or an opening through inaction or failure (solo threat advance <id>); by two in dire straits, like a Demon on a task against time. "
            "It advances by itself when the hero spends a stretch or more (searching, resting).",
            f"At {threats.get('segments', 6)} the danger comes to pass: face it head-on. A threat inherent to the mission or the place starts over (--recurring); any other is gone.",
            "Keep one active whenever the hero is delving somewhere dangerous."]))
    if system.get("search") or system.get("scavenge"):
        pages.append(("Searching and scavenging", [
            "solo search: a careful search for hidden doors, mechanisms, secrets. A stretch passes (threats advance), then SPOT HIDDEN: "
            "a Dragon rolls the search table twice (pick one), a success once, a failure finds nothing, a Demon finds nothing and brings a new danger. "
            "If the hero knows where the hidden thing is, there's no roll.",
            "solo scavenge: rummaging through something specific (supplies, a nest, a fallen foe's gear). A minute or two; the same place again takes a stretch (--again).",
            "Traps: solo table traps. SPOT HIDDEN keeps the hero out of one not yet sprung; EVADE or the like avoids one sprung; harm from solo table harm, or 2D6."]))
    npcs = system.get("npcs", {})
    if npcs.get("templates"):
        lines = [f"- {tid}: HP {t['hp']}, armor {t.get('armor', 0)}, damage {t['damage']}, relevant skills {t['skill']}, others {t.get('other', '?')}, movement {t.get('movement', '?')}"
                 for tid, t in npcs["templates"].items()]
        pages.append(("Simple NPCs", [
            "An NPC the story brings in can fight with a template and an attacker role, committed with it: "
            '{"npc": {"slime_bug": {"name": "Slime bug", "template": "minion", "attacker": "ranged"}}}, then solo fight slime_bug.',
            *lines, f"Attackers: {', '.join(npcs.get('attackers', []))}. On its turn (solo enemy) it rolls the NPC attack table in its column: an attack is a skill roll, anything else is yours to run.",
            "Monsters roll their own attack tables instead. NPCs and monsters may flee or surrender when a fight turns: ask the fortune chart."]))
    abilities = system.get("abilities", {})
    if abilities:
        lines = []
        for spec in abilities.values():
            if spec.get("initiative"):
                lines.append(f"- {spec.get('name')}: fighting alone, draw {spec['initiative']} initiative cards and keep them all: {spec['initiative']} turns a round.")
            if spec.get("push"):
                lines.append(f"- {spec.get('name')}: adventuring alone, push a roll without a condition for {', '.join(f'{v} {t.upper()}' for t, v in spec['push'].items())} (solo push --sole-survivor).")
        pages.append(("Heroic abilities", ["The heroic abilities the engine runs by itself.", *lines]))
    if (system.get("dying") or {}).get("self_rally") or (system.get("rest", {}).get("stretch") or {}).get("tend"):
        pages.append(("Healing alone", [
            "During a stretch rest the hero can tend their own wounds: solo rest stretch --tend (a HEALING roll: more HP on a success).",
            "At zero HP the hero can rally themselves with no bane: solo rally. Rallied, they act again, still making death rolls.",
            "Or try to save their own life: solo death-roll --heal (a HEALING roll instead of the death roll)."]))
    if time:
        pages.append(("Time", [f"{unit}: {seconds} seconds" for unit, seconds in time.items()]
                      + ['Time passes with moves, rests and fight rounds, and with commits: {"time": {"stretch": 1}}. Clocks can tick on it.']))
    pages += _price_pages(system) + _bestiary_pages(system)
    return [{"title": page[0], "text": f"# {page[0]}\n\n{note}\n\n" + "\n".join(page[1]) + "\n",
             **({"search": page[2]} if len(page) > 2 else {})} for page in pages]


# The words a GM looks prices up by, whatever the book calls its chapter.
_PRICE_TERMS = ["prices", "price", "cost", "costs", "buy", "buying", "sell", "selling", "shop", "market", "merchant",
                "trade", "barter", "bartering", "haggle", "money", "coins", "gear", "equipment"]


def _price_pages(system):
    """gear.toml as pages: the coins and a line per category, then a page per category with
    every item and its price, as the book gives them."""
    gear, money = system.get("gear", {}), system.get("money", {})
    if not gear:
        return []
    coins = sorted(money.get("coins", {}).items(), key=lambda c: -c[1])
    groups = {}
    for item_id, item in gear.items():
        groups.setdefault(item.get("category") or "Gear", []).append((item_id, item))
    lines = [f"Coins: {' = '.join(f'{coins[0][1] // value} {coin}' for coin, value in coins)}."] if coins else []
    lines += ["Coins are items on the hero's sheet (\"12 silver\"). An item's price: solo rule <item>. A whole category:", ""]
    lines += [f"- {category} ({len(items)}): solo rule prices {category.lower()}" for category, items in groups.items()]
    pages = [("Prices", lines, _PRICE_TERMS)]
    for category, items in groups.items():
        pages.append((f"Prices: {category}", [_price_line(system, iid, item) for iid, item in items], [category.lower(), f"{category.lower()} prices"]))
    return pages


def _price_line(system, item_id, item):
    extras = [f"{k} {item[k]}" for k in ("weight", "supply") if item.get(k) not in (None, "")]
    weapon, armor = system.get("weapons", {}).get(item_id), system.get("armor", {}).get(item_id)
    if weapon:
        extras.append(f"{weapon.get('skill', '?')}, {weapon.get('damage', '?')} damage")
    if armor is not None:
        extras.append(f"armor {armor}")
    note = f". {item['note']}" if item.get("note") else ""
    return f"- {item.get('name', item_id)}: {item.get('price', '?')}" + (f" ({'; '.join(extras)})" if extras else "") + note


def _bestiary_pages(system):
    bestiary = system.get("bestiary", {})
    if not bestiary:
        return []
    lines = ["Creatures any adventure can use. An adventure's NPC can be one (monster = \"wolf\" in its profile). "
             "In play, bring one in with a commit, then fight it: "
             '{"npc": {"wolf_1": {"name": "Wolf", "monster": "wolf"}}}, then solo fight wolf_1.', ""]
    for monster_id, monster in sorted(bestiary.items()):
        stats = monster.get("stats", {})
        numbers = [f"HP {stats['hp']}" if "hp" in stats else "", f"armor {stats.get('armor', 0)}"]
        numbers += [f"ferocity {stats['ferocity']}" if stats.get("ferocity") else "", f"immune: {stats['immune']}" if stats.get("immune") else ""]
        numbers += [f"attacks: solo table {monster['attacks']}" if monster.get("attacks") else ""]
        role = f", {monster['role']}" if monster.get("role") else ""
        lines.append(f"- {monster_id}: {monster.get('name', monster_id)}{role} ({', '.join(n for n in numbers if n)})")
    return [("Bestiary", lines, ["bestiary", "monster", "monsters", "creature", "creatures", "beast", "beasts", *bestiary])]


def search_rules(folders, topic, extra=()):
    """Rule pages for a topic, best first. Returns (pages, how): how is "title" when the
    topic names pages (by title or search terms), "text" when it is only in their text.
    See `rule_matches` for how pages are found and ranked."""
    matches = rule_matches(folders, topic, extra)
    named = [page for score, page in matches if score >= _NAMED]
    if matches and matches[0][0] >= _EXACT:
        return [matches[0][1]], "title"
    elif named:
        return named, "title"
    else:
        return [page for _, page in matches], "text"


def rule_pages(folders, extra=()):
    """Every rules page: the folders in order (a pack laid over another first, the adventure
    last), then the engine's own pages, which an imported page of the same title replaces
    (the book's page on conditions over the engine's). Pages of the same title in two
    folders are both kept; the first answers a search for that title.

    A page is Markdown with its title on the first line (`# Prices`) and, optionally, the
    words a GM would look it up by on a line of their own after it: `Search: cost, buying,
    inn, lodging`."""
    pages = [_rule_page(path.read_text(encoding="utf-8"), path.stem) for folder in folders for path in sorted(Path(folder).glob("*.md"))]
    seen = {page["title"].lower() for page in pages}
    return pages + [p for p in extra if p["title"].lower() not in seen]


def _rule_page(text, stem):
    lines = text.lstrip().splitlines()
    first = lines[0] if lines else ""
    title = first[2:].strip() if first.startswith("# ") else stem.replace("_", " ")
    terms = next((line.split(":", 1)[1] for line in lines[1:6] if line.lower().startswith("search:")), "")
    page = {"title": title, "text": text}
    words = [w.strip() for w in terms.split(",") if w.strip()]
    return {**page, "search": words} if words else page


_EXACT, _NAMED = 1000, 400


def rule_matches(folders, topic, extra=()):
    """(score, page) for every page the topic finds, best first. The topic as a whole title
    or search term is exact; every word of it in the title, or in one search term, names the
    page; failing that, every word somewhere in the text, scored by how often. A word matches
    whole or as the start of a word: "sneak" finds "sneaking", "inn" never "beginning"."""
    pages = rule_pages(folders, extra)
    needle = " ".join(topic.lower().split())
    if not needle:
        return [(_NAMED, page) for page in pages]
    words = needle.split()
    found = []
    for page in pages:
        title, terms = page["title"].lower(), [t.lower() for t in page.get("search", [])]
        if needle in (title, *terms) or needle.rstrip("s") in (title, *terms):
            score = _EXACT
        elif _all_words(title, words):
            score = _NAMED + 100
        elif any(_all_words(term, words) for term in terms):
            score = _NAMED
        else:
            counts = [len(re.findall(rf"\b{re.escape(w)}", page["text"].lower())) for w in words]
            score = sum(counts) if all(counts) else 0
        if score:
            found.append((score, page))
    return sorted(found, key=lambda f: -f[0])


def _all_words(text, words):
    return all(re.search(rf"\b{re.escape(w)}", text) for w in words)


# Branch conditions ---------------------------------------------------------------
#
# A small expression language, parsed with ast and walked by hand (never eval):
#   npc.orc_leader.fate == 'alive' and promise.warband_joins == 'kept'
#   faction.orcs >= friendly or fact.hall.alarm
#   clock.dark_ritual >= 4 and not visited.cellar

_ROOTS = ("npc", "faction", "promise", "fact", "clock", "scene", "visited", "pc")
_NPC_FIELDS = ("fate", "attitude", "location")
_ALLOWED = (
    ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.Compare,
    ast.Eq, ast.NotEq, ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn,
    ast.Name, ast.Attribute, ast.Constant, ast.List, ast.Tuple, ast.Load,
)


def compile_condition(text):
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as error:
        raise SoloError(f"can't read condition {text!r}: {error.msg}") from None
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED):
            raise SoloError(f"condition {text!r}: {type(node).__name__} isn't allowed")
    for path in _paths(tree):
        if path[0] not in _ROOTS and not (len(path) == 1 and path[0] in ATTITUDES):
            raise SoloError(f"condition {text!r}: unknown name {'.'.join(path)}")
    return tree


def evaluate(condition, state):
    """Evaluate a condition (text or compiled) against campaign state."""
    tree = compile_condition(condition) if isinstance(condition, str) else condition
    return bool(_eval(tree.body, state))


def _eval(node, state):
    match node:
        case ast.BoolOp(op=ast.And(), values=values):
            return all(_eval(v, state) for v in values)
        case ast.BoolOp(op=ast.Or(), values=values):
            return any(_eval(v, state) for v in values)
        case ast.UnaryOp(op=ast.Not(), operand=operand):
            return not _eval(operand, state)
        case ast.Compare(left=left, ops=ops, comparators=comparators):
            values = [_eval(left, state)] + [_eval(c, state) for c in comparators]
            return all(_compare(op, a, b) for op, a, b in zip(ops, values, values[1:]))
        case ast.Constant(value=value):
            return value
        case ast.List(elts=items) | ast.Tuple(elts=items):
            return [_eval(item, state) for item in items]
        case _:
            return _lookup(_path(node), state)


def _compare(op, a, b):
    try:
        match op:
            case ast.Eq():
                return a == b
            case ast.NotEq():
                return a != b
            case ast.In():
                return b is not None and a in b
            case ast.NotIn():
                return b is None or a not in b
            case _ if a is None or b is None:
                return False
            case ast.Lt():
                return a < b
            case ast.LtE():
                return a <= b
            case ast.Gt():
                return a > b
            case _:
                return a >= b
    except TypeError:
        raise SoloError(f"can't compare {a!r} with {b!r} (attitudes compare with bare names: friendly)") from None


def _lookup(path, state):
    root, rest = path[0], path[1:]
    key = rest[0] if rest else None
    match root:
        case "scene":
            return state.get("scene")
        case "npc":
            field = rest[1] if len(rest) > 1 else "fate"
            return state["npcs"].get(key, {}).get(field)
        case "faction":
            return state["factions"].get(key, {}).get("standing")
        case "promise":
            return state["promises"].get(key, {}).get("status")
        case "fact":
            return state["facts"].get(".".join(rest))
        case "clock":
            return state["clocks"].get(key, {}).get("value")
        case "visited":
            return key in state["visited"]
        case "pc":
            pc = state.get("pc") or {}
            if key == "conditions":
                return pc.get("conditions", [])
            else:
                return pc.get("tracks", {}).get(key, {}).get("value")
        case _:
            return ATTITUDES[root]


def _path(node):
    """npc.orc_leader.fate -> ["npc", "orc_leader", "fate"]."""
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        return [node.id] + parts[::-1]
    else:
        raise SoloError("conditions can only read names like npc.<id>.fate")


def _paths(tree):
    """Every name path in a compiled condition, outermost attribute chains only."""
    found = []
    inner = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            inner.add(id(node.value))
    for node in ast.walk(tree):
        if isinstance(node, (ast.Name, ast.Attribute)) and id(node) not in inner:
            found.append(_path(node))
    return found


# Validation -------------------------------------------------------------------

def validate(system, adventure=None):
    """Problems a human should fix, as readable strings. Empty means the pack is sound."""
    problems = _validate_system(system)
    if adventure is not None:
        problems += _validate_adventure(system, adventure)
    return problems


def _validate_system(system):
    problems = []
    gaps = missing(system)
    if gaps:
        problems.append("system: " + missing_text(system, gaps))
    attributes, tracks = system["attributes"], system["tracks"]
    if system.get("family") not in FAMILIES:
        problems.append(f"system: family must be one of {', '.join(FAMILIES)}")
    for condition, attribute in system["conditions"].items():
        if attribute not in attributes:
            problems.append(f"system: condition {condition} points at unknown attribute {attribute}")
    for key, skill in system["skills"].items():
        if skill["attribute"] not in attributes:
            problems.append(f"system: skill {key} points at unknown attribute {skill['attribute']}")
    cost = system["push"].get("cost")
    if isinstance(cost, dict):
        problems += [f"system: push cost uses unknown track {t}" for t in cost if t not in tracks]
    elif cost not in (None, "condition"):
        problems.append('system: push cost must be "condition" or a table of tracks')
    for name, spec in system.get("extra_dice", {}).items():
        if isinstance(spec.get("count"), str) and spec["count"] not in tracks:
            problems.append(f"system: extra dice {name} count uses unknown track {spec['count']}")
    for name, spec in system.get("triggers", {}).items():
        if spec.get("table") and spec["table"] not in system["tables"]:
            problems.append(f"system: trigger {name} rolls unknown table {spec['table']}")
    for table_id, table in system["tables"].items():
        problems += _validate_table(f"system table {table_id}", table)
        problems += _validate_then(f"system table {table_id}", table, system["tables"])
    for rest_id, rest in system["rest"].items():
        where = f"system: rest {rest_id}"
        problems += [f"{where} recovers unknown track {t}" for t in rest.get("recover", {}) if t not in tracks]
        problems += [f"{where} takes unknown time unit {u}" for u in rest.get("time", {}) if u not in system["time"]]
        if rest.get("limit") and rest["limit"] not in system["time"]:
            problems.append(f"{where}: limit must be a time unit ({', '.join(system['time']) or 'none'})")
    problems += _validate_combat(system)
    for source, spec in system.get("light", {}).items():
        where = f"system: light {source}"
        problems += [f"{where} lasts an unknown time unit {u}" for u in spec.get("lasts", {"shift": 1}) if u not in system["time"]]
    creation = system["creation"]
    tables = creation.get("choose", {})
    problems += [f"creation: track {t} isn't in the system" for t in creation.get("tracks", {}) if t not in tracks]
    problems += [f"creation: track {t} reads unknown attribute {a}" for t, a in creation.get("tracks", {}).items() if a not in attributes]
    for table_id, table in tables.items():
        if table.get("roll"):
            ranges = [{"range": option.get("range")} for option in table.get("options", {}).values()]
            problems += _validate_table(f"creation table {table_id}", {"formula": table["roll"], "results": ranges})
        for option_id, option in table.get("options", {}).items():
            where = f"creation: {table_id}.{option_id}"
            named = option.get("skills", []) + option.get("always", [])
            problems += [f"{where} names unknown skill {s}" for s in named if slug(s) not in system["skills"]]
            problems += [f"{where} changes unknown attribute {a}" for a in option.get("attributes", {}) if a not in attributes]
            if option.get("key") and option["key"] not in attributes:
                problems.append(f"{where}: key {option['key']} isn't an attribute")
            if option.get("then") and option["then"] not in tables:
                problems.append(f"{where}: then names unknown table {option['then']}")
    problems += _validate_gear(system)
    for monster_id, monster in system.get("bestiary", {}).items():
        problems += _validate_creature(f"bestiary {monster_id}", monster, system["tables"], system)
    return problems


def _validate_combat(system):
    """[dying], [advancement], [combat], [weapons] and [armor]: all optional."""
    problems = []
    attributes, skills = system["attributes"], system["skills"]
    dying = system.get("dying")
    if dying:
        if dying.get("track") not in system["tracks"]:
            problems.append(f"system: dying track {dying.get('track')} isn't a track")
        if slug(dying.get("roll", "")) not in attributes and slug(dying.get("roll", "")) not in skills:
            problems.append(f"system: dying roll {dying.get('roll')} isn't an attribute or skill")
        problems += _validate_dice("system: dying recover", str(dying.get("recover", "1")))
    advancement = system.get("advancement")
    if advancement:
        problems += _validate_dice("system: advancement roll", advancement.get("roll", "1d20"))
        problems += [f"system: advancement mark_on {m} must be dragon or demon" for m in advancement.get("mark_on", []) if m not in ("dragon", "demon")]
    fight = system.get("combat", {})
    for attribute, table in fight.get("damage_bonus", {}).items():
        if attribute not in attributes:
            problems.append(f"system: damage bonus for unknown attribute {attribute}")
        problems += [p for _, bonus in table if bonus for p in _validate_dice(f"system: damage bonus {attribute}", bonus)]
    if fight and fight.get("track", "hp") not in system["tracks"]:
        problems.append(f"system: combat track {fight.get('track', 'hp')} isn't a track")
    if fight and slug(fight.get("evade", "evade")) not in skills:
        problems.append(f"system: combat evade skill {fight.get('evade', 'evade')} isn't a skill")
    weapons = dict(system.get("weapons", {}))
    if fight.get("unarmed"):
        weapons["unarmed"] = fight["unarmed"]
    for key, weapon in weapons.items():
        if slug(weapon.get("skill", "")) not in skills:
            problems.append(f"system: weapon {key} uses unknown skill {weapon.get('skill')}")
        if weapon.get("bonus") and weapon["bonus"] not in attributes:
            problems.append(f"system: weapon {key} bonus must be an attribute")
        if weapon.get("damage"):
            problems += _validate_dice(f"system: weapon {key} damage", weapon["damage"])
    problems += [f"system: armor {key} must be a whole number" for key, rating in system.get("armor", {}).items() if not isinstance(rating, int)]
    return problems


def _validate_dice(label, expr):
    try:
        dice.parse(expr)
        return []
    except SoloError as error:
        return [f"{label}: {error}"]


def _validate_adventure(system, adventure):
    problems = list(adventure.get("conflicts", []))
    problems += [f"npc {nid}: monster {npc['monster']} isn't in the system's bestiary ({', '.join(system.get('bestiary', {})) or 'it has none'})"
                 for nid, npc in adventure["npcs"].items() if npc.get("monster") and npc["monster"] not in system.get("bestiary", {})]
    adventure = with_system(system, adventure)
    scenes, npcs, factions, clocks = (adventure[k] for k in ("scenes", "npcs", "factions", "clocks"))
    tables = {**system["tables"], **adventure["tables"]}
    known = {"npc": npcs, "faction": factions, "clock": clocks, "visited": scenes}
    if adventure["start"] not in scenes:
        problems.append(f"start scene {adventure['start']} doesn't exist")
    for sid, scene in scenes.items():
        where = f"scene {sid}"
        try:
            text = scene_text(adventure, sid)
        except SoloError as error:
            problems.append(str(error))
            continue
        if not text.strip():
            problems.append(f"{where}: no text (scenes/{sid}.md or text = ...)")
        for target, spec in exits(adventure, sid).items():
            if target not in scenes:
                problems.append(f"{where}: exit to unknown scene {target}")
            if spec["when"]:
                problems += _validate_condition(f"{where} exit {target}", spec["when"], known)
            problems += _validate_time(f"{where} exit {target}", spec["time"], system)
        problems += [f"{where}: unknown npc {n}" for n in scene.get("npcs", []) if n not in npcs]
        problems += [f"{where}: unknown table {t}" for t in scene.get("tables", []) if t not in tables]
        for branch in scene.get("branches", []):
            problems += _validate_condition(f"{where} branch", branch.get("when", ""), known)
            if not branch.get("text"):
                problems.append(f"{where}: branch without text")
        for voice in scene.get("voices", []):
            skill = slug(voice.get("skill", ""))
            if skill not in system["skills"] and skill not in system["attributes"]:
                problems.append(f"{where}: voice uses unknown skill {voice.get('skill')}")
            if not voice.get("text"):
                problems.append(f"{where}: voice without text")
            if voice.get("when"):
                problems += _validate_condition(f"{where} voice", voice["when"], known)
    for nid, npc in npcs.items():
        where = f"npc {nid}"
        if npc.get("faction") and npc["faction"] not in factions:
            problems.append(f"{where}: unknown faction {npc['faction']}")
        if not isinstance(npc.get("many", False), bool):
            problems.append(f"{where}: many is true (a kind of foe met again and again) or false")
        if npc.get("attitude", "neutral") not in ATTITUDES and npc.get("attitude") not in range(-2, 3):
            problems.append(f"{where}: attitude must be one of {', '.join(ATTITUDES)}")
        for secret in npc.get("secrets", []):
            if secret.get("reveal"):
                problems += _validate_condition(f"{where} secret", secret["reveal"], known)
        problems += _validate_creature(where, npc, tables, system)
    if not (isinstance(adventure["chaos"], int) and 1 <= adventure["chaos"] <= 9):
        problems.append("chaos must be a whole number from 1 to 9")
    for fid, faction in factions.items():
        if faction.get("standing", 0) not in range(-2, 3):
            problems.append(f"faction {fid}: standing must be between -2 and 2")
    for cid, clock in clocks.items():
        where = f"clock {cid}"
        if not (isinstance(clock.get("segments"), int) and clock["segments"] >= 1):
            problems.append(f"{where}: segments must be a whole number of 1 or more")
        for trigger in [*clock.get("advance", []), *clock.get("stop", [])]:
            problem = _check_trigger(trigger, system, adventure)
            if problem:
                problems.append(f"{where}: {problem}")
        if clock.get("on_tick") and clock["on_tick"] not in tables:
            problems.append(f"{where}: on_tick rolls unknown table {clock['on_tick']}")
        if clock.get("at_full") and clock["at_full"] not in scenes:
            problems.append(f"{where}: at_full names unknown scene {clock['at_full']}")
        if clock.get("while"):
            problems += _validate_condition(f"{where} while", clock["while"], known)
        for stage in clock.get("stages", []):
            at = stage.get("at")
            if not (isinstance(at, int) and 1 <= at <= clock.get("segments", 1)):
                problems.append(f"{where}: a stage needs at = a segment from 1 to {clock.get('segments')}")
            if not (stage.get("text") or stage.get("note") or stage.get("facts") or stage.get("clock")):
                problems.append(f"{where}: stage {at} does nothing (give it text, note, facts or clock)")
            problems += [f"{where}: stage {at} sets bad fact key {k}" for k in flat_facts(stage.get("facts")) if not FACT_KEY.match(k)]
            problems += [f"{where}: stage {at} moves unknown clock {c}" for c in stage.get("clock", {}) if c not in clocks]
    problems += _validate_time("move_time", adventure["move_time"], system)
    if adventure.get("weapons"):
        problems += [p.replace("system: weapon", "adventure weapon") for p in _validate_combat({**system, "weapons": adventure["weapons"], "combat": {}, "armor": {}})
                     if "weapon" in p]
    for tid, table in adventure["tables"].items():
        problems += _validate_table(f"table {tid}", table)
        problems += _validate_then(f"table {tid}", table, tables)
    return problems


def _validate_creature(where, npc, tables, system):
    """What an NPC or a bestiary entry needs to fight through the engine."""
    problems = []
    if npc.get("attacks"):
        if npc["attacks"] not in tables:
            problems.append(f"{where}: attacks names unknown table {npc['attacks']}")
        else:
            for result in tables[npc["attacks"]].get("results", []):
                if result.get("damage"):
                    problems += _validate_dice(f"{where} attack damage", result["damage"])
    if npc.get("attack"):
        attack = npc["attack"]
        if not attack.get("damage"):
            problems.append(f"{where}: attack needs damage")
        else:
            problems += _validate_dice(f"{where} attack damage", attack["damage"])
        if not attack.get("value") and attack.get("skill") not in npc.get("skills", {}):
            problems.append(f"{where}: attack needs a value, or a skill the npc has under skills")
    rules = system.get("npcs", {})
    if npc.get("template") and npc["template"] not in rules.get("templates", {}):
        problems.append(f"{where}: template must be one of {', '.join(rules.get('templates', {})) or 'none (the system has no [npcs.templates])'}")
    for attacker in [npc["attacker"]] if isinstance(npc.get("attacker"), str) else npc.get("attacker", []):
        if attacker not in rules.get("attackers", []):
            problems.append(f"{where}: attacker must be one of {', '.join(rules.get('attackers', [])) or 'none'}")
    if (npc.get("attack") or npc.get("attacks")) and "hp" not in npc.get("stats", {}) and not npc.get("template"):
        problems.append(f"{where}: a foe needs stats.hp")
    return problems


def _validate_gear(system):
    """gear.toml: every item has a name and a price; with coins declared, a price the
    engine can read (12 silver, 1 gold 5 silver)."""
    problems, money = [], system.get("money", {})
    coins = money.get("coins", {})
    if money and not (coins and all(isinstance(v, int) and v > 0 for v in coins.values())):
        problems.append("gear: [money] coins = { gold = 100, silver = 10, copper = 1 } (each worth so many of the smallest)")
    for alias, coin in money.get("aliases", {}).items():
        if coin not in coins:
            problems.append(f"gear: money alias {alias} names unknown coin {coin}")
    for item_id, item in system.get("gear", {}).items():
        where = f"gear {item_id}"
        if not isinstance(item, dict):
            problems.append(f"{where}: expected a table with name and price")
            continue
        if not item.get("name"):
            problems.append(f"{where}: needs a name")
        if "price" not in item:
            problems.append(f"{where}: needs a price (as the book writes it; \"varies\" if it gives none)")
        elif coins and price(item["price"], money) is None and not str(item["price"]).strip().isalpha():
            problems.append(f"{where}: can't read price {item['price']!r} (coins: {', '.join(coins)})")
    return problems


def _validate_time(label, spent, system):
    if not isinstance(spent, dict):
        return [f"{label}: time is a table of units, like {{ stretch = 1 }}"]
    return [f"{label}: unknown time unit {u} (system has {', '.join(system['time']) or 'none'})" for u in spent if u not in system["time"]]


def _validate_condition(label, text, known):
    try:
        tree = compile_condition(text)
    except SoloError as error:
        return [f"{label}: {error}"]
    problems = []
    for path in _paths(tree):
        if path[0] in known and len(path) > 1 and path[1] not in known[path[0]]:
            problems.append(f"{label}: unknown {path[0]} {path[1]}")
        elif path[0] == "npc" and len(path) > 2 and path[2] not in _NPC_FIELDS:
            problems.append(f"{label}: npc field must be one of {', '.join(_NPC_FIELDS)}")
    return problems


def _check_trigger(trigger, system, adventure):
    kind, _, rest = trigger.partition(":")
    parts = rest.split(":")
    if kind == "time" and rest not in system["time"]:
        return f"unknown time unit in {trigger} (system has {', '.join(system['time']) or 'none'})"
    elif kind == "fact" and not FACT_KEY.match(rest):
        return f"bad fact key in {trigger}"
    elif kind == "scene" and rest not in adventure["scenes"]:
        return f"unknown scene in {trigger}"
    elif kind == "npc" and (len(parts) != 2 or parts[0] not in adventure["npcs"] or parts[1] not in FATES):
        return f"{trigger} should be npc:<id>:<{'|'.join(FATES)}>"
    elif kind == "promise" and (len(parts) != 2 or parts[1] not in PROMISE_STATUSES):
        return f"{trigger} should be promise:<id>:<{'|'.join(PROMISE_STATUSES)}>"
    elif kind == "clock" and (len(parts) != 2 or parts[0] not in adventure["clocks"] or parts[1] != "full"):
        return f"{trigger} should be clock:<id>:full"
    elif kind not in ("time", "fact", "scene", "npc", "promise", "clock", "check"):
        return f"unknown trigger {trigger}"
    else:
        return None


def _validate_then(label, table, tables):
    """A result's `then` names tables that exist."""
    problems = []
    for result in table.get("results", []):
        then = result.get("then", [])
        for next_id in [then] if isinstance(then, str) else then:
            if next_id not in tables:
                problems.append(f"{label}: then names unknown table {next_id}")
    return problems


def _validate_table(label, table):
    formula = table.get("formula", "")
    try:
        possible = dice.outcomes(re.sub(r"@\w+", "0", formula))
    except SoloError as error:
        return [f"{label}: {error}"]
    problems = []
    covered = set()
    for result in table.get("results", []):
        bounds = result.get("range")
        if isinstance(bounds, list) and len(bounds) == 2 and all(isinstance(n, int) for n in bounds):
            values = set(range(bounds[0], bounds[1] + 1))
            if covered & values:
                problems.append(f"{label}: ranges overlap at {min(covered & values)}")
            covered |= values
        else:
            problems.append(f"{label}: every result needs range = [low, high]")
    for result in table.get("results", []):
        if result.get("roll"):
            problems += _validate_dice(f"{label}: result roll", str(result["roll"]))
        if "choices" in result and not (isinstance(result["choices"], list) and result["choices"]):
            problems.append(f"{label}: choices must be a list of options")
    missing = sorted(possible - covered)
    if missing and "@" not in formula:
        problems.append(f"{label}: no result for {', '.join(map(str, missing[:6]))}")
    return problems


def _optional(path):
    return load_data(path) if Path(path).exists() else {}


def _load_folder(folder):
    merged = {}
    for suffix in (".json", ".toml"):
        for path in sorted(Path(folder).glob(f"*{suffix}")):
            merged.setdefault(path.stem, {}).update(load_data(path))
    return merged


# Review ---------------------------------------------------------------------------
#
# An imported adventure is compiled by an agent from a book, so the author needs to see
# its shape in one place and check it against the text: every way between scenes and
# what opens it, every clock and its stages, and every fact the text depends on, which
# the GM will have to commit in play. Each element can carry `source` (a page).

_FACT_READ = re.compile(r"\bfact\.([a-z0-9_]+(?:\.[a-z0-9_]+)*)")


def lint(adventure):
    """Things that load and validate but are probably mistakes, as readable strings."""
    scenes, clocks = adventure["scenes"], adventure["clocks"]
    reached, queue = {adventure["start"]}, [adventure["start"]]
    targets = {c["at_full"] for c in clocks.values() if c.get("at_full")}
    while queue:
        for target in exits(adventure, queue.pop()):
            if target in scenes and target not in reached:
                reached.add(target)
                queue.append(target)
    warnings = [f"scene {sid} can't be reached from {adventure['start']} by any exit (only by solo move --force)"
                for sid in scenes if sid not in reached and sid not in targets]
    warnings += [f"scene {sid} has no way out; if the story ends there, mark it ending = true"
                 for sid, scene in scenes.items()
                 if not scene.get("exits") and not scene.get("ending") and not scene.get("climax") and sid not in targets]
    warnings += [f"scene {sid}: each_round is the text the GM reads every round there" for sid, scene in scenes.items()
                 if "each_round" in scene and not isinstance(scene["each_round"], str)]
    placed = {n for scene in scenes.values() for n in scene.get("npcs", [])} | {n.get("location") for n in adventure["npcs"].values()}
    # Foes are left out: one that enters mid-fight (a tentacle rising, a spider let out of a jar)
    # belongs to no scene until then.
    warnings += [f"npc {nid} is in no scene's npcs (the GM only meets them if a commit brings them in)"
                 for nid, npc in adventure["npcs"].items() if nid not in placed and "hp" not in npc.get("stats", {}) and not npc.get("template")]
    return warnings


def scene_facts(adventure, scene_id):
    """The facts one scene's own conditions read (its exits, branches and voices): what the
    GM needs in front of it there, however long ago the story settled them."""
    scene = adventure["scenes"].get(scene_id, {})
    texts = [spec["when"] for spec in exits(adventure, scene_id).values()]
    texts += [b.get("when") for b in scene.get("branches", [])] + [v.get("when") for v in scene.get("voices", [])]
    return {key for text in texts for key in _FACT_READ.findall(text or "")}


def facts_read(adventure):
    """{fact key: [where it is read]}: the facts the adventure's conditions depend on."""
    reads = {}

    def note(text, where):
        for key in _FACT_READ.findall(text or ""):
            reads.setdefault(key, []).append(where)
    for sid, scene in adventure["scenes"].items():
        for target, spec in exits(adventure, sid).items():
            note(spec["when"], f"exit {sid} -> {target}")
        for branch in scene.get("branches", []):
            note(branch.get("when"), f"branch in {sid}")
        for voice in scene.get("voices", []):
            note(voice.get("when"), f"voice in {sid}")
    for cid, clock in adventure["clocks"].items():
        note(clock.get("while"), f"clock {cid} while")
        for trigger in [*clock.get("advance", []), *clock.get("stop", [])]:
            if trigger.startswith("fact:"):
                reads.setdefault(trigger[5:], []).append(f"clock {cid} trigger")
    for nid, npc in adventure["npcs"].items():
        for secret in npc.get("secrets", []):
            note(secret.get("reveal"), f"secret {nid}.{secret.get('id')}")
    return reads


def spent_text(spent):
    """{"stretch": 1, "round": 3} -> "1 stretch, 3 rounds"."""
    return ", ".join(f"{n} {unit}{'s' if n != 1 else ''}" for unit, n in spent.items())


def outline(adventure):
    """The whole pack at a glance, for the author reviewing an import (GM-only: spoilers)."""
    scenes, clocks = adventure["scenes"], adventure["clocks"]
    src = lambda spec: f" [{spec['source']}]" if spec.get("source") else ""  # noqa: E731
    lines = [f"# {adventure['title']}: outline (spoilers)", "",
             f"{len(scenes)} scenes, {len(adventure['npcs'])} npcs, {len(clocks)} clocks, {len(adventure['tables'])} tables. "
             f"Starts at {adventure['start']}; chaos {adventure['chaos']}"
             + (f"; every move takes {spent_text(adventure['move_time'])}" if adventure["move_time"] else "") + "."
             + (f" Chapters: {', '.join(adventure['chapters'])}." if adventure.get("chapters") else ""), "", "## Scenes", ""]
    for sid, scene in scenes.items():
        flags = [f for f in ("climax", "ending", "dark", "safe") if scene.get(f)]
        lines.append(f"### {sid}: {scene.get('title', sid)}" + (f" ({', '.join(flags)})" if flags else "") + src(scene))
        for target, spec in exits(adventure, sid).items():
            extra = [f"when {spec['when']}"] if spec["when"] else []
            extra += [f"takes {spent_text(spec['time'])}"] if spec["time"] else []
            lines.append(f"- to {target}: {spec['label']}" + (f" ({'; '.join(extra)})" if extra else ""))
        if scene.get("npcs"):
            lines.append(f"- people: {', '.join(scene['npcs'])}")
        for voice in scene.get("voices", []):
            lines.append(f"- voice {voice.get('skill')}" + (f" when {voice['when']}" if voice.get("when") else "") + f": {voice.get('text', '')[:70]}")
        for branch in scene.get("branches", []):
            lines.append(f"- if {branch.get('when')}: {branch.get('text', '')[:70]}")
        lines.append("")
    if clocks:
        lines += ["## Clocks", ""]
        for cid, clock in clocks.items():
            how = ", ".join(clock.get("advance", [])) or "moved by commits only"
            lines.append(f"- {cid} ({clock.get('label', cid)}): {clock.get('segments')} segments, advances on {how}"
                         + (f", while {clock['while']}" if clock.get("while") else "")
                         + (", hidden" if clock.get("hidden") else "") + (", omen" if clock.get("omen") else "")
                         + (f"; full: {clock['at_full']}" if clock.get("at_full") else "") + src(clock))
            for stage in clock.get("stages", []):
                changes = [f"{k} = {json.dumps(v)}" for k, v in flat_facts(stage.get("facts")).items()]
                changes += [f"clock {k} {v}" for k, v in stage.get("clock", {}).items()]
                lines.append(f"  - at {stage.get('at')}: {stage.get('text') or stage.get('note') or ''}" + (f" ({', '.join(changes)})" if changes else ""))
        lines.append("")
    lines += ["## People", ""]
    for nid, npc in adventure["npcs"].items():
        stats = npc.get("stats", {})
        fights = ""
        if "hp" in stats:
            fights = f"; HP {stats['hp']}, armor {stats.get('armor', 0)}" + (f", ferocity {stats['ferocity']}" if stats.get("ferocity") else "")
            fights += f", attacks on {npc['attacks']}" if npc.get("attacks") else f", attacks with {npc['attack'].get('label', 'a weapon')}" if npc.get("attack") else ", NO ATTACK"
        lines.append(f"- {nid}: {npc.get('name', nid)}, {npc.get('attitude', 'neutral')}{fights}" + src(npc))
    set_by_stages = {k for c in clocks.values() for s in c.get("stages", []) for k in flat_facts(s.get("facts"))}
    reads = facts_read(adventure)
    if reads:
        lines += ["", "## Facts the story reads", "The GM commits these as play makes them true (unless a clock's stage sets them). Check each against the text.", ""]
        lines += [f"- {key}: read by {', '.join(where)}" + (" (set by a clock stage)" if key in set_by_stages else "") for key, where in sorted(reads.items())]
    warnings = lint(adventure)
    if warnings:
        lines += ["", "## Worth a look", "", *[f"- {w}" for w in warnings]]
    return "\n".join(lines) + "\n"
