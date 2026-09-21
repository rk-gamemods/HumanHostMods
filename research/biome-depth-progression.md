# Biome depth, zombie level, XP and loot progression

Checked against Steam build 25407931 (game 0.8.311), decompiled into
`HumanHostCodebase/` on 2026-09-19. Research date 2026-09-21.

Question: after the 10-biome sequence starts repeating, what does travelling
further out (Biome 11, 20, 30, ...) actually change?

## Evidence levels

- **Code**: the decompiled C# does this. Proven.
- **Data (runtime)**: read from Addressables prefab bundles the game loads at
  runtime (zombie prefabs). Treated as live.
- **Data (save)**: read from the player's own save (`Save_01`, Easy Save, gzip).
- **Data (scene, unverified)**: a serialized `[SerializeField]` value read from
  the built-in scene files `level0` (Start) and `level1` (World). These are
  **not** confirmed to be the live values. `Skill_Mgr._MaxLevel` reads 100 in
  both scenes, yet the player's save is level 119. The `level1` managers also
  have every array empty (for example `Terrain_Loader_Manager._BiomesLayers`),
  which the terrain code could not run with. The live data likely comes from the
  encrypted `icons_common_scenes` bundle, which was not decrypted. Every
  scene-sourced constant below carries this caveat.
- **Calc**: arithmetic on the above.

Where a formula depends on an unverified constant, the formula is proven and the
number is not. In game you can check the zombie level directly: the hit HP bar
shows `<name> Lv<N>` (`Hand_Tools:Tool_Interact_Mgr`, line 1292).

## 1. Biome progression

**Code.** Biomes are concentric rings around world origin (0,0). Each big terrain
tile's biome index is
`floor(((dist - 12) / biomesWidthDis) mod bioCount)`
(`Terrain:Terrain_Loader_Manager.Load_Unload_BigTerrainScenes_Around_Player`,
lines 666-716). `biomesWidthDis = BigTerraWidth * _BiomesWidthNum` (line 309),
and `bioCount = _BiomesLayers.Length`. Within 10 m of a ring edge a tile has a
50% seeded chance to take the inner neighbour's biome.

- The biome index is only used to choose terrain prefabs, weather zone,
  terrain texture blending and merchants (`Merchant:Merchant_Mgr`, keyed by
  biome name). **No stat, XP or loot calculation reads the biome index, a biome
  number or a cycle count.** No "cycle number" variable exists anywhere in the code.
- The mod wraps the index, so Biome 11 uses the same terrain set as Biome 1.
- Everything that scales with depth reads the **raw distance from origin**
  instead. These are the only origin-distance calculations I found (searched
  for `toZeroDis`, `Vector2.zero` distance, `realPos.x * realPos.x`,
  `origBioIndex`, `belongBioLayer`, `- 512f`):
  1. zombie level in the spawner (`Terrain:NPC_Spawner_Mgr`, line 490-492)
  2. zombie level in hordes (`Terrain:NPC_Horde_Mgr`, line 278-281)
  3. zombie group band, which picks the spawn composition, in both of the above (lines 497 and 282)
  4. loot quality tier gate (`UI:Loot_Mgr.Fill_Quality_Tier_Rate_Factors`, line 141)
  5. memory unloading on band change (`Terrain_Loader_Manager`, line 525; no gameplay effect)

**Data (scene, unverified).** `BigTerraWidth = 1024`, `_BiomesWidthNum = 2`, so
one biome ring is 2,048 m wide. The biome numbers in this report assume that
width, with Biome N starting at `12 + (N-1)*2048` m. The distance formulas do not
depend on this assumption.

**Data (save).** Your save has real position ≈ (-2260, 39448): 39,512 m from
origin, which is ring 20 at 2,048 m per ring.

## 2. Zombie level and stat scaling

**Code.** Zombie level is called `_mutantLevel` (`Creature:Zombie_Input`, default 1).

- Normal spawns: `L = floor((d + I) / I)`, where `d = max(0, playerDistFromOrigin - 512)`
  and `I = _MutantLvDisInterval / _Z_Mutant_F` (`NPC_Spawner_Mgr`, lines 490-492).
  The level is taken from the **player's** position when the spawner runs for
  a terrain tile, not from each zombie's position.
