"""`solo import datasworn`: only what is under CC BY comes in, credited, and coming in again changes
nothing. The data is a small made-up ruleset in Datasworn's shape."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from helpers import FIXTURES, IRONSWORN
from test_cli import CliCase

from solo import SoloError, datasworn, packs

MINI = json.loads((FIXTURES / "mini_datasworn.json").read_text(encoding="utf-8"))


class DataswornImportTest(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.out = Path(folder.name) / "pack"
        self.report = datasworn.build(MINI, self.out)

    def names(self, folder):
        return sorted(path.stem for path in (self.out / folder).glob("*.toml"))

    def load(self, folder, name):
        return packs.load_data(self.out / folder / f"{name}.toml")

    def test_only_what_is_under_cc_by_comes_in(self):
        self.assertEqual(self.names("moves"), ["bruise", "face_danger", "finish", "rest"])  # not "borrowed": that one says NC-SA
        self.assertEqual(self.names("tables"), ["core_omen", "core_weather"])  # not "secret", and not the ask-the-oracle column
        self.assertEqual(self.names("assets"), ["scout"])
        self.assertEqual((self.report["moves"], self.report["tables"], self.report["assets"]), (4, 2, 1))
        self.assertEqual(self.report["left_out"], {"atlas": "1 (by-nc-sa/4.0)", "tables": "1 not under CC BY: core/secret"})

    def test_an_object_takes_the_license_of_what_holds_it_unless_it_says_its_own(self):
        data = copy.deepcopy(MINI)
        data["license"] = "https://creativecommons.org/licenses/by-nc-sa/4.0"
        del data["moves"]["adventure"]["contents"]["borrowed"]["_source"]["license"]
        data["moves"]["adventure"]["_source"] = {"license": "https://creativecommons.org/licenses/by/4.0"}
        with tempfile.TemporaryDirectory() as folder:
            datasworn.build(data, folder)
            # The collection is CC BY, the package is not; the move that has no license of its own follows the collection.
            self.assertEqual(sorted(p.stem for p in (Path(folder) / "moves").glob("*.toml")), ["borrowed", "bruise", "face_danger", "finish", "rest"])
            # The asset says CC BY itself, so it comes in though the package is NC-SA.
            self.assertEqual([path.stem for path in (Path(folder) / "assets").glob("*.toml")], ["scout"])

    def test_a_move_says_what_it_rolls_and_how_it_is_worded(self):
        danger, bruise = self.load("moves", "face_danger"), self.load("moves", "bruise")
        self.assertEqual((danger["kind"], danger["stats"], danger["category"], danger["source"]), ("action", ["edge", "iron"], "Adventure Moves", "Test Rulebook, p. 60"))
        self.assertNotIn("pick", danger)
        self.assertEqual((bruise["stats"], bruise["pick"], bruise["oracle"]), (["iron", "health"], "highest", ["core_omen"]))
        self.assertEqual(danger["text"].strip(), "When **you risk it**, roll +edge or +iron. Then Pay the Price.")
        self.assertIn("(roll it with solo table core_omen)", bruise["text"])
        self.assertEqual(danger["outcomes"], {"strong_hit": "You do it.", "weak_hit": "You do it, at a cost.", "miss": "You don't."})

    def test_the_moves_keep_the_books_order(self):
        self.assertEqual([self.load("moves", move)["order"] for move in ("face_danger", "bruise", "finish", "rest")], [0, 1, 2, 3])

    def test_a_progress_move_reads_a_track_and_a_move_without_a_roll_has_no_outcomes(self):
        finish, rest = self.load("moves", "finish"), self.load("moves", "rest")
        self.assertEqual((finish["kind"], finish["track"]), ("progress", "vow"))
        self.assertEqual((rest["kind"], "outcomes" in rest, "stats" in rest), ("none", False, False))

    def test_a_row_that_sends_you_on_says_where_and_how_often(self):
        omen = self.load("tables", "core_omen")
        self.assertEqual([row.get("then") for row in omen["results"]], [None, ["core_weather"], ["core_omen", "core_omen"]])
        self.assertEqual(omen["results"][0]["text"], "A **crow** watches. See Face Danger.")
        self.assertEqual((omen["formula"], omen["source"]), ("1d10", "Test Rulebook, p. 12"))
        self.assertEqual(self.load("tables", "core_weather")["formula"], "1d6")

    def test_an_asset_keeps_its_abilities_and_which_one_a_new_hero_has(self):
        scout = self.load("assets", "scout")
        self.assertEqual((scout["name"], scout["category"], scout["requirement"]), ("Scout", "Path", "You know the land."))
        self.assertEqual([(a.get("name"), a["enabled"]) for a in scout["abilities"]], [(None, True), ("Keen", False)])
        self.assertEqual(scout["abilities"][0]["text"], "When you Undertake a Journey, add +1.")

    def test_the_odds_of_the_ask_the_oracle_tables_are_reported_for_the_system_to_hold(self):
        self.assertEqual(self.report["odds"], {"likely": 75})

    def test_every_file_says_where_it_came_from_and_its_license(self):
        for folder in ("moves", "tables", "assets"):
            for path in (self.out / folder).glob("*.toml"):
                first = path.read_text(encoding="utf-8").splitlines()[0]
                self.assertTrue(first.startswith("# Generated by `solo import datasworn` from Test Rulebook by A. Writer, Datasworn 0.0.10: CC BY 4.0"), path)

    def test_the_import_runs_again_and_changes_nothing(self):
        before = {path: path.read_text(encoding="utf-8") for path in self.out.rglob("*.toml")}
        datasworn.build(MINI, self.out)
        self.assertEqual({path: path.read_text(encoding="utf-8") for path in self.out.rglob("*.toml")}, before)

    def test_a_file_that_is_someones_own_is_never_touched_and_a_stale_generated_one_goes(self):
        (self.out / "moves" / "house_rule.toml").write_text('name = "House rule"\n', encoding="utf-8")
        (self.out / "moves" / "face_danger.toml").write_text('name = "My Face Danger"\n', encoding="utf-8")  # yours: kept, though the import has one
        stale = self.out / "moves" / "retired.toml"
        stale.write_text("# Generated by `solo import datasworn` from an older book\nname = \"Retired\"\n", encoding="utf-8")
        datasworn.build(MINI, self.out)
        self.assertEqual(self.load("moves", "house_rule")["name"], "House rule")
        self.assertEqual(self.load("moves", "face_danger")["name"], "My Face Danger")
        self.assertFalse(stale.exists())

    def test_what_it_wrote_is_a_system_pack_the_engine_reads(self):
        with tempfile.TemporaryDirectory() as folder:
            pack = Path(folder) / "mini"
            pack.mkdir()
            (pack / "system.toml").write_text((IRONSWORN / "system.toml").read_text(encoding="utf-8"), encoding="utf-8")
            datasworn.build(MINI, pack)
            system = packs.load_system(pack)
            self.assertEqual(sorted(system["moves"]), ["bruise", "face_danger", "finish", "rest"])
            self.assertEqual(packs.validate(system), [])
            titles = [page["title"] for page in packs.engine_rules(system)]
            self.assertIn("Face Danger", titles)
            self.assertIn("Scout", titles)

    def test_it_refuses_what_it_was_not_written_for(self):
        for changes in ({"datasworn_version": "0.1.0"}, {"type": "expansion"}):
            with self.subTest(changes=changes), self.assertRaisesRegex(SoloError, "reads a Datasworn 0.0 ruleset"):
                datasworn.build({**MINI, **changes}, self.out)


class DataswornCommandTest(CliCase):
    def test_the_command_reports_what_came_in_and_what_stayed_out(self):
        source, out = self.tmp / "classic.json", self.tmp / "pack"
        source.write_text(json.dumps(MINI), encoding="utf-8")
        code, printed, err = self.solo("import", "datasworn", str(source), "--out", str(out))
        self.assertEqual(code, 0, err)
        self.assertIn("wrote 4 moves, 2 tables and 1 assets", printed)
        self.assertIn("left out (not under CC BY, or not read): atlas 1 (by-nc-sa/4.0)", printed)
        self.assertIn("likely 75", printed)


if __name__ == "__main__":
    unittest.main()
