"""Dice expressions.

Terms joined by + or -:
  NdM        N dice with M sides, N defaults to 1        3d6, d20
  d66        two d6 read as tens and units (11-66)     d66
  NdMkh[K]   keep the K highest dice, K defaults to 1   2d20kh
  NdMkl[K]   keep the K lowest dice                     3d20kl
  NdMcs>=T   count the dice showing T or more           5d6cs>=6
  NdMxK      the dice's total times K (also * or ×)      2d6x10
  K          a constant                                 1d6+2
"""

import os
import random
import re

from . import SoloError

_TERM = re.compile(r"([+-]?)(?:(\d*)d(\d+)(?:(kh|kl)(\d*))?(?:cs>=(\d+))?(?:[x*×](\d+))?|(\d+))")
# Expressions come from packs other people write, so they are bounded: checking a table
# enumerates every total, and a d100000000 would never finish.
_MAX_DICE = 100
_MAX_SIDES = 1000
_MAX_TERMS = 20
_MAX_OUTCOMES = 1_000_000
_system_rng = random.SystemRandom()


def parse(expr):
    """Split an expression into terms. Raises SoloError on anything it can't read."""
    text = expr.replace(" ", "").lower()
    terms = []
    pos = 0
    while pos < len(text):
        match = _TERM.match(text, pos)
        if match is None or match.end() == pos or (pos > 0 and not match.group(1)):
            raise SoloError(f"can't read dice expression {expr!r} at {text[pos:]!r}")
        sign, count, sides, keep, keep_n, success_at, times, constant = match.groups()
        if any(len(number or "") > 6 for number in (count, sides, keep_n, success_at, times, constant)):
            raise SoloError(f"dice term {match.group(0).lstrip('+-')!r} is out of range")
        elif constant is not None:
            term = {"sign": sign or "+", "text": constant, "constant": int(constant)}
        else:
            term = {
                "sign": sign or "+",
                "text": match.group(0).lstrip("+-"),
                "count": int(count or 1),
                "sides": int(sides),
                "keep": keep,
                "keep_n": int(keep_n or 1),
                "success_at": int(success_at) if success_at else None,
                "times": int(times) if times else 1,
            }
            if term["count"] > _MAX_DICE or not 2 <= term["sides"] <= _MAX_SIDES:
                raise SoloError(f"dice term {term['text']!r} is out of range")
        terms.append(term)
        if len(terms) > _MAX_TERMS:
            raise SoloError(f"dice expression {expr!r} has more than {_MAX_TERMS} terms")
        pos = match.end()
    if not terms:
        raise SoloError("empty dice expression")
    return terms


def fixed_seed():
    """SOLO_SEED, when set, fixes the dice so a roll repeats (tests, demos). Every event
    written under it records the seed (Campaign.append): a roll whose seed was tried
    somewhere else first can't pass for an honest one."""
    seed = os.environ.get("SOLO_SEED")
    if not seed:
        return None
    try:
        return int(seed)
    except ValueError:
        raise SoloError(f"SOLO_SEED must be a whole number, not {seed!r}") from None


def die(sides, rng=None):
    """One die. A d66 is two d6 read as tens and units."""
    rng = rng or _system_rng
    if sides == 66:
        return rng.randint(1, 6) * 10 + rng.randint(1, 6)
    else:
        return rng.randint(1, sides)


def pick(count, rng=None):
    """A number from 1 to count, for drawing from a list (initiative cards, oracle words)."""
    return (rng or _system_rng).randint(1, count)


def roll(expr, rng=None):
    """Roll an expression and return every die, what was kept, and the total."""
    total = 0
    parts = []
    for term in parse(expr):
        if "constant" in term:
            value = term["constant"]
            parts.append({"term": term["text"], "value": value})
        else:
            rolls = [die(term["sides"], rng) for _ in range(term["count"])]
            kept = _keep(rolls, term["keep"], term["keep_n"])
            if term["success_at"] is None:
                value = sum(kept) * term["times"]
            else:
                value = sum(1 for r in kept if r >= term["success_at"])
            parts.append({"term": term["text"], "rolls": rolls, "kept": kept, "value": value})
        total += -value if term["sign"] == "-" else value
    return {"expr": expr, "total": total, "parts": parts}


def outcomes(expr):
    """Every total the expression can produce, used to check that a table covers them all."""
    totals = {0}
    for term in parse(expr):
        values = _term_values(term)
        if term["sign"] == "-":
            values = {-v for v in values}
        if len(totals) * len(values) > _MAX_OUTCOMES:
            raise SoloError(f"dice expression {expr!r} has too many outcomes to check")
        totals = {t + v for t in totals for v in values}
    return totals


def _keep(rolls, keep, keep_n):
    if keep == "kh":
        return sorted(rolls, reverse=True)[:keep_n]
    elif keep == "kl":
        return sorted(rolls)[:keep_n]
    else:
        return list(rolls)


def _term_values(term):
    if "constant" in term:
        return {term["constant"]}
    kept = min(term["count"], term["keep_n"]) if term["keep"] else term["count"]
    if term["success_at"] is not None:
        return set(range(kept + 1))
    elif term["sides"] == 66:
        faces = {tens * 10 + units for tens in range(1, 7) for units in range(1, 7)}
        totals = {0}
        for _ in range(kept):
            totals = {t + f for t in totals for f in faces}
        return totals
    else:
        return {value * term["times"] for value in range(kept, kept * term["sides"] + 1)}
