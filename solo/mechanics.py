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


def action_roll(stat, adds=0, momentum=0, rng=None):
    """Action roll (Ironsworn): an action die (d6) plus a stat and adds, at most 10, against
    two challenge dice (d10). The score has to beat a die, not tie it; beating both is a
    strong hit, one a weak hit, neither a miss. Negative momentum that matches the action
    die cancels it: the die counts for nothing, but the stat and adds still do.
    """
    action = dice.die(6, rng)
    challenge = [dice.die(10, rng), dice.die(10, rng)]
    dulled = momentum < 0 and action == -momentum
    return _read({
        "action": action, "stat": stat, "adds": adds, "momentum": momentum, "dulled": dulled,
        "score": min(10, (0 if dulled else action) + stat + adds), "challenge": challenge, "cancelled": [],
    })


def progress_roll(progress, rng=None):
    """Progress roll: the filled boxes of a progress track (at most 10) against the two
    challenge dice. No action die, and momentum plays no part."""
    return _read({"progress": progress, "score": progress, "challenge": [dice.die(10, rng), dice.die(10, rng)], "cancelled": []})


def burn(outcome, momentum):
    """Burn momentum after an action roll: every challenge die below it is cancelled, and a
    cancelled die counts as beaten. The roll as it would read, or None when burning would
    not improve it (there is nothing under the momentum that the score doesn't beat already)."""
    cancelled = [i for i, die in enumerate(outcome["challenge"]) if die < momentum]
    burned = _read({**outcome, "cancelled": cancelled, "burned": momentum})
    return burned if burned["beaten"] > outcome["beaten"] else None


def momentum_limits(spec, impacts):
    """Momentum's ceiling and its reset with `impacts` marked: each takes one off both, and
    the reset stops at 0. `spec` is the system's [momentum]: min, max and reset."""
    return {"max": spec["max"] - impacts, "reset": max(0, spec["reset"] - impacts)}


def _read(outcome):
    beaten = sum(i in outcome["cancelled"] or outcome["score"] > die for i, die in enumerate(outcome["challenge"]))
    return {**outcome, "beaten": beaten, "hit": ("miss", "weak_hit", "strong_hit")[beaten], "success": beaten > 0,
            "match": outcome["challenge"][0] == outcome["challenge"][1]}
