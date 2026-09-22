# Expanded Hordes: start-here handoff

Status: research complete for an initial decision discussion. **No implementation plan or production implementation is approved.** Recorded 2026-09-21 local date.

**Subsequent discussion:** Consult [confirmed decisions](expanded-hordes-decisions.md) for choices made after this handoff. [Composition follow-up](expanded-hordes-composition.md) resolves the boss-eligibility gap below: Subject 1 and Artificial Mutant are in native horde groups. It provides their probabilities, the full biome roster and a revised effort comparison. Earlier statements that no answers exist or boss eligibility is unresolved are historical.

This document preserves the useful context from the original conversation. It is the entrypoint for the next agent. The longer [research and evidence report](expanded-hordes.md) is supporting reference, not a plan or a requirement to investigate every option further. A [copyable agent prompt](expanded-hordes-agent-prompt.txt) accompanies this handoff.

## What the user actually wants

Research a Human Host mod tentatively called **Expanded Hordes**, allowing much more intense horde events through:

- Configurable fixed or unlimited total spawn budget.
- Configurable start/end times **inside vanilla nighttime only**.
- Configurable concurrent living horde population.
- Replenishment as zombies die.
- Event spawning stops at the first enabled budget/time limit, with vanilla nighttime as the outer boundary.

Research corpse/loot consequences and optional intensity controls. Give basic facts, viable options, relative difficulty, risks and performance implications so the user can choose. Optional ideas are not requirements: boss/special composition, speed/health/damage/resistance/jumping, fewer stronger enemies, performance controls, and scaling from depth, wave, days, player progression or base value.

## User corrections and collaboration boundaries

These corrections are essential context, not optional style preferences:

1. **Work with vanilla as much as possible.** Do not invent daytime horde support or use it to justify extra architecture.
2. **Research is not planning.** The user reserved the product decisions and wants to choose after seeing options and difficulty. The preference for vanilla does not authorize the agent to select a patch strategy, scheduler, cleanup policy, or persistence design.
3. **Keep it basic.** The previous agent investigated far beyond the requested depth. Do not repeat that work or research every possible feature as if it will be built. Existing evidence is sufficient for the initial questions.
4. **The deliverable is a document plus a handoff prompt.** The user does not want to continue the decision process in the original conversation. A separate agent will use these files.
5. **No recommendations unless technically necessary.** Explain tradeoffs without selecting defaults or prioritizing features for the user.
6. **Stop before production implementation.** Disposable experiments were allowed to establish feasibility, but no runtime experiment is currently needed to begin the decision discussion. Unknowns can remain explicitly unknown until relevant choices are made.

The previous agent's statements about centering or retaining a particular implementation were premature and are not decisions. The detailed report has been corrected. No answers have been supplied to its decision questions.

## Basic verified facts

| Subject | Finding | What it means for a decision |
| --- | --- | --- |
| Existing horde mechanism | Vanilla already keeps a living cohort replenished until its finite total runs out. | This is an extension of an existing behavior, not a need to invent horde spawning. |
| Time | Vanilla nighttime is 19:00 through 06:30. Its current randomized starts are 20:00 through 01:00. | Start/end choices can stay within the native night gate. |
| End | Dawn and exhausted spawn total stop new spawns; surviving enemies remain. | Removing survivors would be a separate behavior choice. |
| Population | Loaded world base total is 15, initial pioneers 2, with growth by horde number. A shared AI focus limit is 60. | Total spawned, concurrent living and active pursuit are different controls. More spawned zombies does not guarantee all will pursue. |
| Corpse conversion | Physical ragdolls eventually become cheaper static bodies. The world uses a soft ragdoll conversion threshold of 4. | A living cap alone does not prevent death/physics spikes. |
| Corpse retention | Static-body cap/expiry can permanently delete bodies. Distance hiding preserves them. The cap has exceptions and is not a strict count of every saved corpse. | Raising corpse retention is simple but increases resource use; it is not guaranteed lossless storage. |
| Loot | Permanent corpse removal deletes its loot record/opportunity. Unopened loot is rolled on first opening. | Preserving all loot separately requires more than moving already-generated items. |
| Reload | Native horde restoration requires saved survivors, recreates them at full HP, and clears survivor records by day. | Reliable continuation when saving between replacements is an optional targeted extension, not a reason for daytime support. |
| Scaling | Horde number, distance from world origin and nearby player-built structure HP already influence horde quantity/strength. | Some suggested progression inputs already exist. Days and character progression are other available inputs. |
| Performance | Code inspection found AI/pathfinding, sound/death broadcasts, spawn raycasts, physics/destruction and corpse/loot accumulation costs. | There is no measured safe maximum population or FPS prediction. |

The inspected player saves have horde multiplier 8, corpse cap 300 and lifetime 1 game day. At wave 17, the native formulas calculate 152 total and 32 concurrent. These are saved settings/calculations, not a successful stress test or proposed defaults.

## Decisions still needed

Difficulty is comparative, not an implementation estimate in days: **Low** means a localized setting/hook; **Medium** means coordinating several existing behaviors; **High** means substantial new state, storage or combat integration. No row is selected. Ask about the main behavior first; numeric defaults and edge cases can follow after the feature scope is chosen.

