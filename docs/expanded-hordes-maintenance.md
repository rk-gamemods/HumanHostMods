# Expanded Hordes maintenance

Version 0.2.0 was prepared against Steam build 25448142, Unity 2022.3.62f3
Mono and BepInEx 5.4.23.5. Local source snapshot:
`75505302bbe546b6f783690e4d97230c537edda0`. Verify installed DLLs after updates;
source alone does not establish the serialized asset defaults.

## Ownership and extension

| Files | Responsibility |
| --- | --- |
| `Plugin`, `ModIdentity`, `ModSettings` | Bootstrap, version identity and the single settings schema shared with the pre-launch config generator. |
| `FeatureRuntime` | Per-feature Harmony ownership, idempotent installation, optional hook isolation, one error per failing feature, owned unpatching. |
| `Population`, `PopulationOverrides`, `HordeRules` | Total/living population policy, quantity compensation, guarded field restoration and pure calculations. |
| `CreatureCatalog` | Resolve one identity list against the game's shuffled groups; classify known large types and bosses. |
| `SpecialRoster`, `HordeSetup` | Fresh-spawn selection and catalog initialization before native survivor restoration. |
| `HordeAttraction`, `HordeRunSpeed` | One-time native lure and temporary running animation/movement multiplier. |
| `DamageResistance`, `CombatRules` | Guarded native HP-loss adjustment and pure resistance/category/corpse calculations. |
| `CorpseRetention` | One checked IL insertion at the native corpse-limit read. No replacement manager or saved-setting mutation. |
| `PlacementLog`, `PerformanceMonitor`, `PerformanceRules` | Optional bounded diagnostics, timing hooks and aggregate calculations. |

To support another registered large/boss identity, verify its native group GUID
and prefab index, then add one `CreatureCatalog.Definition`. All matching group
entries receive the classification; only one entry per definition is used for
extra random selection. Do not append or reorder native saved arrays. The
native `is_Boss` flag takes precedence; unknown non-boss identities use regular
resistance. There is no HP/name heuristic, runtime registry framework or dependency
on another mod. Mods adding their registry entries after catalog initialization
need a separately verified integration; this version does not promise that case.

The catalog is cleared before each native horde-manager setup. Registration
failure disables composition/resistance rather than substituting arbitrary types.
Missing individual group identities are skipped with one warning. Prefab indices
are verified against the research snapshot and require rechecking after updates.

## Patch contracts and game evidence

| Native type/member | Reason and boundary |
| --- | --- |
| `NPC_Horde_Mgr._Start` | Catalog resolution before survivor restoration. Native spawner setup has already shuffled groups. |
| `NPC_Horde_Mgr.Get_Plan_To_Spawn_Count` | Budget minus native emitted count; sets total, pioneers and zero wave growth for the existing loop. Native scheduling/coroutine remains intact. |
| `AI_Agen_Mgr.MyStart`, `SetHorde_MaxAllowActiveZombies` | Shared allowance and separate living target. Restore only fields still equal to the last value written by this mod. |
| `NPC_Horde_Mgr.StartHordeEvent` | Successful fresh start identified by the native wave counter; reload does not retrigger attraction. |
| `AI_Agen_Mgr.Broadcast_Sound_Played`, `_InWaitSorting` | Existing native focus-selection notification. Two passes share a five-real-second waiting bound; busy selection may skip a pass. |
| `NPC_Horde_Mgr.Spawn_Horde_NPC` | Only fresh `async: true` calls can substitute biome/group/prefab arguments. Restore calls retain saved identity. |
| `NPC_Spawner_Mgr.NPC_Biomes`, `Terrain_Loader_Manager.BigTerraWidth`, `BiomesWidthDis` | Catalog resolution and native radial-region geometry. |
| `C_Controller_Base.Play_Anim_BaseLayer`, `curr_Move_F`; `NPC_Input._inRunning`, `_npcSpawnSource`; `NPC_Horde_Mgr._corHordeSpawn`; `Creature_Mgr._IsDayTime` | Only the horde running movement clip's speed argument changes while spawning is active at night. Both native rendering paths use this entrypoint. |
| `Char_Status.set__CurrHP` | Last-priority prefix scales requested health loss before the native overkill clamp. Maximum HP, notifications and kill/XP code remain native. |
| `NPC_Horde_Mgr.spawned_Horde_NPCs`, `Spawn_Horde_NPC`, `Put_NPC_Back_To_Pool` | Membership is added after HP initialization and removed before lower pooled-HP reset. Survivors keep membership after dawn; native reload restores it. |
| `Tool_Interacter` hit path; `C_Controller_Base` fall damage; `Smash_Fallen_Manager` falling-structure hit path | Inspected damage paths use `_CurrHP`. Weapon kill XP reads `_MaxHP`; falling-structure kill XP reads a fraction of `_MaxHP`. These calculations are untouched. |
| `GPUI_Dead_Body_Mgr.Spawn_GPUI_Dead_Body` | Transpiler requires exactly one `_MaxCorpseCount` field read, then applies max(native, configured). An unexpected IL shape rejects this feature. |
| `NPC_Horde_Mgr.Remove_AliveHordeNPC` | Death releases the living slot independently of the settled corpse pool. |
| `NPC_Horde_Mgr.GetValidSpawnPosition`, `Try_Get_Spawn_Context`, `Save_Horde_Data_To_Disk` | Debug placement counters and flush boundaries; no replacement placement/retry algorithm. |
| `Zombie_Agent._Update`, `GetValidSpawnPosition`, `Spawn_GPUI_Dead_Body`, `Save_Horde_Data_To_Disk` | Optional inclusive timing hooks. Finalizers return the original exception unchanged. |

