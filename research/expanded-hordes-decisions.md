# Expanded Hordes decisions

Status: core MVP implementation authorized by the user's subsequent build request on 2026-09-21. The user then required local installation and HHMM compatibility; the DLL and standard config are installed. HHMM UI verification is reserved to the user, who explicitly prohibited further computer use. See [implementation and play-test notes](../mods/ExpandedHordes/README.md). The discussion-stage authorization statements below are historical; unselected options remain out of scope. No game launch, save changes or benchmarking were performed.

This record captures the user's answers in the current discussion. The [handoff](expanded-hordes-handoff.md) supplies prior context; the [research report](expanded-hordes.md) supplies supporting evidence. Options in those files are not selected requirements.

## Production pass authorized 2026-09-22

The user added separate regular/large/boss damage resistance where practical,
persistent for horde survivors after the event; maximum HP and health-based XP
must stay unchanged. Independent controls use the native health setter and horde
membership. Defaults chosen for testing are 25% / 40% / 50%, configurable 0-95%.
Run speed retains the user's earlier end-when-spawning-ends decision.

The user selected a larger optional corpse retention setting, default **300**
(verified vanilla menu maximum). Implemented range: 1-5,000, with the higher of
native and configured limits used. This does not reserve living slots, retain
physical ragdolls forever or add separate loot preservation. Native expiry,
distance hiding and oldest-body cleanup remain.

The user authorized modular boundaries, compatibility/failure handling, optional
debug logging and performance profiling, local installation and Workshop-ready
materials. Debug and profiling default off. CPU/GPU measurements are conditional
on native Unity availability and cannot establish exact causal bottlenecks.
Publication awaits the user's runtime testing and account setup. No computer UI,
game launch or publication by the agent is authorized. Existing accepted config
values must survive installation. See the [release contract](expanded-hordes-release-pass.md)
and [maintenance notes](../docs/expanded-hordes-maintenance.md).

This current authorization supersedes the historical discussion-only restrictions
and deferred resistance/corpse/diagnostics statements below. Other optional
features remain unimplemented and require explicit permission.

## Confirmed constraints

- Custom start/end times must stay within vanilla nighttime. Daytime hordes are out of scope.
- Prefer working with vanilla when comparing options; no implementation approach is approved by that preference.
- Optional features remain ideas to evaluate. Do not select product behavior or recommend options unless technically necessary.
- No deployment, game launch, save changes or further benchmarking is authorized.
- Planning and production code require relevant decisions and explicit direction to proceed.
- Discussion format: ask one question at a time with an x-of-y counter; present options in a table with behavior, relative difficulty, and relevant risks/performance implications for every question.

## Confirmed behavior decisions

- **Q1, start timing:** Use native randomized start timing for the initial proof-of-concept mod. Confirmed by the user in this discussion.
- **Q2, end timing:** Use native dawn (06:30) as the spawning window's time limit for the initial proof of concept. The user explicitly accepts vanilla's small polling delay around dawn; an exact cutoff is not required. This does not authorize daytime horde support or decide budget limits or survivor handling.
- **Q3, total budget:** Configurable finite total. A sufficiently large value can provide effectively unlimited replenishment until native dawn. No separate unlimited mode for the initial proof of concept. Exact values remain unset. The user clarified that the preceding discussion already established this choice; do not ask for repeated confirmation.
- **Q4, living population / AI participation:** Allow raising the living horde target and AI allowance through configuration, with a performance disclaimer. Values/defaults remain unset. Do not claim system performance is the only limitation before checking for other hardcoded constraints.
- **Q5, ambient competition:** Retain native population/accounting, with the simple attraction addition below. Defer high ambient population and aggressive respawning to later review. Do not add ambient killing, despawning, spawn suppression or reserved allocation to address this issue now.
- **Q6, replenishment:** Use native steady replacement for the initial proof of concept. More complicated replacement patterns are deferred and should be revisited only if necessary.
- **Q7, survivors:** Use native behavior: reaching the budget or dawn stops new spawning; surviving enemies remain subject to normal game cleanup.
- **Configuration:** Use the standard mod settings-file approach, intended to be easy to edit within HHMM. Exact HHMM compatibility remains unverified; no custom configuration UI is selected.
- **Placement:** Keep native retries. Add lightweight logging to reveal how often placement failures occur. Logging detail/aggregation remains unspecified. The user has not experienced a complete horde failure; this is player experience, not a measured failure rate. Additional recovery is not justified without evidence of a real problem.
- **Ambient attraction:** Once at horde start, issue a best-effort silent sound event at the player plus an elevated event far above the player's position to reduce building obstruction. These are two notifications forming one attraction trigger, not a continuous sound or periodic rebroadcast. The user explicitly requires one-time triggering to avoid repeated processing cost. The user accepts incomplete attraction, including a possible advantage underground, and does not want edge-case handling. Do not escalate this into forced targeting or full horde-membership conversion. This selects behavior for initial scope, not permission to implement. Height and hearing radius remain unset.

