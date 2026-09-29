# Airborne zombies: death and pool reuse investigation

Investigated 2026-09-29 against Human Host 0.8.316, Steam build 25587699.
The user asked for the underlying mod interaction after the recovery workaround
appeared successful, then proposed Expanded Hordes' population/corpse limits.
They observed some airborne zombies and some normal zombies. They did not
observe the moment of spawning or a transition from ground to sky.

## Confirmed failure

All 57 recovery attempts in the successful playtest follow the same ordered
events for the same object: pool return with controller enabled and object
inactive; death completion at the same game time with controller disabled and
object inactive; later horde spawn with the controller still disabled; recovery.
There are 47 distinct pooled object IDs, which are not distinct logical lives.

Across 915 spawn events, 57 were disabled. Across 917 death completions, 68
already had positive reset health, were inactive and no longer awaiting corpse
cleanup, but had disabled controllers. Eleven same-time death bursts account
for those 68 objects. Every burst left four pending ragdolls and immediately
pooled the remainder. For example, 12 deaths left four pending and eight broken
pooled objects. Eleven broken pooled objects were not observed respawning before
the captured session ended.

`Creature:NPC_Input.On_Char_Died` invokes its base method before disabling the
controller. `Creature:C_Controller_Base.On_Char_Died` dispatches death listeners.
`Terrain:NPC_Spawner_Mgr.On_Char_Died` calls `Back_Dead_NPC_To_Pool`, which starts
`Delay_Back_Dead_NPC_To_Pool` synchronously until its first yield.

The coroutine's overflow branch uses `_maxDeadRagdolls`, confirmed as four in
both generated serialized records `level1#762` and
`bundles/icons_common_scenes_all.bundle::serialized-1#11776`. Deaths sharing the
oldest pending frame can complete this coroutine before any yield. It calls
`Terrain:NPC_Horde_Mgr.Put_NPC_Back_To_Pool`, which resets health, removes spawn
ownership, deactivates the object and enables its controller. Returning to the
still-running NPC death callback then disables that prepared controller again.

`Terrain:NPC_Horde_Mgr.Spawn_Horde_NPC` does not explicitly enable the recycled
controller. Normal NPC spawning does. `Creature:C_Controller_Base.MyFixedUpdate`
and `HandleMomentum` apply NPC gravity; the dynamic Rigidbody has built-in
gravity off. Disabled movement therefore leaves physical motion without the
normal controller gravity correction. The earlier report's ten airborne
zombies all had this disabled, unregistered state.

## Which mod exposes it?

Expanded Hordes 0.2.0 currently permits 125 living horde zombies, shared AI 200,
and 1,000 retained corpses. The retained-body setting affects
`Creature:GPUI_Dead_Body_Mgr.Spawn_GPUI_Dead_Body`, which reads
`G_Save:G_Save.ConfigData._MaxCorpseCount` after the overflow decision above.
Its body collections are dynamic dictionaries. No fixed 300-entry storage
boundary was found on this path. Expanded Hordes does not change the separate
four-ragdoll limit.

The local native-branch reproduction produces eight broken pooled objects from
12 same-frame deaths with corpse caps of 50, 300 and 1,000 alike, starting with
zero retained bodies. Four same-frame deaths produce none. Separate-frame deaths
with an older pending frame also avoid immediate pooling in this reproduction.
This rejects the proposed 300-settled-corpse threshold for the recorded failure.

Railgun Turrets is configured for a 10-metre blast radius. The current slot 1
turret state contains six enabled railguns and one enabled laser, all with no
per-turret overrides. Its `TurretAoe.Explode` loops through up to 32 targets,
calling native `Build_System:Smash_Fallen_Manager.Minus_Char_HP`. The native
method can defer hits for animation conversion, then apply them together on
the next frame. HumanHostExplosives also has native area-damage calls.

Larger crowds and area-damage weapons can expose this native ordering defect.
The event logs establish the death bursts and ensuing bad pool state, but do
not identify the weapon responsible for each burst. Railgun attribution remains
a supported candidate, not a proven finding. No vanilla-versus-modded gameplay
comparison was run. There is no evidence that fly-mode state or save corruption
caused these recorded failures.

## Reproducible evidence

Private snapshot, under this worktree:
`.local/user-reported-failure/successful-playtest-20260929T035854/` contains
`events.jsonl` (3,844 rows), `latest.json` and `LogOutput.log`.
The final zero-zombie summary came after leaving the active scene; it does not
prove the population was healthy during combat.

Run from this worktree:

```powershell
py -3 .local/user-reported-failure/verify_death_order.py
py -3 .local/user-reported-failure/inspect_corpse_limits.py
py -3 .local/user-reported-failure/reproduce_burst.py
dotnet run --project .local/user-reported-failure/successful-playtest-20260929T035854/native-burst-repro -c Release
dotnet run --project .local/user-reported-failure/successful-playtest-20260929T035854/native-burst-repro -c Release -- --guard
```

The first native-burst run intentionally fails with eight disabled pooled
objects. The guarded run passes. It extracts the unchanged native NPC death
method and overflow branch and links the production scope tracker. Engine,
pool reset and settled-body storage boundaries are substituted; it does not
run Unity physics or actual game Harmony detours. Generated proprietary source
stays ignored and local. Native assembly SHA-256 values:

- Creature: `62f4cc7b8d070dd6f422624b9f4f565b632f1f3a9fcc6d388f0bbb85777fea93`
- Terrain: `9d7aa125d6037ad943c7baf2724edf2e9ffe713ec939dc2a6fa3881d1ff15fd0`

## Preventative change

The standalone `HumanHost-ExpandedHordes` repository owns the new 0.2.1 guard,
on branch `codex/prevent-disabled-horde-reuse`. Its `docs/DEATH_RECYCLING.md`
documents the contract. It witnesses successful pool return inside a death
callback and restores only the inactive, healthy pooled object's overwritten
enabled flag. It adds no scene scans or per-frame work. An upstream correction
that already leaves the controller enabled is a no-op.

The separate Zombie Movement Fix remains the recovery fallback during the next
user-run playtest. Its existing scans and diagnostic costs are unchanged by
this preventative update. The Admin Panel fly patch also remains separate.
The user controls gameplay; new guard runtime verification is pending.

Local installation completed with the game closed. Standalone commit
`8825782db9554ecfffb91f71b99a222d30fb4c08` built with zero warnings/errors;
48 focused recycling checks and 589 existing/installed-contract checks passed.
Only `BepInEx/plugins/ExpandedHordes/ExpandedHordes.dll` was replaced. All 841
other files under plugins, configs, slot 1 and Auto_Save matched their
pre-install SHA-256 values. The old DLL and manifest are in the standalone
repository's `.local/before-death-recycling-20260929T002450/` directory.
No game launch or public publication was performed.
