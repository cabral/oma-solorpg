"""The adventure cards (DB_Adventure_Cards_v1.pdf): each a place a rumor tells of, as a result of the table `adventure_cards` (a D for the cards, with the page of each)."""

from ...tomlwrite import Inline
from .. import cards, dice

NAME = "Dragonbane Adventure Cards"
PACK = "dragonbane-adventure-cards"
PRINTINGS = {"6f5f18e870238f41": "version 1"}


def recognizes(book):
    return cards.fingerprint(book) in PRINTINGS


def extends(folder):
    return "dragonbane-rulebook" if (folder / "dragonbane-rulebook" / "system.toml").exists() else []


def build(pack):
    book = pack.book
    results = []
    for page, lines in cards.faces(book):
        name, rest = cards.split(lines)
        results.append(Inline({"range": [len(results) + 1, len(results) + 1], "page": page, "text": f"{cards.title(name.lower())}. {cards.sentence(book, rest)}"}))
    pack.toml("tables/adventure_cards.toml", {"name": "Adventure cards", "formula": dice.formula(len(results)), "source": f"pp. {results[0]['page']}-{results[-1]['page']} (a card every second page)", "results": results})
    pack.item("adventure_cards", f"The adventure cards: {len(results)} card faces", "table", [result["page"] for result in results], ["tables/adventure_cards"])