## Future enhancement options

- [Recovered optional features and horde run-speed evidence](expanded-hordes-speed.md): run speed was subsequently authorized and implemented as described below. The other unfinished discussions remain out of scope.
- Configurable fixed start time and configurable random start window. Explicitly deferred by the user; neither is needed for the initial proof of concept. Both remain subject to the nighttime-only constraint. Recording these options does not approve their implementation.
- Ambient population/respawn competition beyond the selected simple attraction: review later; no additional solution in the initial proof of concept.
- Placement recovery beyond native retries: consider only if failure logging establishes a problem.
- Replacement batches, pulses or other more complicated patterns: deferred unless a need emerges.

## Follow-up: horde timing and native quantity

The user explicitly requires preserving vanilla Horde Night cadence (every
night, every other night, every third night, etc.). Source inspection confirms
the current mod leaves `Calculate_And_Set_Next_Horde_Time` and
`Check_Horde_Events` intact; native `_Horde_IntervalF` still controls scheduling
and the disabled-hordes check in `NPC_Horde_Mgr._Start` remains intact.

The user authorized run-speed implementation and confirmed that it must apply
only during the horde time frame and never outside it. The user selected
ending the effect when horde spawning ends. The setting applies to
horde-spawned zombies, with a provisional configurable default of 125%; it does
not change ordinary nights into horde nights or force walking zombies to run.

The user explicitly selected vanilla's Horde Quantity multiplier on the total
so players can reduce the horde through vanilla settings. Total Spawn Budget
now means the base at 100%, with a default of 1,000 and range of 1-50,000.
The user corrected the cap interpretation: **50,000 BEFORE the multiplier**.
Thus 800% permits 8,000 at the default base and 400,000 at the maximum base.
Dawn still stops spawning. Native per-horde count growth remains replaced;
the living target remains its separate simultaneous cap. Captions use the
game's percentage representation. This supersedes the earlier fixed-final-total
implementation and the proposed post-multiplier cap, which was not installed.

The user also requested a Wolfram calculation of an extreme hypothetical spawn
ceiling with immediate kills, 200 living capacity and maximum day duration.
See [timing evidence and arithmetic](expanded-hordes-spawn-ceiling.md); the
numbers are not runtime capacity or performance claims.

## Confirmed composition feature

Each biome retains its local native selection, with added access to every existing boss type and every existing large non-boss type. The intended onset is the repeating biome cycle, region 11 onward, controlled separately for large zombies and bosses. The user selected the spawn-entry approach below after comparing maintenance and compatibility implications. This approves the approach, not implementation work.

The user subsequently supplied these setting definitions:

| Setting | Type / range | Specified default |
| --- | --- | --- |
| Extra Large Zombie Begin Biome | Integer | Not explicitly assigned; region 11 is the stated intended onset |
| Extra Boss Zombie Begin Biome | Integer | Not explicitly assigned; region 11 is the stated intended onset |
| Extra Large Zombie Percentage | 0-40 | 20 |
| Extra Boss Zombie Percentage | 0-40 | 5 |

**Selected approach:** One narrowly scoped patch at entry to `NPC_Horde_Mgr.Spawn_Horde_NPC`, before its original body runs. For fresh spawns, apply the configured region gates and extra category chances. When an extra selection wins, use an existing registered creature's biome/group/prefab identifiers; otherwise retain vanilla's local choice. Vanilla remains responsible for loading, creation, level application, rendering, horde tracking, saving and cleanup. Saved-enemy restoration retains its original identifiers; the inspected callers distinguish restoration with `async: false`.

**Reason for selection:** This is the engineering recommendation for the simplest maintainable option for the requested horde-only feature. It avoids extending shared ambient templates and their saved indices, and avoids modifying compiled coroutine internals. Update dependencies are the spawn-method signature and fresh-versus-restored caller behavior. Relative effort is small selection logic with moderate integration/verification. Runtime reliability is untested; this is a validation limitation, not an undecided approach. See [composition evidence](expanded-hordes-composition.md).

**Confirmed engineering constraint:** Preserve vanilla handling after selection and minimize ongoing compatibility work and special-case bookkeeping. Judge simplicity by maintenance as well as patch size. The earlier comparison's blanket "No" row conflated lack of runtime verification with lack of an engineering recommendation and was misleading; do not reopen the selected approach on that basis.

