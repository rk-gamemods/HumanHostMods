# Expanded Hordes: composition and boss choices

Status: decision evidence, not an implementation plan. Checked 2026-09-21 local date against the installed assets and local source commit `75505302bbe546b6f783690e4d97230c537edda0` (Steam build 25448142). No game launch, deployment, save changes or runtime tests.

## What changed from the earlier research

**Authentic bosses are already eligible for vanilla hordes.** Mountain Forest includes Subject 1; War Zone includes Artificial Mutant. The earlier inspection found only their separate base-terrain assets and left their horde eligibility unresolved. Following the actual world registry through Addressables to the biome prefab lists resolves that gap. A new boss factory/adapter is not established as necessary for these bosses.

The user selected additional large/boss choices across biomes while retaining native local selection, with separate region gates and percentage settings. The selected approach changes existing creature identifiers at the native horde spawn-method entry for fresh spawns. The [decision record](expanded-hordes-decisions.md) owns this scope; implementation is not authorized.

## Vanilla roster and frequency

These are base prefab HP values, before level/settings modifiers. Classification is based on the explicit `is_Boss` flag and the `Z_Man_Big_*` prefab family. It is not a full classification of movement, armor or attacks. Ordinary and large enemies both display simply as "Zombie"; model identifiers distinguish variants.

The game selects one group for an event, not all groups in the biome. Groups are shuffled by world seed at startup, then selected by `floor(max(0, distanceFromOrigin - 512) / 256) % groupCount`. Consequently group suffixes 01/02/03 are not a guaranteed increasing difficulty sequence. The selected group stays fixed during that spawning coroutine.

| First-cycle ring | Biome | Available native groups and class mix | Boss chance per selection |
| --- | --- | --- | --- |
| 1 | Mountain Forest | G01: five ordinary variants. G02: four ordinary, one large (200 HP), Subject 1 (2,000 HP). G03: five ordinary, Subject 1. | G01: 0. G02: 1/83 = 1.205%. G03: 1/81 = 1.235%. |
| 2 | Mossy Forest | G01/G02: five ordinary each. G03: four ordinary and one large (250 HP). | 0 in all three groups. |
| 3 | War Zone | G01: four ordinary and one large (200 HP). G02: four ordinary and Artificial Mutant (4,000 HP). | G01: 0. G02: 1/81 = 1.235%. |
| 4 | Wasteland | Five ordinary variants. | 0. |
| 5 | Desert | Five ordinary variants. | 0. |
| 6 | Rocky Desert | Five ordinary variants. | 0. |
| 7 | Tropical Jungle | Five ordinary variants. | 0. |
| 8 | Tropical Swamp | Registered group has no prefab entries and no outdoor weights. The horde factory returns without spawning from this empty group. | No boss or ordinary spawn from this native list. |
| 9 | Winter Town | Five ordinary variants. | 0. |
| 10 | Winter Forest | Five ordinary variants. | 0. |

Ordinary variants in these lists have 100 base HP. Mountain G02's large zombie has weight 6/83 (7.229%); Mossy G03 and War Zone G01 large zombies have 1/13 (7.692%). Single ordinary-only groups give each of their five variants equal weight.

There is also an extra registry entry using Mountain G03, outside the ten ring entries, and a separate `BaseTerra_NPC_Set` asset containing both bosses. Neither creates a new boss species. The table above describes the ten ring rosters. It does not claim that the empty swamp group rules out surviving zombies arriving from elsewhere or third-party additions.

These percentages apply to prefab selection, not measured successful arrivals. There is no separate boss quota or cooldown in the inspected horde selector. At 1/81 per draw, 100 independent selections have about a 71.13% chance of including at least one boss; at 1/83, about 70.24%. Thus even a boss-bearing group can produce a boss-free horde. A group without a boss cannot produce one just by increasing the total.

Boss strength also differs by spawn path: the ordinary terrain factory gives bosses ten times the per-level HP increment, while the horde factory uses the normal per-level HP increment. Their high base HP remains. Boss damage has separate scaling. "Authentic boss" therefore does not mean identical HP to an ambient boss at the same level.

