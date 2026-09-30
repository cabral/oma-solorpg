"""The starter adventure, The Bell Under the Hill: what a fresh install with no book plays. A
scripted session with fixed dice does what a GM does at the table (rolls a move, reads what the
book says for the result, commits what it gives and costs) through a vow, a journey, a bond
and a fight, and ends where the adventure does."""

import json
import os
import unittest

from helpers import HRAFNA, IRONSWORN, ROOT, CampaignTest, Dice
from test_cli import CliCase

from solo import SoloError, campaign, cli, library, packs

BELL = ROOT / "examples" / "bell-under-the-hill"


class BellCampaignTest(CampaignTest):
    system, adventure, character = IRONSWORN, BELL, HRAFNA

    def hero(self, c):
        return c.state["pc"]

    def momentum(self, c):
        return self.hero(c)["tracks"]["momentum"]["value"]


class PlaythroughTest(BellCampaignTest):
    def test_a_vow_a_journey_a_bond_and_a_fight_from_the_first_scene_to_the_last(self):
        with self.session() as c:
            self.assertEqual((c.state["scene"], self.hero(c)["name"], self.momentum(c)), ("ford", "Hrafna Voss", 2))

            # -- Marrow Ford: the vow. A weak hit: determined, with more questions than answers (+1 momentum).
            vow = c.act("swear_an_iron_vow", stat="heart", rng=Dice(5, 2, 9))  # 5 + 1 = 6 against 2 and 9
            self.assertEqual(vow["outcome"]["hit"], "weak_hit")
            c.commit({"pc": {"momentum": "+1"}})
            c.track_add("Silence the bell", "vow", "dangerous")

            # -- Osk's hearth: a strong hit on Gather Information (+2 momentum), the rhyme, the oil, a milestone.
            c.move("hearth")
            asked = c.act("gather_information", rng=Dice(6, 2, 4))  # 6 + 2 = 8 beats both
            self.assertEqual(asked["outcome"]["hit"], "strong_hit")
            c.commit({"pc": {"momentum": "+2", "items": {"add": ["a jar of lamp oil"]}}, "facts": {"rhyme.known": True},
                      "npc": {"osk": {"attitude": "friendly", "memory": "admitted the lamps were let go dark"}}})
            c.track_mark("silence_the_bell")  # Reach a Milestone: two boxes at a dangerous rank
            self.assertEqual(c.state["progress"]["silence_the_bell"]["ticks"], 8)
            self.assertEqual(self.momentum(c), 5)

            # -- The mill: Forge a Bond with Brenna. A strong hit: mark a tick, and take +2 momentum.
            c.move("ford")
            c.move("mill")
            bond = c.act("forge_a_bond", stat="heart", rng=Dice(6, 1, 2))  # 7 beats 1 and 2
            self.assertEqual(bond["outcome"]["hit"], "strong_hit")
            c.track_mark("bonds")
            c.commit({"pc": {"momentum": "+2", "items": {"add": ["a loaf of bread"]}}, "npc": {"brenna": {"attitude": "friendly"}}})
            self.assertEqual((c.state["progress"]["bonds"]["ticks"], self.momentum(c)), (1, 7))

            # -- The barrow road: the way on is shut until the journey is done.
            c.move("ford")
            c.move("road")
            with self.assertRaisesRegex(SoloError, "the way to mouth isn't open yet"):
                c.move("mouth")
            c.track_add("The barrow road", "journey", "troublesome")
            first = c.act("undertake_a_journey", rng=Dice(3, 2, 9))  # 5 beats only the 2: a weak hit
            self.assertEqual(first["outcome"]["hit"], "weak_hit")
            c.track_mark("the_barrow_road")
            c.commit({"pc": {"supply": "-1"}})  # the weak hit costs a supply

            # A miss with momentum +7 behind it could still be saved: the bell waits until the player chooses.
            second = c.act("undertake_a_journey", rng=Dice(1, 5, 8))  # 1 + 2 = 3: a miss, but the 5 is under the momentum
            self.assertEqual((second["outcome"]["hit"], second.get("open"), c.state["clocks"]["bell"]["value"]), ("miss", True, 0))
            burned = c.burn()
            self.assertEqual((burned["outcome"]["hit"], self.momentum(c), c.state["clocks"]["bell"]["value"]), ("weak_hit", 2, 0))
            c.track_mark("the_barrow_road")
            c.commit({"pc": {"supply": "-1"}})

            # Nothing left to burn: this miss stands, the bell tolls once, and the omen is rolled.
            third = c.act("undertake_a_journey", rng=Dice(2, 9, 9, 4))  # 4 against 9 and 9, matched dice
            self.assertEqual((third["outcome"]["hit"], third["outcome"]["match"], c.state["clocks"]["bell"]["value"]), ("miss", True, 1))
            omen = [e for e in c.events if e["type"] == "table" and e["table"] == "bell_omens"][-1]
            self.assertEqual(omen["text"], "The stroke comes from closer than the hill, and the ground hums with it.")
            self.assertEqual(c.table("pay_the_price", rng=Dice(30))["table"], "pay_the_price")
            c.commit({"pc": {"health": "-1"}})  # the fall in the dark: Endure Harm rolls +health or +iron, whichever is higher
            harm = c.act("endure_harm", rng=Dice(3, 2, 6))
            self.assertEqual((harm["stat"], harm["outcome"]["stat"], harm["outcome"]["hit"]), ("health", 4, "strong_hit"))
            c.commit({"pc": {"momentum": "+1"}})  # embrace the pain
            self.assertEqual((self.hero(c)["tracks"]["health"]["value"], self.hero(c)["tracks"]["supply"]["value"], self.momentum(c)), (4, 3, 3))

            arrived = c.act("reach_your_destination", rng=Dice(4, 7))  # six full boxes beat 4, not 7
            self.assertEqual((arrived["track"], arrived["outcome"]["progress"], arrived["outcome"]["hit"]), ("the_barrow_road", 6, "weak_hit"))
            c.commit({"facts": {"road.done": True}})
            c.track_end("the_barrow_road", "arrived")
            self.assertEqual(c.move("mouth")["to"], "mouth")

            # -- The barrow's mouth: three lamps lit with the oil and the names. A weak hit, and a milestone.
            c.act("secure_an_advantage", stat="heart", rng=Dice(4, 3, 7))
            c.commit({"pc": {"momentum": "+1", "items": {"remove": ["a jar of lamp oil"]}}, "facts": {"lamps.lit": True}})
            c.track_mark("silence_the_bell")

            # -- The long hall: the fight. Enter the Fray with the lamps lit (+1), and the hollow ones become a track.
            c.move("hall")
            fray = c.act("enter_the_fray", stat="heart", adds=1, rng=Dice(5, 2, 6))  # 5 + 1 + 1 = 7 beats both
            self.assertEqual((fray["outcome"]["adds"], fray["outcome"]["hit"]), (1, "strong_hit"))
            c.commit({"pc": {"momentum": "+2"}})
            c.track_add("The hollow ones", "combat", "dangerous")
            strike = c.act("strike", stat="edge", rng=Dice(4, 3, 8))  # a bow at range: 7, a weak hit: inflict harm and lose initiative
            self.assertEqual(strike["outcome"]["hit"], "weak_hit")
            c.track_mark("the_hollow_ones", times=2)  # a deadly weapon does 2 harm, and each harm is a mark
            clash = c.act("clash", stat="edge", rng=Dice(2, 4, 6))  # 5: a weak hit, then Pay the Price
            self.assertEqual(clash["outcome"]["hit"], "weak_hit")
            c.track_mark("the_hollow_ones", times=2)
            c.commit({"pc": {"health": "-2"}})
            hurt = c.act("endure_harm", rng=Dice(1, 5, 9, 1))  # +health 2: 3 against 5 and 9, a miss the player lets stand
            self.assertEqual((hurt["stat"], hurt["outcome"]["hit"], hurt["open"], c.state["clocks"]["bell"]["value"]), ("health", "miss", True, 1))
            c.commit({"pc": {"momentum": "-1"}})  # the story goes on: the miss stands, and the bell tolls a second time
            self.assertEqual((self.hero(c)["tracks"]["health"]["value"], self.momentum(c), c.state["clocks"]["bell"]["value"]), (2, 5, 2))
            finish = c.act("strike", stat="edge", rng=Dice(5, 1, 2))  # a strong hit: +1 harm, and initiative kept
            self.assertEqual(finish["outcome"]["hit"], "strong_hit")
            c.track_mark("the_hollow_ones", times=3)
            self.assertEqual(c.state["progress"]["the_hollow_ones"]["ticks"], 40)  # ten boxes, and no more
            end = c.act("end_the_fight", rng=Dice(4, 9))  # ten boxes beat both
            self.assertEqual((end["track"], end["outcome"]["hit"]), ("the_hollow_ones", "strong_hit"))
            c.track_end("the_hollow_ones", "won")

            # -- The ringers are freed, and the iron door can open.
            freed = c.act("face_danger", stat="iron", rng=Dice(6, 2, 3))
            self.assertEqual(freed["outcome"]["hit"], "strong_hit")
            c.commit({"pc": {"momentum": "+1"}, "facts": {"door.open": True}, "note": "the ringers are led out of the hall"})
            c.track_mark("silence_the_bell")

            # -- The bell chamber: Hild answered with the lamps behind the hero and the rhyme said word for word.
            c.move("bell")
            with self.assertRaisesRegex(SoloError, "the way to dawn isn't open yet"):
                c.move("dawn")
            answer = c.act("compel", stat="heart", adds=1, rng=Dice(4, 2, 3))
            self.assertEqual(answer["outcome"]["hit"], "strong_hit")
            c.commit({"facts": {"bell.silenced": True}, "npc": {"hild": {"attitude": "neutral", "memory": "answered by someone who keeps the oath"}},
                      "pc": {"items": {"remove": ["a loaf of bread"]}}})
            c.track_mark("silence_the_bell")

            # -- The vow is fulfilled on a strong hit: eight boxes beat both dice.
            self.assertEqual(c.state["progress"]["silence_the_bell"]["ticks"], 32)
            done = c.act("fulfill_your_vow", rng=Dice(5, 7))
            self.assertEqual((done["outcome"]["progress"], done["outcome"]["hit"]), (8, "strong_hit"))
            c.track_end("silence_the_bell", "fulfilled")
            c.commit({"facts": {"hero.xp": 2}, "chronicle": "Hrafna answered the bell under the hill and kept Marrow Ford's oath."})
            c.move("dawn")
            c.commit({"end": "The bell is silent, the ringers are home, and the lamps of the barrow will be lit at midwinter."})

            self.assertEqual(c.state["scene"], "dawn")
            self.assertEqual(c.state["ended"]["text"][:12], "The bell is ")
            self.assertEqual({k: v["ended"] for k, v in c.state["progress"].items()},
                             {"bonds": None, "silence_the_bell": "fulfilled", "the_barrow_road": "arrived", "the_hollow_ones": "won"})
            self.assertEqual((c.state["clocks"]["bell"]["value"], c.state["facts"]["hero.xp"]), (2, 2))
            # The oil went into the lamps and the bread onto the ground: what the hero started with is what they carry.
            self.assertEqual(self.hero(c)["items"], ["a hunting bow and a quiver of arrows", "a knife", "a leather gauntlet, and a hawk that answers to it"])
        # Everything above is in the log, and the log alone rebuilds the state.
        replayed = campaign.fold(c.system, c.adventure, c.events)
        self.assertEqual((replayed["progress"], replayed["clocks"], replayed["pc"], replayed["facts"]), (c.state["progress"], c.state["clocks"], c.state["pc"], c.state["facts"]))
        self.assertEqual(replayed["problems"], [])

    def test_the_bell_clock_fills_and_the_gm_is_told_where_it_leads(self):
        with self.session() as c:
            for stroke in range(8):
                c.act("face_danger", stat="edge", rng=Dice(1, 9, 9, 1 + stroke % 6))
            self.assertEqual((c.state["clocks"]["bell"]["value"], c.state["clocks"]["bell"]["full"]), (8, True))
            self.assertTrue(c.state["facts"]["bell.near"])  # the fourth stroke: it is nearer than the hill
            self.assertIn("FULL: run scene the_dead_walk", cli._clock_line(c, "bell"))
            self.assertEqual(c.move("the_dead_walk", force="the bell filled")["to"], "the_dead_walk")


