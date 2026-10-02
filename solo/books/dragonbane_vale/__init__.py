"""The Secret of the Dragon Emperor (DB_Adventures_v2.pdf): the campaign of the Adventure Book as one adventure pack. An opening scene on the road, the village of Outskirt
as the hub, and the adventure sites round it, each its own chapter of the pack, reached from Outskirt and leading back to it. The book's introduction and its notes on
journeys are rules pages, its random events and encounters tables.
"""

import re

from ... import packs
from .. import adventure, pages
from ..pages import clean as clean_title

NAME = "The Secret of the Dragon Emperor"
KIND = "adventure"
PACK = "dragon-emperor"
SYSTEM = "dragonbane"
PRINTINGS = {"0b1ef1668d334426": "the second printing"}
# The chapters that are sites, by their bookmark, and the word their scenes' ids start with.
SITES = {"5. Riddermound": "riddermound", "6. Bothild’s Lode": "bothild", "7. Temple of the Purple Flame": "temple", "8. Tower of Sighs": "sighs", "9. Oracle Cave": "oracle",
         "10. Troll’s Spire": "spire", "11. Dead Eyes Cave": "deadeyes", "12. Fort Malus": "malus", "13. The Village of the Day Before": "village", "14. Road’s End Inn": "inn",
         "15. The Isle of Mist": "isle"}
HUB = ("3. Outskirt", "outskirt", "3")


def recognizes(book):
    return book.fingerprint()[:16] in PRINTINGS


def build(pack):
    book = pack.book
    pack.adventure.update({"title": NAME, "system": SYSTEM, "summary": f"{NAME}, from your copy of the Adventure Book.", "source": book.manifest.get("source", "")})
    _tables(pack)
    _rules(pack)
    arrival = _outskirt(pack)
    pack.adventure["start"] = _opening(pack, arrival)
    _journeys(pack)
    for title, prefix in SITES.items():
        _site(pack, title, prefix)
    maps = sorted({page for section in book.sections if section.title.startswith("Map:") for page in section.pages})
    pack.item("maps", "Maps", "component", maps, [], status="skipped", note="Pictures of the maps: the places' own words, and the ways between them, are the scenes.")


def _within(section):
    return {part.number for part in (section, *section.subtree())}


def _tables(pack):
    """Every table of the book, before any scene is written: a scene sends its reader to a table by its page, and the table may be in a later chapter."""
    book = pack.book
    adventure.tables_under(pack, book.find("1. Introduction"), "vale")
    for title, prefix in (("3. Outskirt", "outskirt"), ("4. Journeys", "journeys"), *SITES.items()):
        adventure.tables_under(pack, book.find(title), prefix)


def _rules(pack):
    """The introduction, and the notes on journeys, as rules pages: the campaign's background for the GM to look up."""
    book = pack.book
    keep = _within(book.find("1. Introduction")) | _within(book.find("4. Journeys"))
    maps = {section.number for section in book.sections if section.title.startswith("Map:")}
    pages.build(pack, (), skip=lambda section: section.number not in keep or section.number in maps or section.title.startswith("Table:"), listings=("Contents", "Index"))


def _opening(pack, after):
    """The opening on the road, one scene: the situation and every part of it, the dying man, the ambush and what comes after it."""
    chapter = pack.book.find("2. Opening Scene")
    words, crowd = adventure.background(pack, chapter.find("The Situation"), "opening", pack.facts.setdefault("npc_ids", set()))
    parts = [child for child in chapter.children if child.title != "The Situation" and not child.title.startswith("Map:")]
    scene = adventure.scene_of(pack, "chapter_02_opening", "opening", re.sub(r"^\d+\.\s*", "", chapter.title), parts, "opening", first=words, after=(after, "the village of Outskirt"), crowd=crowd)
    pack.item("opening_situation", "The opening scene's situation", "place", chapter.find("The Situation").pages, [f"scenes/{scene}"])
    return scene


def _outskirt(pack):
    """The village: its arrival scene, with what the book says of the village and its random events and rumors, and its places, all open on the village square."""
    book = pack.book
    chapter = book.find(HUB[0])
    tables = list(adventure.tables_under(pack, chapter, HUB[1]).values())
    words, crowd = adventure.background(pack, chapter.find("The Situation"), HUB[1], pack.facts.setdefault("npc_ids", set()))
    found = adventure.scenes(pack, "chapter_03_outskirt", chapter, HUB[1], hub=HUB[2], situation=False)
    arrival = adventure.scene_of(pack, "chapter_03_outskirt", "outskirt_arrival", "Arrival", [chapter.find("Arrival")], HUB[1], first=words, after=(found[0].id, found[0].name), tables=tables, crowd=crowd)
    spec = pack.chapter("chapter_03_outskirt")["scenes"]
    pack.chapter("chapter_03_outskirt")["scenes"] = {arrival: spec.pop(arrival), **spec}
    pack.facts["hub"] = next(place.id for place in found if HUB[2] in place.keys)
    pack.item("outskirt_situation", "The situation in Outskirt", "place", chapter.find("The Situation").pages, [f"scenes/{arrival}"])
    return arrival


def _journeys(pack):
    """The random encounters of the journeys, on the village square, from where the heroes set out."""
    chapter = pack.book.find("4. Journeys")
    tables = list(adventure.tables_under(pack, chapter, "journeys").values())
    pack.chapter("chapter_04_journeys").setdefault("scenes", {})[pack.facts["hub"]] = {"tables": tables}


def _site(pack, title, prefix):
    """An adventure site: its places as scenes, its first reached from the village square and leading back to it."""
    chapter = pack.book.find(title)
    number = int(re.match(r"(\d+)\.", title).group(1))
    chapter_id = f"chapter_{number:02d}_{prefix}"
    found = adventure.scenes(pack, chapter_id, chapter, prefix)
    hub = pack.facts["hub"]
    spec = pack.chapter(chapter_id)["scenes"]
    spec[found[0].id]["exits"] = {**spec[found[0].id].get("exits", {}), hub: "Leave, back to Outskirt"}
    spec[hub] = {"exits": {found[0].id: f"Journey to {clean_title(title)}"}}
    after = [child for child in chapter.children if child.title not in ("The Situation", "Locations") and not child.title.startswith(("Map:", "Table:"))]
    if after:
        last = adventure.scene_of(pack, chapter_id, f"{prefix}_{packs.slug(clean_title(after[0].title))}", clean_title(after[0].title), after, prefix)
        spec[found[-1].id]["exits"] = {**spec[found[-1].id].get("exits", {}), last: f"Onward, to {clean_title(after[0].title)}"}
