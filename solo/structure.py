"""The regions a document layout model finds on each page: tables, pictures, captions,
headings, running heads, footnotes, body text. `solo extract` writes them beside the lines:

  structure/0042.json   {page, width, height, regions: [{kind, bbox, lines, ref, caption, class}]}

`kind` is the model's label (`table`, `picture`, `caption`, `section_header`, `title`, `text`,
`list_item`, `page_header`, `page_footer`, `footnote`, ...). `bbox` is [x0, y0, x1, y1] in the
page's points, origin top left, as in layout/0042.json. `lines` are the indices of the lines of
layout/0042.json the region covers, so an importer never intersects boxes itself. `ref` is the
model's own id for the region. A picture has `class` (`geographical_map`, `photograph`, `logo`,
`other`, ...) when the model classified it, and a table or a picture its `caption` text when the model
tied one to it.

The model is Docling (docs/INGESTION_PLAN.md says why), and this is the only module that
imports it, only inside `convert`, which runs in the ingest environment `make ingest-deps`
makes: a virtual environment of its own, since PyTorch and the models are hundreds of
megabytes nobody needs to play. `solo extract` starts `python -m solo.structure` there as a
subprocess and reads back what it wrote; the rest of solo stays the standard library and
PyMuPDF. Without the environment the extract is what it always was, and the manifest's
`structure` is null.

The text stays PyMuPDF's: a region only says which of the page's lines it holds. The
characters the audit reads back against a pack are the PDF's own.
"""

import json
import os
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

from . import SoloError

READER = "docling"
# The version make ingest-deps installs. Docling's labels and models move between versions;
# the schema above is this project's, so a new version is a change in this module only.
DOCLING = "2.150.0"
# Pictures rendered at this scale (200 dpi) when a later step crops them; the layout model
# reads the page at its own resolution whatever this is.
IMAGE_SCALE = 2.8
# A line belongs to a region when this much of its box is inside the region's.
COVERED = 0.5
# The picture classes that are maps. Docling's figure classifier (v2.5) has no plain "map":
# it tells a geographical one from a topographical one, and a dungeon's floor plan may land
# in either, or in "engineering_drawing" or "other". The measurement of step 1 says which.
MAP_CLASSES = ("geographical_map", "topographical_map")


def environment():
    """The ingest environment's folder: $SOLO_INGEST, else ~/.local/share/solo/ingest."""
    if os.environ.get("SOLO_INGEST"):
        return Path(os.environ["SOLO_INGEST"]).expanduser()
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local/share") / "solo" / "ingest"


def python():
    """The ingest environment's Python, or None when it isn't there."""
    found = environment() / "bin" / "python"
    return found if found.exists() else None


MISSING = ("no layout model: tables, pictures and running heads are found by the extract's own rules, as before. "
           "make ingest-deps installs Docling (CPU, a few hundred megabytes, outside the system Python) for structure/")