- Level is linear in distance and has **no cap**. It never wraps with the biome.
- Effects of level. These are the only reads of `_mutantLevel` and of the
  `_MutantLv*` constants in the codebase:

| Effect | Formula | Where |
| --- | --- | --- |
| Max HP | `+(L-1) × 10`; bosses `× 10` (so `+100` per level) on normal spawns | `NPC_Spawner_Mgr.Spawn_NPC`, lines 1095-1100 |
| Max HP (horde) | `+(L-1) × 10`, with **no** boss multiplier | `NPC_Horde_Mgr.Spawn_Horde_NPC`, lines 746-750 |
| Attack damage vs characters | `+(L-1) × 0.5` flat, boss `× 10` | `Tool_Interact_Mgr.Add_Zombie_Mutant_Damage`, line 1035 |
| Damage vs blocks/buildings | `+(L-1) × 0.1` flat, boss `× 10`, then `× _Z_DmgBlockF` | `Tool_Interact_Mgr.Get_Hit_SoundMat_Damage`, lines 1014-1026 |
| HP bar label | `Lv<L>` | `Tool_Interact_Mgr`, line 1292 |

- Level does **not** affect armor or resistances, movement speed, attack
  behaviour, abilities, XP multipliers or loot. `_mutantLevel` is not read
  anywhere else.
- Final max HP is `(_origMaxHP × _maxHP_Factor − _costedMaxHP + _addedMaxHp) × _DnaDmgMaxHp_Factor`
  (`Creature:Char_Status._MaxHP`, line 97).

**Data (runtime).** Zombie prefabs (`zb_*` bundles): regular `Z_Man_*` have
`_origMaxHP = 100`. `Z_Man_Big_01` has 250 and `Z_Man_Big_02`/`_03` have 200.
`Z_Boss_01` has 2,000 and `Z_Boss_02` has 4,000 (`is_Boss = 1`). Every prefab has
`_maxHP_Factor = 1` and `_addedMaxHp = 0`.

**Data (scene, unverified).** `_MutantLvDisInterval = 100`, `_MutantLvHpPerTime = 10`,
`_MutantLvAttckPerTime = 0.5`, `_MutantLvAttckBlockPerTime = 0.1`. These match the
code defaults.

**Spawn composition. Code.** The spawn group is
`floor(d / groupBandDis) mod groups.Length` (`NPC_Spawner_Mgr`, line 497;
`NPC_Horde_Mgr`, line 282). Like the biome, it **wraps**, so the set of zombie
types and the boss slots repeat. `groupBandDis` defaults to 256 in code; the
live value is serialized per biome and unverified. Outdoor count is
`group.outdoorSum × _OutdoorZ_NumF` (line 503), with no distance term.

**Calc** (Mutation Rate 1.0, mid-biome distance, scene constants):

| Biome | Distance (m) | Level | Regular HP | Boss_01 HP | +Attack | +Block dmg |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 1,036 | 6 | 150 | 2,500 | +2.5 | +0.5 |
| 5 | 9,228 | 88 | 970 | 10,700 | +43.5 | +8.7 |
| 10 | 19,468 | 190 | 1,990 | 20,900 | +94.5 | +18.9 |
| 11 | 21,516 | 211 | 2,200 | 23,000 | +105 | +21 |
| 15 | 29,708 | 292 | 3,010 | 31,100 | +145.5 | +29.1 |
| 20 | 39,948 | 395 | 4,040 | 41,400 | +197 | +39.4 |
| 30 | 60,428 | 600 | 6,090 | 61,900 | +299.5 | +59.9 |
| 50 | 101,388 | 1,009 | 10,180 | 102,800 | +504 | +100.8 |

At your saved position this gives level 390, which you can check against the HP bar.

## 3. Mutation system

**Code.** A "mutation" is just the zombie level above. It has no separate
mutant type, no mutation roll or probability, no tiers and no visual variant.
Every zombie, bosses included, gets a level.

- **What the Mutation Rate setting does** (`G_Save.ConfigData._Z_Mutant_F`): it
  divides the distance per level, `I = 100 / F`. So `L ≈ (d − 512) × F / 100 + 1`.
  The level gain per km is `10 × F`.
