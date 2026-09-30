The bell hangs from a beam of black oak in a round chamber where the roof rises into darkness: a great bronze thing green with age, its mouth ringed with names too worn to read. It is swinging, and there is no rope to swing it. Below it stands a woman in a shroud the colour of river-ice, her hands folded on the pommel of an iron staff, her face turned down, listening to it the way you listen to your own name.

She lifts her head. Her eyes are the two pale lamps of a road no one has lit in a long time.

"You've come to answer," says Hild. "Good. Someone should."

::: gm
**Hild** is the Warden and she is angry in the cold, exact way of a law being read aloud. She wants what she was promised: three lamps and three names, oil and bread, said and kept. She fears the only thing the dead fear, to be forgotten. Play her formal, cadenced, never raising her voice; she says *the ford* and *the oath* and *the ones who are owed*. She will not lie. She does not want to hurt anyone. But she is very old, and very strong, and the bell will go on ringing until someone answers for the ford.

**Three ways this can end.** None is wrong; each costs something.

1. **Keep the oath.** If the hero has lit the lamps (`lamps.lit`) or does it now, says her three names, and lays down bread and oil, she listens. This is a *Compel* (+heart), or *Face Danger* (+heart) with the lamps behind it; +1 if `rhyme.known` and the hero said it word for word. On a strong hit she takes the offering, the bell falls silent, and the ringers wake. On a weak hit she takes it, but wants more: a promise (make one, and hold them to it: it is a vow of its own, or a bond with the hamlet). On a miss she means to be answered another way, and the hero is in the fight of their life. Commit **`bell.silenced`**.
2. **Break her.** The hero can fight Hild. She is a **formidable** foe (1 progress per harm; she inflicts 3 harm). This is a desperate thing and a bad idea, and the player should be told so before it starts. Track: **`solo track add "Hild the Warden" --kind combat --rank formidable`**. If the hero wins, the bell stops for good: commit **`hild.slain`** and **`bell.silenced`**, and a consequence, because the oath is broken and no one keeps the ford's dead any more: the dead of the hamlet's little graveyard will walk again, in the spring.
3. **Run.** The hero can leave. The bell goes on, and nothing else will silence it: every miss the hero makes after this is another stroke, and Marrow Ford falls one household at a time as the eighth comes closer.

**After.** When the bell falls silent, the hero can leave the barrow and go down to the morning (`dawn`): the exit opens with the fact `bell.silenced`. Before they leave, if Hild has been answered, she may say one thing to them, and it should be worth hearing: what the barrow's dead have been keeping the river from. Ask the oracle.

**The vow.** When the hero believes they've done what they swore, *Fulfill Your Vow*: a progress roll against the vow's track. Make sure they've made progress on it along the way: a milestone is an event that moves the story (`Reach a Milestone`): learning the truth, reaching the barrow, freeing the ringers, silencing the bell.

**Moves that fit here:** Compel, Face Danger, Secure an Advantage, Endure Stress (Hild's cold, her grief), Enter the Fray, Strike, Clash, End the Fight (if they fight), Fulfill Your Vow.
:::
