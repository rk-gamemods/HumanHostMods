# Horde run speed and unfinished feature discussions

Research began 2026-09-21. The user subsequently authorized implementation,
restricted the effect to horde time, and selected ending it when horde spawning
ends. Implemented as a configurable 125% default for horde-spawned zombies;
ordinary attracted zombies remain unchanged. See the
[current implementation and play checks](../mods/ExpandedHordes/README.md).
Other optional features listed below remain unapproved and unimplemented.

## Run speed: modest implementation scope

A configurable multiplier is feasible: 100% means each zombie's normal running
speed; 125% means 25% faster. The game already identifies horde-spawned enemies,
so distinguishing them from ordinary nearby zombies needs no new membership
system. A speed multiplier need not force walking zombies to start running.

The implemented narrow hook is `C_Controller_Base.Play_Anim_BaseLayer`: change its
speed argument only for a qualifying zombie's running movement clip. This
method handles both normal animation and GPU crowd animation, and updates speed
even when the current clip stays the same. Scaling the running animation should
keep leg motion and movement together. Build and policy checks pass; runtime
behavior is not yet verified. Attack clips remain outside the filter.

A one-time assignment to `_moveSpeed` at spawn would not work reliably. Native
animation continuously supplies movement speed, and target/day/running changes
reset movement factors. A blanket animation multiplier could also speed up
attacks or other actions. Neither shortcut is needed for the requested feature.

The multiplier itself should have very low processing cost. Faster arrivals can
concentrate fighting, collisions and base destruction; their performance cost
has not been measured. No additional zombies or extra path searches are
inherently required by a run-speed multiplier.

The user confirmed that the speed change must apply only during the horde time
frame, with normal running speed outside it, and selected ending the effect
when horde spawning ends. The implementation checks `_corHordeSpawn` and
`_IsDayTime`, plus native horde membership and running state. It changes the
animation call argument, without mutating saved or pooled movement stats.
Necessary play checks are actual running speed,
unchanged attacks/walking, normal versus crowd rendering, and returning to
normal speed at the selected boundary.

## Source evidence

Inspected local game source revision
`75505302bbe546b6f783690e4d97230c537edda0` (Steam build 25448142):

- [NPC_Horde_Mgr.Spawn_Horde_NPC](../HumanHostCodebase/Terrain/NPC_Horde_Mgr.cs):
  sets `_npcSpawnSource = 2` on horde enemies.
- [Zombie_Input](../HumanHostCodebase/Creature/Zombie_Input.cs): `OnEnable`,
  `On_Zombie_Found_Target`, `On_Zombie_Lost_Target`, `On_Char_Was_Hit` and
  `On_DayTimeChanged` govern native walk/run choices and reset factors.
- [NPC_Input](../HumanHostCodebase/Creature/NPC_Input.cs): `NPC_Fast_Run` resets
  factors; `Move_NPC_To_Pos` reads GPU crowd root-motion speed.
- [RootMotion_Handler.OnAnimatorMove](../HumanHostCodebase/Creature/RootMotion_Handler.cs):
  derives ordinary animation movement speed and applies the bone-injury cap.
- [C_Controller_Base](../HumanHostCodebase/Creature/C_Controller_Base.cs):
  `Input_WSAD` sends movement clips and their speed to `Play_Anim_BaseLayer`;
  that method supports both render modes. `CalculateMoveVelocity` and
  `MyFixedUpdate` apply movement through the native physics controller.

## Other discussions and later decisions

Update 2026-09-22: the user subsequently authorized damage resistance, increased
corpse retention and optional diagnostics, now implemented in 0.2.0. See the
[release contract](expanded-hordes-release-pass.md). Stagger/knockdown changes,
separate loot preservation and the other options below remain unimplemented.

These were retained in the [handoff](expanded-hordes-handoff.md), D6-D11, and
[original research](expanded-hordes.md#5-optional-intensity-and-progression-controls),
but were not completed in the decision discussion. The effort assessments below
come from that earlier research; this follow-up rechecked run speed specifically.

| Feature | Earlier assessment and unresolved choice |
| --- | --- |
| Horde health | Relatively small multiplier; more maximum HP also increases native kill XP. |
| Horde attack damage | Modest scope; damage to the player and damage to structures can be separate choices. |
| Resistance and stagger/knockdown | A narrow existing damage factor is simpler than covering every damage source or reaction. |
| Attack speed | Separate from running speed; needs animation and attack timing to agree. |
| Jumping | More involved; larger jump values do not create usable navigation routes. |
| Corpse and loot handling | Retain native cleanup, retain bodies longer, or preserve loot separately. Stronger guarantees require more state. |
| Save/load continuation | Native behavior versus preserving replenishment through a save with no surviving horde members, or preserving survivor HP. |
| Difficulty progression and rewards | Optional scaling inputs and XP/loot behavior; not needed to expose a fixed run-speed multiplier. |
| Fewer stronger enemies or adaptive population | Strength tuning is narrower; automatic population adjustment adds changing difficulty and control logic. |

Existing boss/large-zombie composition is already implemented. The table records
the earlier research, not permission to implement additional features. The later
resistance/corpse authorization is recorded above.