- It has no minimum, maximum or breakpoint beyond the slider range, and no cap on level.
- Repeated biome cycles keep raising the level linearly, because it reads
  distance, not the biome.
- Mutation affects HP, attack, block damage and the label. **It affects XP
  only through max HP** (see section 4). It does not affect loot, drops or resources.

**Data (scene).** The slider range is 0.2–3.0, rounded to 0.1
(`G_Config_Setter.Sync_Slider_Text_Percentage`). Presets: Easy 0.5,
Normal 1.0, Hard 1.5, Hardcore 2.0 (`G_Config_Setter.Click_Difficulty_Preset`).
Your save has 1.0.

**Calc** (level at mid-biome):

| Biome | F=0.2 | F=0.5 | F=1.0 | F=1.5 | F=2.0 | F=3.0 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 2 | 3 | 6 | 8 | 11 | 16 |
| 10 | 38 | 95 | 190 | 285 | 380 | 569 |
| 20 | 79 | 198 | 395 | 592 | 789 | 1,184 |
| 30 | 120 | 300 | 600 | 899 | 1,199 | 1,798 |
| 50 | 202 | 505 | 1,009 | 1,513 | 2,018 | 3,027 |

## 4. XP from zombie kills

**Code.** XP is the victim's **max HP**. It has no per-type table, no level or
biome multiplier and no player-level scaling.

| Kill path | XP awarded | Where |
| --- | --- | --- |
| Player weapon hit (melee, gun, bow, thrown; `Tool_Interacter` owned by the player) | `(int)MaxHP` | `Hand_Tools:Tool_Interacter`, line 1814 |
| Trap | `(int)(MaxHP × 0.3)` | `Build_System:Smash_Fallen_Manager.OnTrapTrigger`, line 1338 → line 1140 |
| Car impact | `(int)(MaxHP × 0.3)` | `Build_System:TopOnHit`, line 841 |
| Armor reflect perk | `0.3 × MaxHP` **plus** `MaxHP` if the HP bar hits 0 (1.3× total) | `Tool_Interacter.Check_Armor_Reflect_Damage`, lines 2781-2787 |
| Falling trees, shards, fall damage | 0 (`getEXP` defaults to false) | `Tree_Falling_Handler`, line 171; `Shards_Collide_Ground`, line 43; `Smash_Fallen_Manager`, line 1583 |

Vanilla has no companions or turrets. (`Railgun Turrets` is a third-party mod.)

- Then `Char_Skills.GainCharacterExp` adds `round(addEXP × _ExpFactor)`, only
  while `level < Skill_Mgr._MaxLevel` (`Creature:Char_Skills`, lines 161-167).
- On level-up the current XP is set to 0, so overflow past the threshold is
  lost (line 174). This is negligible at high levels.
- Difficulty affects XP only through the XP slider, `_ExpFactor`
  (range 0.1–3.0; presets 2.0 / 1.0 / 0.5 / 0.2; your save has 1.2).
- **So XP per kill does scale with depth**, because HP does:
  `XP = (base + 10(L−1)) × ExpFactor` for weapon kills. Normal-spawn bosses
  gain 100 XP per level.

**XP curve.** `Skill_Mgr.CalculateExpRequired`: level 1→2 costs 200, then
`round(200 × 1.07^(L−1))` for level L→L+1 (exponential growth type).
**Verified against your save**: level 119 with `_characterExpToNext = 586,568`,
which equals `round(200 × 1.07^118)` exactly. `_MaxLevel` is serialized. The
scene files say 100, but your level 119 shows the live value is higher, and I
could not read it.

| Level | XP to next | | Range | Total XP |
| --- | --- | --- | --- | --- |
| 100 | 162,191 | | 1→100 | 2.31 M |
| 119 | 586,568 | | 100→119 | 6.06 M |
| 150 | 4.78 M | | 119→150 | 59.9 M |
| 199 | 131.5 M | | 119→200 | 2.00 B |

**Calc: does going deeper speed up 100→200?** Weapon kills of regular zombies,
XP slider 1.2, Mutation Rate 1.0:

