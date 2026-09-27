"""Resolvers, one per mechanics family.

A resolver turns numbers into an outcome. It knows nothing about files, packs or
events: campaign.py gathers the inputs and records what comes back.
"""

from . import dice


def d20_under(target, boons=0, banes=0, rng=None):
    """Roll-under d20 (Dragonbane). Boons and banes cancel one for one; each one left
    over adds a d20, keeping the lowest for boons and the highest for banes.
    A 1 is a Dragon (always a success), a 20 a Demon (always a failure).
    """
    net = boons - banes
    if net > 0:
        expr = f"{1 + net}d20kl"
    elif net < 0:
        expr = f"{1 - net}d20kh"
    else:
        expr = "d20"
    rolled = dice.roll(expr, rng)
    result = rolled["total"]
    dragon = result == 1
    demon = result == 20
    success = dragon or (not demon and result <= target)
    return {
        "expr": expr,
        "rolls": rolled["parts"][0]["rolls"],
        "result": result,
        "target": target,
        "success": success,
        "dragon": dragon,
        "demon": demon,
        "pushable": not success and not demon,
    }


def d6_pool(groups, success=6, rng=None):
    """Dice pool (Year Zero). `groups` is a list of {"name", "count", "sides", "on_one"}.
    Each die at or above a threshold scores; `success` is a threshold (6) or a list of
    [threshold, hits] pairs ([[10, 2], [6, 1]] for Blade Runner). A group with `on_one`
    names a trigger fired when any of its dice shows a 1 (Alien stress dice: "panic").
    """
    rolled = [
        {**group, "rolls": [dice.die(group["sides"], rng) for _ in range(max(0, group["count"]))]}
        for group in groups
    ]
    return _pool_outcome(rolled, success)


def d6_pool_push(previous, add_dice, success=6, rng=None):
    """Push a pool: reroll every die that didn't score and add dice to named groups
    (Alien adds a stress die). Dice that scored stay as they are."""
    rules = _success_rules(success)
    groups = []
    for group in previous["groups"]:
        rolls = [r if _hits(r, rules) else dice.die(group["sides"], rng) for r in group["rolls"]]
        extra = add_dice.get(group["name"], 0)
        rolls += [dice.die(group["sides"], rng) for _ in range(extra)]
        groups.append({**group, "rolls": rolls, "count": len(rolls)})
    return _pool_outcome(groups, success)


def _pool_outcome(groups, success):
    rules = _success_rules(success)
    hits = sum(_hits(r, rules) for group in groups for r in group["rolls"])
    triggers = sorted({g["on_one"] for g in groups if g.get("on_one") and 1 in g["rolls"]})
    return {"groups": groups, "successes": hits, "success": hits > 0, "triggers": triggers, "pushable": True}


def _success_rules(success):
    if isinstance(success, int):
        return [(success, 1)]
    else:
        return sorted(((int(t), int(h)) for t, h in success), reverse=True)


def _hits(value, rules):
    return next((hits for threshold, hits in rules if value >= threshold), 0)
