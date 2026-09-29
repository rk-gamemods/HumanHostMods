# Human Host - Zombie Movement Fix

An automatic workaround for living zombies whose movement controllers are
disabled while their physics bodies remain active. It targets the state found
in the affected slot 1 session. It attempts both recovery of affected zombies
already present and correction of new occurrences. **The user reports that the
recovery stopped the visible flyers; its log records 57 successful repairs.**

Load the save and play normally. No hotkey is required. HHMM's local-mod entry
uses the DLL name **Human Host - Zombie Movement Fix**. This is separate from
[Admin Panel - Fly Mode Fix](../AdminPanelFlyModeFix/README.md), which patches
two confirmed Admin Panel bugs. Subsequent investigation established a separate
death/pool ordering failure; see [the investigation](../../research/zombie-death-recycling.md).

## What the evidence establishes

The user's observation is that some zombies are airborne and others behave
normally. They have not witnessed a zombie going from ground to sky and cannot
see the spawn moment. The diagnostic evidence is separate: all ten airborne
living zombies in the latest 0.1.2 report had disabled controllers, no fixed
update registration, and active dynamic bodies with built-in gravity off.
The report also contained 108 enabled, registered controllers. Some successive
samples showed positive vertical velocity while controller calls had stopped.
Pooled object IDs do not establish continuity across logical lifetimes.

Human Host applies NPC gravity through its controller updates. A disabled,
unregistered controller cannot apply that gravity. The earlier manual hover
repair required registered controllers and near-zero vertical velocity, so it
selected none of the ten recorded failures. Replaying those rows through the
new missing-movement detector recognizes all ten. Ownership, corpse cleanup
and landing checks still require live validation.

The successful playtest establishes the ordering for all 57 repairs: native
cleanup enabled the pooled controller, the still-running death callback disabled
it again, and the horde later reused it disabled. Same-frame death bursts exceed
the separate four-pending-ragdoll limit. The settled-corpse setting does not
control that limit. The weapon causing each burst remains unknown; no save
corruption has been established. Expanded Hordes 0.2.1 adds prevention for this
specific ordering. This plugin remains the recovery fallback during verification.

## Repair limits

The scanner requires two seconds of continuous, unpaused game time with the
controller disabled and unregistered. The zombie must be initialized, alive,
active, upright, represented by the normal crowd renderer, and owned by the
game's spawn registry. Horde zombies must also be in its living registry.
Pending corpse cleanup, ragdolls, attached bodies, safe scenes, disabled
collision, conflicting collider registrations and different gravity setups
exclude repair. Save changes, world shifts and observation gaps reset the wait.

Terrain must be loaded under the player and a static supporting surface must
be found under the zombie. Raised bodies need a clear standing capsule and
support across its footprint. The capsule check respects collision layers and
other bodies. Unsafe or missing terrain leaves the zombie unchanged and
records the reason. Near-ground zombies retain their position.

Before changing anything, the plugin writes a journal entry. It clears residual
velocity, places an airborne zombie vertically on verified ground, resets the
fall-height baseline and ground probes, and enables its controller. Unity's
[OnEnable lifecycle](https://docs.unity3d.com/2022.3/Documentation/ScriptReference/MonoBehaviour.OnEnable.html)
dispatches the game's normal registration of movement, AI, gravity, collider
mapping and anti-fall updates. Health and inventory are not assigned. Completion
requires an enabled, registered controller with unchanged health.

An already-corrected controller is ineligible on repeat. A partial failure
stops repair rather than retrying mutations indefinitely. The workaround
requires game version 0.8.316 and the exact inspected Creature and Terrain
assembly hashes; changed game code disables it pending review. If another
patch corrects the controller first, this workaround does nothing.

This plugin does not rewrite saves on disk. The user's normal game save can
persist recovered positions. Keep the pre-install save backup until play
testing is complete. Removing this plugin while the game is closed removes
the workaround on the next launch.

## Diagnostics and verification

`BepInEx/plugins/Human Host - Zombie Movement Fix/diagnostics/latest.json`
lists unresolved disabled controllers and exclusion reasons. `events.jsonl`
records repair attempts and read-only disable, death, horde-spawn and pool
events. It includes actual health, spawn ownership, pending cleanup, lifetime
counter, position, world offset and velocity. An active living zombie's disable
event includes a bounded caller stack. The event journal retains two files of
roughly 8 MiB each. No diagnostic hook changes game lifecycle results.

Verified against the current `HumanHostCodebase` before implementation:

- `C_Controller_Base.MyFixedUpdate`, `HandleMomentum`, `OnEnable`, `OnDisable`,
  `Sync_AntiFall_Anchor`: gravity, movement registration and recovery anchors.
- `Zombie_Input.OnEnable`, `OnDisable`, `On_Char_Died`: controller lifecycle;
  the last two have read-only postfixes.
- `NPC_Input.OnEnable`: anti-fall registration.
- `Creature_Mgr.Register_Char_FixedUpdate`, `UnRegister_Char_FixedUpdate`:
  registration and delayed removal; the observation delay avoids same-frame
  disable/enable races.
- `NPC_Horde_Mgr.Spawn_Horde_NPC`, `Broadcast_Npc_Focus_Player_Event`,
  `Put_NPC_Back_To_Pool`, `_aliveHordeNPCs`: completed spawn notification,
  object reuse and living ownership. The notification and pool methods have
  read-only postfixes; the asynchronous spawn entrypoint is not patched.
- `NPC_Spawner_Mgr.spawned_NPCs`, `_waitBackPoolDead_NPCs`,
  `Delay_Back_Dead_NPC_To_Pool`: ordinary spawn ownership and pending corpses.
- `Char_GPUI_Render._switchToAnimancerAlready`, `CMF.Mover.Reset_Rays`:
  representation transitions and ground probes.

```powershell
dotnet run --project tests/ZombieMovementFix.Checks -c Release
dotnet build HumanHostMods.slnx -c Release
# Only while the game is closed:
dotnet build mods/ZombieMovementFix -c Release -p:DeployToGame=true
```

The isolated checks cover classification, exclusions, observation resets,
journal failure, repeat application and completion verification. They do not
simulate Unity collisions or execute engine callbacks. The user performs game
launches and gameplay. After the next slot 1 session, verify the plugin's load
line, repair events, restored fixed updates, remaining airborne zombies and
new errors. Do not declare the user's save fixed solely from these code checks.
