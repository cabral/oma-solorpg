"""Travel: shifts, the kilometers each covers, the pathfinder's roll, mishaps, the forced march and making camp.
Played on the made-up test rules (tests/fixtures/house): 12 kilometers a shift on foot, two shifts a day and a
third forced, on an adventure with no clocks to tick as the shifts pass."""

from helpers import FIXTURES, CampaignTest, Dice

from solo import SoloError


class Journey(CampaignTest):
    adventure = FIXTURES / "delve"

    def legs(self, c):
        return [(e["distance"], e["left"]) for e in c.events if e["type"] == "journey"]

    def test_a_journey_along_a_road_takes_a_shift_for_each_stretch_with_no_roll(self):
        with self.session() as c:
            c.journey(30, road=True)
            self.assertEqual(self.legs(c), [(12, 18), (12, 6), (6, 0)])  # the third shift is a forced march
            self.assertEqual(c.state["time"], 3 * 21600)
            self.assertEqual([e["type"] for e in c.events if e["type"] == "check"], [])

    def test_mounted_travel_covers_twice_the_ground(self):
        with self.session() as c:
            c.journey(24, mounted=True, road=True)
            self.assertEqual(self.legs(c), [(24, 0)])

    def test_off_the_road_the_pathfinder_rolls_each_shift_with_a_bane_for_having_no_map(self):
        with self.session() as c:
            c.journey(24, rng=Dice(2, 3, 2, 3))  # bushcraft 4 (INT 9), a bane: two dice, the worse counts
            rolls = [e for e in c.events if e["type"] == "check"]
            self.assertEqual([(e["banes"], e["outcome"]["result"], e["outcome"]["success"]) for e in rolls], [(1, 3, True), (1, 3, True)])
            self.assertEqual(self.legs(c), [(12, 12), (12, 0)])

    def test_a_map_takes_the_bane_away(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Map"]}}})
            c.journey(12, rng=Dice(3))
            roll = next(e for e in c.events if e["type"] == "check")
            self.assertEqual((roll["banes"], roll["boons"]), (0, 0))

    def test_a_spyglass_gives_a_boon_which_a_missing_map_cancels(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Spyglass"]}}})
            c.journey(12, rng=Dice(3))  # a bane and a boon make a normal roll: one die
            roll = next(e for e in c.events if e["type"] == "check")
            self.assertEqual((roll["banes"], roll["boons"]), (1, 1))

    def test_difficult_terrain_is_another_bane(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Map"]}}})
            c.journey(12, difficult=True, rng=Dice(2, 3))
            self.assertEqual(next(e for e in c.events if e["type"] == "check")["banes"], 1)

    def test_a_dragon_doubles_the_ground_that_shift(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Map"]}}})
            c.journey(24, rng=Dice(1))
            self.assertEqual(self.legs(c), [(24, 0)])

    def test_a_failed_roll_is_a_mishap_and_fog_halves_the_ground(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Map"]}}})
            c.journey(6, rng=Dice(19, 1))  # fails; the mishap table: fog, so half of 12 is covered: the 6 there were
            self.assertEqual(self.legs(c), [(6, 0)])
            self.assertEqual([e["type"] for e in c.events if e["type"] in ("check", "table")], ["check", "table"])

    def test_getting_lost_covers_nothing(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Map"]}}})
            c.journey(12, rng=Dice(19, 2, 3))  # lost: nothing; then a fine roll
            self.assertEqual(self.legs(c), [(0, 12), (12, 0)])

    def test_a_mishap_the_gm_must_run_stops_the_journey(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Map"]}}})
            c.journey(24, rng=Dice(19, 3))  # a beast: the journey stops for the GM, 12 of the 24 still to go
            self.assertEqual(self.legs(c), [(12, 12)])

    def test_a_third_shift_in_a_day_is_a_forced_march_and_nobody_goes_a_fourth(self):
        with self.session() as c:
            c.system["journey"]["shifts_per_day"] = 4
            c.journey(48, road=True)
            self.assertEqual([e.get("forced") for e in c.events if e["type"] == "journey"], [None, None, True])
            self.assertIn("exhausted", c.state["pc"]["conditions"])
            self.assertEqual(c.events[-1]["left"] if c.events[-1]["type"] == "journey" else None, 12)
            with self.assertRaisesRegex(SoloError, "walked as far as anyone does today"):
                c.journey(12, road=True)

    def test_a_new_day_starts_the_count_again(self):
        with self.session() as c:
            c.journey(24, road=True)
            c.commit({"time": {"shift": 1}})  # the day's third shift passes, and a new day begins
            c.journey(12, road=True)
            self.assertEqual([e["shifts"] for e in c.events if e["type"] == "journey"], [1, 2, 1])

    def test_an_exhausted_hero_cant_march_a_third_shift(self):
        with self.session() as c:
            c.commit({"pc": {"conditions": {"add": ["exhausted"]}}})
            c.journey(36, road=True)
            self.assertEqual(self.legs(c), [(12, 24), (12, 12)])

    def test_an_ability_helps_the_pathfinder_and_is_paid_for_once(self):
        with self.session() as c:
            c.commit({"pc": {"abilities": {"add": ["Trailwise"]}, "items": {"add": ["Map"]}}})
            c.journey(24, use="trailwise", rng=Dice(9, 2, 3))  # the first shift with a boon (two dice); the second without
            self.assertEqual(c.state["pc"]["tracks"]["wp"]["value"], 10)
            self.assertEqual([e["boons"] for e in c.events if e["type"] == "check"], [1, 0])
            with self.assertRaisesRegex(SoloError, "Heavy swing doesn't help on a journey"):
                c.commit({"pc": {"abilities": {"add": ["Heavy swing"]}}})
                c.journey(12, use="heavy swing")

    def test_a_journey_needs_the_packs_rules_and_a_distance(self):
        with self.session() as c:
            with self.assertRaisesRegex(SoloError, "how far"):
                c.journey(0)
            c.system.pop("journey")
            with self.assertRaisesRegex(SoloError, r"has no \[journey\] rules"):
                c.journey(10)


class Camp(CampaignTest):
    adventure = FIXTURES / "delve"

    def test_without_a_sleeping_fur_the_roll_has_a_bane_and_a_tent_gives_a_boon(self):
        with self.session() as c:
            bare = c.camp(rng=Dice(2, 3))
            self.assertEqual((bare["banes"], bare["boons"]), (1, 0))
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Sleeping fur", "Tent"]}}})
            fitted = c.camp(rng=Dice(9, 2))
            self.assertEqual((fitted["banes"], fitted["boons"], fitted["outcome"]["success"]), (0, 1, True))