## Available controls and relative effort

Low means a localized selection/configuration change. Medium means coordinating existing selection, counters and/or asset groups. These are comparative judgments, not completed implementations or time estimates.

| Control | What it gives the player | Relative effort and implications |
| --- | --- | --- |
| Weights or category percentages within the current group | More/fewer ordinary, large and boss selections where that category exists. | Low-Medium. Existing weighted selection fits this. A missing class needs another source group; increasing a zero boss weight cannot invent an eligible boss. Horde settings should not unintentionally change shared ambient selection. |
| Boss percentage available in every populated biome | Select an already registered boss from Mountain Forest or War Zone when the boss choice wins. | Medium. Existing factory, rendering groups and saved identifiers support this shape. Requires selection across groups and validation of loading/cleanup, not a newly invented boss system. |
| At least one boss per event | Guarantee a boss selection early enough to occur before normal dawn termination, rather than rely solely on random weights. | Low-Medium once an eligible boss source is available; Medium overall when offered across biomes. Needs a small amount of event accounting. Arrival remains conditional on ordinary spawning succeeding. |
| Controlled composition ratios | Keep actual emitted composition near configured percentages, or guarantee specified class counts in completed portions of a wave. | Medium. More counting than independent random rolls, but no requirement for a new spawning framework. A random 10% chance and a quota of ten bosses per hundred successful spawns are different behaviors. Exact whole-event ratios can be interrupted by dawn. |
| All-biome mixes after ring 10 | Keep first-cycle composition, then draw from multiple native groups starting in the second cycle. | Medium. The distance gate is Low effort; cross-group selection/loading and configuration make the complete feature Medium. It can use the same cross-group capability needed for bosses outside their home biomes. |

The native horde factory already accepts `biomeIndex`, `groupIndex`, `npcPrefabIndex`, level and position; it loads the chosen group's assets, registers ownership and saves the three identifiers. This is evidence that existing mechanics can support mixing. It is not a runtime validation of every mixed combination.

Percentage controls alone cost little compared with simulating the enemies. Mixed groups can load more models/textures/animation/rendering data and cause first-load spikes. Boss-heavy hordes can cost more in combat/physics and last longer; no measured per-boss multiplier exists. Replacing ordinary enemies with bosses need not increase the living count. However, a random spawn percentage does not ensure that the same percentage of living enemies are bosses: longer-lived bosses can accumulate. An optional concurrent boss limit would be a separate choice, not assumed scope.

## Original templates versus existing spawn identities

The user selected the existing-identity approach at the native spawn-method entry after this comparison. It is the engineering recommendation for simplest maintenance within the requested scope, not a runtime-proven implementation. Template editing remains comparison evidence, not an open competing decision.

| Candidate | Concrete work and limits |
| --- | --- |
| Patch original runtime templates and weights | Possible. `TerraTop_NPC_Set.NPC_Prefabs` holds prefab entries, while `NPC_Bio_Set.Group.sampleArray_Outdoor` and `sampleAll_Outdoor` hold selection weights separately. Changing `NPC_Info.rateCount` alone does not rebuild the inspected runtime weights. Adding missing types needs both structures coordinated. Ambient and horde factories use the same group data, so horde-only percentages and region thresholds still need scoped selection behavior. Saved enemies and corpses resolve numbered entries again; appended entries must remain available with consistent identities when restored or cleaned up. |
| Selected: choose an existing registered identity at fresh horde spawn entry | The factory already accepts biome, group and prefab indices and loads the matching native group. Local selection remains native unless an extra special choice wins. This avoids appended template entries and gives the native factory the original identity for loading, rendering, saving and cleanup. Preserve restoration identifiers, spawn level and position. The inspected restoration caller passes `async: false`; fresh calls use the default `true`. The method signature and this caller distinction need verification after updates. Runtime validation remains outstanding. |

Rendering is not an established blocker to template mixing. `Char_GPUI_Render.Ensure_GPUI_Registration_Valid` calls the crowd manager's `AddPrefabInstance`, but this inspection does not establish that every foreign prototype works under every group's manager. Do not claim a custom renderer is required. The existing-identity candidate avoids depending on foreign-manager compatibility by using each prefab's native group.

