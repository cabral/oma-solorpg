"""Importers for the books of a game: `solo import book` reads a PDF's bookmarks and layout and writes
the system pack an agent would have written from it, without one.

A recipe is a module here that knows one book (one printing of it): where in its bookmarks each
table, spell and stat block is, and how to read it. It holds locations and ways of reading, never
the book's words or numbers: those come from the PDF, each time, so a pack built from the book is the
same for everyone who owns it and nothing of the book is in this repository. A book no recipe
recognizes is imported the way it always was, by an agent with the solo-rules-import skill.
"""

import shutil
from pathlib import Path

from .. import SoloError, library
from ..sections import Book
from .pack import Pack

# Where a pack built here says so, so that a re-run replaces it and nothing else.
MARK = "# Built by `solo import book`"


def recipes():
    """The recipes, each a module with NAME, PACK (the folder its pack is built into), extends(folder) (what that pack is laid
    over, given the folder of packs it is built into), recognizes(book) and build(pack)."""
    from . import dragonbane_cards, dragonbane_core, dragonbane_magic, dragonbane_solo
    return (dragonbane_core, dragonbane_magic, *dragonbane_cards.DECKS, dragonbane_solo)


def recipe_for(book):
    """The recipe that knows this book, or None."""
    return next((recipe for recipe in recipes() if recipe.recognizes(book)), None)


def plan(folders):
    """([(folder, recipe)], [folder]): the books some recipe knows, in the order their packs go on one another (the rules, then what goes over them, the solo
    booklet last), and the ones none does."""
    order = {recipe: at for at, recipe in enumerate(recipes())}
    known, unknown = [], []
    for folder in folders:
        recipe = recipe_for(Book(folder))
        if recipe:
            known.append((folder, recipe))
        else:
            unknown.append(folder)
    return sorted(known, key=lambda pair: order[pair[1]]), unknown


def build(folder, out=None, replace=False):
    """Build the system pack for the book `solo extract` left in `folder`: (the pack's folder, the files written, what the recipe has to say).
    A pack already at `out` is refused, unless `replace` and it was built here."""
    book = Book(folder)
    recipe = recipe_for(book)
    if recipe is None:
        raise SoloError(f"{book.manifest.get('source', folder)}: no importer knows this book, or this printing of it (it has {len(book.outline)} bookmarks, "
                        f"fingerprint {book.fingerprint()[:16]}). Import it with an agent and the solo-rules-import skill.")
    target = Path(out).expanduser() if out else library.home() / "systems" / recipe.PACK
    made = (target / "system.toml").read_text(encoding="utf-8").startswith(MARK) if (target / "system.toml").exists() else False
    if replace and made:
        shutil.rmtree(target)
    elif (target / "system.toml").exists():
        raise SoloError(f"{target} already holds a pack" + (" built by solo import book: --replace builds it again" if made else " (not one this built: build into another folder with --out, then compare)"))
    pack = Pack(book, target, recipe.NAME, recipe.extends(target.parent))
    recipe.build(pack)
    return target, pack.write(folder), [*book.notes, *pack.notes]
