"""What a recipe builds: a system pack, held in memory until it is written.

A recipe reads a book's sections (solo/sections.py) and adds to the pack: a file, a section
of system.toml, creation.toml or gear.toml, and an inventory item saying where the book had it
and where it went. `write` then puts the lot on disk, inventory.toml included, so that
`solo audit` can check the pack against the book's pages the way it checks one an agent wrote.
"""

import re
from pathlib import Path

from .. import SoloError, packs
from ..tomlwrite import dump_toml

_SPANS = re.compile(r"\d+")


class Pack:
    def __init__(self, book, out, name, extends=None):
        self.book, self.out, self.name = book, Path(out), name
        self.system = {"format": packs.FORMAT, **({"extends": extends} if extends else {})}
        self.creation, self.gear = {}, {}
        self.files, self.items, self.notes = {}, {}, []
        # What one component found for another (the unarmed attack the gear table gives the combat rules).
        self.facts = {}

    def file(self, path, text):
        """A file of the pack's own (a rules page, a table): written as it is."""
        if path in self.files:
            raise SoloError(f"the recipe wrote {path} twice")
        self.files[path] = text if text.endswith("\n") else text + "\n"

    def toml(self, path, data, comments=()):
        self.file(path, dump_toml(data, comments))

    def item(self, item_id, name, kind, pages, to, status="mapped", note=""):
        """One thing the book holds, the pages it is on and what in the pack holds it. A
        second item with the same id gets a number after it."""
        taken, number = item_id, 2
        while taken in self.items:
            taken, number = f"{item_id}_{number}", number + 1
        entry = {"name": name, "kind": kind, "pages": sorted(set(pages)), "status": status}
        if to:
            entry["to"] = list(to)
        if note:
            entry["note"] = note
        self.items[taken] = entry
        return taken

    def note(self, text):
        """Something the recipe couldn't read or had to decide: the importer says it after the build."""
        self.notes.append(text)

    def write(self, extract):
        """Write the pack: its files, its sections of system.toml, creation.toml and gear.toml, and
        an inventory of everything in them. Nothing is overwritten that the recipe didn't write
        before: a pack that is already there is refused."""
        if (self.out / "system.toml").exists():
            raise SoloError(f"{self.out} already holds a pack: build into an empty folder, then compare")
        self.out.mkdir(parents=True, exist_ok=True)
        header = [f"Built by `solo import book` from {self.book.manifest.get('source', 'the book')}; every number and word below is read from its pages.",
                  "Pages are the PDF's, as solo extract numbers them."]
        files = {"system.toml": dump_toml(self.system, header), "inventory.toml": dump_toml(
            {"source": self.name, "extract": str(extract), "items": self.items}, ["What the book holds and where it went: see docs/PACK_FORMAT.md."])}
        for name, data in (("creation.toml", self.creation), ("gear.toml", self.gear)):
            if data:
                files[name] = dump_toml(data, header)
        for path, text in {**files, **self.files}.items():
            target = self.out / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
        return sorted([*files, *self.files])
