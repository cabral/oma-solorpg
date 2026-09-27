import unittest

from helpers import Dice

from solo import SoloError, dice, mechanics


class DiceTest(unittest.TestCase):
    def test_keep_lowest_and_highest(self):
        self.assertEqual(dice.roll("3d20kl", Dice(12, 4, 17))["total"], 4)
        self.assertEqual(dice.roll("2d20kh", Dice(12, 4))["total"], 12)

    def test_counting_successes_plus_a_constant(self):
        result = dice.roll("5d6cs>=6+1", Dice(6, 2, 6, 1, 5))
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["parts"][0]["rolls"], [6, 2, 6, 1, 5])

    def test_subtraction_and_default_count(self):
        self.assertEqual(dice.roll("d20 - 2", Dice(10))["total"], 8)

    def test_d66_reads_tens_and_units(self):
        self.assertEqual(dice.roll("d66", Dice(3, 5))["total"], 35)

    def test_bad_expressions_are_rejected(self):
        for expr in ("", "2x6", "d1", "101d6", "1d6+@stress", "1d1001", "d" + "9" * 5000, "+".join(["1"] * 21)):
            with self.subTest(expr=expr), self.assertRaises(SoloError):
                dice.parse(expr)

    def test_outcomes(self):
        self.assertEqual(dice.outcomes("1d6"), set(range(1, 7)))
        self.assertEqual(dice.outcomes("2d20kl"), set(range(1, 21)))
        self.assertEqual(dice.outcomes("3d6cs>=6"), {0, 1, 2, 3})
        self.assertEqual(len(dice.outcomes("d66")), 36)
        self.assertEqual(dice.outcomes("1d4+1d4"), set(range(2, 9)))

    def test_outcomes_refuse_expressions_too_big_to_check(self):
        with self.assertRaisesRegex(SoloError, "too many outcomes"):
            dice.outcomes("100d1000+100d1000")


class D20UnderTest(unittest.TestCase):
    def test_success_at_or_under_the_target(self):
        outcome = mechanics.d20_under(10, rng=Dice(10))
        self.assertTrue(outcome["success"])
        self.assertFalse(outcome["pushable"])

    def test_failure_can_be_pushed(self):
        outcome = mechanics.d20_under(10, rng=Dice(11))
        self.assertFalse(outcome["success"])
        self.assertTrue(outcome["pushable"])

    def test_dragon_always_succeeds_and_demon_always_fails(self):
        dragon = mechanics.d20_under(0, rng=Dice(1))
        demon = mechanics.d20_under(20, rng=Dice(20))
        self.assertTrue(dragon["dragon"] and dragon["success"])
        self.assertTrue(demon["demon"])
        self.assertFalse(demon["success"] or demon["pushable"])

    def test_boons_and_banes_cancel_and_stack(self):
        self.assertEqual(mechanics.d20_under(10, 1, 1, Dice(7))["expr"], "d20")
        self.assertEqual(mechanics.d20_under(10, 2, 0, Dice(15, 9, 12))["result"], 9)
        bane = mechanics.d20_under(10, 0, 1, Dice(3, 14))
        self.assertEqual((bane["expr"], bane["result"], bane["success"]), ("2d20kh", 14, False))


class PoolTest(unittest.TestCase):
    def group(self, name, count, sides=6, on_one=None):
        return {"name": name, "count": count, "sides": sides, "on_one": on_one}

    def test_sixes_score_and_a_one_on_stress_fires_the_trigger(self):
        outcome = mechanics.d6_pool([self.group("base", 2), self.group("stress", 1, on_one="panic")], 6, Dice(6, 3, 1))
        self.assertEqual((outcome["successes"], outcome["success"], outcome["triggers"]), (1, True, ["panic"]))

    def test_push_rerolls_misses_keeps_hits_and_adds_dice(self):
        first = mechanics.d6_pool([self.group("base", 2), self.group("stress", 0, on_one="panic")], 6, Dice(6, 2))
        pushed = mechanics.d6_pool_push(first, {"stress": 1}, 6, Dice(6, 4))
        self.assertEqual(pushed["groups"][0]["rolls"], [6, 6])
        self.assertEqual(pushed["groups"][1]["rolls"], [4])
        self.assertEqual(pushed["successes"], 2)

    def test_step_dice_with_double_successes(self):
        groups = [self.group("attribute", 1, sides=10), self.group("skill", 1, sides=8)]
        self.assertEqual(mechanics.d6_pool(groups, [[10, 2], [6, 1]], Dice(10, 7))["successes"], 3)


if __name__ == "__main__":
    unittest.main()
