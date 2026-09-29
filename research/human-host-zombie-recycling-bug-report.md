# Horde zombies reused with movement disabled after simultaneous deaths

**Severity: Low (mod compatibility).** Living zombies lose movement/gravity
updates and can remain airborne. Observed in modded combat; vanilla and
multiplayer reproduction are untested.

**Detected:** Human Host **0.8.316**, Steam build **25587699**, Windows x64,
BepInEx **5.4.23.5**. Relevant loaded mods:[1]

| Mod | Version | Relevant configuration or role |
|---|---|---|
| Expanded Hordes | 0.2.0 | 125 living horde zombies; 1,000 retained corpses |
| Railgun Turrets | 1.0.0 | 10 m area-damage radius |
| Human Host Explosives | 0.3.0 | Additional area-damage provider |
| Wandering Hordes - Zombie Overhaul | 0.1.3 | Other zombie-behavior changes present |
| Human Host Quick Loot | 1.0.5 | Corpse cleanup present |
| Admin Panel / Admin Panel - Fly Mode Fix | 1.1.9 / 0.1.2 | Present during capture |
| Human Host - Zombie Movement Fix | 0.1.0 | Instrumentation and recovery workaround |

This is not a minimal mod set; all 31 plugin versions are in [1]. Area damage
provides plausible simultaneous-kill triggers; the responsible weapon is unproven.

## Failure sequence

1. **Creature.dll:** `NPC_Input.On_Char_Died` calls
   `C_Controller_Base.On_Char_Died` **before** assigning `enabled = false`.
   The base method dispatches `Creature_Mgr._On_Char_Died`.
2. **Terrain.dll:** `NPC_Spawner_Mgr.On_Char_Died` →
   `Back_Dead_NPC_To_Pool` → `Delay_Back_Dead_NPC_To_Pool`.
   When `_waitSpawnBodyCount > _maxDeadRagdolls` (serialized limit **4**)
   and `startFrame == min(_corStartFrameList)`, the overflow branch completes
   cleanup **before its first yield**, inside the original death call.[1] [2]
   Same-frame deaths can satisfy this tie condition.
3. `NPC_Horde_Mgr.Put_NPC_Back_To_Pool` resets health, removes spawn ownership,
   deactivates the object and sets its controller `enabled = true` for reuse.
4. Returning to `NPC_Input.On_Char_Died` executes the remaining
   `enabled = false`, overwriting that reset. Later, `Spawn_Horde_NPC` activates
   the pooled object without explicitly re-enabling its controller.
5. **Creature.dll:** `C_Controller_Base.MyFixedUpdate` / `HandleMomentum`
   no longer supply normal NPC gravity. Affected recorded bodies were dynamic
   with `Rigidbody.useGravity = false`.[1]

The retained-corpse setting is separate: `GPUI_Dead_Body_Mgr.Spawn_GPUI_Dead_Body`
reads `_MaxCorpseCount` after this overflow decision.

## Reproduction and evidence

**Suggested engine test:** with no pending ragdoll cleanup, kill 12 initialized
horde zombies with ragdolls available through the normal damage path in one
frame. Inspect controllers after death returns and after `Spawn_Horde_NPC`
reuses them. Reusable controllers should remain enabled.

An offline reproduction using the unchanged native death method and overflow
branch produced **four pending ragdolls and eight disabled pooled controllers**
at corpse limits **50, 300 and 1,000**. Engine/pool boundaries were substituted;
this was not a Unity test. All **57 recorded recovery cases** independently followed
pool-return/enabled → death-return/disabled → live-spawn/disabled.[1]

## Mod-side mitigation

Local **Expanded Hordes 0.2.1** records successful pool return inside the same
death callback. On return, it restores the overwritten enabled flag only if
the object remains inactive, healthy, unowned by the spawn registry and absent
from pending cleanup. Exceptions and already-enabled controllers are left
alone. No recurring scans are added. The reproduction passes with this guard;
gameplay verification of this prevention is pending.[1]

Native fix candidate: defer pool return until death dispatch finishes, so death
processing cannot overwrite the reset. Callback side effects need your review;
the mod workaround is not a prescribed engine design.

[1]: human-host-zombie-recycling-evidence.txt
[2]: https://docs.unity3d.com/2022.3/Documentation/ScriptReference/MonoBehaviour.StartCoroutine.html
