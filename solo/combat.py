"""Combat data: what the hero carries, damage bonuses, armor and initiative.

The rules live in the system pack ([combat], [weapons], [armor]); campaign.py runs the
fight and records it. Items on a sheet are plain text ("Broadsword", "Leather armor"),
matched to the pack by slug.
"""

import re

from . import SoloError, dice
from .packs import slug


def weapons(system):
    """Every weapon the system knows, unarmed included, keyed by id."""
    known = {}
    for key, spec in system.get("weapons", {}).items():
        known[slug(key)] = {
            "id": slug(key),
            "label": spec.get("label") or key.replace("_", " ").capitalize(),
            "skill": spec["skill"],
            "damage": spec.get("damage", ""),
            "bonus": spec.get("bonus"),
            "parry": spec.get("parry", True),
            "attack": spec.get("attack", True),
            # What the weapon tables give, for the pack that has them: the hands it takes, the STR it
            # asks for, how far it reaches (meters, or "str" for a thrown weapon), what it can take when
            # it parries, and what it is (piercing, slashing, thrown...).
            "grip": spec.get("grip"),
            "str": spec.get("str"),
            "range": spec.get("range"),
            "durability": spec.get("durability"),
            "features": [slug(f) for f in spec.get("features", [])],
            "ranged": bool(spec.get("ranged")),
        }
    unarmed = system.get("combat", {}).get("unarmed")
    if unarmed:
        known["unarmed"] = {"id": "unarmed", "label": unarmed.get("label", "Unarmed"), "skill": unarmed["skill"],
                            "damage": unarmed.get("damage", "1"), "bonus": unarmed.get("bonus"), "parry": False, "attack": True,
                            "grip": None, "str": None, "range": None, "durability": None, "features": [], "ranged": False}
    return known


# The kinds of damage a blow does; a foe's resistance may name one, or `physical` for every weapon's.
DAMAGE = ("slashing", "piercing", "bludgeoning")


def damage_types(arm):
    """The kinds of damage a weapon does (a sword slashes or pierces, as the wielder says)."""
    return [feature for feature in arm["features"] if feature in DAMAGE]


def resisted(foe, kind, dealt):
    """(damage, how) once a foe's resistances have had their say about damage of this kind, after armor:
    none of it from what the foe is immune to, half (rounded up) of what it resists."""
    def covers(names):
        return kind in names or ("physical" in names and kind in DAMAGE)
    if covers(foe.get("immune_to", [])):
        return 0, "immune"
    elif dealt and covers(foe.get("resist", [])):
        return (dealt + 1) // 2, "half"
    else:
        return dealt, None


def kit(system, pc):
    """The weapons the hero carries (unarmed always), the armor they wear and what it adds up to."""
    carried = {slug(item) for item in pc.get("items", [])}
    known = weapons(system)
    armor = system.get("armor", {})
    worn = [key for key in armor if slug(key) in carried]
    return {
        "weapons": [{**w, "condition": pc.get("damaged", {}).get(wid)} for wid, w in known.items() if wid in carried or wid == "unarmed"],
        "armor": sum(int(armor[key]) for key in worn),
        "worn": [slug(key) for key in worn],
    }


def powers(system, pc):
    """The heroic abilities the hero has, as the Table's buttons need them: `cost` (what is paid, or "varies"), `afford` (whether the hero can
    pay now), and `use`, where it is asked for: with an attack, a parry or a dodge (`on`), a rest, a new round, a journey, or alone (`solo ability`);
    an ability that is only ever passive has none."""
    held = {slug(name) for name in pc.get("abilities", [])}
    have = lambda track: pc["tracks"].get(track, {}).get("value", 0)
    found = []
    for aid, spec in system.get("abilities", {}).items():
        if aid in held or slug(spec.get("name", aid)) in held:
            pay, on = spec.get("pay", {}), None
            if spec.get("extra_damage"):
                use = "attack"
            elif spec.get("boon") == "parry" or spec.get("reaction"):
                use, on = "defend", "parry" if spec.get("boon") == "parry" else spec["reaction"]
            elif spec.get("heal") and spec.get("rest"):
                use, on = "rest", spec["rest"]
            elif spec.get("initiative_pick") or spec.get("initiative_keep"):
                use = "round"
            elif spec.get("boon") == "journey":
                use = "journey"
            else:
                use = "alone" if pay else None
            afford = have(spec.get("track", "wp")) > 0 if pay == "varies" else all(have(track) >= int(n) for track, n in pay.items())
            found.append({"id": aid, "name": spec.get("name", aid), "cost": pay or None, "track": spec.get("track", "wp"), "afford": afford, "use": use, "on": on})
    return found


def armor_banes(system, pc, skill, ranged=False):
    """The pieces of armor and helmets the hero wears that put a bane on this skill (or, for a ranged
    attack, on all ranged attacks): their ids, one bane each."""
    gear = system.get("gear", {})
    return [item for item in kit(system, pc)["worn"]
            if skill in gear.get(item, {}).get("banes", []) or (ranged and "ranged_attack" in gear.get(item, {}).get("banes", []))]


def strength_needed(system, pc, arm):
    """(bane, cannot) for using a weapon: a bane on every attack and parry when the hero's STR is
    below what it asks for, and no use at all below half of it."""
    need = arm.get("str")
    have = pc["attributes"].get(system.get("encumbrance", {}).get("attribute", "str"), 0) if need else 0
    return bool(need and have < need), bool(need and have * 2 < need)


