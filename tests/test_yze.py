"""The d6-pool family through the same campaign code as Dragonbane."""

import unittest

from helpers import FIXTURES, CampaignTest, Dice

from solo import campaign


class YearZeroTest(CampaignTest):
    system = FIXTURES / "yze" / "system"
    adventure = FIXTURES / "yze" / "adventure"
    character = FIXTURES / "yze" / "rook.toml"

    def test_pool_counts_sixes_and_a_stress_one_rolls_panic(self):
        with self.session() as c:
            # agility 4, mobility 2, stress 1; the stress die shows 1, then panic is 1d6+1
            event = c.check("mobility", rng=Dice(6, 2, 3, 4, 6, 5, 1, 5))
            panic = [e for e in c.events if e["type"] == "table"][-1]
        sizes = {g["name"]: len(g["rolls"]) for g in event["outcome"]["groups"]}
        self.assertEqual(sizes, {"base": 4, "skill": 2, "stress": 1})
        self.assertEqual((event["outcome"]["successes"], event["outcome"]["triggers"]), (2, ["panic"]))
        self.assertEqual((panic["total"], panic["text"]), (6, "Keeps it together."))

    def test_push_raises_stress_and_adds_a_stress_die(self):
        with self.session() as c:
            c.check("observation", rng=Dice(2, 3, 4, 5, 3))
            pushed = c.push(rng=Dice(6, 2, 2, 2, 4, 3))
            stress = c.state["pc"]["tracks"]["stress"]["value"]
        self.assertEqual(stress, 2)
        self.assertTrue(campaign.describe(pushed).endswith("; STRESS +1"))
        self.assertEqual(len(pushed["outcome"]["groups"][2]["rolls"]), 2)
        self.assertEqual(pushed["outcome"]["successes"], 1)

    def test_banes_remove_skill_dice_before_base_dice(self):
        with self.session() as c:
            event = c.check("mobility", banes=3, rng=Dice(2, 2, 2, 2))
        sizes = {g["name"]: len(g["rolls"]) for g in event["outcome"]["groups"]}
        self.assertEqual(sizes, {"base": 3, "skill": 0, "stress": 1})


if __name__ == "__main__":
    unittest.main()
