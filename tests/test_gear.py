"""What the hero carries changes the rolls: armor hampers the skills the book names, a weapon asks for
STR and for room to be used, and a parry or a blow armor stops is suffered by the weapon. Played on the
made-up test rules (tests/fixtures/house), so every number here is the fixture's."""

from helpers import BEASTS, DRAGONS, CampaignTest, Dice

from solo import SoloError, cli


class Armor(CampaignTest):
    def test_worn_armor_puts_a_bane_on_the_skills_it_hampers(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Chainmail"]}}})
            event = c.check("sneaking", rng=Dice(3, 9))  # a bane: two dice, the worse counts
        self.assertEqual((event["banes"], event["gear_banes"], event["outcome"]["result"]), (1, ["chainmail"], 9))
        self.assertIn("banes 1 [chainmail]", cli.campaign.describe(event))

    def test_a_skill_the_armor_leaves_alone_rolls_as_always(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Chainmail"]}}})
            event = c.check("awareness", rng=Dice(3))
        self.assertEqual((event["banes"], event.get("gear_banes")), (0, None))

    def test_a_helmet_hampers_every_ranged_attack_and_nothing_else_the_weapon_does(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Open helmet", "Reed bow", "Quiver"]}}})
            c.fight(["cultist"], rng=Dice(1, 1))
            shot = c.attack("cultist", "reed bow", distance=10, rng=Dice(2, 9))  # a bane: two dice
            self.assertEqual(shot["gear_banes"], ["open_helmet"])
            c.next_round(rng=Dice(1, 1))
            blow = c.attack("cultist", "broadsword", rng=Dice(19))
            self.assertIsNone(blow.get("gear_banes"))


class StrengthAndReach(CampaignTest):
    def fight(self, c, *items):
        c.commit({"pc": {"items": {"add": list(items)}}})
        c.fight(["cultist"], rng=Dice(1, 1))

    def test_a_weapon_that_asks_for_more_STR_than_the_hero_has_is_a_bane_to_use(self):
        with self.session() as c:
            self.fight(c, "Hook sword")
            blow = c.attack("cultist", "hook sword", rng=Dice(2, 19))  # STR 15 of 18: two dice, the worse (19) misses
        self.assertEqual((blow["gear_banes"], blow["outcome"]["result"]), (["STR 18 needed"], 19))

    def test_a_weapon_the_hero_is_too_weak_for_is_refused(self):
        with self.session() as c:
            self.fight(c, "Maul")
            with self.assertRaisesRegex(SoloError, "too weak for the maul: it needs STR 40"):
                c.attack("cultist", "maul", rng=Dice(2))

    def test_a_bow_needs_a_quiver(self):
        with self.session() as c:
            self.fight(c, "Reed bow")
            with self.assertRaisesRegex(SoloError, "needs a quiver"):
                c.attack("cultist", "reed bow", distance=10)

    def test_a_shot_from_too_near_or_too_far_is_a_bane_and_from_beyond_twice_the_range_is_refused(self):
        with self.session() as c:
            self.fight(c, "Reed bow", "Quiver")
            near = c.attack("cultist", "reed bow", distance=2, rng=Dice(2, 12))
            self.assertEqual(near["gear_banes"], ["within 2 meters of a ranged weapon"])
            c.next_round(rng=Dice(1, 1))
            fine = c.attack("cultist", "reed bow", distance=30, rng=Dice(12))
            self.assertIsNone(fine.get("gear_banes"))
            c.next_round(rng=Dice(1, 1))
            far = c.attack("cultist", "reed bow", distance=60, rng=Dice(2, 12))
            self.assertEqual(far["gear_banes"], ["60 meters is beyond the reed bow's range (30)"])
            c.next_round(rng=Dice(1, 1))
            with self.assertRaisesRegex(SoloError, "61 meters is beyond twice the reed bow's range"):
                c.attack("cultist", "reed bow", distance=61)

    def test_a_thrown_weapon_reaches_as_many_meters_as_the_hero_has_STR(self):
        with self.session() as c:
            self.fight(c, "Dart")
            thrown = c.attack("cultist", "dart", distance=15, rng=Dice(12))  # STR 15: in range
            self.assertIsNone(thrown.get("gear_banes"))
            c.next_round(rng=Dice(1, 1))
            with self.assertRaisesRegex(SoloError, "31 meters is beyond twice"):
                c.attack("cultist", "dart", distance=31)

    def test_a_blow_beyond_a_melee_weapons_reach_is_refused(self):
        with self.session() as c:
            self.fight(c)
            with self.assertRaisesRegex(SoloError, "5 meters is beyond the broadsword's reach"):
                c.attack("cultist", "broadsword", distance=5)


class Durability(CampaignTest):
    system = BEASTS

    def test_a_parry_against_a_blow_worse_than_the_weapon_can_take_breaks_it_until_it_is_mended(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Parry sword"]}}})
            c.fight(["cultist"], rng=Dice(1, 1))
            c.enemy(rng=Dice(5))  # a hit: 1d8
            parry = c.defend("parry", "parry sword", rng=Dice(4, 8))  # the parry succeeds; the blow rolls 8 against durability 6
            worn = c.events[-1]
            self.assertEqual((worn["type"], worn["damage"], worn["durability"], worn["broke"]), ("durability", 8, 6, True))
            self.assertEqual(c.state["pc"]["damaged"], {"parry_sword": "broken"})
            self.assertEqual(c.state["pc"]["tracks"]["hp"]["value"], 14)
            c.next_round(rng=Dice(1, 1))
            with self.assertRaisesRegex(SoloError, "parry sword is broken: mend it first"):
                c.attack("cultist", "parry sword")
            self.assertEqual({w["id"]: w["condition"] for w in kit(c)["weapons"]}["parry_sword"], "broken")  # the Table shows it, and its Mend button
            c.repair("parry sword", rng=Dice(2))  # CRAFTING: the pack's repair skill
            self.assertEqual(c.state["pc"]["damaged"], {})
            self.assertEqual({w["id"]: w["condition"] for w in kit(c)["weapons"]}["parry_sword"], None)
            c.attack("cultist", "parry sword", rng=Dice(19))

    def test_a_blow_the_weapon_can_take_leaves_it_whole(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Parry sword"]}}})
            c.fight(["cultist"], rng=Dice(1, 1))
            c.enemy(rng=Dice(5))
            c.defend("parry", "parry sword", rng=Dice(4, 6))  # 6 does not exceed durability 6
            self.assertFalse(c.events[-1]["broke"])
            self.assertEqual(c.state["pc"]["damaged"], {})

    def test_a_piercing_blow_never_damages_a_parrying_weapon(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Parry sword"]}}, "npc": {"thornback": {"name": "Thornback", "monster": "thornback"}}})
            c.fight(["thornback"], rng=Dice(1, 1))
            c.enemy(rng=Dice(1))  # the spine: piercing
            self.assertEqual(c.state["combat"]["incoming"]["kind"], "piercing")
            c.defend("parry", "parry sword", rng=Dice(4))
            self.assertNotEqual(c.events[-1]["type"], "durability")
            self.assertEqual(c.state["pc"]["damaged"], {})

    def test_a_melee_blow_the_armor_stops_entirely_falls_on_the_weapon(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Dart", "Parry sword"]}}, "npc": {"brute": {"name": "Brute", "template": "boss", "attacker": "melee"}}})
            c.fight(["brute"], rng=Dice(1, 2))
            c.attack("brute", "parry sword", rng=Dice(3, 1, 1))  # 2 against armor 3: nothing gets through, and 2 is under durability 6
            self.assertEqual([c.events[-1]["type"], c.events[-1]["how"], c.events[-1]["broke"]], ["durability", "armor", False])
            c.next_round(rng=Dice(1, 2))
            c.attack("brute", "dart", rng=Dice(3, 3))  # 3 against armor 3, and the dart's durability is 2
            self.assertTrue(c.events[-1]["broke"])
        self.assertEqual(c.state["pc"]["damaged"], {"dart": "broken"})

    def test_an_artisan_mends_what_needs_no_roll(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Parry sword"]}}})
            c.fight(["cultist"], rng=Dice(1, 1))
            c.enemy(rng=Dice(5))
            c.defend("parry", "parry sword", rng=Dice(4, 8))
            c.repair("parry sword", artisan=True)
            self.assertEqual(c.state["pc"]["damaged"], {})
            with self.assertRaisesRegex(SoloError, "is whole"):
                c.repair("parry sword", artisan=True)


class Load(CampaignTest):
    """Capacity is half the STR, rounded up; what weighs what comes from the price lists."""

    def load(self, c):
        from solo import combat
        return combat.encumbrance(c.system, c.state["pc"])

    def test_the_hero_carries_what_the_lists_weigh_and_weapons_at_hand_are_free(self):
        with self.session() as c:
            # Ragna, STR 15: capacity 8. A broadsword and a shield (at hand), a torch (1), a rope the
            # lists don't know (1), four rations (a quarter each) and six silver (tiny).
            self.assertEqual(self.load(c), {"carried": 3.0, "capacity": 8, "over": False})

    def test_armor_worn_a_whistle_and_coins_under_a_hundred_weigh_nothing(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Chainmail", "Whistle", "90 silver"]}}})
            self.assertEqual(self.load(c)["carried"], 3.0)
            c.commit({"pc": {"items": {"add": ["250 copper"]}}})
            self.assertEqual(self.load(c)["carried"], 6.0)  # 346 coins in all: three hundreds are three items

    def test_a_backpack_adds_to_the_capacity_once_and_a_prefix_finds_the_quiver(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Backpack", "Backpack", "Quiver"]}}})
            self.assertEqual(self.load(c), {"carried": 4.0, "capacity": 10, "over": False})

    def test_weapons_past_the_third_count_and_too_much_is_over_encumbered(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Dagger", "Spear", "Chest", "Chest", "Chest"]}}})
            load = self.load(c)
            self.assertEqual((load["carried"], load["over"]), (3.0 + 1 + 9, True))  # the dagger is the third weapon at hand; the spear the fourth
            self.assertIn("OVER-ENCUMBERED", cli.scene_digest(c))
            self.assertEqual(campaign_load(c), load)


def kit(c):
    from solo import campaign
    return campaign.snapshot(c.system, c.state, c.adventure)["kit"]


def campaign_load(c):
    from solo import campaign
    return campaign.snapshot(c.system, c.state, c.adventure)["load"]


class Dragons(CampaignTest):
    """A Dragon on the hero's attack is the player's choice; one on a parry strikes back; a Demon brings a mishap."""

    system = DRAGONS

    def two_foes(self, c, *items):
        c.commit({"pc": {"items": {"add": list(items)}}})
        c.fight(["cultist", "priest"], rng=Dice(1, 2, 3))

    def test_a_dragon_with_more_than_one_use_waits_for_the_players_choice(self):
        with self.session() as c:
            self.two_foes(c, "Spike")
            c.attack("cultist", "spike", rng=Dice(1))
            self.assertEqual((c.events[-1]["type"], c.events[-1]["options"]), ("choice", ["double", "attack", "pierce"]))
            self.assertEqual(c.state["choice"]["options"], ["double", "attack", "pierce"])
            self.assertEqual(len([e for e in c.events if e["type"] == "damage"]), 0)
            with self.assertRaisesRegex(SoloError, "a Dragon is waiting for its choice first"):
                c.enemy("priest")
            with self.assertRaisesRegex(SoloError, "choose what the Dragon does: double, attack, pierce"):
                c.dragon("fly")
            c.dragon("double", rng=Dice(4, 4, 1))  # 1d8 twice and the STR bonus
            blow = c.events[-1]
            self.assertEqual((blow["type"], blow["expr"], blow["dealt"]), ("damage", "1d8+1d8+1d4", 9))
            self.assertIsNone(c.state["choice"])

    def test_a_blow_chosen_to_go_through_armor_ignores_it(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Spike"]}}, "npc": {"brute": {"name": "Brute", "template": "boss", "attacker": "melee"}}})
            c.fight(["brute", "cultist"], rng=Dice(1, 2, 3))
            c.attack("brute", "spike", rng=Dice(1))
            c.dragon("pierce", rng=Dice(5, 2))
            blow = c.events[-1]
            self.assertEqual((blow["armor"], blow["dealt"], blow["how"]), (0, 7, "pierce"))  # boss armor 3 doesn't count

    def test_a_free_attack_on_another_foe_costs_no_turn(self):
        with self.session() as c:
            self.two_foes(c, "Spike")
            c.attack("cultist", "spike", rng=Dice(1))
            c.dragon("attack", "priest", rng=Dice(2, 3, 18))  # the first blow lands as it is; the free attack misses
            self.assertEqual([e["type"] for e in c.events[-3:]], ["dragon", "damage", "check"])
            self.assertEqual(c.events[-1]["attack"], {"weapon": "spike", "label": "Spike", "target": "priest", "free": True})
            with self.assertRaisesRegex(SoloError, "already attacked this round"):
                c.attack("priest", "spike")

    def test_a_dragon_with_one_use_is_not_a_choice(self):
        with self.session() as c:
            c.fight(["priest"], rng=Dice(1, 1))
            hit = c.attack("priest", "broadsword", rng=Dice(1, 3, 3, 2, 2, 1))  # alone, with a weapon that is nothing special: the dice double
            self.assertNotIn("choice", [e["type"] for e in c.events])
            blow = next(e for e in c.events if e["type"] == "damage")
            self.assertEqual(blow["expr"], "2d6+2d6+1d4")

    def test_a_dragon_on_a_parry_strikes_back_and_does_not_double(self):
        with self.session() as c:
            c.fight(["cultist"], rng=Dice(1, 1))
            c.enemy(rng=Dice(5))  # a hit
            c.defend("parry", "broadsword", rng=Dice(1, 3, 3, 2))  # a Dragon: the counterattack is an automatic hit
            blow = next(e for e in c.events if e["type"] == "damage")
            self.assertEqual((blow["how"], blow["expr"], blow["target"]), ("counter", "2d6+1d4", "cultist"))
            self.assertIsNone(c.state["combat"])  # the counterattack finished the cultist, and the fight

    def test_against_a_critical_hit_only_a_dragon_defends(self):
        with self.session() as c:
            c.fight(["cultist"], rng=Dice(1, 1))
            c.enemy(rng=Dice(1))  # the cultist rolls a Dragon: its dagger can't be parried or dodged without one
            self.assertTrue(c.state["combat"]["incoming"]["critical"])
            evade = c.defend("evade", rng=Dice(4, 2, 2))  # Ragna's Evade 10: a 4 would do, but not against this
            self.assertFalse(evade["outcome"]["success"])
            self.assertEqual(c.events[-1]["type"], "harm")

    def test_a_demon_on_an_attack_rolls_the_mishap_and_damages_the_weapon(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Spike"]}}})
            c.fight(["cultist"], rng=Dice(1, 1))
            c.attack("cultist", "spike", rng=Dice(20, 2, 3))  # a Demon, and the table says: damaged (and the ritual clock ticks)
            self.assertEqual(c.state["pc"]["damaged"], {"spike": "damaged"})
            c.next_round(rng=Dice(1, 1))
            blow = c.attack("cultist", "spike", rng=Dice(2, 19))  # a bane for the damage: two dice
            self.assertEqual(blow["gear_banes"], ["spike damaged"])

    def test_a_demon_can_make_the_hero_hit_themselves_with_the_weapon_and_no_bonus(self):
        with self.session() as c:
            c.fight(["cultist"], rng=Dice(1, 1))
            c.attack("cultist", "broadsword", rng=Dice(20, 3, 4, 5, 3))  # the mishap: the broadsword's 2d6, armor 0
            harm = next(e for e in c.events if e["type"] == "harm")
            self.assertEqual((harm["expr"], harm["dealt"]), ("2d6", 9))
            self.assertEqual(c.state["pc"]["tracks"]["hp"]["value"], 5)


class Monsters(CampaignTest):
    """What the book says about monsters: a resistance halves a kind of damage, a troll heals, a swarm feeds, an attack
    isn't repeated, and a monster dodges or parries at a fixed skill."""

    system = BEASTS

    def monster(self, c, name, *more):
        c.commit({"npc": {name: {"name": name.replace("_", " ").capitalize(), "monster": name}}})
        c.fight([name, *more], rng=Dice(*range(1, 4)))

    def test_a_resistance_halves_the_kind_of_damage_after_armor_rounded_up(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Spike", "Parry sword"]}}})
            self.monster(c, "bone_walker")
            c.attack("bone_walker", "spike", rng=Dice(3, 5, 2))  # piercing: 5+2 = 7, armor 1 = 6, half
            blow = c.events[-1]
            self.assertEqual((blow["kind"], blow["resisted"], blow["dealt"]), ("piercing", "half", 3))
            self.assertIn("piercing damage is halved", campaign_text(blow))
            c.next_round(rng=Dice(1, 2))
            c.attack("bone_walker", "parry sword", rng=Dice(3, 5, 2))  # slashing: nothing is resisted
            self.assertEqual((c.events[-1].get("resisted"), c.events[-1]["dealt"]), (None, 6))

    def test_a_weapon_that_cuts_and_stabs_does_the_damage_the_wielder_says(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Twin blade"]}}})
            self.monster(c, "bone_walker")
            c.attack("bone_walker", "twin blade", rng=Dice(3, 5, 2))  # the first kind: slashing
            self.assertEqual((c.events[-1]["kind"], c.events[-1]["dealt"]), ("slashing", 6))
            c.next_round(rng=Dice(1, 2))
            c.attack("bone_walker", "twin blade", kind="piercing", rng=Dice(3, 5, 2))
            self.assertEqual((c.events[-1]["kind"], c.events[-1]["dealt"]), ("piercing", 3))
            c.next_round(rng=Dice(1, 2))
            with self.assertRaisesRegex(SoloError, "can't do bludgeoning damage: slashing, piercing"):
                c.attack("bone_walker", "twin blade", kind="bludgeoning")

    def test_physical_resistance_covers_every_weapon_and_immunity_takes_all_of_it(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Spike"]}}})
            self.monster(c, "leech_swarm")
            c.attack("leech_swarm", "spike", rng=Dice(3, 5, 3))
            self.assertEqual((c.events[-1]["resisted"], c.events[-1]["dealt"]), ("half", 4))  # 5+3 = 8, half
        with self.session() as c:
            c.end_fight()
            c.commit({"pc": {"items": {"add": ["Spike"]}}})
            self.monster(c, "wraith")
            c.attack("wraith", "spike", rng=Dice(3, 5, 3))
            self.assertEqual((c.events[-1]["resisted"], c.events[-1]["dealt"]), ("immune", 0))
            fire = c.wound("wraith", "2d6", "a torch", kind="fire", rng=Dice(3, 4))  # fire isn't physical
            self.assertEqual((fire.get("resisted"), fire["dealt"]), (None, 7))
            cut = c.wound("wraith", "2d6", "a blade", kind="slashing", rng=Dice(3, 4))
            self.assertEqual((cut["resisted"], cut["dealt"]), ("immune", 0))

    def test_a_monster_that_heals_does_so_before_each_of_its_turns(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Spike"]}}})
            self.monster(c, "moss_troll")
            c.attack("moss_troll", "spike", rng=Dice(3, 4, 1))  # 5 damage: HP 25
            c.enemy(rng=Dice(3, 1, 4))  # heals 3 (a d4), then rolls its attack: 4 is the bite
            heal = next(e for e in c.events if e["type"] == "heal")
            self.assertEqual((heal["hp_was"], heal["hp"], heal["by"]), (25, 28, "regeneration"))
            self.assertEqual(c.state["combat"]["foes"]["moss_troll"]["hp"], 28)

    def test_a_swarm_that_feeds_heals_by_the_harm_it_does(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Spike"]}}})
            self.monster(c, "leech_swarm")
            c.attack("leech_swarm", "spike", rng=Dice(3, 4, 1))  # half of 5-... : spike 4+1 = 5, half rounded up = 3: HP 9
            c.enemy(rng=Dice(3))
            c.defend("take", rng=Dice(5))  # the swarm bites for 5; it drains that much
            heal = next(e for e in c.events if e["type"] == "heal")
            self.assertEqual((heal["hp_was"], heal["hp"], heal["by"]), (9, 12, "drain"))  # up to its 12 and no more

    def test_a_monster_never_repeats_an_attack_the_second_roll_is_the_next_on_the_table(self):
        with self.session() as c:
            self.monster(c, "moss_troll")
            first = c.enemy(rng=Dice(1))  # the claw
            self.assertEqual(first["text"], "It claws at you.")
            c.defend("take", rng=Dice(3))
            second = c.enemy(rng=Dice(2))  # the claw again: it becomes the bite
            self.assertEqual((second["text"], second.get("again")), ("It bites at you.", True))
            c.defend("take", rng=Dice(3))
            third = c.enemy(rng=Dice(6))  # the stomp; then
            c.defend("take", rng=Dice(2, 2))
            fourth = c.enemy(rng=Dice(5))  # the stomp again: the last result wraps to the first
            self.assertEqual((third["text"], fourth["text"], fourth.get("again")), ("It stomps on you.", "It claws at you.", True))

    def test_a_monster_dodges_against_the_packs_number_and_against_a_critical_hit_only_a_dragon_does(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Spike"]}}})
            self.monster(c, "bone_walker")
            c.attack("bone_walker", "spike", defended="dodge", rng=Dice(3, 7))  # a hit; its own EVADE is 9: a 7 dodges it
            self.assertEqual([e["type"] for e in c.events[-2:]], ["check", "defence"])
            self.assertTrue(c.events[-1]["avoided"])
            self.assertEqual(c.state["combat"]["foes"]["bone_walker"]["hp"], 14)
            self.assertEqual(c.to_act(), [])  # the hero has attacked, and its dodge was its action
            c.next_round(rng=Dice(1, 2))
            c.attack("bone_walker", "spike", defended="dodge", rng=Dice(1, 4, 3, 3, 2))  # a Dragon: only a Dragon dodges; a 4 doesn't
            defence = [e for e in c.events if e["type"] == "defence"][-1]
            self.assertEqual((defence["critical"], defence["avoided"]), (True, False))
            self.assertEqual(c.events[-1]["type"], "damage")

    def test_a_monster_parries_only_with_a_weapon_and_rolls_the_monster_number(self):
        with self.session() as c:
            c.commit({"pc": {"items": {"add": ["Spike"]}}})
            self.monster(c, "leech_swarm")
            with self.assertRaisesRegex(SoloError, "carries no weapon to parry with"):
                c.attack("leech_swarm", "spike", defended="parry", rng=Dice(3))
        with self.session() as c:
            c.end_fight()
            c.commit({"pc": {"items": {"add": ["Spike"]}}})
            self.monster(c, "moss_troll")
            c.attack("moss_troll", "spike", defended="parry", rng=Dice(3, 12))  # 12: the monster number, a parry
            self.assertTrue(c.events[-1]["avoided"])


def campaign_text(event):
    from solo import campaign
    return campaign.describe(event)
