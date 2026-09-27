"""Combat data: what the hero carries, damage bonuses, armor and initiative.

The rules live in the system pack ([combat], [weapons], [armor]); campaign.py runs the
fight and records it. Items on a sheet are plain text ("Broadsword", "Leather armor"),
matched to the pack by slug.
"""

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
        }
    unarmed = system.get("combat", {}).get("unarmed")
    if unarmed:
        known["unarmed"] = {"id": "unarmed", "label": unarmed.get("label", "Unarmed"), "skill": unarmed["skill"],
                            "damage": unarmed.get("damage", "1"), "bonus": unarmed.get("bonus"), "parry": False, "attack": True}
    return known


def kit(system, pc):
    """The weapons the hero carries (unarmed always) and the armor they wear."""
    carried = {slug(item) for item in pc.get("items", [])}
    known = weapons(system)
    armor = system.get("armor", {})
    return {
        "weapons": [w for wid, w in known.items() if wid in carried or wid == "unarmed"],
        "armor": sum(int(rating) for key, rating in armor.items() if slug(key) in carried),
    }


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


def deal(cards, count, rng=None):
    """Initiative cards 1..cards dealt to `count` fighters, no card twice (Dragonbane)."""
    if count > cards:
        raise SoloError(f"only {cards} initiative cards for {count} fighters")
    deck = list(range(1, cards + 1))
    hand = []
    for _ in range(count):
        hand.append(deck.pop(dice.pick(len(deck), rng) - 1) if len(deck) > 1 else deck.pop())
    return hand
