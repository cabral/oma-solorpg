"""The prose of the solo booklet, as rules/<id>.md for `solo rule` (solo/books/pages.py): the tools, the rules for surviving alone and the exploring."""

from .. import pages
from ..pages import Kind, under


def _data(section):
    return section.title.startswith(("Table:", "Statblock"))


KINDS = [Kind(lambda trail: trail[-1].startswith("Heroic Ability:"), "heroic", "ability", ["heroic ability", "heroic abilities"])]


def build(pack):
    pages.build(pack, KINDS, _data, (), "The credits.")
