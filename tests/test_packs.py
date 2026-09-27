import copy
import tempfile
import tomllib
import unittest
from pathlib import Path

from helpers import DRAGONBANE, RED_TUSK

from solo import SoloError, packs


class LoadingTest(unittest.TestCase):
    def test_example_packs_validate(self):
        self.assertEqual(packs.validate(packs.load_system(DRAGONBANE), packs.load_adventure(RED_TUSK)), [])

    def test_authored_toml_extends_generated_json(self):
        npc = packs.load_adventure(RED_TUSK)["npcs"]["orc_leader"]
        self.assertEqual(npc["name"], "Grukk Red Tusk")
        self.assertEqual(npc["stats"]["hp"], 16)

    def test_skills_are_normalised(self):
        skills = packs.load_system(DRAGONBANE)["skills"]
        self.assertEqual(skills["hunting_fishing"], {"attribute": "agl", "name": "Hunting & Fishing", "untrained": True})
        self.assertEqual(skills["spot_hidden"]["name"], "Spot hidden")

    def test_scene_files_stay_inside_the_adventure(self):
        adventure = packs.load_adventure(RED_TUSK)
        self.assertIn("::: gm", packs.scene_text(adventure, "gate"))
        for escape in ("../../README.md", "/etc/hostname"):
            with self.subTest(file=escape):
                tampered = copy.deepcopy(adventure)
                tampered["scenes"]["gate"]["file"] = escape
                with self.assertRaisesRegex(SoloError, "inside the adventure folder"):
                    packs.scene_text(tampered, "gate")
                problems = packs.validate(packs.load_system(DRAGONBANE), tampered)
                self.assertIn("scene gate: its file must be inside the adventure folder", problems)

    def test_toml_strings_round_trip(self):
        for text in ("Ragna 🐉", 'quote " and \\ backslash', "tab\tand bell\x07"):
            with self.subTest(text=text):
                self.assertEqual(tomllib.loads(f"title = {packs.toml_string(text)}")["title"], text)

    def test_rules_search_prefers_exact_titles_then_falls_back_to_text(self):
        with tempfile.TemporaryDirectory() as folder:
            rules = Path(folder)
            (rules / "sneaking.md").write_text("# Sneaking\nRoll to move unseen.")
            (rules / "sneak_attack.md").write_text("# Sneak Attack\nA boon when unseen.")
            (rules / "pushing.md").write_text("# Pushing\nReroll for a condition.")
            self.assertEqual([p["title"] for p in packs.search_rules([rules], "sneaking")[0]], ["Sneaking"])
            self.assertEqual(len(packs.search_rules([rules], "sneak")[0]), 2)
            self.assertEqual(packs.search_rules([rules], "condition"), ([{"title": "Pushing", "text": "# Pushing\nReroll for a condition."}], "text"))


class ValidationTest(unittest.TestCase):
    def test_catches_broken_references(self):
        system = packs.load_system(DRAGONBANE)
        adventure = copy.deepcopy(packs.load_adventure(RED_TUSK))
        adventure["scenes"]["road"]["exits"]["nowhere"] = "A missing door"
        adventure["scenes"]["hall"]["branches"].append({"when": "npc.ghost.fate == 'dead'", "text": "Boo."})
        adventure["clocks"]["dark_ritual"]["advance"].append("time:fortnight")
        adventure["tables"]["omens"]["results"].pop()
        problems = "\n".join(packs.validate(system, adventure))
        for expected in ("exit to unknown scene nowhere", "unknown npc ghost", "unknown time unit", "no result for 6"):
            self.assertIn(expected, problems)


class ConditionTest(unittest.TestCase):
    state = {
        "scene": "hall",
        "visited": ["road", "hall"],
        "npcs": {"grukk": {"fate": "alive", "attitude": 1}},
        "factions": {"orcs": {"standing": -1}},
        "promises": {"help": {"status": "kept"}},
        "facts": {"hall.alarm": True},
        "clocks": {"ritual": {"value": 4}},
        "pc": {"tracks": {"hp": {"value": 3}}, "conditions": ["scared"]},
    }

    def test_expressions(self):
        cases = {
            "npc.grukk.fate == 'alive' and promise.help == 'kept'": True,
            "npc.grukk.attitude >= friendly": True,
            "faction.orcs >= neutral": False,
            "fact.hall.alarm and not visited.cellar": True,
            "clock.ritual >= 4 and scene == 'hall'": True,
            "'scared' in pc.conditions and pc.hp < 5": True,
            "promise.unknown == 'kept'": False,
            "npc.nobody.attitude > hostile": False,
            "scene in ['cellar', 'cave']": False,
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(packs.evaluate(text, self.state), expected)

    def test_only_reading_state_is_allowed(self):
        for text in ("__import__('os')", "npc.grukk.fate.upper()", "x = 1", "lambda: 1", "secret.value"):
            with self.subTest(text=text), self.assertRaises(SoloError):
                packs.compile_condition(text)

    def test_comparing_an_attitude_with_text_explains_itself(self):
        with self.assertRaisesRegex(SoloError, "bare names"):
            packs.evaluate("npc.grukk.attitude >= 'friendly'", self.state)


if __name__ == "__main__":
    unittest.main()
