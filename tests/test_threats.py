"""A threat that advances on an activity moves once for it: a rest that lasts a shift is one step, not one for each
of the stretches in it. Played on the made-up test rules (tests/fixtures/house) with that rule laid over them."""

from helpers import ACTIVITY, FIXTURES, CampaignTest, Dice


class Activity(CampaignTest):
    system, adventure = ACTIVITY, FIXTURES / "delve"

    def test_a_shifts_rest_brings_a_threat_one_step_and_not_one_for_every_stretch(self):
        with self.session() as c:
            c.move("adit")
            c.threat("Goblins come down the tunnel", threat_id="goblins")
            c.commit({"pc": {"hp": 5}})
            c.rest("shift", rng=Dice(1))
            self.assertEqual(c.state["clocks"]["goblins"]["value"], 2)

    def test_what_takes_less_than_a_stretch_brings_it_no_closer_and_a_stretch_or_more_does(self):
        with self.session() as c:
            c.move("adit")
            c.threat("Goblins come down the tunnel", threat_id="goblins")
            c.commit({"time": {"round": 3}})
            self.assertEqual(c.state["clocks"]["goblins"]["value"], 1)
            c.commit({"time": {"stretch": 1}})
            self.assertEqual(c.state["clocks"]["goblins"]["value"], 2)
            c.commit({"time": {"shift": 1}})
            self.assertEqual(c.state["clocks"]["goblins"]["value"], 3)
