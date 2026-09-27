"""A book's roll table, from its text into a pack's tables/<id>.toml.

Copying a table by hand is where an import goes wrong quietly: a range typed 4-5 for 4-6,
a row dropped at a page break, a result half-remembered. This reads the table the way
`solo extract` found it (a Markdown grid, tables/p0042-1.md) or as roll lines taken from a
page ("1-2 Frozen in place"), works out the dice from the header or the ranges, and writes
the table the engine reads. `solo validate` then checks the ranges cover every roll, and
`solo audit` that every result is on the page the inventory cites.
"""

import re
from pathlib import Path

from . import SoloError, packs

_DASH = r"[-‐-―−]"
_ROLL = re.compile(rf"^\s*(\d{{1,3}})(?:\s*{_DASH}\s*(\d{{1,3}}))?\s*[.:)]?\s+(\S.*)$")
_RANGE = re.compile(rf"^\s*(\d{{1,3}})(?:\s*{_DASH}\s*(\d{{1,3}}))?\s*[.:)]?\s*$")
_DIE = re.compile(r"^\s*(\d*)\s*[dD]\s*(\d+|%)\s*$")


def parse(text):
    """(formula or None, [{range, text}]) from Markdown table rows or roll lines."""
    lines = [line.rstrip() for line in text.splitlines()]
    if sum(1 for line in lines if line.strip().startswith("|")) >= 2:
        return _grid(lines)
    return _roll_lines(lines)


def _cells(line):
    return [re.sub(r"<br\s*/?>", " ", cell).strip() for cell in line.strip().strip("|").split("|")]


def _grid(lines):
    rows = [_cells(line) for line in lines if line.strip().startswith("|")]
    rows = [row for row in rows if not all(re.fullmatch(r":?-{2,}:?", cell) or not cell for cell in row)]
    header, body = rows[0], rows[1:]
    if _RANGE.match(header[0]) and not _DIE.match(header[0]):
        header, body = None, rows  # no header row: the first row is already a result
    formula = _formula_word(header[0]) if header else None
    results = []
    for row in body:
        found = _RANGE.match(row[0])
        if not found:
            if results and any(row[1:]):  # a result broken over two rows
                results[-1]["text"] += " " + " ".join(cell for cell in row[1:] if cell)
            continue
        parts = [cell for cell in row[1:]]
        text = parts[0] if parts else ""
        for name, cell in zip((header or [])[2:], parts[1:]):
            if cell:
                text += f"; {name}: {cell}" if name else f"; {cell}"
        results.append({"range": _span(found), "text": " ".join(text.split())})
    return formula, results


def _roll_lines(lines):
    formula, results = None, []
    for line in lines:
        found = _ROLL.match(line)
        if found:
            results.append({"range": _span(found), "text": " ".join(found.group(3).split())})
        elif results and line.strip():
            results[-1]["text"] += " " + " ".join(line.split())  # a result that runs onto the next line
        elif not results and line.strip():
            formula = formula or next((_formula_word(word) for word in re.split(r"[\s(),]+", line) if _formula_word(word)), None)
    return formula, results


def _span(match):
    low = int(match.group(1))
    high = int(match.group(2)) if match.group(2) else low
    # "00" on a d100 is a hundred.
    return [100 if low == 0 and match.group(1) == "00" else low, 100 if high == 0 and (match.group(2) or "") == "00" else high]


def _formula_word(word):
    found = _DIE.match(word or "")
    if not found:
        return None
    count, sides = found.group(1) or "1", found.group(2)
    if sides == "%":
        return "1d100"
    elif sides == "66" and count == "1":
        return "d66"
    return f"{count}d{sides}"


def guess_formula(results):
    """The dice a table's ranges were written for, when its header doesn't say."""
    values = [v for r in results for v in r["range"]]
    if not values:
        return None
    low, high = min(values), max(values)
    if low >= 11 and high <= 66 and all(1 <= v // 10 <= 6 and 1 <= v % 10 <= 6 for v in values):
        return "d66"
    if (low, high) == (2, 12):
        return "2d6"
    if (low, high) == (3, 18):
        return "3d6"
    return f"1d{high}"


def write(text, out, name=None, formula=None, source=None):
    """Parse the table and write it as TOML. Returns (path, problems): the file is written
    either way, and the problems (ranges that don't cover the dice, a row read twice) say
    what to fix in it by looking at the book's page."""
    found_formula, results = parse(text)
    if not results:
        raise SoloError("no table rows found: expected Markdown rows (| 1-2 | text |) or lines like \"1-2 Frozen in place\"")
    formula = formula or found_formula or guess_formula(results)
    out = Path(out)
    name = name or out.stem.replace("_", " ").capitalize()
    lines = [f"name = {packs.toml_string(name)}", f"formula = {packs.toml_string(formula)}"]
    if source:
        lines.append(f"source = {packs.toml_string(source)}")
    lines.append("results = [")
    lines += [f"  {{ range = [{r['range'][0]}, {r['range'][1]}], text = {packs.toml_string(r['text'])} }}," for r in results]
    lines.append("]")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    problems = packs._validate_table(f"table {out.stem}", {"formula": formula, "results": results})
    return out, problems