| Biome | XP per kill | Kills 119→150 | Kills 119→200 | Kills for 199→200 alone |
| --- | --- | --- | --- | --- |
| 10 | 2,388 | 25,072 | 838,416 | 55,079 |
| 20 | 4,848 | 12,350 | 412,982 | 27,131 |
| 30 | 7,308 | 8,193 | 273,965 | 17,998 |
| 50 | 12,216 | 4,901 | 163,895 | 10,767 |

Yes, deeper kills are worth more, and XP per kill rises linearly with distance.
But each level costs 7% more than the last, so the benefit grows linearly while
the cost grows exponentially. Doubling the distance halves the kill count.
Reaching 200 still takes hundreds of thousands of kills at any practical depth.
Raising Mutation Rate to 3.0 at the same distance gives the same XP gain as
travelling three times as far.

## 5. Loot and reward scaling

**Code.**

- **Item quality** is the only reward that reads depth.
  `Item_Slot_Mgr.Build_Loot_Quality_Rates` multiplies each tier's base rate by
  `Loot_Mgr.Fill_Quality_Tier_Rate_Factors`. For tier index q ≥ 1 the factor is
  `clamp01((dist − ((q−1)·I − I/2)) / (I/2))`, with `I = _QualityCapDistanceInterval`.
  Tier q is fully open at `dist ≥ (q−1)·I`. Any rate that is removed goes to
  the lowest tier, and the loot perk `_lootQualityRateBoost` is applied after.
  The quality is rolled when a non-stackable item's slot first initializes
  (`Slot_Info`, line 516), using the player's distance at that moment.
- **Crafted item quality** uses craft level, not distance (`UI:Craft_Items`, lines 905-945).
- **Quantity, drop chance, loot-table choice**: `Loot_Mgr` container fill
  uses `_spawnRateRange × _Loot_Rate_Total × (1 + _lootCountRateBoost)`, and
  stack size uses the same factors (lines 364-433). None of these has a
  distance, biome or zombie-level term. Resource yields from mining, trees and
  digging use only `_Loot_Rate_Total` (`TopOnHit`, `Tree_Falling_Handler`, `Terrain_Dig`).
- **Unique, boss or mutant rewards**: no code path ties a reward to
  `_mutantLevel`, `is_Boss`, or depth. Container loot tables come from the
  container prefab. Which containers and merchants exist depends on the biome,
  and that wraps.

**Data (scene, unverified).** There are 6 tiers with base rates
0.50 / 0.25 / 0.15 / 0.05 / 0.04 / 0.01 and durability factors
1.0 / 1.5 / 2.25 / 3.25 / 4.5 / 6.0 (`level0` Item_Slot_Mgr).
`_QualityCapDistanceInterval = 2000`. **Calc:** the top tier (q=5) is fully
open at 8,000 m, which is in Biome 4 at 2,048 m per ring. **Quality is capped
long before Biome 10**, and even a changed interval would still give a fixed cap
at `4 × I`.

## 6. Settings (what the code actually does)

| Setting (field) | Slider | Effect in code |
| --- | --- | --- |
| Difficulty (`_DifficultyIndex`) | preset list | Only fills the other sliders. No code reads it during play. |
| Mutation Rate (`_Z_Mutant_F`) | 0.2–3.0 | Distance per zombie level = 100/F. |
| XP (`_ExpFactor`) | 0.1–3.0 | Multiplies all XP gains. |
| Loot spawn (`_Loot_Rate_Total`) | 0.2–3.0 | Container slot chance, stack sizes, resource yields. Not quality. |
| Loot refresh (`_Refresh_Loot_Days`) | 0–20 | Refresh time for emptied containers; 0 disables refresh. |
| Zombie damage to characters (`_Z_DmgCreatureF`) | 0.2–3.0 | Damage factor (`Tool_Interacter`, line 2415). |
| Zombie damage to blocks (`_Z_DmgBlockF`) | 0–3.0 | Block damage factor. |
| Outdoor zombie count (`_OutdoorZ_NumF`) | 0.2–2.0 | `group.outdoorSum ×` factor. |
| Indoor zombie count (`_SysHouseZ_NumF`) | 0.2–1.5 | **No gameplay effect found.** It is only read and written by the settings UI. |
| Horde interval (`_Horde_IntervalF`) | 0–14 days | Days between hordes; 0 disables. |
| Horde size (`_Horde_Z_NumF`) | 0.2–8.0 | Base horde count and pioneer count. |
| Run type, anger, frenzy | option lists | Movement mode, sprint rules, rage-run on nearby death. No level interaction. |

