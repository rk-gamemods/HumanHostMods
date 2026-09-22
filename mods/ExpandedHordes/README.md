# Expanded Hordes 0.2.0

Configurable horde population, running speed, damage resistance, special-zombie
chances and corpse retention. Prepared for Human Host Steam build 25448142,
BepInEx 5.4.23.5 and Unity 2022.3 Mono. **Runtime play testing is pending.**

## Install and configure

Close the game, then run:

```powershell
pwsh -NoProfile -File tools/Install-ExpandedHordes.ps1
```

The installer builds and hash-verifies the dedicated
`BepInEx/plugins/ExpandedHordes/ExpandedHordes.dll`, creates/refreshes the standard
`BepInEx/config/rkgamemods.humanhost.expandedhordes.cfg`, and preserves accepted
existing values. Edit **Expanded Hordes** in HHMM with the game closed, then
restart. No additional gameplay mod or in-game ModMenu registration is required.

HHMM 1.3.0 folder scanning, file ownership and BepInEx config parsing were checked
against [its source](https://github.com/xem888/HHMM/tree/v1.3.0) at
`cd5bfe8d7700fec5f87d26051544d19cacee6019`. Its friendly name comes from the
plugin/config header. The GUID remains `rkgamemods.humanhost.expandedhordes`.
The user performs HHMM UI and gameplay verification; the agent must not launch
the game or operate computer UI.

## Settings

| Setting | Default | Range / meaning |
| --- | ---: | --- |
| Total Spawn Budget | 1,000 | 1-50,000 **before** vanilla Horde Quantity. At 800%: default 8,000 total, maximum 400,000. Replacements count; dawn can stop it sooner. |
| Living Horde Target | 75 | 1-1,000. Separate simultaneous cap, limited by shared allowance and remaining total. Vanilla limit: 60. |
| Shared AI Allowance | 90 | 1-1,000. Vanilla: 60. Shared with ordinary zombies, including between hordes. |
| Horde Run Speed Percentage | 125% | 25-300%. Horde running during active nighttime spawning only. Ends with spawning or dawn. |
| Regular Zombie Resistance | 25% | 0-95% incoming health damage prevented for regular horde types. |
| Large Zombie Resistance | 40% | 0-95% for known large non-boss horde types. |
| Boss Resistance | 50% | 0-95% for horde bosses; native boss flag takes precedence. |
| Extra Large Zombie Begin Biome | 11 | 1-1,000,000. Radial region gate for extra large choices. Moving inward closes it again. |
| Extra Boss Zombie Begin Biome | 11 | 1-1,000,000. Independent boss gate. |
| Extra Large Zombie Percentage | 20% | 0-40%. Chance per fresh zombie, including replacements. |
| Extra Boss Zombie Percentage | 5% | 0-40%. Separate chance per fresh zombie. |
| Elevated Sound Height | 100 m | 0-100 m. One silent lure at your head and one above it, once at fresh horde start. |
| Hearing Radius | 250 m | 1-250 m. Existing nearby zombies only; height uses part of the reach. |
| Retained Corpse Limit | 300 | 1-5,000. Higher of this and native limit; 300 is the vanilla menu maximum. Shared settled-body pool. |
| Debug Mode | Off | Event, placement and patch-overlap details. Errors remain logged when off. |
| Performance Profiling | Off | 15-second frame/method log and CSV summaries, plus available CPU/GPU timing. |

Resistance defaults and the 5,000 corpse upper bound are provisional tuning, not
measured safe limits. At 50% resistance, half the health damage gets through.
Maximum HP and health-based kill XP stay unchanged. Resistance follows native
horde membership after dawn and reload, using current settings. Ordinary zombies
attracted into the fight do not gain it. No save fields or persistent stat
modifiers are added. Run speed has the shorter selected lifetime: it returns to
normal when spawning ends or dawn arrives. Walking and attacks remain native.

Each fresh spawn gets its own composition choice. With both gates open, defaults
give 20% extra large, 5% extra boss and 75% native selection. Native selection can
also include specials. These are not exact final ratios or guaranteed bosses.
Reload keeps saved types. The catalog includes three large types and two bosses.

Vanilla controls enabled hordes, every-N-nights cadence, randomized start and dawn.
Vanilla starts at 15 total at 100% (120 at 800%), adding 2 per previous horde.
The mod uses base times Horde Quantity without wave growth. A base of 20 at 800%
gives 160; tiny bases at low percentages can round to zero.

Corpses do **not** fill living horde slots. Native settled-body creation usually
evicts an old body at its retention target; first-use prefab exceptions mean
this is not a strict count. Expiry and distance hiding remain native. More bodies
do not mean permanently active, collision-stacking ragdolls. Permanent removal
can delete loot; separate loot preservation is not included.

The lure never loads more world or creates distant enemies. Inspected normal
ambient spawning is 50-100 m away, with delayed removal beyond 150 m. The 250 m
maximum also covers up to 100 m of lure height. Obstruction, current targets and
native pursuit rules can prevent a response. Cost is unmeasured.

## Diagnostics, compatibility and release

Debug logs aggregate placement failures rather than every zombie/hit. Profiling
writes `performance.csv` beside the DLL and rotates at approximately 5 MiB into
one previous file. It records frame times, selected inclusive method timings,
managed memory and population counts. Missing CPU/GPU data says unavailable.
Hints are not causal diagnoses, full-engine profiles or per-mod GPU attribution.
Profiling adds overhead.

Separate owned patches disable affected features on detected failures. This
cannot guarantee compatibility with arbitrary mods rewriting the same methods.
Forced-death effects can bypass resistance; some hit displays may show original
rather than reduced damage. Native survivor HP restore, zero-survivor reload
gaps, empty ordinary swamp selection and dawn polling remain.

```powershell
dotnet build HumanHostMods.slnx -c Release
dotnet run --project tests/ExpandedHordes.Checks -c Release -- 'C:/Steam/steamapps/common/Human Host/Human Host_Data/Managed'
pwsh -NoProfile -File tools/Package-ExpandedHordes.ps1
```

Automated checks cover pure behavior, installed method/field contracts and the
exact corpse-limit IL seam. They do not execute Unity or Harmony detours.
The install payload contains only the original DLL and README. Preview,
description, sample config, hashes and upload instructions accompany it.
Publication awaits the user's [play-test checklist](../../release/ExpandedHordes/PLAYTEST.md)
and any account setup; no upload runs automatically.

See [maintenance boundaries and native-member evidence](../../docs/expanded-hordes-maintenance.md),
[validation record](../../docs/expanded-hordes-validation.md),
[publication instructions](../../release/ExpandedHordes/PUBLISHING.md),
[decisions](../../research/expanded-hordes-decisions.md),
[verified creature roster](../../research/expanded-hordes-roster.md) and
[hypothetical spawn ceiling](../../research/expanded-hordes-spawn-ceiling.md).

To uninstall, close the game and disable/remove only the ExpandedHordes plugin
folder through the installing manager. Avoid simultaneous local/Workshop copies.