Evidence: [TerraTop_NPC_Set.cs](../HumanHostCodebase/Build_System/TerraTop_NPC_Set.cs), `NPC_Info`; [NPC_Spawner_Mgr.cs](../HumanHostCodebase/Terrain/NPC_Spawner_Mgr.cs), `NPC_Bio_Set.Group`, `Spawn_NPC`, `On_Get_DeadBodyPrefab`; [NPC_Horde_Mgr.cs](../HumanHostCodebase/Terrain/NPC_Horde_Mgr.cs), `Spawn_Horde_NPCs` and `Spawn_Horde_NPC`; [Char_GPUI_Render.cs](../HumanHostCodebase/Creature/Char_GPUI_Render.cs), `Ensure_GPUI_Registration_Valid`. Same local source revision as the composition evidence above. No production edits or runtime checks.

## Ring 11 and later

The loaded world has ten ring layers in the order above and repeats them. The terrain code derives biome selection from radial distance; it does not maintain a "visited all ten biomes" achievement. A ring-11 gate can therefore be derived from the existing distance/ring calculation without a new exploration-history system.

Whether the rule should activate only while the player is beyond the first cycle, or remain unlocked after returning inward, is still a product choice. The latter needs a remembered milestone. No choice is selected here. Existing depth-based zombie-level growth already continues beyond the first cycle; introducing a mix adds composition variety on top of that growth.

## Evidence and reproducibility

- Existing loaded-world extract: `.local/expanded-hordes/world-assets.json`, `NPC_Spawner_Mgr.NPC_Biomes` and `Terrain_Loader_Manager._BiomesLayers`.
- Installed `StreamingAssets/aa/catalog.json`: decoded key/bucket/entry records map each registry GUID to its asset path.
- Eleven installed `zb_*_assets_all_*.bundle` files: read with the already installed local UnityPy/typetree tools. All relevant set/prefab component reads completed without parser errors. Duplicate DLL registration notices from the generator did not prevent extraction.
- `py -3 '.local/expanded-hordes/extract_roster.py' zb_mountain zb_desert zb_forest zb_desert_rocky zb_winterforest zb_wintertown zb_warzone zb_rainforest zb_wasteland zb_swamp zb_baseterrain`
- `py -3 '.local/expanded-hordes/catalog_roster_links.py'`, then `py -3 '.local/expanded-hordes/verify_composition.py'`: all 16 registry group references resolved; prefab counts, all weight arrays and all weight sums matched. Joined evidence is in ignored `.local/expanded-hordes/composition-verified.json`.
- Installed Terrain, AI and Creature DLL hashes match the earlier verification snapshot. No decompilation refresh was needed.
- [NPC_Horde_Mgr.cs](../HumanHostCodebase/Terrain/NPC_Horde_Mgr.cs): `Spawn_Horde_NPCs`, `Spawn_Horde_NPC`, save/restore and pool return. [NPC_Spawner_Mgr.cs](../HumanHostCodebase/Terrain/NPC_Spawner_Mgr.cs): `_Start` group shuffle and `Spawn_NPC` boss HP scaling. [MathClass.cs](../HumanHostCodebase/Static_Class/MathClass.cs): integer-list `Random_Pick_Array_Index`. [Terrain_Loader_Manager.cs](../HumanHostCodebase/Terrain/Terrain_Loader_Manager.cs): ring selection. [Zombie_Input.cs](../HumanHostCodebase/Creature/Zombie_Input.cs): boss stat behavior.
- Percentages and illustrative independent-draw probabilities were calculated with the connected Wolfram evaluator: `N[100 {1/83,1/81,6/83,1/13},8]` and `N[100 (1-(1-#)^100)& /@ {1/83,1/81},8]`. These are calculations, not benchmarks or observed event frequencies.

Full prefab identifiers are in the [roster appendix](expanded-hordes-roster.md). [Confirmed decisions and open questions](expanded-hordes-decisions.md) remain the scope authority.