def reach(system, pc, arm, distance):
    """What a blow at `distance` meters asks of this weapon: ("bane", why) past its range up to twice
    it (and within 2 meters of a ranged weapon), ("out", why) beyond that or beyond a melee weapon's
    reach, else None. A thrown weapon reaches as many meters as the hero has STR, or twice that."""
    spec, name = arm.get("range"), arm["label"].lower()
    if spec in ("str", "str*2"):
        strength = pc["attributes"].get(system.get("encumbrance", {}).get("attribute", "str"), 0)
        spec = strength * (2 if spec == "str*2" else 1)
    melee = spec if isinstance(spec, int) and not arm["ranged"] else 2
    if arm["ranged"] or ("thrown" in arm["features"] and distance > melee):
        if arm["ranged"] and distance <= 2:
            return "bane", "within 2 meters of a ranged weapon"
        elif spec and distance > 2 * spec:
            return "out", f"{distance} meters is beyond twice the {name}'s range ({spec})"
        elif spec and distance > spec:
            return "bane", f"{distance} meters is beyond the {name}'s range ({spec})"
    elif distance > melee:
        return "out", f"{distance} meters is beyond the {name}'s reach ({melee})"
    return None


def weapon(system, pc, name=None, purpose="attack"):
    """A carried weapon by name, or the first one fit for the purpose (attack or parry)."""
    carried = kit(system, pc)["weapons"]
    fit = [w for w in carried if w[purpose]]
    if name:
        key = slug(name)
        # An id or a whole label; else the one weapon a word of it fits ("sword" with a
        # broadsword and a short sword carried is refused, not guessed).
        fits = [w for w in carried if w["id"] == key or slug(w["label"]) == key] or [w for w in carried if key and key in slug(w["label"])]
        if not fits:
            raise SoloError(f"you don't carry {name!r}; weapons: {', '.join(w['id'] for w in carried) or 'none'}")
        elif len(fits) > 1:
            raise SoloError(f"{name!r} could be {', '.join(w['id'] for w in fits)}: name the weapon")
        elif not fits[0][purpose]:
            raise SoloError(f"{fits[0]['label']} can't be used to {purpose}")
        return fits[0]
    elif fit:
        return next((w for w in fit if w["id"] != "unarmed"), fit[0])
    else:
        raise SoloError(f"nothing to {purpose} with")


def damage_bonus(system, pc, attribute):
    """The dice a strong or quick hero adds to a weapon's damage, from the pack's table."""
    table = system.get("combat", {}).get("damage_bonus", {}).get(attribute or "", [])
    value = pc["attributes"].get(attribute, 0)
    return next((bonus for top, bonus in table if value <= top), "") if table else ""


def damage_expression(base, bonus="", dragon=False, dragon_rule=None):
    """A weapon's damage as one dice expression. A Dragon with the "double" rule rolls the
    weapon's dice twice."""
    terms = [base] * (2 if dragon and dragon_rule == "double" else 1)
    if bonus:
        terms.append(bonus)
    return "+".join(t for t in terms if t)


def deal(cards, count, rng=None, reserved=()):
    """Initiative cards 1..cards dealt to `count` fighters, no card twice (Dragonbane). A card in
    `reserved` is already someone's and isn't in the deck."""
    if count > cards - len(reserved):
        raise SoloError(f"only {cards} initiative cards for {count + len(reserved)} fighters")
    deck = [n for n in range(1, cards + 1) if n not in reserved]
    hand = []
    for _ in range(count):
        hand.append(deck.pop(dice.pick(len(deck), rng) - 1) if len(deck) > 1 else deck.pop())
    return hand


def encumbrance(system, pc):
    """What the hero carries against what they can, for a system with an [encumbrance] section:
    {carried, capacity, over}. Capacity is STR over a divisor, rounded up, and a carrier (a backpack)
    adds to it. Not counted: armor worn, the weapons at hand (up to the section's number), and what
    weighs nothing (a tiny item); coins count one item to so many. An item the price lists don't know
    weighs 1, and "4 field rations" is four of the ration's weight."""
    spec = system.get("encumbrance")
    if not spec:
        return None
    capacity = -(-pc["attributes"].get(spec.get("attribute", "str"), 0) // int(spec.get("divisor", 2)))
    gear, money = system.get("gear", {}), system.get("money", {}).get("coins", {})
    armor, known, carriers = {slug(key) for key in system.get("armor", {})}, weapons(system), spec.get("carriers", {})
    carried, at_hand, coins, taken = 0.0, 0, 0, set()
    for item in pc["items"]:
        found = re.match(r"^(\d+)\s+(.+)$", item.strip())
        count, name = (int(found.group(1)), found.group(2)) if found else (1, item)
        key = slug(name)
        singular = next((k for k in (key, key[:-1], key[:-2]) if k in gear or k in known or k in armor or k in carriers or k.split("_")[0] in money), key)
        if singular.split("_")[0] in money:
            coins += count
        elif singular in armor:
            continue
        elif singular in known:
            carried += max(0, count - max(0, int(spec.get("at_hand", 3)) - at_hand))
            at_hand += count
        elif singular in carriers:
            capacity += int(carriers[singular]) * (singular not in taken)
            taken.add(singular)
        else:
            carried += count * _weight(gear, singular)
    carried += coins // int(spec.get("coins", 100)) if spec.get("coins") else 0
    return {"carried": round(carried, 2), "capacity": capacity, "over": carried > capacity}


def _weight(gear, key):
    """A thing's weight in the price lists: its own entry, or the first whose id starts with it
    (a "quiver" is the quiver of arrows); an item they don't list weighs 1."""
    entry = gear.get(key) or next((gear[k] for k in gear if k.startswith(key + "_")), None)
    return float(entry["weight"]) if entry and "weight" in entry else 1.0