| ID | Decision | Viable options and player effect | Difficulty / main tradeoff |
| --- | --- | --- | --- |
| D1 | Start and end | Fixed nighttime hour, configurable random window, or native randomized start; custom night end or vanilla dawn. | Low-Medium. Midnight/load handling needed; no daytime support. |
| D2 | Budget and concurrent population | Both fixed/unlimited budget are in the concept. Choose how living horde size is configured and whether ambient zombies affect that target. | Medium. Horde-only accounting is narrower; a true combined cap also involves ambient spawning. Values/defaults remain unset. |
| D3 | Replenishment | Steady replacements or periodic batches. | Medium overall; steady replacement already exists. Batches add pressure/recovery rhythm and potential spawn spikes. |
| D4 | Survivors at the first limit | Leave them as vanilla does, remove immediately, or remove after a grace period. | Low-Medium. Removal reduces load but changes combat and requires proper pool cleanup. Immediate removal at budget exhaustion also removes the final arrivals. |
| D5 | AI participation | Keep the shared focus allowance, raise it, or separate horde/ambient allowances. | Low for a global increase; Medium-High for separate allocation. More active pursuit costs CPU/pathfinding. No tested safe value. |
| D6 | Corpse/loot policy | Native loss, more retained bodies, loot markers after body removal, aggregated caches, or ground drops. | Native/raised retention: Low. Separate persistent loot/cache: High. Ground drops add clutter/physics and do not automatically preserve unopened loot. |
| D7 | Loot timing and overflow, if preservation is wanted | Roll when collected, at death, or at eviction; select retention/expiry/overflow. | High for a separate loot system. Timing changes perk/location-dependent rolls. Unlimited preservation can grow without bound. |
| D8 | Reload fidelity | Native behavior, continuation through zero-survivor refill gaps, or additional survivor HP persistence. | Low / Medium / Medium-High. Extra fidelity needs state beyond the current save. |
| D9 | Optional strength/composition | Health/damage multipliers, existing prefab weights, authentic bosses, movement, resistance or jumping. | Health/damage/weights: Low-Medium. Boss integration/movement: Medium or more. Universal resistance/jump changes: more involved. Optional, not assumed. |
| D10 | Progression and rewards | No additional scaling, or selected depth/wave/day/character/base inputs; retain or change stat-linked XP. | Low-Medium for existing input snapshots. New gear/wealth scores are additional work. More HP currently means more kill XP. |
| D11 | Performance approach | Configured cap, fewer stronger enemies, or adaptive population based on frame time. | Fixed cap/strength: narrower. Adaptive behavior: more logic and changing difficulty. Practical limits remain unmeasured. |
| D12 | Other behavior, only if relevant | Native placement/flee/death handling or changes; config-only versus HUD; next-event versus live setting changes. | Low to High depending on the change. These are follow-up choices, not requirements to expand scope now. |

## What was done and where it is

Repository: `C:\Users\Admin\Documents\GIT\GameMods\HumanHostMods`

Game install: `C:\Steam\steamapps\common\Human Host`

- User noted a game update. The repository tool refreshed all 48 assemblies to Steam build **25448142**, from 25407931.
- `HumanHostCodebase` is its own gitignored local Git repository. Its refreshed source commit is **75505302bbe546b6f783690e4d97230c537edda0**. The tool made that local source commit; nothing was pushed.
- Read the actual Addressables world and selected prefab bundles. Important trap: built-in `level1` and C# initializer values differ from the world actually loaded. Do not overwrite the verified values with those defaults.
- Decoded and inspected assets only in ignored `.local/expanded-hordes/`. Installed inspection dependencies there, not into the game. Read compressed saves without changing them.
- `dotnet build HumanHostMods.slnx -c Release` passed with 0 warnings/errors. This builds existing HelloHost; it is not proof of an Expanded Hordes prototype.
- No production mod code, deployment, game launch, save mutation or runtime benchmark occurred. No plan was approved. No parent-repository commit was made.

Useful files:

- `research/expanded-hordes.md`: detailed findings, full options/risk/performance tables and source-member evidence map. Read selectively when a decision needs more explanation.
- `.local/expanded-hordes/verification.json`: current configuration extracts and 12 DLL SHA-256 hashes.
- `.local/expanded-hordes/world-assets.json`, `bundle-assets.json`, `desert-assets.json`, `forest-assets.json`: extracted manager/prefab evidence, local only.
- `.local/expanded-hordes/decode_world.ps1`, `inspect_assets.py`, `prefab_summary.py`, `save_and_hash_probe.py`: disposable inspection scripts. No need to rerun for the initial discussion.
- `.local/expanded-hordes/PNPH-save.json`, `DBD-save.json`: read-only extracted save evidence. These are not runtime population measurements.
- `.local/expanded-hordes/validate_report.py`: basic report link/table/whitespace check.
- `tools/Get-ModEnvStatus.ps1`, `tools/Decompile-GameCode.ps1`: existing repository environment/source tools. Do not refresh all assets/source again unless there is evidence of another game update.

The existing BepInEx log predates the updated assemblies, so it is not current runtime validation. Installed third-party mods may affect later benchmarks. Do not alter their plugins/configuration. Source repo contains preexisting/editor-generated `obj` artifacts; do not clean them as part of this handoff.

## Remaining uncertainty, without more investigation now

No tested population ceiling or FPS numbers; no runtime boss adapter test; separate lossless loot generation remains unprototyped; exact cave/scene transitions, third-party plugin interactions, extra save-state recovery and ModMenu integration remain unverified. These only need further work if the user's chosen scope depends on them.

Boss assets were confirmed (Artificial Mutant 4,000 base HP, Subject 1 2,000), but their availability through the current horde registry was not established. Do not present a boss toggle as finished or trivial. Some large regular zombies are not bosses.

## Next agent's job

Use this handoff to help the user make the decisions, at the basic level requested. Keep the discussion and any decision record in that separate task. Do not repeat the full investigation, choose answers, turn optional ideas into requirements, or begin implementation. Refer to the detailed report only for the question at hand. Record actual user answers clearly and distinguish them from unresolved options. Planning comes after the user's choices and direction to proceed.