class PackTest(unittest.TestCase):
    def setUp(self):
        self.system, self.adventure = packs.load_system(IRONSWORN), packs.load_adventure(BELL)

    def test_it_validates_and_lints_clean(self):
        self.assertEqual(packs.validate(self.system, self.adventure), [])
        self.assertEqual(packs.lint(self.adventure), [])

    def test_it_asks_for_no_book(self):
        self.assertEqual(self.adventure["system"], "ironsworn")
        self.assertEqual(packs.missing(self.system), [])
        self.assertTrue(self.adventure["summary"])
        self.assertNotIn("Hild", self.adventure["summary"])  # the card is spoiler-free

    def test_every_scene_can_be_reached_and_every_person_is_somewhere(self):
        reached, queue = {"ford"}, ["ford"]
        while queue:
            for target in packs.exits(self.adventure, queue.pop()):
                if target not in reached:
                    reached.add(target)
                    queue.append(target)
        self.assertEqual(reached | {"the_dead_walk"}, set(self.adventure["scenes"]))  # the last is where the clock leads
        placed = {n for scene in self.adventure["scenes"].values() for n in scene.get("npcs", [])}
        self.assertEqual(placed, set(self.adventure["npcs"]))

    def test_its_words_are_its_own(self):
        # The adventure quotes the rules by name only: no text of the book's moves is copied into it.
        moves = [move["text"].strip().splitlines()[0] for move in self.system["moves"].values()]
        for path in BELL.rglob("*.md"):
            text = path.read_text(encoding="utf-8")
            for line in moves:
                self.assertNotIn(line[:60], text, path)


