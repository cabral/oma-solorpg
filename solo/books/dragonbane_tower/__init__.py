"""The Sinking Tower (Dragonbane Quickstart): the adventure of the quickstart booklet as an adventure pack, the places of its tower as scenes, its people and
monsters as NPCs, its scoring as a rules page, and its pre-generated heroes. The rules the booklet repeats are the core rulebook's, which the system pack has in full.
"""

from ... import packs
from .. import adventure, grid
from . import heroes
from ..pages import clean as clean_title

NAME = "The Sinking Tower"
KIND = "adventure"
PACK = "sinking-tower"
SYSTEM = "dragonbane"
PRINTINGS = {"e60b2569a542372c": "the quickstart booklet"}
# What the booklet holds that is not the adventure.
RULES = ("Introduction", "1. The Basic Rules", "2. Combat & Damage", "3. Monsters", "4. Magic")


def recognizes(book):
    return book.fingerprint()[:16] in PRINTINGS


def build(pack):
    book = pack.book
    chapter = book.find("5. The Sinking Tower")
    pack.adventure.update({"title": clean_title(chapter.title), "system": SYSTEM, "summary": f"{clean_title(chapter.title)}, from your copy of the quickstart booklet.", "start": "opening",
                           "source": book.manifest.get("source", "")})
    _scenes(pack, chapter)
    _scoring(pack, chapter.find("Scoring"))
    heroes.build(pack)
    for title in RULES:
        section = book.find(title)
        pack.item(f"book_{packs.slug(title)}", clean_title(title), "mechanic", section.pages, [], status="skipped",
                  note="The booklet's own short version of the rules: the core rulebook's pack has them in full.")
    maps = book.find("Player Maps")
    pack.item("player_maps", "Player maps", "component", maps.pages, [], status="skipped", note="Pictures of the maps for the players to look at: the places' own words are the scenes.")
    front = [page for page in sorted(book.by_page) if 0 < page < min(section.page for section in book.sections) and book.by_page[page]]
    if front:
        pack.item("front_matter", "Cover and credits", "other", front, [], status="skipped", note="The cover, the credits and what is in the booklet.")


def _scenes(pack, chapter):
    """The opening, which holds the situation and the guidelines for the GM, and then the places of the tower."""
    book = pack.book
    opening, situation, guidelines = chapter.find("Adventure Opening"), chapter.find("The Situation"), chapter.find("Guidelines for Convention Play")
    found = adventure.scenes(pack, "tower", chapter, "tower", situation=False)
    both = sorted([*situation.lines(own=True), *guidelines.lines(own=True)], key=lambda line: line["n"])
    words = (adventure.blocks(book, opening.lines(own=True)) + adventure.child_blocks(pack, opening) + [("text", "**The Situation**")] + adventure.blocks(book, both)
             + adventure.child_blocks(pack, guidelines))
    scenes = pack.chapter("tower")["scenes"]
    pack.chapter("tower")["scenes"] = {"opening": {"title": "The Sinking Tower", "source": f"p. {opening.page}", "exits": {found[0].id: f"Into the tower: {found[0].name}"}}, **scenes}
    pack.file("scenes/opening.md", adventure.scene_file(adventure.mend(book, words), [], {}, adventure.table_pages(pack)))
    pack.item("place_opening", "The situation, the guidelines and the adventure opening", "place", [*situation.pages, *guidelines.pages, *opening.pages], ["scenes/opening"])


def _scoring(pack, section):
    """The scoring a convention table plays for, as a rules page: what it says, then each thing that scores and where, with its points."""
    book = pack.book
    lines = [line for line in section.lines(own=True) if line["page"] == section.page]
    header, rows = grid.read(lines, book.glue)
    intro = [text for style, text in adventure.blocks(book, [line for line in lines if line["size"] >= 10]) if style == "text"]
    page = ["# Scoring", "Search: scoring, score, points, convention play, tournament", "", *[f"{text}\n" for text in intro],
            *[f"- {row['cells'][0]} ({row['cells'][1]}): {row['cells'][2]}" for row in rows if row["cells"][0] and row["cells"][2]], "", f"Source: {pack.name}, PDF p. {section.page}"]
    pack.file("rules/scoring.md", "\n".join(page))
    pack.item("scoring", "Scoring", "mechanic", [section.page], ["rules/scoring.md"])
