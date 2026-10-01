"""`solo compare`: two system packs side by side, to see what a pack built from a book (`solo import book`) does differently from one an agent wrote
from the same book, before one replaces the other.

The data is compared as the engine loads it: every table, creature, spell, the numbers of system.toml, creation and gear, key by key. The rules pages
are compared by name and by words, since the two packs may well word them alike and name them otherwise.
"""

import re
from pathlib import Path

from . import SoloError, packs

# The folders of one file per entry, and the files of one whole.
_FOLDERS = ("tables", "bestiary", "spells", "characters")
_FILES = ("system.toml", "creation.toml", "gear.toml")


def compare(a, b):
    """{area: {"same": n, "different": [(name, [what differs]...)], "only_a": [...], "only_b": [...]}} for two pack folders."""
    a, b = Path(a).expanduser(), Path(b).expanduser()
    for folder in (a, b):
        if not (folder / "system.toml").exists():
            raise SoloError(f"{folder} is not a system pack (no system.toml)")
    found = {name: _whole(a / name, b / name) for name in _FILES}
    for folder in _FOLDERS:
        found[folder] = _entries(a / folder, b / folder)
    found["rules"] = _pages(a / "rules", b / "rules")
    return found


def _whole(a, b):
    """One file against another, key by key."""
    one, two = (packs.load_data(path) if path.exists() else {} for path in (a, b))
    return {"same": int(one == two), "different": [("", _walk(one, two))] if one != two else [], "only_a": [], "only_b": []}


def _entries(a, b):
    """The files of a folder, entry by entry."""
    one = {path.stem: path for path in sorted(a.glob("*.toml"))}
    two = {path.stem: path for path in sorted(b.glob("*.toml"))}
    different = [(name, _walk(packs.load_data(one[name]), packs.load_data(two[name]))) for name in one if name in two and packs.load_data(one[name]) != packs.load_data(two[name])]
    return {"same": sum(1 for name in one if name in two) - len(different), "different": different, "only_a": sorted(set(one) - set(two)), "only_b": sorted(set(two) - set(one))}


def _pages(a, b):
    """Rules pages: the same page is the same title; its words are compared with the spacing and the Search and Source lines left out."""
    def read(folder):
        pages = {}
        for path in sorted(folder.glob("*.md")) if folder.exists() else []:
            text = path.read_text(encoding="utf-8").splitlines()
            body = " ".join(line for line in text[1:] if not line.startswith(("Search:", "Source:")))
            pages[text[0].removeprefix("# ").strip().lower()] = " ".join(body.split())
        return pages
    one, two = read(a), read(b)
    different = [(title, ["the words differ"]) for title in one if title in two and one[title] != two[title]]
    return {"same": sum(1 for title in one if title in two) - len(different), "different": different, "only_a": sorted(set(one) - set(two)), "only_b": sorted(set(two) - set(one))}


def _walk(one, two, path=""):
    """What differs between two loaded values, as lines: a key only one has, or a value that isn't the same."""
    if isinstance(one, dict) and isinstance(two, dict):
        found = []
        for key in sorted(set(one) | set(two), key=str):
            where = f"{path}{key}"
            if key not in one:
                found.append(f"only in the second: {where} = {_short(two[key])}")
            elif key not in two:
                found.append(f"only in the first: {where} = {_short(one[key])}")
            else:
                found += _walk(one[key], two[key], where + ".")
        return found
    if isinstance(one, list) and isinstance(two, list) and any(isinstance(item, dict) for item in [*one, *two]):
        found = [f"{path[:-1]}: {len(one)} entries / {len(two)}"] if len(one) != len(two) else []
        for at, (left, right) in enumerate(zip(one, two)):
            found += _walk(left, right, f"{path}{at}.")
        return found
    return [] if one == two else [f"{path[:-1]}: {_short(one)} / {_short(two)}"]


def _short(value, size=70):
    text = re.sub(r"\s+", " ", str(value))
    return text if len(text) <= size else text[:size - 1] + "…"


def render(found, names=("first", "second"), details=8):
    """The comparison as Markdown: a line for each area, then the differences (the first few of each, or all with details=0)."""
    lines = [f"# {names[0]} against {names[1]}", "", "| area | same | different | only in the first | only in the second |", "|---|---|---|---|---|"]
    for area, result in found.items():
        lines.append(f"| {area} | {result['same']} | {len(result['different'])} | {len(result['only_a'])} | {len(result['only_b'])} |")
    for area, result in found.items():
        if result["different"] or result["only_a"] or result["only_b"]:
            lines += ["", f"## {area}"]
            for name, what in (result["different"] if not details else result["different"][:details]):
                lines += [f"- {name or area}:"] + [f"  - {line}" for line in (what if not details else what[:details])]
            lines += [f"- only in the first: {', '.join(result['only_a'])}"] if result["only_a"] else []
            lines += [f"- only in the second: {', '.join(result['only_b'])}"] if result["only_b"] else []
            hidden = len(result["different"]) - details if details else 0
            lines += [f"- and {hidden} more that differ"] if hidden > 0 else []
    return "\n".join(lines) + "\n"
