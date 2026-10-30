"""Dice expressions.

Terms joined by + or -:
  NdM        N dice with M sides, N defaults to 1        3d6, d20
  d66        two d6 read as tens and units (11-66)     d66
  NdMkh[K]   keep the K highest dice, K defaults to 1   2d20kh
  NdMkl[K]   keep the K lowest dice                     3d20kl
  NdMkK      keep the K highest dice                    4d6k3
  NdM keep K, keep highest [K], keep lowest [K]         4d6 keep 3, 2d20 keep lowest
  NdMcs>=T   count the dice showing T or more           5d6cs>=6
  NdMxK      the dice's total times K (also * or ×)      2d6x10
  K          a constant                                 1d6+2

Case and white space don't matter, except that white space can't split a number: "2d6 3" is an
error, not 2d63. What a person typed by mistake is refused, never read as something else: a dice
count, a keep, a success number and a multiplier are at least 1, and a term counts successes or
multiplies, not both. Digits are 0-9, and an expression has at most 1000 characters.
"""

import os
import random
import re

from . import SoloError

# ASCII, so \d is 0-9 and no other digit. A keep is kh or kl (or keephighest or keeplowest), with its
# number after, which may be left out; or k or keep, which keep the highest and need their number.
_TERM = re.compile(
    r"([+-]?)(?:(\d*)d(\d+)(?:(?:(kh|kl|keephighest|keeplowest)(\d*)|(keep|k)(\d+)))?(?:cs>=(\d+))?(?:[x*×](\d+))?|(\d+))",
    re.ASCII,
)
# White space as JavaScript's \s has it (tab, line feed, vertical tab, form feed, carriage return,
# the space separators, the byte order mark, and the line and paragraph separators), so that a
# JavaScript implementation of these rules reads the same text the same way.
_SPACE_CHARS = "".join(chr(c) for c in (
    0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0xA0, 0x1680, *range(0x2000, 0x200B),
    0x2028, 0x2029, 0x202F, 0x205F, 0x3000, 0xFEFF,
))
_SPACES = re.compile(f"[{_SPACE_CHARS}]+")
_SPLIT_NUMBER = re.compile(f"[0-9][{_SPACE_CHARS}]+[0-9]")
# Only the letters A-Z are lower-cased: str.lower() reads the Kelvin sign as a k.
_LOWER = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
# Expressions come from packs other people write, so they are bounded: checking a table
# enumerates every total, and a d100000000 would never finish.
_MAX_DICE = 100
_MAX_SIDES = 1000
_MAX_TERMS = 20
_MAX_CHARS = 1000
_MAX_OUTCOMES = 1_000_000
_system_rng = random.SystemRandom()


def parse(expr):
    """Split an expression into terms. Raises SoloError on anything it can't read."""
    if len(expr) > _MAX_CHARS:
        raise SoloError(f"dice expression is longer than {_MAX_CHARS} characters")
    elif _SPLIT_NUMBER.search(expr):
        raise SoloError(f"can't read dice expression {expr!r}: white space splits a number")
    text = _SPACES.sub("", expr).translate(_LOWER)
    terms = []
    pos = 0
    while pos < len(text):
        match = _TERM.match(text, pos)
        if match is None or match.end() == pos or (pos > 0 and not match.group(1)):
            raise SoloError(f"can't read dice expression {expr!r} at {text[pos:]!r}")
        sign, count, sides, keep_which, keep_digits, keep_plain, keep_plain_digits, success_at, times, constant = match.groups()
        keep = "kl" if keep_which in ("kl", "keeplowest") else "kh" if keep_which or keep_plain else None
        keep_n = keep_digits or keep_plain_digits
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
            if not 1 <= term["count"] <= _MAX_DICE or not 2 <= term["sides"] <= _MAX_SIDES:
                raise SoloError(f"dice term {term['text']!r} is out of range")
            elif term["keep_n"] < 1 or term["times"] < 1 or (success_at is not None and term["success_at"] < 1):
                raise SoloError(f"dice term {term['text']!r} is out of range")
            elif success_at is not None and times is not None:
                raise SoloError(f"dice term {term['text']!r} counts successes and also multiplies")
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