class LibraryTest(CliCase):
    def test_a_player_with_no_book_can_pick_it_and_begin(self):
        os.environ["SOLO_HOME"] = str(self.tmp / "empty")
        library_listing = json.loads(self.solo("library")[1])
        adventure = next(a for a in library_listing["adventures"] if a["id"] == "bell-under-the-hill")
        self.assertEqual(adventure["system"], "ironsworn")
        self.assertIn("ironsworn", [system["id"] for system in library_listing["systems"]])
        self.assertEqual({hero["id"] for hero in next(s for s in library_listing["systems"] if s["id"] == "ironsworn")["characters"]},
                         {"hrafna", "torvald", "eydis"})
        # The New adventure screen's clicks: Begin with the default (a random hero), then again with a pre-made one.
        for hero in ("random", "torvald"):
            with self.subTest(hero=hero):
                code, out, err = self.solo("new", adventure["path"], "--character", hero, "--seed", "3", "--dir", str(self.tmp / f"game-{hero}"))
                self.assertEqual(code, 0, err)
                self.assertIn("MOMENTUM +2", out)
        scene = self.solo("-C", str(self.tmp / "game-random"), "scene")[1]
        self.assertIn("Marrow Ford is twelve turf-roofed houses", scene)
        self.assertIn("## Clocks\n- The bell (bell): 0/8. Next stage at 4", scene)
        self.assertIn("Stats: ", scene)


if __name__ == "__main__":
    unittest.main()
