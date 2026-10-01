"""The Book of Magic (Dragonbane_Book_of_Magic.pdf): the schools of magic, with their spells, tricks and recipes, laid over the core rules as the system pack
`dragonbane-book-of-magic`. It repeats the core spells, six of them revised, and the revised ones here are the official ones."""

from . import rules, spells, system

NAME = "Dragonbane Book of Magic"
PACK = "dragonbane-book-of-magic"
PRINTINGS = {"1012763420cd23b8": "first printing"}


def recognizes(book):
    return book.fingerprint()[:16] in PRINTINGS


def extends(folder):
    """The core rules, when they are in the folder the pack is built into."""
    return ["dragonbane-rulebook"] if (folder / "dragonbane-rulebook" / "system.toml").exists() else []


def build(pack):
    if not pack.system.get("extends"):
        pack.note("the core rules aren't imported here yet (dragonbane-rulebook): this pack goes over them, so build them first and then build this again with --replace")
    system.build(pack)
    spells.build(pack)
    rules.build(pack)
