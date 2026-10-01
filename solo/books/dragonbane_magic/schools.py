"""The schools of magic of the Book of Magic: a chapter each, numbered ("2. Animism"); general magic is the first and is no school of its own."""

import re

from ... import packs
from .. import pages


def chapters(book):
    return [section for section in book.root.children if re.match(r"\d+\.\s", section.title)]


def skill(chapter):
    """The skill a chapter's spells are cast with: its name in snake case ("2. Animism" is `animism`); `general` for general magic."""
    name = pages.clean(chapter.title)
    return "general" if name == "General Magic" else packs.slug(name)
