"""The Red Tusk Hall played from the first scene to its end, with fixed dice.

This covers what the unit tests don't: that the pieces work together through a whole
adventure the way a GM would drive them. It does not replace a real session through
the panel and an agent.
"""

from helpers import CampaignTest, Dice

from solo import campaign, cli, library


class RedTuskPlaythrough(CampaignTest):
    def test_parley_then_win_the_ritual_cave(self):
        with self.session() as c:
            c.set_prefs(tone="grim folk horror", veils=["drowning"])
            c.move("gate", rng=Dice(15))  # 15: Spot Hidden stays silent about the axe
            c.check("sneaking", rng=Dice(12))  # base chance 5: the guards see Ragna
            c.commit({"note": "the horn sounds", "facts": {"hall.alarm": True}}, rng=Dice(2))
            self.assertEqual(c.state["clocks"]["dark_ritual"]["value"], 1)
            c.commit({"pc": {"items": {"add": ["broken axe"]}}})

            c.move("hall", rng=Dice(15))
            self.assertIn("The warband is awake and armed.", cli.scene_digest(c))
            c.check("persuasion", boons=1, rng=Dice(12, 4))  # the axe gives a boon
            c.commit({
                "note": "Ragna returns the axe and parleys with Grukk",
                "npc": {"orc_leader": {"attitude": "+1", "memory": "Ragna returned his son's axe"}},
                "promise": {"id": "warband_joins", "npc": "orc_leader", "terms": "fights beside Ragna if his warriors are freed"},
                "pc": {"items": {"remove": ["broken axe"]}},
            })

            c.move("cellar", rng=Dice(2))  # Spot Hidden 2 vs 4: the chalk spiral
            self.assertIn("chalk_spiral", c.state["clues"])
            self.assertIn("a spiral with an eye in it", cli.scene_digest(c))
            self.assertIn("It's dark here", cli.scene_digest(c))
            c.light("torch")
            self.assertNotIn("torch", c.state["pc"]["items"])
            c.commit({"note": "freed the three warriors", "promise": {"id": "warband_joins", "status": "kept"}})
            c.move("final_battle", rng=Dice(15))
            self.assertIn("Grukk and the Red Tusk warband charge in behind you", cli.scene_digest(c))

            c.fight(["priest", "cultist", "cultist"], rng=Dice(1, 1, 1, 1))
            c.attack("priest", rng=Dice(3, 6, 6, 2))
            c.enemy("priest", rng=Dice(15))
            c.enemy("cultist", rng=Dice(4))
            c.defend("parry", rng=Dice(2))
            c.enemy("cultist_2", rng=Dice(9))
            c.defend("take", rng=Dice(5))
            self.assertEqual(c.state["pc"]["tracks"]["hp"]["value"], 9)
            c.next_round(rng=Dice(1, 1, 1, 1))
            c.attack("priest", rng=Dice(7, 1, 1, 1))
            c.next_round(rng=Dice(1, 1, 1, 1))
            c.attack("cultist", rng=Dice(5, 6, 6, 4))
            c.next_round(rng=Dice(1, 1, 1))
            c.attack("cultist_2", rng=Dice(6, 6, 6, 4))
            self.assertIsNone(c.state["combat"])  # the last foe down ends the fight
            self.assertEqual(c.events[-1]["type"], "fight_end")

            c.commit({"npc": {"priest": {"fate": "dead"}, "cultist": {"fate": "dead"}}})
            c.commit({
                "end": "The priest is dead, the pool goes still, and the Red Tusk orcs keep their hill.",
                "chronicle": "Ragna parleyed with Grukk, freed his warriors and stopped the ritual.",
            })
            c.mark("persuasion", reason="overcame an obstacle without violence")
            c.advance(rng=Dice(15))

            state = c.state
            kinds = [entry["kind"] for entry in state["story"]]
            self.assertEqual(kinds.count("scene"), 5)
            self.assertIn("voice", kinds)
            self.assertIn("hit", kinds)
            self.assertEqual(state["story"][-1]["kind"], "event")  # the advancement roll
            self.assertEqual(state["pc"]["skills"]["persuasion"]["value"], 9)
            self.assertIn("the pool goes still", state["ended"]["text"])
            self.assertIn("- ended: The priest is dead", cli.resume_digest(c))
            rebuilt = campaign.fold(c.system, c.adventure, c.events)
        self.assertEqual(rebuilt, state)
        [card] = [card for card in library.listing()["campaigns"] if card["path"] == str(self.root)]
        self.assertIn("the pool goes still", card["ended"])
