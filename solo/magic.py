"""Spells: what a spell costs, how hard it hits at a power level, and how many a hero may hold ready.

The spells are data (`spells/<id>.toml` in a system pack) and so are the rules that apply to all of
them (`[magic]` in system.toml: what a power level costs, the dice a body can give, the table a Demon
rolls). campaign.py casts: it pays, rolls the school, and applies what comes of it.
"""

import re

from . import SoloError, packs
from .packs import slug


def find(system, name):
    """(id, spell) for a spell by its id or its name."""
    key = slug(name)
    found = next(((sid, spell) for sid, spell in system.get("spells", {}).items() if key in (sid, slug(spell.get("name", sid)))), None)
    if found is None:
        raise SoloError(f"no spell called {name!r}; spells: {', '.join(sorted(system.get('spells', {}))) or 'none'}")
    return found


def cost(system, spell, power):
    """WP to cast: a trick one (it always succeeds); a spell that has power levels so much for each; one that
    doesn't always the price of one level."""
    magic = system["magic"]
    if spell.get("trick"):
        return int(magic.get("trick_cost", 1))
    return int(magic.get("cost", 2)) * (power if spell.get("power", True) else 1)


def leveled(expr, more, power):
    """A spell's dice at a power level: each level past the first adds a die of each kind there
    ({dice = 1}), or other dice ({add = "1d6"})."""
    extra = power - 1
    if not more or extra <= 0:
        return expr
    elif "dice" in more:
        return re.sub(r"(\d*)d(\d+)", lambda m: f"{int(m.group(1) or 1) + int(more['dice']) * extra}d{m.group(2)}", expr)
    else:
        return "+".join([expr] + [more["add"]] * extra)


def limit(system, pc):
    """How many spells the hero can hold prepared: the base chance of the attribute the rules name."""
    attribute = system["magic"].get("prepared", "int")
    return packs.base_chance(system, pc["attributes"].get(attribute, 0))


def skill_of(system, school):
    """The skill a school is rolled as: its own, or the one it uses (Harmonism is PERFORMANCE)."""
    return system["skills"].get(school, {}).get("uses") or school


def school(system, pc, spell, asked=None):
    """The skill a spell is cast with: its school's. A general spell takes any school the hero is trained in,
    the best of them unless the player says."""
    schools = [key for key, skill in system["skills"].items() if not skill["untrained"]]
    if asked:
        if slug(asked) not in schools:
            raise SoloError(f"a school of magic is one of: {', '.join(schools)}")
        return slug(asked)
    elif spell.get("school") in schools:
        return spell["school"]
    trained = [(pc["skills"].get(skill_of(system, key), {}).get("value", 0), key) for key in schools if pc["skills"].get(skill_of(system, key), {}).get("trained")]
    if not trained:
        raise SoloError(f"{pc['name']} knows no school of magic")
    return max(trained)[1]


def sheet(system, pc):
    """What the Table shows of a hero's magic, or None for a hero with no spells or a game with no [magic]: the spells they
    know (spells before tricks, by rank), each with what the buttons need (its cost at power 1, whether it has power levels, is
    prepared, hits a foe, heals), how many may be held ready, the power levels, and the dice the body can give when the WP are nearly spent."""
    rules = system.get("magic")
    if rules and pc.get("spells"):
        known = {slug(key): spell for key, spell in system.get("spells", {}).items()}
        known.update({slug(spell.get("name", key)): spell for key, spell in system.get("spells", {}).items()})
        held = {slug(name) for name in pc.get("prepared", [])}
        spells = []
        for name in pc["spells"]:
            spell = known.get(slug(name), {})
            spells.append({"name": name, "rank": spell.get("rank", 0), "school": spell.get("school"), "trick": bool(spell.get("trick")),
                           "prepared": slug(name) in held, "power": bool(spell.get("power", True)) and not spell.get("trick"),
                           "cost": cost(system, spell, 1) if spell else None, "damage": bool(spell.get("damage")), "heal": bool(spell.get("heal")),
                           "reaction": spell.get("casting_time") == "reaction"})
        track = rules.get("track", "wp")
        nearly_spent = pc["tracks"][track]["value"] <= int(rules.get("body_below", 1))
        return {"track": track, "max_power": int(rules.get("max_power", 3)), "limit": limit(system, pc), "body": rules.get("body", []) if nearly_spent else [],
                "ready": sum(spell["prepared"] for spell in spells), "spells": sorted(spells, key=lambda spell: (spell["trick"], spell["rank"], spell["name"]))}
    else:
        return None
