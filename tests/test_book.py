"""What the Book shows: the story feed, the hero's skills speaking up, light, the codex,
the route, the portrait, fight figures and the Hall of the Fallen."""

import json

from helpers import CampaignTest, Dice

from solo import SoloError, campaign, cli, gm, library, portrait


class StoryTest(CampaignTest):
    def test_speech_rolls_and_scenes_make_the_story_in_order(self):
        with self.session() as c:
            c.say("Rain on the road. What do you do?")
            c.say("I climb to the gate.", by="player")
            c.move("gate", rng=Dice(10, 15))
            c.check("sneaking", rng=Dice(12))
            story = c.state["story"]
        self.assertEqual([e["kind"] for e in story], ["scene", "gm", "player", "scene", "roll"])
        self.assertEqual(story[3]["title"], "The Palisade Gate")
        self.assertEqual(story[4]["outcome"]["target"], 4)
        self.assertFalse(story[4]["outcome"]["success"])

    def test_gm_commits_stay_out_of_the_story(self):
        with self.session() as c:
            c.commit({"note": "the GM's bookkeeping", "facts": {"gate.seen": True}})
            kinds = [e["kind"] for e in c.state["story"]]
        self.assertEqual(kinds, ["scene"])


class VoiceTest(CampaignTest):
    def test_a_scene_voice_speaks_only_on_a_success(self):
        with self.session() as c:
            c.move("gate", rng=Dice(10, 15))  # Spot Hidden 5: 15 fails
            self.assertEqual(c.state["voices"], [])
            self.assertTrue(c.state["log"][-1]["hidden"])
            self.assertNotIn("voice", [e["kind"] for e in c.state["story"]])
            c.move("hall", rng=Dice(10, 3))  # Awareness 10: 3 succeeds
            voices = c.state["voices"]
            story = c.state["story"][-1]
            digest = cli.scene_digest(c)
        self.assertEqual(voices[0]["label"], "Awareness")
        self.assertEqual((story["kind"], story["label"]), ("voice", "Awareness"))
        self.assertIn("his eyes go to the floor behind the throne", story["text"])
        self.assertIn("## What the hero noticed", digest)

    def test_a_voice_can_bring_a_clue_and_the_scene_forgets_old_voices(self):
        with self.session() as c:
            c.move("gate", rng=Dice(2))
            c.move("hall", rng=Dice(15))
            self.assertEqual(c.state["voices"], [])
            c.move("cellar", rng=Dice(4))
        self.assertIn("chalk_spiral", c.state["clues"])

    def test_the_gm_raises_a_voice_and_the_dice_decide(self):
        with self.session() as c:
            heard = c.voice("myths_legends", "Split tusks mean a chieftain who lost a duel.", rng=Dice(3))
            silent = c.voice("awareness", "Someone is behind you.", rng=Dice(18))
            with self.assertRaisesRegex(SoloError, "needs the line"):
                c.voice("awareness", " ")
        self.assertTrue(heard["heard"])
        self.assertFalse(silent["heard"])
        self.assertEqual([v["label"] for v in c.state["voices"]], ["Myths & Legends"])


class LightTest(CampaignTest):
    def test_a_torch_comes_off_the_gear_and_burns_out_after_a_shift(self):
        with self.session() as c:
            c.light("torch")
            self.assertEqual(c.state["light"]["label"], "Torch")
            self.assertNotIn("torch", c.state["pc"]["items"])
            with self.assertRaisesRegex(SoloError, "already burning"):
                c.light()
            c.rest("stretch", rng=Dice(1, 1))
            self.assertIsNotNone(c.state["light"])
            c.commit({"time": {"shift": 1}}, rng=Dice(1))  # the ritual ticks: one omen
            self.assertIsNone(c.state["light"])
            last = [e for e in c.events if e["type"] == "light"][-1]
            with self.assertRaisesRegex(SoloError, "isn't carrying a torch"):
                c.light()
        self.assertEqual(last["reason"], "burned out")

    def test_counted_torches_go_down_one_at_a_time(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"remove": ["torch"], "add": ["3 torches"]}}})
            c.light()
            self.assertIn("2 torches", c.state["pc"]["items"])
            c.snuff()
            c.light()
            self.assertIn("torch", c.state["pc"]["items"])

    def test_the_gm_hears_about_darkness_and_the_book_sees_the_time_left(self):
        with self.session() as c:
            c.move("cellar", force="test")
            self.assertIn("It's dark here", cli.scene_digest(c))
            c.light()
            c.commit({"time": {"stretch": 2}})
            self.assertIn("5 h 30 min left", cli.scene_digest(c))
        state = json.loads((self.root / "state.json").read_text())
        self.assertTrue(state["dark"])
        self.assertEqual(state["light"]["left"], 21600 - 1800)