## Vanilla comparisons

Loaded world assets give base total 15, initial living target 2 and growth 2 per
completed horde. At Horde Quantity `P%` and horde number `N` starting at 1:

- Total: `round(15 * P / 100) + 2 * (N - 1)`.
- Living: `min(60, round(2 * P / 100) + N - 1)`, also limited by remaining total.
- Shared AI allowance: 60.

At 800% and horde 17, vanilla gives 152 total and 32 living. The mod's total is
`round(base * P / 100)` without wave growth; 50,000 is the base maximum, before
the multiplier. The living target remains independent of that multiplier.

Normal ambient spawn positions are 50-100 m from the player, with saved positions
restored within 100 m. Native ambient removal beyond 150 m is delayed, not an
absolute limit on every loaded zombie. The 250 m lure maximum covers that normal
ambient retention distance plus up to 100 m of added height. It never loads the
distant world. Existing horde zombies and other distance-changing mods can use
different ranges. Both lure passes examine loaded agents; more responses can
increase obstruction checks and later AI/combat work. No FPS cost was measured.

The actual `G_Config_Setter._MaxCorpseCount_S` asset has min 5, max 300 and serialized
value 50. The mod deliberately defaults to the menu maximum 300, as requested.
Native settled-body creation usually evicts one oldest active body at the limit;
its first-use prefab branch skips the check. The setting is a retention target,
not a strict count of every saved/hidden body or ragdoll. Distance hiding retains
saved bodies; permanent expiry/removal can delete their loot records. No new
loot-preservation or permanent physics system was added.

## Diagnostics and compatibility

Debug and profiling are separate, off by default and applied at startup. Normal
diagnostic hooks are installed only when debugging is enabled; native method
timing hooks are installed only for profiling. Errors remain visible. Debug
output reports other Harmony owners on shared hooks as overlap, not an assertion
of incompatibility. Runtime failures disable the affected feature for the session;
this is not a guarantee of recovery from arbitrary game/other-mod exceptions.

Every 15 real seconds profiling reports FPS, mean/p95/max frame time, available
CPU main/render and GPU timing, presentation wait, managed memory, gen-0 GC count,
native living/settled-body counts and selected inclusive method call/total/max
times. Mean/max cover every valid frame; p95 uses up to the first 8,192 frames per
window. Calls spanning async continuations are not timed beyond the synchronous
method boundary. Sections can overlap and must not be summed as a frame budget.
Memory is managed heap only, not total RAM/VRAM. A missing count is `-1`.

Unity's release player may not expose CPU/GPU timings without Frame Timing Stats.
Unavailable measurements are labeled; the mod does not change the game's boot or
graphics settings. CPU/GPU hints compare available times and cannot identify a
causal bottleneck or attribute GPU time to this mod. Profiling adds overhead.
Use comparable scene/population/settings with profiling on and off before making
performance claims. See [Unity 2022.3 Frame Timing Manager](https://docs.unity3d.com/2022.3/Documentation/Manual/frame-timing-manager.html).

The CSV stays beside this mod's DLL, rotating at approximately 5 MiB into one
previous file (two files total). CSV I/O failure logs once and leaves log summaries
running. Turning profiling off does not delete collected reports. No telemetry,
network service, extra profiler package or background worker is used.

Health resistance does not change stun, knockdown, armor, attack damage or XP
formulas. Another prefix can adjust incoming HP too; last priority lets this
mod see earlier changes, but another mod can still replace/bypass the setter.
Direct forced-death effects and raw HP field writes are outside this boundary.
Combat hit displays may reflect the original damage rather than reduced HP loss.

## Validation and release workflow

```powershell
pwsh -NoProfile -File tools/Get-ModEnvStatus.ps1
dotnet build HumanHostMods.slnx -c Release
dotnet run --project tests/ExpandedHordes.Checks -c Release -- 'C:/Steam/steamapps/common/Human Host/Human Host_Data/Managed'
pwsh -NoProfile -File tools/Package-ExpandedHordes.ps1
pwsh -NoProfile -File tools/Install-ExpandedHordes.ps1
```

The installer refuses deployment while the game is running. It preserves accepted
config values, refreshes captions and verifies the installed DLL hash. Packaging
ships only the mod DLL and player README, generates fresh sample defaults outside
the payload, checks native method/field/IL contracts and preserves an existing
Workshop item ID. Repeated generation must preserve file hashes. No game launch
or publication is part of either script.

Automated policy and installed-metadata checks do not execute Harmony detours or
Unity. Complete [the manual release gate](../release/ExpandedHordes/PLAYTEST.md)
before publication. Prepared materials and upload instructions are under
`dist/ExpandedHordes-0.2.0/` after packaging.

Future work remains unimplemented: separate loot preservation, zero-survivor
reload continuation, permanent ragdoll piles, attack/stagger/jump changes,
adaptive population, exact special quotas, placement recovery, new biome fallback
and deep GPU attribution. Each needs explicit scope approval.
