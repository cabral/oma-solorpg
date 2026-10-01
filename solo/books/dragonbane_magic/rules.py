"""The prose of the Book of Magic as rules/<id>.md for `solo rule` (solo/books/pages.py): the schools' preambles, spells, recipes, enchantments and artifacts."""

from .. import pages
from ..pages import Kind


def _data(section):
    return section.title.startswith(("Chart:", "Statblock"))


def _spell(trail):
    """A spell, recipe or enchantment: the chapter, its "Spells" or "Recipes", a rank and the page; or, with no ranks, the chapter, its list and the page."""
    return (len(trail) in (3, 4) and trail[0][:1].isdigit() and trail[1] in ("Spells", "Recipes") and (len(trail) == 3 or trail[2].startswith("Rank "))
            and not trail[-1].startswith(("Rank ", "Chart:", "Sidebar:")))


def _chapter(section):
    while section.parent.number >= 0:
        section = section.parent
    return pages.clean(section.title)


def _school(section):
    return [f"School: {_chapter(section)}."]


def _school_terms(section):
    chapter = _chapter(section).lower()
    return [f"{chapter} spell", *(["recipe", "alchemy recipe"] if chapter == "alchemy" else [])]


KINDS = [Kind(_spell, "spell", "spell", ["spell", "spells"], _school, _school_terms)]


def build(pack):
    pages.build(pack, KINDS, _data, ("Contents", "Index of Spells, Recipies, and Magic Tricks"), "The credits.")
