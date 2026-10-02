"""Importers for the books of a game: `solo import book` reads a PDF's bookmarks and layout and writes
the system pack or the adventure pack an agent would have written from it, without one.

A recipe is a module here that knows one book (one printing of it): where in its bookmarks each
table, spell and stat block is, and how to read it. It holds locations and ways of reading, never
the book's words or numbers: those come from the PDF, each time, so a pack built from the book is the
same for everyone who owns it and nothing of the book is in this repository. A book no recipe
recognizes is imported the way it always was, by an agent with the solo-rules-import skill.
"""

import shutil
from pathlib import Path

from .. import SoloError, library, packs
from ..sections import Book
from .pack import AdventurePack, Pack

# Where a pack built here says so, so that a re-run replaces it and nothing else.
MARK = "# Built by `solo import book`"


def recipes():
    """The recipes, each a module with NAME, PACK (the folder its pack is built into), extends(folder) (what that pack is laid
    over, given the folder of packs it is built into), recognizes(book) and build(pack). A recipe for an adventure says KIND = "adventure"
    and SYSTEM (the system pack it is for, which has to be built first); its `build` gets an AdventurePack."""
    from . import dragonbane_cards, dragonbane_core, dragonbane_magic, dragonbane_solo, dragonbane_tower, dragonbane_vale
    return (dragonbane_core, dragonbane_magic, *dragonbane_cards.DECKS, dragonbane_solo, dragonbane_tower, dragonbane_vale)


def kind_of(recipe):
    return getattr(recipe, "KIND", "system")


def recipe_for(book):
    """The recipe that knows this book, or None."""
    return next((recipe for recipe in recipes() if recipe.recognizes(book)), None)


def plan(folders):
    """([(folder, recipe)], [folder]): the books some recipe knows, in the order their packs go on one another (the rules, then what goes over them, the solo
    booklet, then the adventures, which are for the rules), and the ones none does."""
    order = {recipe: at for at, recipe in enumerate(recipes())}
    known, unknown = [], []
    for folder in folders:
        recipe = recipe_for(Book(folder))
        if recipe:
            known.append((folder, recipe))
        else:
            unknown.append(folder)
    return sorted(known, key=lambda pair: order[pair[1]]), unknown


def build(folder, out=None, replace=False, systems=None, adventures=None):
    """Build the pack for the book `solo extract` left in `folder`: (the pack's folder, the files written, what the recipe has to say). It goes in `out`,
    or in the recipe's own folder of `systems` or `adventures` (default ~/Games/solo/systems and ~/Games/solo/adventures); an adventure is built for the
    system pack in `systems`. A pack already there is refused, unless `replace` and it was built here."""
    book = Book(folder)
    recipe = recipe_for(book)
    if recipe is None:
        raise SoloError(f"{book.manifest.get('source', folder)}: no importer knows this book, or this printing of it (it has {len(book.outline)} bookmarks, "
                        f"fingerprint {book.fingerprint()[:16]}). Import it with an agent and the solo-rules-import skill.")
    kind = kind_of(recipe)
    folders = {"system": Path(systems).expanduser() if systems else library.home() / "systems",
               "adventure": Path(adventures).expanduser() if adventures else library.home() / "adventures"}
    target = Path(out).expanduser() if out else folders[kind] / recipe.PACK
    main = target / (AdventurePack.MAIN if kind == "adventure" else Pack.MAIN)
    made = main.read_text(encoding="utf-8").startswith(MARK) if main.exists() else False
    if replace and made:
        shutil.rmtree(target)
    elif main.exists():
        raise SoloError(f"{target} already holds a pack" + (" built by solo import book: --replace builds it again" if made else " (not one this built: build into another folder with --out, then compare)"))
    if kind == "adventure":
        pack = AdventurePack(book, target, recipe.NAME, packs.load_system(folders["system"] / recipe.SYSTEM))
    else:
        pack = Pack(book, target, recipe.NAME, recipe.extends(target.parent))
    recipe.build(pack)
    written = pack.write(folder)
    problems = packs.validate(pack.system_pack, packs.load_adventure(target)) if kind == "adventure" else []
    if problems:
        raise SoloError(f"{target.name} was built, and the engine says it can't be played:\n  " + "\n  ".join(problems))
    return target, written, [*book.notes, *pack.notes]