Your save: Difficulty 4 (custom), XP 1.2, Mutation 1.0, Loot 1.0, Horde size 8, Outdoor 2.

## 7. Hordes

**Short answer.** Your base makes hordes stronger (higher zombie level), not
bigger. If you are inside a reasonably sized base when the horde starts, all of
it counts. Shape does not matter, only how much you have built and how strong
it is. Only an absurdly large base, spread over hundreds of metres, risks
leaving part of it uncounted (see the details below). A horde never ends up
weaker than normal zombies at your distance from the world origin.

**Details: what counts as the base.**

- It is measured once, from where you are standing when the night's horde
  starts. It is not tied to a sleeping bag, campfire or any other item. If you
  are away from the base at that moment, the base does not count.
- The game casts 4 rays down at points diagonally out from you, about 220 m
  away (the larger of `ScenePropManager.aroundPlayerDistance` and
  `aroundPlayerDisDecal`, 50 m and 220 m in code; live values unverified). It
  records the terrain tile each ray hits (`ScenePropManager.Spawn_Objects_Around_Player`,
  lines 433-449). Tiles are 512 × 512 m (`Terrain_Loader_Manager._TerraSize`),
  so this picks 1 to 4 whole tiles: the one you are on, plus any neighbours
  those points reach.
- Every player-built piece on those tiles counts (`Build_Info.Type.PlayerDeployedBI`):
  walls, floors, workbenches, crates, traps, lights and so on. Pieces belonging
  to pre-built world houses (`SysHouseTop` set) are excluded.
- Each piece adds its full max HP (`Shards_HP_All`). Damage does not reduce it,
  and upgrades raise it.
- The game has no normal way to show which tile you are on or where you are
  within it. That is why the practical rule is to keep the base compact and be
  inside it at horde start.

**Formulas** (`NPC_Horde_Mgr`, lines 257-281):

- `distLv = ceil((d + I) / I)`: the same distance formula as normal spawns, but
  rounded up, so it is usually one level higher.
- `baseLv = round(600 × (1 − e^(−S/10000/600)))`, where S is the summed
  `Shards_HP_All` of player-built blocks on the terrain tiles around the player.
  This approaches 600 and never reaches it.
- `hordeLevel = max(baseLv, distLv)`.
- Horde bosses get only `+10` HP per level (no ×10).
- Horde size is `round(_HordeZombieAll × _Horde_Z_NumF) + (wave − 1) × _ZombiesPerWaveAdd`
  (line 178), where the wave counter only goes up (line 220). **Horde size grows
  every wave with no cap.** Scene values, unverified: 30 base and +2 per wave.
  Your save is at wave 8.

**Calc.** Building S ≈ 1.09 M total block HP near origin gives level-100
hordes. 4.16 M gives level 300, and 10.75 M gives level 500. So you can get
high-level zombies, and their XP, without travelling, up to just under level
600. Distance is the only way past 600.

## 8. Max useful player level

**Code.** Character level does one thing: it grants perk points. A search of
`_characterLevel` across the whole codebase finds only the level-up logic, the
XP bar text and the level-up check. No stat, loot, crafting or merchant code
reads it.

- `Skill_Mgr.Check_If_LevelUp` (line 452) opens the perk pick when
  `level − (sumOfLearnedPerkLevels + 1 − _InitTalentLv) > 0`. That is one point
  per level. The character's starting talent counts at its starting level.
- A pick offers only perks below their `maxLv` (`Sum_Skill_LV`, lines 525-540).
  When every perk is maxed, the pick panels stay hidden.
- Deleting a perk level refunds its point but adds one stack of DNA damage
  (max HP × `1 − value%`, 18 stacks at most; `Press_Ok_To_Delete_Skill`,
  lines 1680-1745). The stacks wear off one at a time on a timer (line 1449).
  Respeccing therefore needs no spare levels.
