"""What keeps a long story together: the GM's memory at the start of a session, a new
hero after a death, an adventure's own heroes, and the author's view of a pack."""

import copy
import shutil
import tempfile
from pathlib import Path

from helpers import BUNDLED, DRAGONBANE, FIXTURES, RED_TUSK, CampaignTest, Dice

from solo import SoloError, campaign, cli, creation, library, packs


class LongMemory(CampaignTest):
    def test_resume_carries_the_chronicle_open_promises_clues_and_the_gone(self):
        with self.session() as c:
            c.say("The road climbs to the gate.", "gm")
            c.commit({
                "chronicle": "Ragna reached the hill and heard the drums.",
                "promise": {"id": "warband_joins", "npc": "orc_leader", "terms": "fights beside Ragna"},
                "clue": ["chalk_spiral"],
                "npc": {"cultist": {"fate": "dead"}},
            })
            c.state["npcs"]["cultist"]["met"] = True
            digest = cli.resume_digest(c)
        self.assertIn("## The story so far (your chronicle, latest last)\n- [0d 00:00, The Old Road] Ragna reached the hill", digest)
        self.assertIn("- warband_joins (to orc_leader): fights beside Ragna", digest)
        self.assertIn("- chalk_spiral", digest)
        self.assertIn("Cultist (dead)", digest)

    def test_resume_marks_what_the_player_never_saw_however_long_ago(self):
        with self.session() as c:
            c.say("The road climbs to the gate.", "gm")
            secret = c.commit({"facts": {"road.watched": True}})
            for _ in range(45):  # more than the table's log keeps
                c.check("swords", rng=Dice(3))
            digest = cli.resume_digest(c)
        [line] = [line for line in digest.splitlines() if line.startswith(f"- #{secret['seq']} ")]
        self.assertTrue(line.endswith("(hidden from the player)"))

    def test_the_scene_lists_the_facts_the_story_has_settled(self):
        with self.session() as c:
            c.commit({"facts": {"hall.alarm": True, "gate.axe_found": "in the mud"}})
            digest = cli.scene_digest(c)
        self.assertIn('## Facts (settled by the story: this place and the people here first, then the latest)\n'
                      '- hall.alarm: true\n- gate.axe_found: "in the mud"', digest)


class NewHero(CampaignTest):
    def kill(self, c):
        c.commit({"pc": {"hp": 0}})
        for _ in range(3):
            c.death_roll(rng=Dice(20))
            if c.state["pc"]["dead"]:
                break
        self.assertTrue(c.state["pc"]["dead"])

    def test_only_after_a_death(self):
        with self.session() as c, self.assertRaisesRegex(SoloError, "still alive"):
            c.take_over("ragna")

    def test_the_story_goes_on_with_a_new_hero_and_remembers_the_old(self):
        with self.session() as c:
            c.commit({"facts": {"hall.alarm": True}, "clock": {"dark_ritual": "+1"}})
            self.kill(c)
            c.take_over("human thief", name="Tove", seed=3)
            pc = c.state["pc"]
            self.assertEqual((pc["name"], pc["dead"], c.state["ended"], c.state["fallen"]), ("Tove", False, None, None))
            self.assertTrue(c.state["facts"]["hall.alarm"])  # the world is as the dead hero left it
            self.assertEqual(c.state["clocks"]["dark_ritual"]["value"], 2)  # the alarm ticks it too
            self.assertEqual(c.state["heroes"][0]["name"], "Ragna")
            self.assertEqual(c.state["heroes"][0]["fate"], "died")
            self.assertIn("- Ragna: died", cli.resume_digest(c))
            c.check("awareness", rng=Dice(2))  # the new hero can act
            self.assertEqual(campaign.fold(c.system, c.adventure, c.events), c.state)
        [fallen] = [f for f in library.listing()["fallen"] if f["path"] == str(self.root)]
        self.assertEqual(fallen["name"], "Ragna")

    def test_an_npc_offered_as_the_replacement_leaves_the_cast(self):
        with tempfile.TemporaryDirectory() as folder:
            pack = Path(folder) / "red-tusk"
            shutil.copytree(RED_TUSK, pack)
            (pack / "characters").mkdir()
            (pack / "characters" / "orc_leader.toml").write_text(
                (BUNDLED / "characters" / "ragna.toml").read_text().replace('name = "Ragna"', 'name = "Grukk"')
                + "\nreplacement = true\n")
            root = campaign.create(self.tmp / "grukk", DRAGONBANE, pack, BUNDLED / "characters" / "ragna.toml")
            with campaign.session(root) as c:
                self.kill(c)
                c.take_over("orc_leader")
                self.assertEqual(c.state["pc"]["name"], "Grukk")
                self.assertEqual(c.state["npcs"]["orc_leader"]["fate"], "gone")
            # A replacement waits in the story, so it isn't offered as a starting hero.
            [card] = [a for a in library.listing()["adventures"] if a["id"] == "red-tusk"]
            self.assertEqual(card["characters"], [])


