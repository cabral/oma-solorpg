"""A book's bookmarks as sections, each with the lines that are its own.

`solo extract` writes every page's lines and the book's bookmarks (solo/layout.py). This
reads them back, with the standard library only, and answers what an importer asks: which
lines does the section the book calls "Lightning Fast" hold, and what does it say?

A bookmark points at a place on a page, and a section runs from there to the next
bookmark. Two things get in the way. Sidebars and tables sit in the middle of a page's
text, and the body text goes on past them, so a line belongs to the sidebar's bookmark only
if it is not body text (the typeface most of the book is set in). And the bookmarks are a
tree (a spell under its school under the spell list), so a section has its `own` lines, up
to its first child, and all of them with the children's.

    book = Book(folder)
    section = book.find("3. Skills", "Heroic Abilities", "Lightning Fast")
    section.text()            # the words, in paragraphs, hyphens at line ends joined
    section.lines()           # the lines, with where they are and how they are set
"""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from . import SoloError

# Text lighter than this is a sidebar's: light type on a dark box.
_LIGHT = 0.5
# Dark text this big is a heading, whatever its typeface: it starts body text.
_HEADING = 10.5
# A short line lower on the page than this share of its height is a footer.
_FOOTER = 0.94
_SOFT_HYPHEN = "\u00ad"
_BULLET = "\u2726"
# Words that only end another: a hyphen before one is a line's break ("success-" "fully"), never a compound.
_ENDINGS = frozenset({"fully", "ly", "less", "lessly", "ness", "ment", "ments", "able", "ably", "ible", "ibly", "ing", "ings", "tion", "tions", "sion", "sions", "ity", "ous", "ful", "ize", "ise", "ised", "ized"})
# A paragraph set in this far from its column's margin makes room for a big initial.
_DROPCAP = 20
# A cell this far under a table's last line is still its own.
_ROW_GAP = 24
# How many lines before a heading are looked at for words set under it.
_REACH = 60
# A line this far below the last, in lines of its size, starts a new paragraph.
_PARAGRAPH = 1.45
# A line indented this far past the last one starts a paragraph too.
_INDENT = 6


class Section:
    """One bookmark, with its place in the tree and the lines it owns."""

    def __init__(self, book, number, entry):
        self.book, self.number = book, number
        self.level, self.title, self.page = entry["level"], entry["title"], entry["page"]
        self.x, self.y = entry["x"], entry["y"]
        self.parent, self.children = None, []
        self.start, self.body, self.owned = None, True, []

    def __repr__(self):
        return f"<{self.title!r} p. {self.page}>"

    def find(self, *titles):
        """The descendant called `titles[0]`, then the one under it called `titles[1]`, and so on."""
        here = self
        for title in titles:
            here = here.book._child(here, title)
        return here

    def subtree(self):
        for child in self.children:
            yield child
            yield from child.subtree()

    def lines(self, own=False):
        """The lines this section owns, from its bookmark to its first child's; or, unless `own`,
        the children's too, in page order."""
        if own:
            return self.owned
        return sorted([*self.owned, *(line for child in self.subtree() for line in child.owned)], key=lambda line: line["n"])

    def text(self, own=False):
        return paragraphs(self.lines(own), self.book.glue)

    def span(self):
        """Every line from where this section starts to where the next of its level or higher does, whoever owns them: a
        table a bookmark points into the middle of, or one set in two columns that the flow of the page splits, is whole here."""
        after = next((s for s in self.book.sections[self.number + 1:] if s.level <= self.level), None)
        return self.book.lines[self.start:after.start if after else len(self.book.lines)]

    @property
    def pages(self):
        return sorted({line["page"] for line in self.lines()}) or [self.page]


