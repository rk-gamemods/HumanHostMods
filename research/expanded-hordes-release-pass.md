# Expanded Hordes release preparation

Scope authorized 2026-09-22: persistent resistance for horde-spawned zombies,
separate regular/large/boss controls if practical, larger optional corpse
capacity (default 300), modular code, compatibility/failure isolation, optional
debug logging and profiling, local installation and Workshop-ready materials.
Publication waits for the user's play test and account setup. No computer use,
game launch, save changes, speculative gameplay features or bundled game code.

## Boundaries

| Owner | Contract |
| --- | --- |
| Plugin / feature installation | Bind settings once; install independent Harmony groups; rollback only the failing group; unpatch only this mod on shutdown. |
| Population / attraction | Preserve existing multiplied budget, separate living cap, vanilla cadence and one-time attraction. |
| Creature catalog | One definition list for built-in special identities; resolve against native shuffled groups. Native boss flag takes precedence; unknown types are regular until explicitly classified. |
| Resistance | Scale health loss for living, registered horde zombies; never change maximum health, XP or ambient enemies. Native membership persists through dawn and reload and ends on pool removal. No additional save schema. |
| Run speed | Retain the selected nighttime spawning-only boundary. |
| Corpse retention | Change only the limit consumed by native corpse creation; never mutate saved world settings, disable cleanup, or replace the corpse manager. Respect a higher limit supplied by another mod. |
| Diagnostics | Off by default. Bounded aggregate logs and CSV summaries; report missing GPU/CPU timing as unavailable, not zero or a diagnosed bottleneck. Original game exceptions remain visible. |
| Packaging | Original DLL and documentation only; repeatable offline build, content hashes, Workshop description/preview/upload instructions; no automatic publication. |

## Source checks and acceptance

`NPC_Horde_Mgr.Remove_AliveHordeNPC` removes a dead zombie from the living
population. `GPUI_Dead_Body_Mgr.Spawn_GPUI_Dead_Body` independently evicts an
old retained corpse when its active-body count reaches the configured limit.
Its first-instance branch does not perform that eviction, so this is a native
retention target, not an exact global cap. Native lifetime and distance handling
remain in force. More retained settled bodies do not mean permanent physical
ragdolls or a guarantee of collision-based piles.

`Char_Status._CurrHP` is the common inspected health-loss boundary for weapons,
falls and falling structures. Guarding by native horde membership excludes
spawn initialization and pool reset: the former happens before registration,
the latter restores lower base HP after removal. Healing and dead bodies are
excluded. Maximum HP and kill XP calculations are untouched. Other mods that
bypass this property or force death directly are outside this boundary.

Acceptance includes policy tests, installed-assembly method/field/IL checks,
config upgrade/readback/idempotence, clean build, deployment hash, package
allowlist/hash checks and a written manual test matrix. Runtime compatibility,
damage feedback, saved survivors, corpse appearance and performance require
the user's play test; automated checks cannot certify those outcomes.