class AdventureHeroes(CampaignTest):
    def test_an_adventures_own_heroes_come_before_the_systems(self):
        system = packs.load_system(DRAGONBANE)
        adventure = {"characters": {"ragna": {"name": "Ragna of the tower"}}}
        self.assertEqual(creation.character(system, "ragna", adventure=adventure)["name"], "Ragna of the tower")
        self.assertEqual(creation.character(system, "ragna")["name"], "Ragna")


class Review(CampaignTest):
    def test_outline_shows_gates_stages_and_the_facts_the_gm_must_commit(self):
        text = packs.outline(packs.load_adventure(FIXTURES / "gates"))
        self.assertIn("- to stairs: Stairs that unfold from the ceiling (when fact.hall.stairs_open)", text)
        self.assertIn("  - at 2: The floor shakes. (hall.flooded = true)", text)
        self.assertIn("- hall.stairs_open: read by exit hall -> stairs", text)
        self.assertIn("- tower.sinking: read by clock collapse while, clock collapse trigger (set by a clock stage)", text)

    def test_lint_finds_unreachable_scenes_dead_ends_and_npcs_nobody_meets(self):
        adventure = copy.deepcopy(packs.load_adventure(RED_TUSK))
        adventure["scenes"]["cellar"]["exits"] = {}
        adventure["scenes"]["hall"]["exits"].pop("cellar")
        adventure["npcs"]["witness"] = {"name": "A witness"}
        warnings = packs.lint(adventure)
        self.assertIn("scene cellar can't be reached from road by any exit (only by solo move --force)", warnings)
        self.assertIn("scene cellar has no way out; if the story ends there, mark it ending = true", warnings)
        self.assertIn("npc witness is in no scene's npcs (the GM only meets them if a commit brings them in)", warnings)
        self.assertFalse(any("tentacle" in w for w in warnings))  # a foe may rise mid-fight


class Commits(CampaignTest):
    def test_a_negative_number_for_a_track_is_a_loss_not_a_setting(self):
        with self.session() as c:
            event = c.commit({"pc": {"hp": -3}})
        self.assertEqual(c.state["pc"]["tracks"]["hp"]["value"], 11)
        self.assertIsNone(c.state["pc"]["dying"])
        self.assertIn("read hp -3 as a loss of 3", event["warnings"][0])

    def test_the_gm_sees_the_skills_that_exist(self):
        with self.session() as c:
            self.assertIn("Skills: awareness 10, evade 10, persuasion 8, swords 14; untrained: acrobatics 4", cli.scene_digest(c))
            with self.assertRaisesRegex(SoloError, "no skill or attribute called 'search'; Dragonbane has: str, con"):
                c.check("search")

    def test_one_name_is_one_condition_or_item(self):
        with self.session() as c:
            c.commit({"pc": {"conditions": {"add": "dazed"}, "items": {"add": "a green emerald"}}})
        self.assertEqual(c.state["pc"]["conditions"], ["dazed"])
        self.assertIn("a green emerald", c.state["pc"]["items"])

    def test_the_rules_the_engine_runs_answer_solo_rule(self):
        with self.session() as c:
            pages = packs.engine_rules(c.system)
            found, _ = packs.search_rules([], "grapple", extra=pages)
        self.assertEqual([p["title"] for p in found], ["Fights"])
        conditions = next(p["text"] for p in pages if p["title"] == "Conditions")
        self.assertIn("- dazed: a bane on every roll that uses Agility (agl)", conditions)
        self.assertIn("Stretch rest", [p["title"] for p in pages])

    def test_nested_tracks_are_read_and_money_is_pointed_to_items(self):
        with self.session() as c:
            c.commit({"pc": {"tracks": {"hp": "-2"}}})
            self.assertEqual(c.state["pc"]["tracks"]["hp"]["value"], 12)
            with self.assertRaisesRegex(SoloError, "coins and gear are items"):
                c.commit({"silver": 30})
            with self.assertRaisesRegex(SoloError, "coins and gear are items"):
                c.commit({"pc": {"gold": 3}})

    def test_the_hero_can_be_wounded_by_a_fall_and_armor_helps_unless_it_cant(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Leather armor"]}}})
            fall = c.wound("hero", "1d6", why="a fall on wet stone", rng=Dice(4))
            self.assertEqual((fall["dealt"], c.state["pc"]["tracks"]["hp"]["value"]), (3, 11))
            c.wound("hero", "1d6", why="scalding steam", armor=False, rng=Dice(4))
            self.assertEqual(c.state["pc"]["tracks"]["hp"]["value"], 7)
            self.assertIn("scalding steam: 4 damage", c.state["log"][-1]["text"])

    def test_an_unknown_table_suggests_the_near_ones(self):
        with self.session() as c, self.assertRaisesRegex(SoloError, "did you mean location_danger"):
            c.table("danger")
