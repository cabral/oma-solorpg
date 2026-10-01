"""Rules pages from a book's sections: a rules/<id>.md for `solo rule` for each section that has words of its own, with the title, the words to find it
by, the lines of its stat block (rank, requirement, willpower points), what the book says, and where.

What a recipe says is only what is its own: which sections are data elsewhere (`skip`), which are lists the book sets out and so are named by what they
are (`Kind`), and which are listings of the book's own pages (`listings`). A table's cells that stand on a page the section only names are cut off at the
table's header, and a table the recipe wrote as data is pointed at (`solo table fear`).
"""

import re

from .. import packs
from ..audit import spans
from ..sections import paragraphs
from . import dice

# The words in front of a bookmark's title that say what sort of section it is, not what it is called.
_PREFIXES = ("Sidebar", "Sidabar", "Optional Rule", "Ability", "Heroic Ability", "NPC")


class Kind:
    """A list the book sets out (the heroic abilities, the spells): `where(trail)` says whether a section is one of them, by the titles from the top to
    it; its pages are named `<prefix>_<title>`, found by `terms` (and `find(section)`, more for that section), and kept in the inventory as `kind`;
    `extra(section)` is more lines for its page."""

    def __init__(self, where, prefix="", kind="mechanic", terms=(), extra=None, find=None):
        self.where, self.prefix, self.kind, self.terms, self.extra, self.find = where, prefix, kind, list(terms), extra, find


def under(*path):
    """The sections under the one at the end of this path of titles (not the section itself)."""
    return lambda trail: trail[:len(path)] == path and len(trail) > len(path)


def build(pack, kinds=(), skip=lambda section: False, listings=(), front_note=""):
    book = pack.book
    pages = {}
    for section in book.sections:
        if not (skip(section) or section.title in listings):
            words = _words(book, section)
            if words:
                pages[section.number] = words
    kind_of = {number: _kind(book.sections[number], kinds) for number in pages}
    names, titles = _names(book, pages, kind_of), _titles(book, pages)
    for number, words in pages.items():
        section = book.sections[number]
        pack.file(f"rules/{names[number]}.md", _page(pack, section, words, titles[number], kind_of[number]))
        pack.item(f"rules_{names[number]}", clean(section.title), kind_of[number].kind, sorted({line["page"] for line in section.lines(own=True)}), [f"rules/{names[number]}.md"])
    front = [page for page in sorted(book.by_page) if 0 < page < min(section.page for section in book.sections) and book.by_page[page]]
    if front:
        pack.item("front_matter", "Credits and what this printing changed", "other", front, [], status="skipped", note=front_note or "The credits and notes on the printing.")
    for title in listings:
        section = book.find(title)
        pack.item(f"book_{packs.slug(title)}", title, "other", section.pages, [], status="skipped", note="A listing of the book's own pages, which the pack has in full.")


def clean(title):
    """A section's title as its page names it: without the bookmark's "Sidebar:" and the like, and without a chapter's number."""
    head, _, rest = title.partition(":")
    return re.sub(r"^\d+\.\s+", "", rest.strip() if rest and head in _PREFIXES else title)


def _kind(section, kinds):
    trail = tuple(s.title for s in _trail(section))
    return next((kind for kind in kinds if kind.where(trail)), Kind(None))


def _trail(section):
    trail = []
    while section.number >= 0:
        trail.insert(0, section)
        section = section.parent
    return trail


def _words(book, section):
    """The blocks of a section's text: a list of ("bullet", text) and ("text", paragraph), the line that is the title left out and a table cut off at its
    header; [] for a section that says nothing of its own."""
    lines = section.lines(own=True)
    cut = next((at for at, line in enumerate(lines) if dice.is_marker(line)), len(lines))
    titles = {re.sub(r"\W", "", title).lower() for title in (clean(section.title), section.title)}
    blocks = []
    for paragraph in paragraphs(lines[:cut], book.glue).split("\n\n"):
        if paragraph and re.sub(r"\W", "", paragraph).lower() not in titles:
            blocks.append(("bullet", paragraph.lstrip("✦").strip()) if paragraph.startswith("✦") else ("text", paragraph))
    return blocks


def _names(book, pages, kind_of):
    """The file name of each page: the title in snake case, after what kind of thing it is (heroic_, spell_) when the book lists them. A title two sections
    share has the section it stands under in front of it, for both."""
    base = {number: f"{kind_of[number].prefix}_{packs.slug(clean(book.sections[number].title))}".lstrip("_") for number in pages}
    taken = {}
    for number, name in base.items():
        taken.setdefault(name, []).append(number)
    names = {}
    for name, numbers in taken.items():
        for number in numbers:
            parent = base.get(book.sections[number].parent.number) or packs.slug(clean(book.sections[number].parent.title))
            names[number] = name if len(numbers) == 1 else f"{parent}_{name}"
    seen = {}
    for number in sorted(names):
        again = seen.setdefault(names[number], [])
        again.append(number)
        if len(again) > 1:
            names[number] = f"{names[number]}_{len(again)}"
    return names


def _above(section):
    """The title of the section a section stands under, passing over an "Introduction" ("" for a chapter)."""
    parent = section.parent
    while parent.number >= 0 and clean(parent.title) == "Introduction":
        parent = parent.parent
    return clean(parent.title) if parent.number >= 0 else ""


def _titles(book, pages):
    """What each page is called: its section's title, or, for a title that more than one page has, the section it stands under in front of it."""
    count = {}
    for number in pages:
        title = clean(book.sections[number].title).lower()
        count[title] = count.get(title, 0) + 1
    return {number: f"{_above(book.sections[number])}: {clean(book.sections[number].title)}"
            if count[clean(book.sections[number].title).lower()] > 1 and _above(book.sections[number]) else clean(book.sections[number].title) for number in pages}


def _page(pack, section, words, title, kind):
    """The page: its title, the words to find it by, its lines and words, what the kind adds, the table it points at, and the source."""
    book = pack.book
    above = _above(section).lower()
    intro = clean(section.title) == "Introduction"
    search = list(dict.fromkeys([title.lower(), *([] if intro else [clean(section.title).lower()]), *kind.terms, *(kind.find(section) if kind.find else []), *([above] if above and not kind.prefix and not intro else []),
                                 *(["optional rule"] if section.title.startswith("Optional Rule") else [])]))
    out = [f"# {title}", f"Search: {', '.join(search)}", ""]
    bullets = [text for style, text in words if style == "bullet"]
    out += [f"- {text}" for text in bullets] + ([""] if bullets else [])
    for style, text in words:
        if style == "text":
            out += [text, ""]
    for line in (kind.extra(section) if kind.extra else []):
        out += [line, ""]
    for here in (section, *section.children):
        found = pack.facts.get("tables", {}).get(here.number)
        if found:
            out += [f"The table is solo table {found[0]} ({re.sub(r'^1d', 'd', found[1]).upper()}).", ""]
    pages = sorted({line["page"] for line in section.lines(own=True)})
    printed = [book.printed(page) for page in pages]
    out.append(f"Source: {pack.name}, PDF p. {spans(pages)}" + (f" (printed {spans(printed)})" if all(printed) else ""))
    return "\n".join(out)
