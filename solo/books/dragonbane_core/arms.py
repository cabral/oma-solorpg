"""The weapons and armor of the gear tables, found by the words a profession page or a stat block uses for them."""

import re

# Called another thing where they are used: the profession pages say "warhammer (small)" for the table's "Warhammer, Light", and the
# stat blocks say "wooden club" where the table has a small one and a large one (the small one is used).
SAME = {"warhammer (small)": "light warhammer", "wooden club": "small wooden club"}


def known(system):
    """{the words of an entry run together: its id} for every weapon and piece of armor the pack has."""
    return {name.replace("_", ""): name for name in [*system["weapons"], *system["armor"]]}


def find(known, text):
    """The id of the weapon or armor a phrase names ("shield (small)" is the small shield), or None. The words are taken as they
    come and in the other order: "light crossbow" and "Crossbow, Light" are one thing."""
    words = re.findall(r"[a-z]+", SAME.get(text.strip().lower(), text.lower()))
    return known.get("".join(words)) or known.get("".join(reversed(words)))
