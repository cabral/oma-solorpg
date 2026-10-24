import unittest

from helpers import Dice

from solo import SoloError, dice, mechanics


class DiceTest(unittest.TestCase):
    def test_keep_lowest_and_highest(self):
        self.assertEqual(dice.roll("3d20kl", Dice(12, 4, 17))["total"], 4)
        self.assertEqual(dice.roll("2d20kh", Dice(12, 4))["total"], 12)

    def test_kept_dice_in_words_are_kh_and_kl(self):
        # "keep 3" and "k3" keep the highest three, as the Table's dice field says; the words
        # "highest" and "lowest" say which, and then the number is optional.
        wanted = {
            "4d6kh3": ("4d6 keep 3", "4d6k3", "4D6 KEEP 3", "4d6 k 3", "4d6 keep highest 3", "4d6 Keep Highest 3", "4d6keephighest3"),
            "4d6kl2": ("4d6 keep lowest 2", "4d6keeplowest2", "4d6 KEEP LOWEST 2"),
            "2d20kh": ("2d20 keep highest", "2d20keephighest"),
            "2d20kl": ("2d20 keep lowest",),
            "4d6kh3cs>=5": ("4d6 keep 3 cs >= 5", "4d6k3cs>=5"),
            "4d6kh3x10": ("4d6 keep 3 x 10", "4d6k3*10"),
        }
        for short, spellings in wanted.items():
            reading = [(t["count"], t["sides"], t["keep"], t["keep_n"], t["success_at"], t["times"]) for t in dice.parse(short)]
            for expr in spellings:
                with self.subTest(expr=expr):
                    got = [(t["count"], t["sides"], t["keep"], t["keep_n"], t["success_at"], t["times"]) for t in dice.parse(expr)]
                    self.assertEqual(got, reading)
        self.assertEqual(dice.roll("4d6 keep 3", Dice(5, 2, 6, 4))["total"], 15)
        self.assertEqual(dice.roll("4d6 keep lowest 2", Dice(5, 2, 6, 4))["total"], 6)
        self.assertEqual(dice.roll("2d20 keep highest", Dice(7, 15))["parts"][0]["kept"], [15])
        self.assertEqual(dice.outcomes("4d6 keep 3"), set(range(3, 19)))

    def test_a_keep_in_words_needs_its_number_unless_it_says_which(self):
        for expr in ("4d6k", "4d6 keep", "4d6 keep cs>=5", "4d6k0", "4d6 keep 0", "4d6 keep highest 0", "4d6 keep lowest 0"):
            with self.subTest(expr=expr), self.assertRaises(SoloError):
                dice.parse(expr)
        for expr in ("4d6 keep 3 highest", "4d6 keep highest lowest 2", "4d6 keep high 3", "4d6 keeps 3", "4d6kept3", "d6 keep 3 keep 2"):
            with self.subTest(expr=expr), self.assertRaisesRegex(SoloError, "can't read"):
                dice.parse(expr)

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

    def test_white_space_is_ignored_but_never_joins_two_numbers(self):
        for expr in ("2d6 + 3", " 2D6\t+\n3 ", "4D6 KH 3", "5d6 c s > = 6", "d 6", "1 d 6", "d6\xa0+\xa01"):
            with self.subTest(expr=expr):
                self.assertTrue(dice.parse(expr))
        for expr in ("2d6 3", "d6 6", "1 2d6", "2d6x1 0", "d6\xa06"):
            with self.subTest(expr=expr), self.assertRaisesRegex(SoloError, "splits a number"):
                dice.parse(expr)

    def test_a_term_that_rolls_nothing_or_counts_every_die_is_refused(self):
        for expr in ("0d6", "d6kh0", "d6kl0", "d6cs>=0", "d6x0", "2d6+0d4"):
            with self.subTest(expr=expr), self.assertRaisesRegex(SoloError, "out of range"):
                dice.parse(expr)
        self.assertEqual(dice.roll("d6+0", Dice(4))["total"], 4)

    def test_a_term_counts_successes_or_multiplies_not_both(self):
        for expr in ("5d6cs>=6x2", "5d6cs>=6*2", "5d6kh3cs>=5\xd72"):
            with self.subTest(expr=expr), self.assertRaisesRegex(SoloError, "successes and also multiplies"):
                dice.parse(expr)

    def test_digits_and_letters_are_ascii(self):
        arabic_indic_three = chr(0x663)
        kelvin_sign = chr(0x212A)
        for expr in (arabic_indic_three + "d6", f"4d6{kelvin_sign}h3", f"d6+{arabic_indic_three}"):
            with self.subTest(expr=expr), self.assertRaises(SoloError):
                dice.parse(expr)

    def test_an_expression_has_at_most_1000_characters(self):
        self.assertTrue(dice.parse("2d6" + " " * 997))
        with self.assertRaisesRegex(SoloError, "longer than 1000"):
            dice.parse("2d6" + " " * 998)

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