class CodexTest(CampaignTest):
    def test_the_codex_blanks_what_the_player_hasnt_learned(self):
        with self.session() as c:
            c.move("gate", rng=Dice(10, 15))
            c.move("hall", rng=Dice(10, 15))
            with self.assertRaisesRegex(SoloError, "orc_leader has wants, fears, tunnel"):
                c.commit({"learn": ["orc_leader.name"]})
            with self.assertRaisesRegex(SoloError, "unknown npc"):
                c.commit({"learn": ["nobody.wants"]})
            c.commit({"learn": ["orc_leader.wants", "orc_leader.tunnel"]})
        state = json.loads((self.root / "state.json").read_text())
        [grukk] = state["codex"]
        self.assertEqual(grukk["known"], {"wants": "Riches for his warband, and his three missing warriors back."})
        self.assertEqual(grukk["secrets"], ["A smugglers' tunnel runs from behind the throne straight to the ritual cave."])
        self.assertEqual(grukk["unknown"], 1)
        self.assertIsNone(grukk["stats"])
        self.assertNotIn("looking weak", json.dumps(state["codex"]))

    def test_the_route_counts_unexplored_ways_without_naming_them(self):
        with self.session() as c:
            c.move("gate", rng=Dice(10, 15))
        state = json.loads((self.root / "state.json").read_text())
        self.assertEqual([(r["id"], r["unexplored"], r["here"]) for r in state["route"]], [("road", 0, False), ("gate", 1, True)])
        self.assertNotIn("Chieftain", json.dumps(state["route"]))


class PortraitTest(CampaignTest):
    def test_the_face_follows_the_hero(self):
        with self.session() as c:
            self.assertEqual(portrait.hero(c.system["art"], c.state["pc"], c.state)["mood"], "calm")
            c.commit({"pc": {"conditions": {"add": ["angry"]}}})
            angry = portrait.hero(c.system["art"], c.state["pc"], c.state)
            c.commit({"pc": {"hp": 3, "conditions": {"remove": ["angry"]}}})
            hurt = portrait.hero(c.system["art"], c.state["pc"], c.state)
            c.commit({"pc": {"hp": 0}})
            dying = portrait.hero(c.system["art"], c.state["pc"], c.state)
        self.assertEqual(angry["mood"], "angry")
        self.assertTrue(any("╤╤╤╤" in line for line in angry["lines"]))  # teeth bared
        self.assertEqual((hurt["mood"], hurt["tint"]), ("hurt", "grave"))
        self.assertEqual(dying["mood"], "dying")
        # Ragna is a dwarf fighter: a helmet on top, a beard below, every row the same width.
        self.assertIn("[=====|==|=====]", dying["lines"][2])
        self.assertEqual(len({len(line) for line in dying["lines"]}), 1)

    def test_the_ink_says_what_each_stroke_is(self):
        with self.session() as c:
            c.commit({"pc": {"hp": 7}})  # half: a first wound
            face = portrait.hero(c.system["art"], c.state["pc"], c.state)
        self.assertEqual([len(i) for i in face["ink"]], [len(line) for line in face["lines"]])
        strokes = {k: "".join(line[j] for line, ink in zip(face["lines"], face["ink"]) for j, mark in enumerate(ink) if mark == k)
                   for k in "ewgoh"}
        self.assertEqual((strokes["e"], strokes["w"]), ("●●", "╱"))
        self.assertIn("[=====|==|=====]", strokes["g"])  # the helmet
        self.assertEqual(set(strokes["o"]), {"◆"})       # the beads in the beard
        self.assertEqual(set(strokes["h"]), set("\\|/"))  # the beard itself, in strands

    def test_a_dragon_brings_a_grin(self):
        with self.session() as c:
            c.check("swords", rng=Dice(1, 6))  # a Dragon, and its effect
            face = portrait.hero(c.system["art"], c.state["pc"], c.state)
        self.assertEqual((face["mood"], face["tint"]), ("triumph", "bright"))

    def test_an_art_pack_without_a_mood_falls_back_to_calm(self):
        with self.session() as c:
            c.check("swords", rng=Dice(1, 6))  # a Dragon: the triumph face
            art = {**c.system["art"], "moods": {k: v for k, v in c.system["art"]["moods"].items() if k != "triumph"}}
            face = portrait.hero(art, c.state["pc"], c.state)
            calm = portrait.hero(art, {**c.state["pc"]}, {**c.state, "last_check": None})
        self.assertEqual(face["mood"], "triumph")
        self.assertEqual(face["lines"], calm["lines"])

    def test_fights_carry_figures_and_the_last_exchange(self):
        with self.session() as c:
            c.fight(["orc_leader", "cultist"], rng=Dice(1, 2, 3))
            c.attack("cultist", rng=Dice(3, 6, 6, 4))
        state = json.loads((self.root / "state.json").read_text())
        self.assertIn("(ò)_(ó)", "".join(state["figures"]["foes"]["orc_leader"]))
        self.assertIn("(x x)", "".join(state["figures"]["foes"]["cultist"]))  # fallen
        self.assertIn("|#|", "".join(state["figures"]["hero"]))  # Ragna's shield: she fights best with a sword
        self.assertEqual(state["combat"]["last"]["to"], "cultist")
        self.assertEqual(state["combat"]["last"]["seq"], max(e["seq"] for e in state["story"] if e["kind"] == "hit"))
        self.assertTrue(state["combat"]["last"]["hit"])
        self.assertIn("orc_leader", state["faces"])


