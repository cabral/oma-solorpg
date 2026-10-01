"""A page as lines with their place and style, and the book's bookmarks with where each points.

`solo extract` writes these beside the text (layout/0042.json and outline.json) for the
importers in solo/books/: a book that has bookmarks for every spell, ability and table
can be read by a program, where text alone has lost which column a line was in and
which lines were a sidebar's. This is the only part of the importers that needs PyMuPDF;
solo/sections.py reads the files back with the standard library.

A line is {x0, y0, x1, y1, text, size, font, color, col, words}, in reading order: `col` is 0
for the left column, 1 for the right and 2 for a line that spans the page. `size`, `font` and
`color` are the style most of its characters have; a line with more than one style (a bold
label, then the text) also has `spans`: [[text, font, size, color], ...]. `words` is
[[x0, x1], ...], one per word of `text.split()`. A running head or footer is marked `running`.
Coordinates are the page's, origin top left, in points.
"""


def reading_order(blocks, rect, bbox=lambda block: block[:4]):
    """[(block, column)] in the order a person reads the page. A block that spans the page
    (a heading, a table, a full-width box) splits it into bands; inside a band the left
    column is read before the right. `column` is 0 (left), 1 (right) or 2 (spans the page)."""
    middle = (rect.x0 + rect.x1) / 2
    ordered, band = [], []

    def flush():
        band.sort(key=lambda entry: (entry[1], bbox(entry[0])[1], bbox(entry[0])[0]))
        ordered.extend(band)
        band.clear()

    for block in sorted(blocks, key=lambda block: (bbox(block)[1], bbox(block)[0])):
        x0, _, x1, _ = bbox(block)
        if x0 < middle - 10 and x1 > middle + 10:  # crosses the gutter: spans the page
            flush()
            ordered.append((block, 2))
        else:
            band.append((block, int(x0 >= middle)))
    flush()
    return ordered


def page_layout(page, number, running=frozenset(), form=str):
    """One page's lines in reading order. `running` holds the forms of the headers and
    footers (as `form` writes them) that the extract took out of the text; the first and last
    two lines of the page that match are marked so a reader can skip them."""
    blocks = [b for b in page.get_text("rawdict")["blocks"] if b["type"] == 0]
    lines = []
    for block, column in reading_order(blocks, page.rect, lambda b: b["bbox"]):
        for line in block["lines"]:
            spans = [(span, "".join(char["c"] for char in span["chars"])) for span in line["spans"]]
            text = "".join(text for _, text in spans).replace("\xa0", " ")
            if text.strip():
                dominant = max(spans, key=lambda entry: len(entry[1].strip()))[0]
                entry = {"x0": round(line["bbox"][0], 1), "y0": round(line["bbox"][1], 1), "x1": round(line["bbox"][2], 1),
                         "y1": round(line["bbox"][3], 1), "text": text, "size": round(dominant["size"], 1),
                         "font": dominant["font"], "color": dominant["color"], "col": column,
                         "words": _words([char for span, _ in spans for char in span["chars"]])}
                styles = [(text, span["font"], round(span["size"], 1), span["color"]) for span, text in spans if text]
                if len({style[1:] for style in styles}) > 1:
                    entry["spans"] = [list(style) for style in styles]
                lines.append(entry)
    edge = lines[:2] + lines[-2:] if len(lines) > 4 else lines
    for entry in edge:
        if running and form(entry["text"]) in running:
            entry["running"] = True
    return {"page": number, "width": round(page.rect.width, 1), "height": round(page.rect.height, 1), "lines": lines}


def _words(chars):
    """[[x0, x1], ...]: where each word of the line starts and ends, in the order of text.split(),
    so a table's cells that the PDF set in one line can be cut apart at the gaps."""
    words, current = [], None
    for char in chars:
        if char["c"].isspace():
            current = None
        elif current is None:
            current = [round(char["bbox"][0], 1), round(char["bbox"][2], 1)]
            words.append(current)
        else:
            current[1] = round(char["bbox"][2], 1)
    return words


def outline(doc):
    """The bookmarks as [{level, title, page, x, y}]: where each one points, on the page, in
    the page's own coordinates (y from the top); x and y are None for a bookmark that names a
    page and no place on it. One to nowhere is left out."""
    found = []
    for level, title, number, where in doc.get_toc(simple=False):
        if 1 <= number <= doc.page_count:
            point = where.get("to")
            x, y = (None, None) if point is None else _moved(doc[number - 1].transformation_matrix, point.x, point.y)
            found.append({"level": level, "title": " ".join(title.split()), "page": number,
                          "x": None if x is None else round(x, 1), "y": None if y is None else round(y, 1)})
    return found


def _moved(matrix, x, y):
    return matrix.a * x + matrix.c * y + matrix.e, matrix.b * x + matrix.d * y + matrix.f
