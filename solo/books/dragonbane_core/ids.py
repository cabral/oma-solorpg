"""The ids the core rules' tables are known by: what an adventure names (`fear`), what the engine's rules
name (`demon_roll_melee`), what a monster's attacks are called. A table the book titles otherwise is its
title in snake case."""

from ... import packs

TABLES = {
    "Fear Table": "fear",
    "Demon Roll in Melee": "demon_roll_melee",
    "Demon Roll in Ranged Combat": "demon_roll_ranged",
    "Magical Mishaps": "magical_mishaps",
    "Mishaps": "journey_mishaps",
    "Leaving the Adventure Site": "leaving_the_site",
}


def table(title):
    """The id of a table by the title of its bookmark ("Table: Fear Table" is `fear`)."""
    name = title.removeprefix("Table:").strip()
    return TABLES.get(name) or packs.slug(name)


def sentence(title):
    """A title in sentence case: "Giant Spider" is "Giant spider" (words in capitals, like NPC, stay)."""
    first, *rest = title.split()
    return " ".join([first, *(word if word.isupper() else word.lower() for word in rest)])


def label(entry_id):
    """What an entry of the pack is called: `light_warhammer` is "Light warhammer"."""
    return entry_id.replace("_", " ").capitalize()
