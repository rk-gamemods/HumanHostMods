# Admin Panel - Fly Mode Fix

An automatic patch for Admin Panel, with a manual repair tool for zombies
already stuck in the air. The patch runs whenever the game runs. The repair
tool runs only when requested. Both are included in this one mod.

Human Host Mod Manager lists it as **Admin Panel - Fly Mode Fix**, next to
**Admin Panel** when sorted by name. Its DLL carries the same name because
HHMM uses the filename for locally installed mods. Previously named
ZombieRecovery; remove that old DLL when upgrading to avoid duplicate copies.

Prepared for Human Host 0.8.316.
It corrects two Admin Panel 1.1.9 patches that affect all creature controllers
when the player enables Fly Mode. Existing airborne zombies need separate
diagnosis: that fly flag is not serialized, and turning it off resumes gravity
in the isolated controller reproduction. The guard alone does not establish
the cause of a problem that survives restarting the game.

## Compatibility boundary

The guard requires both version 1.1.9 and SHA-256
`a2b02ef182a1c1e88aa591ada1fc87adfb3e3b0a02ce6336328e0a246de0ac6d`.
It verifies the original two Harmony registrations, preserves their priority
and before/after metadata, and replaces only those registrations with wrappers
that call the original Admin Panel methods for player controllers. Other NPCs
retain the game result and normal input. Other mods' patches remain registered.

Installation is idempotent within the plugin instance. Failure rolls back the
registrations, and unloading restores the original registrations. An updated
or otherwise changed Admin Panel DLL is left untouched, even if its version
number did not change. This deliberately avoids applying today's workaround
to a future upstream correction. It does not guarantee compatibility with
every other mod's patch ordering.

No third-party files or configuration are edited. Removing this plugin while
the game is closed removes the guard on the next launch.

## Diagnostics and recovery

Reports are written to `BepInEx/plugins/Admin Panel - Fly Mode Fix/diagnostics/latest.json`.
Version 0.1.2 fixes a diagnostic defect in 0.1.1: the old serializer wrote totals
but omitted the per-zombie rows. Reports now use plain data contracts and verify
the row count before publication. A rolling history retains successive snapshots
(two files of roughly 8 MiB each). Read-only movement and anti-fall probes record
controller calls and repositioning, while each row reports why repair excludes
that zombie and where its physics body and visible model are located. These
probes do not change movement. The persistent floating-zombie cause remains
unconfirmed until a report from the affected game session supplies that evidence.

Press **Ctrl+Shift+F8** to request a fresh report. Recovery starts disabled on
each session and save change. **Ctrl+Shift+F9** enables a 120-game-second pass;
repeating the shortcut during that pass does not restart it.

A zombie must be alive, upright, non-ragdoll, using active registered dynamic
physics, and at least eight metres above a raycast-confirmed surface. Its
height and vertical velocity must remain nearly stationary for six game
seconds. Pauses, streaming gaps, save changes and world-origin shifts cannot
accumulate that observation. Missing terrain, falling zombies and unsuitable
surfaces are excluded. Ground placement requires a clear capsule and support
across the footprint.

Recovery moves only vertically, clears motion, updates the anti-fall anchor
and fall-height baseline, and refreshes mover rays. It preserves health and
inventory. A journal record must be written before changing the zombie.
Grounded zombies no longer qualify on subsequent passes. Normal game saving
persists recovered positions; this plugin does not rewrite save files.

Back up the entire save and autosave before recovery. The detector is
conservative and cannot recover every possible cause of an airborne zombie.
Reports and journal entries are local diagnostics, not suitable for commits.

## Inspected game members

Verified against the 0.8.316 decompilation before implementation:

- `C_Controller_Base.DetermineControllerState`, `Input_WSAD`, `MyFixedUpdate`
  and `HandleMomentum`: shared player/NPC movement and gravity.
- `C_Controller_Base.Anti_Fallen_Into_EmptyAir_NPC`, `Sync_AntiFall_Anchor`:
  recovery anchor and periodic NPC fallback.
- `Creature_Mgr.Raycast_FixedUpdate`: controller registration and ground tests.
- `CMF.Mover.Reset_Rays`: rebuild ground probes after repositioning.
- `NPC_Horde_Mgr._Restore_Horde_NPCs`, `Save_Horde_Data_To_Disk`: saved world
  positions and their restoration.
- Admin Panel `Plugin.DetermineControllerState_Postfix` and
  `Plugin.Input_WSAD_Prefix`: the two unscoped Fly Mode patches.

## Build and checks

```powershell
dotnet run --project tests/AdminPanelFlyModeFix.Checks -c Release
dotnet build HumanHostMods.slnx -c Release
# Only while the game is closed:
dotnet build mods/AdminPanelFlyModeFix -c Release -p:DeployToGame=true
```

The isolated checks cover production decision rules, not Unity terrain or
Harmony dispatch. The user performs all game launches, gameplay and HHMM UI
verification. After user testing, inspect the BepInEx log for the two
replacements and compare diagnostic reports before and after any recovery.
