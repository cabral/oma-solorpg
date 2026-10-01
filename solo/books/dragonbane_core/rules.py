"""The prose of the core rules, as rules/<id>.md for `solo rule`: a page for each section of the book that has words of its own (solo/books/pages.py).

What the recipe says is which sections are data elsewhere (the tables, the stat blocks), which are the book's lists (the heroic abilities, the skills, the
spells, the professions, a kin's innate abilities) and so are named by what they are, and which are listings of the book's own pages.
"""

from .. import pages
from ..pages import Kind, under

_LISTINGS = ("Contents", "Index")


def _school(section):
    return [f"School: {section.parent.title}."] if section.parent.title != "Spell List" else []


def _school_terms(section):
    return [f"{section.parent.title.lower()} spell"] if section.parent.title != "Spell List" else []


def _kin(section):
    return [f"Innate ability of the {section.parent.title.lower()}."]


def _kin_ability(trail):
    return len(trail) > 2 and trail[:2] == ("2. Your Player Character", "Kin") and trail[-1].startswith("Ability:")


KINDS = [Kind(under("3. Skills", "Heroic Abilities"), "heroic", "ability", ["heroic ability", "heroic abilities"]),
         Kind(under("3. Skills", "The Core Skills"), "skill", "mechanic", ["skill"]),
         Kind(under("5. Magic", "Spell List"), "spell", "spell", ["spell", "spells"], _school, _school_terms),
         Kind(under("2. Your Player Character", "Profession"), "profession", "mechanic", ["profession", "professions"]),
         Kind(_kin_ability, "kin", "ability", ["kin ability", "innate ability"], _kin),
         Kind(lambda trail: trail[0].startswith("7."), kind="creature"),
         Kind(lambda trail: trail[0].startswith("8."), kind="advice")]


def _data(section):
    """Tables and stat blocks are data (tables/, bestiary/); a monster's own table of attacks is too, but the bestiary's introduction's is prose."""
    return section.title.startswith(("Table:", "Statblock")) or (section.title == "Monster Attacks" and section.parent.title != "Introduction")


def build(pack):
    pages.build(pack, KINDS, _data, _LISTINGS, "The credits, and the list of corrections the second printing made (the pages here already have them).")
