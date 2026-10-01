"""`solo compare`: two packs, area by area."""

import tempfile
import unittest
from pathlib import Path

from solo import SoloError, compare


def pack(folder, system="format = 1\n", tables=(), rules=()):
    folder.mkdir(parents=True)
    (folder / "system.toml").write_text(system, encoding="utf-8")
    (folder / "tables").mkdir()
    for name, text in tables:
        (folder / "tables" / f"{name}.toml").write_text(text, encoding="utf-8")
    (folder / "rules").mkdir()
    for name, text in rules:
        (folder / "rules" / f"{name}.md").write_text(text, encoding="utf-8")
    return folder


class CompareTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.tmp = Path(folder.name)

    def test_tables_that_agree_differ_by_a_row_or_belong_to_one_pack_are_told_apart(self):
        rows = 'name = "T"\nformula = "1d2"\nresults = [{ range = [1, 1], text = "a" }, { range = [2, 2], text = "b" }]\n'
        first = pack(self.tmp / "a", tables=[("same", rows), ("moved", rows), ("mine", rows)])
        second = pack(self.tmp / "b", tables=[("same", rows), ("moved", rows.replace('text = "b"', 'text = "c", kind = "fire"')), ("theirs", rows)])
        found = compare.compare(first, second)["tables"]
        self.assertEqual((found["same"], found["only_a"], found["only_b"]), (1, ["mine"], ["theirs"]))
        self.assertEqual(found["different"], [("moved", ["only in the second: results.1.kind = fire", "results.1.text: b / c"])])

    def test_the_numbers_of_system_toml_are_compared_key_by_key_and_pages_by_title_and_words(self):
        first = pack(self.tmp / "a", "format = 1\n[time]\nround = 10\n", rules=[("x", "# Fear\nSearch: fear\n\nBe afraid.\n\nSource: A\n"), ("y", "# Rest\nSearch: rest\n\nSleep.\n")])
        second = pack(self.tmp / "b", "format = 1\n[time]\nround = 6\n", rules=[("z", "# Fear\nSearch: fright, panic\n\nBe   afraid.\n\nSource: B\n"), ("w", "# Rest\n\nSleep well.\n")])
        found = compare.compare(first, second)
        self.assertEqual(found["system.toml"]["different"], [("", ["time.round: 10 / 6"])])
        self.assertEqual((found["rules"]["same"], found["rules"]["different"]), (1, [("rest", ["the words differ"])]))

    def test_a_folder_that_is_not_a_pack_is_refused_and_the_report_is_markdown(self):
        with self.assertRaisesRegex(SoloError, "not a system pack"):
            compare.compare(self.tmp, self.tmp)
        first = pack(self.tmp / "a")
        report = compare.render(compare.compare(first, pack(self.tmp / "b")), ("one", "two"))
        self.assertTrue(report.startswith("# one against two\n\n| area | same |"))


if __name__ == "__main__":
    unittest.main()
