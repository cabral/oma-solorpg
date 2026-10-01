"""The Dragonbane core rules (the second printing, DB_Rules_v2.pdf): its bookmarks and layout, read into
the system pack `dragonbane-rulebook` (`make dragonbane` builds it), laid over the bundled names."""

from . import abilities, bestiary, creation, gear, rules, spells, system, tables

NAME = "Dragonbane Core Rules"
PACK = "dragonbane-rulebook"
# The bookmarks of the printings this was written against (Book.fingerprint).
PRINTINGS = {"1df6219d28619e82": "second printing"}


def extends(folder):
    """What the pack goes over: the bundled names of Dragonbane's things."""
    return "bundled:dragonbane"


def recognizes(book):
    return book.fingerprint()[:16] in PRINTINGS


def build(pack):
    gear.build(pack)
    system.build(pack)
    tables.build(pack)
    creation.build(pack)
    bestiary.build(pack)
    abilities.build(pack)
    spells.build(pack)
    rules.build(pack)