class Book:
    def __init__(self, folder):
        self.folder = Path(folder).expanduser()
        manifest_path = self.folder / "manifest.json"
        if not manifest_path.exists():
            raise SoloError(f"{self.folder} isn't solo extract's folder (no manifest.json): run solo extract on the book first")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not manifest.get("layout"):
            raise SoloError(f"{self.folder} was extracted before importers could read it (no layout/): run solo extract on the PDF again")
        self.manifest = manifest
        self.lines = []
        self.by_page = {}
        self.folio = {}
        for path in sorted((self.folder / "layout").glob("*.json")):
            page = json.loads(path.read_text(encoding="utf-8"))
            found = self.by_page.setdefault(page["page"], [])
            for line in page["lines"]:
                if line.get("running") and line["text"].strip().isdigit():
                    self.folio[page["page"]] = int(line["text"])
                # A short line in the bottom of the page is a footer, whether or not it repeats enough to be taken for one.
                if not line.get("running") and not (line["y0"] > page["height"] * _FOOTER and len(line["text"]) <= 60):
                    line = {**line, "page": page["page"], "width": page["width"], "height": page["height"], "n": len(self.lines)}
                    found.append(line)
                    self.lines.append(line)
        body = Counter()
        for line in self.lines:
            body[_family(line)] += len(line["text"])
        self.body = body.most_common(1)[0][0] if body else ""
        self.words = _vocabulary(self.lines)
        self.notes = []
        self._dropcaps()
        self.outline = json.loads((self.folder / "outline.json").read_text(encoding="utf-8"))
        self.sections = [Section(self, number, entry) for number, entry in enumerate(self.outline)]
        self.root = Section(self, -1, {"level": 0, "title": "", "page": 1, "x": 0, "y": 0})
        self._tree()
        self._place()
        self._assign()

    # The tree -------------------------------------------------------------------------

    def _tree(self):
        trail = [self.root]
        for section in self.sections:
            while trail[-1].level >= section.level:
                trail.pop()
            section.parent = trail[-1]
            trail[-1].children.append(section)
            trail.append(section)

    def _place(self):
        """Find the line each bookmark points at: the first line on its page, in its column, at
        or below the place it points to. A bookmark that names only a page starts at the line
        that says its title. One whose page has no such line starts at the page's end (and owns
        nothing). Whether it starts body text or a box (a sidebar, a table) depends on the line:
        body text and headings start body text, and so does a line followed by body text; so does
        a chapter, whatever its title is set in."""
        for section in self.sections:
            page = self.by_page.get(section.page, [])
            # A bookmark with no place, or one at the very foot of the page (the PDF's way of saying nowhere), is found by its title.
            if section.y is None or (page and section.y >= page[0]["height"] - 5):
                heading = {_key(section.title), _key(section.title.split(":", 1)[-1])}
                at = next((line for line in page if _key(line["text"]) in heading), None)
            else:
                middle = page[0]["width"] / 2 if page else 0
                side = 1 if section.x >= middle else 0
                covers = lambda line: line["x0"] - 6 <= section.x <= line["x1"] + 6
                # A line of the bookmark's column, or one set across the page (a title) unless it sits wholly in the other half.
                across = lambda line: line["col"] == 2 and not (line["x1"] < middle if side else line["x0"] > middle)
                below = [line for line in page if line["y0"] >= section.y - 3 and (line["col"] == side or across(line))]
                # A heading the bookmark points into is its place; else the line closest below it (a table's bookmark points into the table).
                heading = [line for line in below if covers(line) and line["y0"] <= section.y + 15 and line["size"] >= 9.5 and line["font"].endswith("-Bold")]
                at = heading[0] if heading else min(below, key=lambda line: (round((line["y0"] - section.y) / 4), line["n"]), default=None)
            section.start = at["n"] if at else self._page_end(section.page)
            after = self.lines[at["n"] + 1] if at and at["n"] + 1 < len(self.lines) else None
            section.body = bool(at) and (section.level == 1 or self._is_body(at) or (after is not None and self._is_body(after) and after["page"] == at["page"]))

    def _dropcaps(self):
        """A paragraph that begins with a big initial set as a drawing, which the PDF's text doesn't have: the first lines are set in to make room for it. The
        letter is the one that makes the first word the most common word of the book it can be ("he" is "the"), or the word "A"; each is told in `notes`."""
        count = Counter(word.lower() for line in self.lines for word in re.findall(r"[A-Za-z’']+", line["text"].replace(_SOFT_HYPHEN, "")))
        margins = {}
        for line in self.lines:
            if _family(line) == self.body and line["size"] >= 9.5:
                margins.setdefault((line["page"], line["col"]), Counter())[round(line["x0"])] += 1
        for at, line in enumerate(self.lines[:-1]):
            margin = margins.get((line["page"], line["col"]), Counter()).most_common(1)
            following = self.lines[at + 1]
            before = self.lines[at - 1] if at else None
            indented = lambda other: other is not None and (other["page"], other["col"]) == (line["page"], line["col"]) and margin and other["x0"] - margin[0][0] >= _DROPCAP
            if _family(line) == self.body and line["size"] >= 9.5 and indented(line) and indented(following) and abs(line["x0"] - following["x0"]) < 2 and not indented(before):
                word = re.match(r"[A-Za-z’']+", line["text"])
                ranked = sorted(((count[(letter + word.group()).lower()], letter) for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ"), reverse=True) if word else [(0, "")]
                letter = ranked[0][1] if ranked[0][0] else "A " if word and count[word.group().lower()] > 1 else ""
                near = [other for number, other in ranked[1:3] if number and number * 4 >= ranked[0][0]]
                line["text"] = letter + line["text"]
                self.notes.append(f"p. {line['page']}: the big initial before {word.group()!r} is not in the PDF's text; "
                                  + (f"read as {letter.strip()!r}" + (f" (it could be {' or '.join(map(repr, near))}: check the page)" if near and ranked[0][0] else "") if letter
                                     else "which letter it is can't be told, and the word is left as it stands"))

    def _is_body(self, line):
        """Body text, or a heading: dark type in the book's typeface, or big enough to be one."""
        red, green, blue = (line["color"] >> 16) & 255, (line["color"] >> 8) & 255, line["color"] & 255
        light = (0.299 * red + 0.587 * green + 0.114 * blue) / 255 > _LIGHT
        spans = line.get("spans") or []
        # A bold label that runs into body text ("Name: words ...") is a line of body text; its label is not a heading.
        mostly = bool(spans) and sum(len(text.strip()) for text, font, *_ in spans if font.split("-")[0] == self.body) >= 0.4 * len(line["text"].strip())
        return not light and (_family(line) == self.body or line["size"] >= _HEADING or mostly)

    def _assign(self):
        """Give every line to a bookmark. Body text goes to the last bookmark that starts body
        text, whatever box has come since; anything else goes to the last bookmark of any kind."""
        starts = {}
        for section in sorted(self.sections, key=lambda s: (s.start, s.number)):
            starts.setdefault(section.start, []).append(section)
        flow = latest = None
        for line in self.lines:
            for section in starts.get(line["n"], []):
                latest = section
                flow = section if section.body else flow
            owner = flow if self._is_body(line) else latest
            line["owner"] = owner.number if owner else None
        self._reclaim()
        self._continue_tables()
        for line in self.lines:
            if line["owner"] is not None:
                self.sections[line["owner"]].owned.append(line)

    def _continue_tables(self):
        """The cells of a table that the order of the PDF's lines put with the text beside it: cell-sized lines of a prose section, not body text, that start where
        one of the table's columns does and stand within its length (or a row's height below it) are its own."""
        tables = {section.number for section in self.sections if section.title.startswith("Table:")}
        for number in tables:
            mine = [line for line in self.lines if line["owner"] == number]
            if mine:
                page = mine[-1]["page"]
                edges = {round(line["x0"]) for line in mine if line["page"] == page}
                top, bottom = min(line["y0"] for line in mine if line["page"] == page), max(line["y0"] for line in mine if line["page"] == page)
                more = True
                while more:
                    more = False
                    for line in self.by_page[page]:
                        if (line["owner"] not in tables and line["owner"] is not None and line["size"] <= 9.3 and not self._is_body(line)
                                and top <= line["y0"] <= bottom + _ROW_GAP and any(abs(line["x0"] - edge) <= 3 for edge in edges)):
                            line["owner"], bottom, more = number, max(bottom, line["y0"]), True

    def _reclaim(self):
        """A heading can come after the words under it, in the order the PDF gives the lines (a box in the right column, whose title follows the
        table above it): the lines before a heading on its page that are set under it, in its column, are its own."""
        for section in self.sections:
            head = self.lines[section.start] if section.start < len(self.lines) else None
            if head is not None and section.level > 1 and head["size"] >= 9.5 and head["font"].endswith("-Bold"):
                for line in self.lines[max(0, head["n"] - _REACH):head["n"]]:
                    if self._under(line, head):
                        line["owner"] = section.number

    @staticmethod
    def _under(line, head):
        """Whether a line is set below a heading, on the same page, and mostly within the heading's width."""
        across = min(line["x1"], head["x1"]) - max(line["x0"], head["x0"])
        return line["page"] == head["page"] and line["y0"] > head["y0"] and across >= 0.4 * (line["x1"] - line["x0"])

    def _page_end(self, page):
        before = [n for n in self.by_page if n <= page and self.by_page[n]]
        return self.by_page[max(before)][-1]["n"] + 1 if before else 0

    # Finding and reading -------------------------------------------------------------

    def find(self, *titles):
        """A section by the titles from the top: find("3. Skills", "Heroic Abilities")."""
        return self.root.find(*titles)

    def _child(self, section, title):
        want = _key(title)
        found = [s for s in section.subtree() if _key(s.title) == want]
        if not found:
            near = sorted({s.title for s in section.subtree()}, key=lambda t: -_overlap(t, title))[:5]
            where = f"under {section.title!r}" if section is not self.root else "in the bookmarks"
            raise SoloError(f"{self.manifest.get('source', 'the book')}: no section {title!r} {where} (closest: {', '.join(near) or 'none'}); "
                            "this may be another printing than the importer was written for")
        # The shallowest, then the first in the book: a title that repeats deeper down is not the one meant.
        return min(found, key=lambda s: (s.level, s.number))

    def glue(self, text, part):
        """`text` ends at a hyphen and `part` goes on. A line broken in the middle of a word
        (char-, acter) is joined whole; a hyphen the word has of its own (one-, handed) stays. The
        book says which: the word is written whole, or with its hyphen, somewhere else in it."""
        left, right = re.search(r"[\w’']+$", text[:-1]), re.match(r"[\w’']+", part)
        if not (left and right):
            return f"{text} {part}"
        head, tail = left.group().lower(), right.group().lower()
        whole = re.sub(r"[’']s$", "", head + tail)
        if tail in _ENDINGS:
            return text[:-1] + part
        elif f"{head}-{tail}" in self.words:
            return text + part
        elif head + tail in self.words or whole in self.words:
            return text[:-1] + part
        else:
            return text + part if (len(head) >= 4 and head in self.words) or left.group().isupper() else text[:-1] + part

    def printed(self, page):
        """The page number printed on a PDF page, where the book prints one."""
        return self.folio.get(page)

    def fingerprint(self):
        """A hash of the bookmarks' levels and titles: the same for every copy of a printing, whatever a shop stamped on it, and different for
        another printing."""
        digest = hashlib.sha256()
        for entry in self.outline:
            digest.update(f"{entry['level']}|{entry['title']}\n".encode())
        return digest.hexdigest()


# Lines into words --------------------------------------------------------------------------

def paragraphs(lines, glue=None, hanging=False):
    """The lines as paragraphs, blank line between. A word broken at a line end by a soft
    hyphen comes back whole, a real hyphen at a line end is decided by `glue`. A bullet, a
    gap, a first line indented, or body text back at a bullet's margin starts a paragraph; a
    sentence cut by the end of a column or a page goes on. With `hanging`, the lines after the
    first are the ones set in (a stat block's entries): a paragraph starts where a line is back
    at the margin the last one began at."""
    out, last, bullet, margin, numbered = [], None, None, None, False
    for line in lines:
        text = line["text"].strip().replace(_SOFT_HYPHEN + " ", " ")
        if not text.replace(_SOFT_HYPHEN, ""):
            continue
        if last is None:
            new = True
        elif (last["page"], last["col"]) == (line["page"], line["col"]) and line["y0"] >= last["y0"]:
            new = (line["y0"] - last["y0"] > _PARAGRAPH * max(line["size"], last["size"]) or text.startswith(_BULLET)
                   or (abs(line["size"] - last["size"]) > 1 and max(line["size"], last["size"]) >= _HEADING)
                   or (bullet is not None and line["x0"] < bullet + 3)
                   or (bullet is None and (hanging or numbered) and line["x0"] < margin + 3)
                   or (bullet is None and not (hanging or numbered) and line["x0"] - last["x0"] > _INDENT))
        else:
            new = out[-1][-1].rstrip()[-1:] in ".!?:;)\"”’" or not text[:1].islower()
        if new:
            out.append([text])
            bullet = line["x0"] if text.startswith(_BULLET) else None
            margin, numbered = line["x0"], re.match(r"\d+\.\s", text) is not None
        else:
            out[-1].append(text)
        last = line
    return "\n\n".join(join(parts, glue or _glue) for parts in out)


def join(parts, glue):
    text = parts[0]
    for part in parts[1:]:
        if text.endswith(_SOFT_HYPHEN):
            text = text[:-1] + part
        elif text.endswith("-") and part[:1].isalpha():
            text = glue(text, part)
        else:
            text = f"{text} {part}"
    return re.sub(r"\s+", " ", text.replace(_SOFT_HYPHEN, "")).strip()


def _glue(text, part):
    return text + part


def _vocabulary(lines):
    """Every word the book spells out, hyphenated compounds whole, leaving out the last word of
    a line that ends at a hyphen (it is half a word)."""
    words = set()
    for line in lines:
        text = line["text"].replace(_SOFT_HYPHEN, "").strip().lower()
        found = re.findall(r"[\w’']+(?:-[\w’']+)*", text)
        words.update(found[:-1] if text.endswith("-") else found)
    return words


def _family(line):
    return line["font"].split("-")[0]


def _key(title):
    return " ".join(title.lower().replace(_SOFT_HYPHEN, "").split())


def _overlap(a, b):
    a, b = set(_key(a).split()), set(_key(b).split())
    return len(a & b) / max(1, len(a | b))
