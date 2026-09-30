"""`solo review`: the play test's checks over a campaign played for real."""

import json

from helpers import CampaignTest, Dice
from test_cli import CliCase

from solo import SoloError, campaign, review


class ReviewTest(CampaignTest):
    def kinds(self, c, trace=None):
        return [kind for kind, _ in review.review(c, trace)]

    def test_a_clean_table_has_nothing_to_look_at(self):
        with self.session() as c:
            c.say("Rain on the road. What do you do?")
            c.say("I go to the gate.", by="player")
            c.say("The gate looms out of the rain. What do you do?")
            self.assertEqual(review.review(c), [])
            self.assertIn("Nothing found", review.render([], "The Red Tusk Hall"))

    def test_bookkeeping_in_the_story_is_found_in_the_message_that_carries_it(self):
        with self.session() as c:
            c.say("Rain on the road. What do you do?")
            c.say("I go to the gate.", by="player")
            event = c.say("You reach the gate (Sneaking, 14 vs 5, failed). I'll commit it now.")
            found = review.review(c)
        self.assertTrue(all(detail.startswith(f"#{event['seq']}:") for _, detail in found), found)
        self.assertEqual({kind for kind, _ in found}, {"bookkeeping", "no_question"})

    def test_a_cut_message_is_not_reviewed(self):
        with self.session() as c:
            c.say("You reach the gate (Sneaking, 14 vs 5, failed). What do you do?")
            c.strike()
            self.assertEqual(review.review(c), [])

    def test_a_foe_that_never_struck_back(self):
        with self.session() as c:
            c.fight(["cultist"], rng=Dice(1, 3))
            c.attack("cultist", rng=Dice(19))  # a miss
            self.assertEqual(self.kinds(c), [])  # the fight is still open: its round may not be over
            c.next_round(rng=Dice(1, 3))
            found = review.review(c)
        self.assertEqual([kind for kind, _ in found], ["fight"])
        self.assertIn("the hero attacked and no foe attacked back", found[0][1])

    def test_a_consequence_that_came_due_and_was_never_paid(self):
        with self.session() as c:
            c.commit({"consequence": {"id": "debt", "text": "Grukk remembers the insult", "at": ["hall"]}})
        with self.session() as c:
            c.move("gate", force="the test")
            c.move("hall", force="the test")  # the session's end announces what came due
        with self.session() as c:
            self.assertEqual(self.kinds(c), ["forced", "forced"])  # due, but the GM hasn't had two messages since
            for n in range(2):
                c.say(f"Grukk glares at you. What do you do? ({n})")
            found = [d for k, d in review.review(c) if k == "unpaid"]
            self.assertEqual(len(found), 1)
            self.assertIn("debt came due", found[0])
            c.commit({"consequence": {"id": "debt", "status": "done"}})
            self.assertNotIn("unpaid", self.kinds(c))

    def test_a_person_keeps_their_name_unless_the_story_names_them_now(self):
        with self.session() as c:
            c.commit({"npc": {"smith": {"name": "Odd", "role": "a smith"}}})
            c.commit({"npc": {"smith": {"name": "odd", "memory": "seen at the forge"}}})  # the same name: nothing changes
            with self.assertRaisesRegex(SoloError, "smith is already called Odd: a person keeps their name"):
                c.commit({"npc": {"smith": {"name": "Osk the smith"}}})
            self.assertEqual(c.state["npcs"]["smith"]["name"], "Odd")
            c.commit({"npc": {"smith": {"name": "Osk the smith"}}, "override": "she gives her name at last"})
            self.assertEqual(c.state["npcs"]["smith"]["name"], "Osk the smith")
            self.assertEqual(campaign.fold(c.system, c.adventure, c.events), c.state)
            found = [d for k, d in review.review(c) if k == "two_names"]
        self.assertEqual(len(found), 1)
        self.assertIn("smith was 'Odd', and is now 'Osk the smith'", found[0])

    def test_one_name_under_two_ids_but_not_a_foe_met_in_numbers(self):
        with self.session() as c:
            c.commit({"npc": {"smith": {"name": "Osk", "role": "a smith"}}})
            c.commit({"npc": {"tinker": {"name": "Osk", "role": "a tinker"}, "guard_1": {"name": "Guard"}, "guard_2": {"name": "Guard"}}})
            found = [d for k, d in review.review(c) if k == "two_names"]
        self.assertEqual(len(found), 1, found)
        self.assertIn("'Osk' is smith and tinker", found[0])

    def test_refused_commands_come_from_the_trace(self):
        with self.session() as c:
            trace = self.tmp / "trace.jsonl"
            trace.write_text("\n".join(json.dumps(line) for line in [
                {"argv": ["check", "sneaking"], "error": None},
                {"argv": ["setup", "--plugin"], "error": "the GM can't run that"},
            ]) + "\n")
            found = review.review(c, trace)
        self.assertEqual(found, [("refused", "solo setup --plugin: the GM can't run that")])


class ReviewCommand(CliCase):
    def test_solo_review_prints_a_report(self):
        self.new_game()
        code, out, _ = self.solo("-C", self.game, "review")
        self.assertEqual(code, 0)
        self.assertIn("Nothing found", out)
        self.solo("-C", self.game, "say", "You see it (Sneaking, 14 vs 5, failed).")
        code, out, _ = self.solo("-C", self.game, "review")
        self.assertIn("## bookkeeping", out)
        self.assertIn("## no_question", out)