The selected extra percentages are chances to substitute a shared special into a native horde slot, leaving other choices vanilla. Native specials can still occur in the remainder; these settings are not exact final category ratios or minimum boss quotas.

## Open questions and validation gaps

All seven core-behavior questions and the composition approach are answered. Remaining composition details: the two begin-biome defaults have not been explicitly assigned; permanent unlock after returning inward is unspecified; the swamp's empty native ordinary roster needs a fallback choice only if full mixed hordes there are required. These details do not authorize additional systems or edge-case work. The selected patch still requires runtime verification when separately authorized.

Resolved by targeted asset/source inspection: authentic bosses are already in native horde lists. Mountain Forest groups 02/03 include Subject 1 at 1/83 and 1/81 per selection; War Zone group 02 includes Artificial Mutant at 1/81. Other groups can have zero boss chance. Group order is shuffled by seed, with distance selecting a group in 256 m bands. All 16 registry group entries resolve and their weights match the extracted prefabs. Tropical Swamp's group is empty. See [composition evidence and difficulty comparison](expanded-hordes-composition.md) and [full roster](expanded-hordes-roster.md).

Existing horde factory/save identifiers support choosing across registered biome groups. The earlier blanket assumption that authentic bosses need a new adapter is withdrawn for these registered bosses. Category percentages within a group are Low-Medium; cross-biome selection and controlled ratios are Medium comparative effort. A ring-11 distance gate is a small addition to a mixed-group option. Random percentages do not guarantee boss presence; minimum counts or controlled ratios are separate selectable behaviors. Mixed/boss-heavy runtime performance remains untested.

- **Attraction details:** Height and hearing radius remain unset. One-time triggering at horde start is confirmed; continuous or periodic attraction is excluded. Full horde accounting is not part of the selected simple sound attraction.

Later groups, not yet opened: corpse/loot policy and conditional preservation details; reload fidelity; optional strength/progression/performance features; other behavior only if relevant. Their question counts depend on the user's chosen scope. AI participation and basic configuration/placement scope are answered above. Finishing the core group did not finish the decision discussion; continue through remaining relevant groups without requiring the user to remind the assistant.

## Uncertainty

Use the handoff's existing findings for the initial discussion. Safe population limits and FPS impact remain unmeasured. Investigate other unknowns only when a decision depends on them.

Required follow-up for the chosen configurable limits: establish whether other hardcoded constraints restrict living population or AI participation. The inspected allowance is mutable, but a complete absence of other limits has not been established. Standard config-file editing through HHMM also needs verification. Neither uncertainty authorizes implementation, runtime checks or broad edge-case research now.

## Q3 clarification: large finite budgets

Q3 is resolved: configurable finite total. The user established that a large finite total can provide effectively unlimited replenishment until dawn; the interacting limits below explain its behavior.

Targeted source check against local game-source commit `75505302bbe546b6f783690e4d97230c537edda0`:

- A sufficiently large finite budget can serve that purpose using the native paced loop. A separate unlimited mode/controller is not technically necessary for that behavior. The research report's blanket rejection of a huge native loop count and requirement for an unlimited flag are not established technical requirements.
- `NPC_Horde_Mgr.Get_Plan_To_Spawn_Count` calculates base total times the saved quantity multiplier, plus wave growth, minus already spawned. Setting the base alone does not set the final total. One million fits the integer counter, but extreme inputs/intermediate arithmetic need validation; no safe maximum setting was tested.
- `Spawn_Horde_NPCs` separately limits living members using pioneers, the same quantity multiplier, wave growth and the AI allowance (60 in previously inspected loaded assets). It waits for a living slot and serial spawning, with a 0.1 scaled-second delay. A large remaining budget does not allocate a million enemies upfront or bypass these controls.
- The AI allowance also governs shared ambient/horde focus selection. Raising only the total does not ensure more simultaneous attackers. Distance/base scaling affects strength and composition, not an additional total-budget cap in the inspected calculation.
- Terrain context and valid placement can prevent or delay spawning; factory failures can leave a finite event short. Native restoration requires saved survivors, so a large budget does not repair continuation through zero-survivor save/load gaps.
- `Check_Horde_Events` polls daytime at five scaled-second intervals and stops the spawn coroutine. An outstanding asynchronous spawn can also finish later. The user accepts vanilla's small dawn delay; the assistant's earlier inference that strict cutoff handling was required is withdrawn. Exact runtime overshoot is unmeasured.

