"""The repository holds no book: no run of words from a book's pages is in any file of it (the importers hold where things are, never what they say).

The books are only on the machine of someone who owns them, so this looks where `solo extract` leaves them (SOLO_HOME/sources, or SOLO_SOURCES, a folder of extracts)
and has nothing to check without them. A run is eight words long and has to read like prose (several of the little words every sentence has): labels and table headers ("Requirement: Word, gesture, casting time:
Action") are the game's own terms, and a pattern that has to name a phrase to find it (a regular expression) is kept short of eight words.
"""

import os
import re
import subprocess
import unittest
from pathlib import Path

from solo import library

RUN = 8
_WORDS = re.compile(r"[a-z0-9’']+")
_LITTLE = frozenset("the a an and or of to in on with you your is are it its if that this each can may must will as by for at from they their which when then any all not".split())


def runs(text):
    """The runs of RUN words in a text that read like prose."""
    words = _WORDS.findall(text.lower().replace("\u00ad", ""))
    found = (words[at:at + RUN] for at in range(len(words) - RUN + 1))
    return {" ".join(run) for run in found if sum(word in _LITTLE for word in run) >= 3}


def tracked():
    """Every file of the repository, committed or not (a new one is where a leak would be)."""
    out = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=library.REPO, capture_output=True, text=True, check=True).stdout
    return [library.REPO / name for name in out.splitlines() if name and (library.REPO / name).is_file()]


class NoBookTextTest(unittest.TestCase):
    def test_no_file_of_the_repository_has_a_run_of_words_from_a_book(self):
        folder = Path(os.environ.get("SOLO_SOURCES") or library.home() / "sources")
        pages = sorted(folder.glob("*/pages/*.txt")) if folder.is_dir() else []
        if not pages:
            self.skipTest("no extracted books here to look for")
        book = set()
        for page in pages:
            book |= runs(page.read_text(encoding="utf-8"))
        found = []
        for path in tracked():
            if path.suffix in (".png", ".jpg", ".svg", ".ico", ".woff", ".woff2", ".pdf"):
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            same = runs(text) & book
            if same:
                found.append(f"{path.relative_to(library.REPO)}: {len(same)} runs, e.g. {sorted(same)[0]!r}")
        self.assertEqual(found, [], "words of a book in the repository:\n" + "\n".join(found))


if __name__ == "__main__":
    unittest.main()