- Crafting level comes from the Artisan perk's level (line 1160), not from character level.

**Data (runtime asset).** `All_Skills_Set` (`sharedassets0.assets`) contains:

| Group | Perks | Max level each | Total |
| --- | --- | --- | --- |
| Fight | 12 | 5 | 60 |
| Survive | 15 | 8 | 120 |
| Craft | 8 | 5 | 40 |
| **All** | **35** | | **220** |

This asset matches your save: 30 perks learned, every one at or below these
maxima (several survival perks at 8/8), 120 levels spent.

**Calc.** Max useful level = `220 + 1 − starting talent level`. Your save starts
with Scavenger 5 (`_InitTalentLv = 5`), so for you that is **level 216**. At
level 119 you have 120 perk levels spent and 3 points unspent
(119 − (120 + 1 − 5) = 3). That leaves 100 perk levels, which takes 97 more
character levels. Each level past 216 grants a point that can't be spent.

XP from 119 to 216 is about 5.93 billion: 2.00 B to reach 200, then 3.92 B more
for 200→216. That is roughly 1.22 M weapon kills of regular zombies at Biome 20,
or 485 k at Biome 50 (XP slider 1.2, Mutation Rate 1.0). This only holds if the
live `_MaxLevel` is at least 216, and that value is still unknown.

## Summary table

| Mechanic | Improves after Biome 10? | How it scales | Cap |
| --- | --- | --- | --- |
| Zombie level | Yes | `floor((d−512)/(100/F)) + 1`, linear in distance, ignores biome | None (horde base-size term caps at 600) |
| Zombie health/damage | Yes (harder) | HP +10/level (boss +100), attack +0.5/level, block +0.1/level | None |
| Mutation chance | Not a chance | Same as zombie level; the setting scales levels per km | None |
| XP per kill | Yes | = max HP × XP slider; weapon 1.0×, trap/car 0.3× | None per kill. XP stops mattering at level 221 − starting talent level (216 for your save), when all 220 perk levels are bought |
| Loot quality | No | Distance ramp on tier weights | All 6 tiers open at 8 km (≈ Biome 4) |
| Loot quantity | No | No depth term at all | n/a |
| Unique rewards | No | Biome-specific containers and merchants repeat every 10 biomes | n/a |
| Other progression benefits | No | Nothing else reads depth | n/a |

## Answer

For a level 100+ player, going from Biome 10 to 20, 30, 40 or further gives
**one** mechanical benefit: more XP per zombie kill. XP equals the zombie's
max HP, which rises by 10 per zombie level, and zombie level rises linearly
with distance from origin with no cap. At Mutation Rate 1.0, a regular zombie
is worth about 2,000 XP at Biome 10, 4,000 at Biome 20 and 6,100 at Biome 30,
multiplied by your XP slider. The player XP curve grows 7% per level, so this
only shortens the grind in proportion: doubling your distance halves the kills
needed. From 119 to 200 is still about 413 k weapon kills at Biome 20.

Everything else is only additional difficulty or repetition. Zombie HP,
attack and block damage all rise with the same linear formula. Loot quality
maxed out around 8 km, loot quantity never scaled, and terrain, spawn groups,
containers and merchants repeat on the 10-biome loop.

You can get the same XP gain without travelling in two ways. Raising the
Mutation Rate multiplies zombie level at any distance: 3.0 at Biome 10 roughly
equals 1.0 at Biome 30. Building a large base also raises horde levels, up to
just under 600. Both give the same XP per kill as distance does, because XP
only reads max HP.

## Unresolved

- Live values of every scene-serialized constant (`_MaxLevel`,
  `_MutantLvDisInterval`, `_MutantLv*PerTime`, biome width, `groupBandDis`,
  quality rates and interval, horde base and wave step). The formulas are
  proven. The numbers need an in-game check: UnityExplorer on `Skill_Mgr`,
  `Creature_Mgr`, `Loot_Mgr` and `Terrain_Loader_Manager`, or comparing the HP
  bar's `Lv` against your distance.
- How the live World-scene data is supplied at runtime. The built-in `level1`
  holds placeholder managers, and the `icons_common_scenes` bundle is encrypted.