Sources: [NPC_Horde_Mgr.cs](../HumanHostCodebase/Terrain/NPC_Horde_Mgr.cs), members named above and `Try_Get_Spawn_Context`; [AI_Agen_Mgr.cs](../HumanHostCodebase/AI/AI_Agen_Mgr.cs), `SetHorde_MaxAllowActiveZombies` and sound focus selection; existing research for loaded asset values and reload/factory findings. These findings do not select an implementation approach.

## Supporting facts for the related decisions

- **AI competition:** Increasing the horde living target needs its pioneer calculation and allowance to permit it. Raising the shared allowance preserves ambient competition and increases potential AI load. Ambient removal or reserved focus were discussed but are deferred, not initial requirements.
- **Placement detection:** `GetValidSpawnPosition` returns an explicit failure position (`y = -10000`), and `Try_Get_Spawn_Context` reports failure. Native placement already performs multiple random/raycast passes; the spawn loop retries rejected replacement positions without consuming the loop iteration.
- **Deferred placement recovery options:** New anchor/direction, wider valid area, or waiting for terrain context. New anchors could change attack direction, wider searches add raycast cost, and missing biome data may not recover just by waiting. These are untested options; native retries plus lightweight logging are the selected scope.

Discussion corrections: state which limits are configurable or recoverable and compare remedies, rather than presenting current vanilla settings as immutable blockers. Do not repeatedly ask the user to confirm choices already established in discussion. Behavior selections above do not authorize planning or production code.

Prefer small, best-effort mitigations using native mechanics when comparing solutions. Explain an inexpensive workaround before treating a downside as grounds for a more complicated feature. Do not pursue completeness or rare edge cases beyond the user's chosen scope.

## Ambient attraction: bounded feasibility evidence

Same local source revision as above; inspected members were hash-verified. No runtime test or production changes.

Selected refinement: paired player-position/elevated-position AI sound events. The elevated obstruction ray can clear some intervening buildings; this is plausible from the inspected code, not runtime-proven. `soundSourcePos` supplies hearing/obstruction location while `soundSource`/`charController` identify the pursuit target. With player target data, an elevated sound position can still result in pursuit of the player, rather than an airborne waypoint. Height also contributes to three-dimensional hearing distance. The broadcast manager can ignore a new event while a prior focus-selection pass is running, so both events must be allowed to process. These are local API details to respect if implementation is later authorized, not reasons to add a new AI system.

The comparison below records alternatives evaluated; direct targeting and horde-membership conversion are not selected.

| Option | Existing support and player effect | Relative difficulty / limits |
| --- | --- | --- |
| Silent AI sound event | `AI_Agen_Mgr.Broadcast_Sound_Played` accepts player source data and `hearDis`; this call does not require playing a gunshot audio clip. Eligible zombies target the player through their existing response. | Low-Medium. `Zombie_Agent.On_Sound_Played` retains obstruction and focus checks, so a huge hearing radius alone does not compel every loaded zombie to respond. |
| Directly target the player | `Zombie_Agent.MoveToTarget` and `AI_Agent.Begin_Move_To_Target` provide existing target assignment; `AI_Agen_Mgr.On_Horde_Spawn` uses this path. | Low-Medium for initial attraction of eligible loaded living zombies. Bypasses hearing checks but still uses normal pursuit/pathfinding and later focus selection; not guaranteed permanent pursuit. |
| Also count ambient zombies as horde members | Attraction alone does not alter native horde living membership or emitted count. Counting recruits, replenishing their deaths and preserving ownership across saves/cleanup are additional behaviors. | Medium or higher depending on selected accounting and persistence. Merely changing their target does not provide these features. |

The AI registry provides a bounded set of loaded agents; distant unloaded zombies cannot respond to this event. No single maximum useful recruitment radius has been verified. Pulling existing zombies in does not create extra zombies at the trigger, but increases active pathfinding/combat and concentrates arrivals/deaths. Without accounting changes, recruited ambient attackers are additional to the horde's configured living target. Natural cleanup by combat depends on them reaching the fight and being killed.

Evidence: [AI_Agen_Mgr.cs](../HumanHostCodebase/AI/AI_Agen_Mgr.cs), `Broadcast_Sound_Played` and `On_Horde_Spawn`; [Zombie_Agent.cs](../HumanHostCodebase/AI/Zombie_Agent.cs), `On_Sound_Played` and `MoveToTarget`; [AI_Agent.cs](../HumanHostCodebase/AI/AI_Agent.cs), `Begin_Move_To_Target`; [Creature_Mgr.cs](../HumanHostCodebase/Creature/Creature_Mgr.cs), `OnSoundPlayed_Param`.
