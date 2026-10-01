"""The treasure deck (DB_Treasure_Cards_v1.pdf) as the table `treasure`: a D40 for the forty cards, each a coin, a valuable, a thing to pick the kind of, or a
find with a danger in it. A result names the page of its card (`page`), and the audit reads it against that card alone.
"""

import re

from ...tomlwrite import Inline
from .. import cards, dice
from ..read import roll

NAME = "Dragonbane Treasure Cards"
PACK = "dragonbane-treasure-cards"
PRINTINGS = {"0c8dd96c20352f76": "version 1"}
_VALUE = re.compile(r"^(\d*D\d+)(?:\s*×\s*(\d+))?\s+(copper|silver|gold) coins$", re.I)
_CHOICES = re.compile(r"Roll (D\d+)[^.:]*[.:]?\s*(1:.*?)(?:\.\s|\.?$)")


def recognizes(book):
    return cards.fingerprint(book) in PRINTINGS


def extends(folder):
    return "dragonbane-rulebook" if (folder / "dragonbane-rulebook" / "system.toml").exists() else []


def build(pack):
    book = pack.book
    results = []
    for page, lines in cards.faces(book):
        results.append(Inline({"range": [len(results) + 1, len(results) + 1], "page": page, **_card(book, lines)}))
    pack.toml("tables/treasure.toml", {"name": "Treasure cards", "formula": dice.formula(len(results)), "source": f"pp. {results[0]['page']}-{results[-1]['page']} (a card every second page)", "results": results})
    pack.item("treasure_deck", f"The treasure deck: {len(results)} card faces", "table", [result["page"] for result in results], ["tables/treasure"],
              note="One die for the cards, drawn with replacement as the solo booklet has it (note the card, shuffle it back).")


def _card(book, lines):
    """What a card gives, from its words: coins that roll their own number, a valuable worth a roll of coins, one thing of several to choose among, or a find."""
    title, rest = cards.split(lines)
    name = title.capitalize()
    worth = _VALUE.match(rest[0]) if rest else None
    if worth and title.lower() == f"{worth.group(3).lower()} coins":
        return {"text": f"{{value}} {worth.group(3).lower()} coins", "roll": _dice(worth)}
    elif worth:
        return {"text": f"{name}, worth {{value}} {worth.group(3).lower()} coins", "roll": _dice(worth)}
    said = cards.sentence(book, rest)
    choices = _CHOICES.search(said)
    if choices:
        before, after = said[:choices.start()].strip(), said[choices.end():].strip()
        return {"text": " ".join(part for part in (f"{name}." if before or after else name, before, after) if part), "choices": [item.strip(" ,.") for item in re.split(r"\s*\d+:\s*", choices.group(2)) if item.strip(" ,.")]}
    card = {"text": f"{name}. {said}"}
    dice_in = re.search(r"\b(\d*D\d+) damage", said)
    if dice_in:
        card.update({"text": card["text"].replace(dice_in.group(1), "{value}", 1), "roll": roll(dice_in.group(1))})
    return card


def _dice(found):
    expression = roll(found.group(1))
    return f"{expression}x{found.group(2)}" if found.group(2) else expression
