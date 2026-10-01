"""The improvised weapon cards (DB_Improvised_Weapons_Cards_v1.pdf): a rules page for each card, the lines of what it does, and a page that lists them."""

import re

from ... import packs
from ...audit import spans
from .. import cards

NAME = "Dragonbane Improvised Weapons Cards"
PACK = "dragonbane-improvised-weapons"
PRINTINGS = {"6fb2471dfed8c296": "version 1"}


def recognizes(book):
    return cards.fingerprint(book) in PRINTINGS


def extends(folder):
    return "dragonbane-rulebook" if (folder / "dragonbane-rulebook" / "system.toml").exists() else []


def build(pack):
    book = pack.book
    made = []
    for page, lines in cards.faces(book):
        title, rest = cards.split(lines)
        name = cards.title(title.lower())
        said = []
        for line in rest:
            if line.startswith("✦") or not said:
                said.append([line.lstrip("✦")])
            else:
                said[-1].append(line)
        card_id = f"improvised_weapon_{packs.slug(name)}"
        pack.file(f"rules/{card_id}.md", "\n".join([f"# Improvised weapon: {name}", f"Search: {name.lower()}", "", *(f"- {cards.sentence(book, parts)}" for parts in said), "",
                                                    f"Source: {pack.name}, PDF p. {page}"]))
        pack.item(card_id, name, "mechanic", [page], [f"rules/{card_id}.md"])
        made.append((name, page))
    pack.file("rules/improvised_weapon_cards.md", "\n".join(["# Improvised weapon cards", "Search: improvised weapon card, improvised weapon cards, improvised weapon deck, scenery, environment, special attack", "",
                                                             f"The improvised weapon cards: {'; '.join(name for name, _ in made)}. Each has its own page (solo rule <its name>).", "",
                                                             f"Source: {pack.name}, PDF pp. {spans([page for _, page in made])}"]))
    pack.item("improvised_weapon_cards", "Improvised weapon cards", "mechanic", [page for _, page in made], ["rules/improvised_weapon_cards.md"])
