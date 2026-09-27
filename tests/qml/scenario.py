"""Real engine state for rendering the Book: The Red Tusk Hall, played to a fight."""

import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent.parent), str(HERE.parent)]
os.environ.setdefault("XDG_STATE_HOME", tempfile.mkdtemp())

from helpers import DRAGONBANE, RAGNA, RED_TUSK, Dice, install_rules  # noqa: E402, F401
from solo import campaign  # noqa: E402


def play(out):
    root = campaign.create(Path(tempfile.mkdtemp()) / "game", DRAGONBANE, RED_TUSK, RAGNA)
    with campaign.session(root) as c:
        c.say("Rain has turned the old road to mud. Ahead, smoke rises from behind a palisade of sharpened logs, "
              "and the wind carries drums and laughter down the hill.\n\nFresh boot prints, *too big for a human*, "
              "lead up toward the gate. What do you do?")
        c.say("I follow the prints up to the gate, keeping to the ditch.", by="player")
        c.move("gate", rng=Dice(2))
        c.say("The gate is shut. A torch gutters above it, and someone has carved a tusk into the wood. "
              "In the mud lies a broken axe. Two shapes move on the platform. **What now?**")
        c.say("I try to slip past the guards.", by="player")
        c.check("sneaking", rng=Dice(12))
        c.commit({"note": "the horn sounds", "facts": {"hall.alarm": True}}, rng=Dice(4))
        c.say("A horn splits the rain. Somewhere below the hall, a chant answers it.")
        c.move("hall", rng=Dice(3))
        c.commit({"learn": ["orc_leader.fears"]})
        c.say("Grukk rises from his throne of shields, laughing too loud, and hefts his axe. Behind him a cultist "
              "in a sodden robe draws a curved knife. What do you do?")
        c.say("I draw my broadsword and go for the cultist first.", by="player")
        c.fight(["orc_leader", "cultist"], rng=Dice(1, 2, 3))
        c.attack("cultist", rng=Dice(3, 6, 6, 4))
        c.enemy("orc_leader", rng=Dice(5))
        c.defend("take", rng=Dice(6, 2))
        c.commit({"pc": {"conditions": {"add": ["angry"]}}})
    (Path(out) / "fight.json").write_text((root / "state.json").read_text())
    with campaign.session(root) as c:
        c.enemy("orc_leader", rng=Dice(5))
        c.defend("take", rng=Dice(8, 8))
        c.next_round(rng=Dice(1, 2))  # struck down after attacking: the first death roll is next round
        c.death_roll(rng=Dice(20))
        c.say("Not like this. Not in an orc's hall.", by="player")
        c.next_round(rng=Dice(1, 2))
        c.death_roll(rng=Dice(15))
    (Path(out) / "dead.json").write_text((root / "state.json").read_text())
    return root


if __name__ == "__main__":
    play(sys.argv[1])
