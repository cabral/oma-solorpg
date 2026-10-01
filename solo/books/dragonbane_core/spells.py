"""Chapter 5's spell list as spells/<id>.toml: each spell with its rank, requirements, casting time, range and duration and, for the ones the engine can cast,
what they do (solo/books/spelllist.py). A school's magic tricks are spells of rank 0.
"""

from ... import packs
from .. import spelllist


def build(pack):
    book = pack.book
    for school in book.find("5. Magic", "Spell List").children:
        made = []
        skill = "general" if school.title == "General Magic" else packs.slug(school.title)
        for section in school.children:
            if section.title == "Magic Tricks":
                made += [_write(pack, trick.title, spelllist.trick(skill, trick.title, trick.page)) for trick in section.children]
            else:
                made.append(_write(pack, section.title, spelllist.spell(book, skill, section)))
        pack.item(f"spells_{packs.slug(school.title)}", f"{school.title} spells and tricks", "spell", school.pages, [f"spells/{spell}" for spell in made])


def _write(pack, title, spell):
    pack.toml(f"spells/{packs.slug(title)}.toml", spell)
    return packs.slug(title)
