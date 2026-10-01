"""The solo booklet (DB_Solo_Adventure_v1.2.pdf, "Alone in Deepfall Breach"): the tools of playing alone, laid over the core rules as the system pack
`dragonbane` (and over the card decks, when they have been imported too)."""

from . import rules, system, tables

NAME = "Dragonbane Solo Rules"
PACK = "dragonbane"
# The packs this one goes over when they are there: the rules first, then each deck of cards (their own books, their own recipes).
BASES = ("dragonbane-rulebook", "dragonbane-book-of-magic", "dragonbane-treasure-cards", "dragonbane-improvised-weapons", "dragonbane-adventure-cards")
PRINTINGS = {"6b64df25669315d3": "version 1.2"}


def recognizes(book):
    return book.fingerprint()[:16] in PRINTINGS


def extends(folder):
    """The base packs that are in the folder the pack is built into."""
    return [name for name in BASES if (folder / name / "system.toml").exists()]


def build(pack):
    if "dragonbane-rulebook" not in pack.system.get("extends", []):
        pack.note("the core rules aren't imported here yet (dragonbane-rulebook): this pack goes over them, so build them first and then build this again with --replace")
    tables.build(pack)
    system.build(pack)
    rules.build(pack)