class FallenTest(CampaignTest):
    def test_a_dead_hero_goes_to_the_hall_with_their_last_words(self):
        with self.session() as c:
            c.say("I stand my ground. Come on, then!", by="player")
            c.fight(["orc_leader"], rng=Dice(1, 2))
            c.enemy("orc_leader", rng=Dice(5))
            c.defend("take", rng=Dice(8, 8))
            c.death_roll(rng=Dice(20))
            c.next_round(rng=Dice(1, 2))
            c.death_roll(rng=Dice(15))
            fallen = c.state["fallen"]
        self.assertEqual(fallen["by"], "Grukk Red Tusk")
        self.assertEqual(fallen["epitaph"], "I stand my ground. Come on, then!")
        [hall] = [f for f in library.listing()["fallen"] if f["path"] == str(self.root)]
        self.assertEqual(hall["name"], "Ragna")
        self.assertTrue(any("╳" in line for line in hall["portrait"]))


class CutTest(CampaignTest):
    """The player's X-card: a cut message leaves the Book and recall, the log keeps it, the GM is told."""

    def told(self, c):
        c.say("Rain on the road. What do you do?")
        c.say("I look for the gate.", by="player")
        c.commit({"facts": {"road.spider": True}, "note": "a spider waits"})
        c.say("A spider the size of a dog drops onto the road. What do you do?")

    def test_a_cut_message_leaves_the_book_and_recall_but_not_the_log(self):
        with self.session() as c:
            self.told(c)
            event = c.strike("no spiders")
            self.assertEqual(event["target"], c.events[-2]["seq"])
            self.assertNotIn("spider the size", " ".join(b.get("text", "") for b in c.state["story"]))
            self.assertEqual(c.state["last_said"]["text"], "Rain on the road. What do you do?")  # the one before comes back
            self.assertFalse(c.state["awaiting_player"])
            self.assertIn("spider the size", " ".join(e.get("text", "") for e in c.events if e["type"] == "said"))  # append-only
            self.assertNotIn("spider the size", cli.recall_text(c, "spider"))
            self.assertEqual(campaign.fold(c.system, c.adventure, c.events), c.state)

    def test_the_gm_is_told_what_was_cut_what_the_player_said_and_what_it_had_committed(self):
        with self.session() as c:
            self.told(c)
            c.strike("no spiders")
            digest = cli.resume_digest(c, book=True)
            self.assertIn("## Cut by the player", digest)
            self.assertIn("A spider the size of a dog", digest)  # the GM must know what to avoid
            self.assertIn("The player said: no spiders", digest)
            self.assertIn("road.spider = true", digest)  # what it committed stands unless retracted
            self.assertIn("Rain on the road", digest.split("## Last said")[1])  # and the last message left is the one before
            line = gm.since_gm(c)[-1]
            self.assertIn("the player cut your message", line)
            self.assertIn("Don't repeat it or come back to it", line)

    def test_cutting_again_goes_one_message_further_back_and_nothing_to_cut_is_refused(self):
        with self.session() as c:
            with self.assertRaisesRegex(SoloError, "hasn't said anything to cut"):
                c.strike()
            self.told(c)
            c.strike()
            c.strike()
            self.assertIsNone(c.state["last_said"])
            with self.assertRaisesRegex(SoloError, "hasn't said anything to cut"):
                c.strike()
            self.assertEqual(len(c.state["struck"]), 2)
            self.assertIn("this is the opening", cli.resume_digest(c))

    def test_the_gm_speaking_again_is_awaiting_the_player_again(self):
        with self.session() as c:
            self.told(c)
            c.strike()
            c.say("Only wet cobbles. What do you do?")
            self.assertTrue(c.state["awaiting_player"])
            self.assertEqual(c.state["last_said"]["text"], "Only wet cobbles. What do you do?")