def read(pdf, out, width, say=None):
    """Run the layout model on `pdf` in the ingest environment and write `out`/structure/.
    Returns (the manifest's `structure` entry or None, a note for the player or None)."""
    interpreter = python()
    if interpreter is None:
        return None, MISSING
    pages = len(list((out / "layout").glob("*.json")))
    if say:
        say(f"reading the layout of {pages} pages with {READER} (a few seconds a page on a CPU)...")
    with tempfile.TemporaryDirectory() as folder:
        raw_path = Path(folder) / "structure.json"
        env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [str(Path(__file__).resolve().parent.parent), os.environ.get("PYTHONPATH")]))}
        started = time.monotonic()
        done = subprocess.run([str(interpreter), "-m", "solo.structure", str(pdf), str(raw_path)],
                              env=env, capture_output=True, text=True)
        seconds = round(time.monotonic() - started, 1)
        if done.returncode != 0 or not raw_path.exists():
            last = next((line for line in reversed(done.stderr.splitlines()) if line.strip()), f"exit code {done.returncode}")
            return None, f"the layout model failed ({last.strip()}): the extract is written without structure/"
        raw = json.loads(raw_path.read_text(encoding="utf-8"))
    folder = out / "structure"
    counts = Counter()
    for number, page in sorted((int(n), p) for n, p in raw["pages"].items()):
        layout_path = out / "layout" / f"{number:0{width}d}.json"
        lines = json.loads(layout_path.read_text(encoding="utf-8"))["lines"] if layout_path.exists() else []
        regions = attach(page["regions"], lines)
        counts.update(region["kind"] for region in regions)
        counts["map"] += sum(1 for region in regions if region.get("class") in MAP_CLASSES)
        (folder / f"{number:0{width}d}.json").write_text(
            json.dumps({"page": number, "width": page["width"], "height": page["height"], "regions": regions},
                       ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    entry = {"reader": raw["reader"], "version": raw["version"], "seconds": seconds,
             "pages": len(raw["pages"]), "tables": counts["table"], "pictures": counts["picture"], "maps": counts["map"]}
    return entry, None


def attach(regions, lines):
    """The regions with `lines`: the indices of the page's lines each one covers."""
    found = []
    for region in regions:
        held = [i for i, line in enumerate(lines) if covered(region["bbox"], line)]
        found.append({**region, "lines": held})
    return found


def covered(bbox, line):
    """Whether at least COVERED of the line's box is inside `bbox`. A line with no area
    (PyMuPDF gives one for a lone space) counts by its middle."""
    x0, y0, x1, y1 = bbox
    width, height = line["x1"] - line["x0"], line["y1"] - line["y0"]
    if width <= 0 or height <= 0:
        x, y = (line["x0"] + line["x1"]) / 2, (line["y0"] + line["y1"]) / 2
        return x0 <= x <= x1 and y0 <= y <= y1
    inside = max(0.0, min(x1, line["x1"]) - max(x0, line["x0"])) * max(0.0, min(y1, line["y1"]) - max(y0, line["y0"]))
    return inside >= COVERED * width * height


# Measuring ------------------------------------------------------------------------------
#
# Step 1 of docs/INGESTION_PLAN.md: before anything is built on the model, count on real
# books what it finds against what the extract and the inventories already know.

def measure(folder, inventory=None):
    """What the layout model found in an extract, against the extract's own tables and running
    heads and, given an inventory (audit.load_inventory's), the tables it lists."""
    folder = Path(folder).expanduser()
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if not manifest.get("structure"):
        raise SoloError(f"{folder} has no structure/: extract the book again with the layout model installed (make ingest-deps)")
    width = max(4, len(str(manifest["pages"])))
    pages, classes, disagree = {}, Counter(), []
    for path in sorted((folder / "structure").glob("*.json")):
        page = json.loads(path.read_text(encoding="utf-8"))
        pages[page["page"]] = page
        layout_path = folder / "layout" / f"{page['page']:0{width}d}.json"
        lines = json.loads(layout_path.read_text(encoding="utf-8"))["lines"] if layout_path.exists() else []
        running = {i for i, line in enumerate(lines) if line.get("running")}
        framed = {i for region in page["regions"] if region["kind"] in ("page_header", "page_footer") for i in region["lines"]}
        if running != framed:
            disagree.append(page["page"])
        classes.update(region.get("class") or "unclassified" for region in page["regions"] if region["kind"] == "picture")
    with_table = sorted(n for n, page in pages.items() if any(r["kind"] == "table" for r in page["regions"]))
    index = folder / "tables" / "index.json"
    own = json.loads(index.read_text(encoding="utf-8")) if index.exists() else []
    result = {
        "pages": len(pages),
        "seconds": manifest["structure"]["seconds"],
        "seconds_a_page": round(manifest["structure"]["seconds"] / max(1, len(pages)), 2),
        "tables": sum(1 for page in pages.values() for r in page["regions"] if r["kind"] == "table"),
        "table_pages": with_table,
        "extract_table_pages": sorted({entry["page"] for entry in own}),
        "running_disagreed": disagree,
        "pictures": sum(classes.values()),
        "picture_classes": dict(classes.most_common()),
        "map_pages": sorted(n for n, page in pages.items() if any(r.get("class") in MAP_CLASSES for r in page["regions"])),
    }
    if inventory is not None:
        tables = {item_id: item["pages"] for item_id, item in inventory["items"].items() if item.get("kind") == "table"}
        result["inventory_tables"] = len(tables)
        result["inventory_tables_missed"] = sorted(item_id for item_id, cited in tables.items() if not set(cited) & set(with_table))
    return result


def report(found):
    """measure()'s numbers as the lines `solo structure` prints."""
    lines = [f"{found['pages']} pages read in {found['seconds']} s ({found['seconds_a_page']} s a page)",
             f"tables: {found['tables']} on {len(found['table_pages'])} pages; the extract's own rules found tables on {len(found['extract_table_pages'])} pages"]
    only_model = sorted(set(found["table_pages"]) - set(found["extract_table_pages"]))
    only_rules = sorted(set(found["extract_table_pages"]) - set(found["table_pages"]))
    if only_model:
        lines.append(f"  only the model: pages {_pages(only_model)}")
    if only_rules:
        lines.append(f"  only the extract's rules: pages {_pages(only_rules)}")
    if "inventory_tables" in found:
        missed = found["inventory_tables_missed"]
        lines.append(f"inventory: {found['inventory_tables'] - len(missed)} of {found['inventory_tables']} tables are on a page the model found a table on")
        if missed:
            lines.append(f"  not found: {', '.join(missed)}")
    disagree = found["running_disagreed"]
    lines.append(f"running heads: the model and the extract's repetition test disagree on {len(disagree)} pages"
                 + (f": {_pages(disagree)}" if disagree else ""))
    classes = ", ".join(f"{name} {count}" for name, count in found["picture_classes"].items())
    lines.append(f"pictures: {found['pictures']}" + (f" ({classes})" if classes else ""))
    if found["map_pages"]:
        lines.append(f"  maps on pages {_pages(found['map_pages'])}")
    return lines


def _pages(numbers):
    """[3, 4, 5, 9] -> "3-5, 9"."""
    runs = []
    for n in numbers:
        if runs and n == runs[-1][1] + 1:
            runs[-1][1] = n
        else:
            runs.append([n, n])
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in runs)


# The ingest environment's side ----------------------------------------------------------
#
# Everything below runs under the ingest environment's Python, never the engine's.

def convert(pdf):
    """The layout model's regions for every page of `pdf`, in the extract's coordinates:
    {reader, version, pages: {n: {width, height, regions: [{kind, bbox, ref, caption?, class?}]}}}."""
    from importlib.metadata import version

    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling_core.types.doc import ContentLayer

    options = PdfPipelineOptions()
    options.do_ocr = False  # the text layer is the PDF's own: a scan is flagged by the extract, and OCR is ocrmypdf's job
    options.do_table_structure = True
    options.table_structure_options.do_cell_matching = True  # cells matched back onto the PDF's own text
    options.do_picture_classification = True
    options.generate_picture_images = True  # the classifier reads the picture's crop
    options.images_scale = IMAGE_SCALE
    models = Path(sys.prefix) / "models"  # where make ingest-deps fetched them; without, Docling downloads its own on first use
    if models.is_dir():
        options.artifacts_path = str(models)
    converter = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)})
    document = converter.convert(str(pdf)).document

    pages = {number: {"width": round(page.size.width, 1), "height": round(page.size.height, 1), "regions": []}
             for number, page in document.pages.items()}
    layers = {ContentLayer.BODY, ContentLayer.FURNITURE}
    for item, _ in document.iterate_items(with_groups=False, traverse_pictures=False, included_content_layers=layers):
        label = getattr(item.label, "value", str(item.label))
        for prov in item.prov:
            page = pages.get(prov.page_no)
            if page is None:
                continue
            box = prov.bbox.to_top_left_origin(page_height=document.pages[prov.page_no].size.height)
            region = {"kind": label, "bbox": [round(box.l, 1), round(box.t, 1), round(box.r, 1), round(box.b, 1)], "ref": item.self_ref}
            captions = [ref.resolve(document).text for ref in getattr(item, "captions", []) or []]
            if any(captions):
                region["caption"] = " ".join(text for text in captions if text)
            kind = _picture_class(item)
            if kind:
                region["class"] = kind
            page["regions"].append(region)
    return {"reader": READER, "version": version("docling"), "pages": {str(n): p for n, p in pages.items()}}


def _picture_class(item):
    meta = getattr(item, "meta", None)
    classification = getattr(meta, "classification", None) if meta is not None else None
    predictions = getattr(classification, "predictions", None) or []
    if not predictions:
        return None
    best = max(predictions, key=lambda p: p.confidence or 0)
    return best.class_name


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print("usage: python -m solo.structure <pdf> <out.json>  (run by solo extract in the ingest environment)", file=sys.stderr)
        return 2
    found = convert(Path(argv[0]))
    Path(argv[1]).write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
