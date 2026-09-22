# Expanded Hordes release gate

**Status: awaiting the user's runtime play test.** Automated checks do not run
Unity, Harmony detours, graphics or HHMM. Do not publish until the checks below
pass on the packaged DLL. Use a backed-up/disposable save and record the game
build, mod version, relevant settings, other mods and `BepInEx/LogOutput.log`.

## First launch and basic regression

- Confirm HHMM lists **Expanded Hordes**, with 16 settings and readable captions.
  Existing values should remain. Enable Debug Mode for this test, then restart.
- Check the startup line says version 0.2.0. Load a world and find the catalog
  summary with three large and two boss types. No new errors, fatal errors or
  disabled-feature messages should appear. Debug hook-overlap lines alone are
  informational, not proof of a conflict.
- Use base budget 10, living target 3 and Horde Quantity 100%, then 200% in
  separate tests. Expected budgets are 10 and 20, with living target still 3.
  Check replacement after kills and no new arrivals once the budget runs out.
- Verify the game's disabled-horde and every-N-nights settings still work.
  With budget remaining, spawning ends around native dawn (06:30, allowing
  native polling and an outstanding spawn). Survivors remain.
- Compare 100% and 125% run speed. Only horde members running during active
  nighttime spawning change speed. Check speed returns when the budget runs
  out and at dawn. Walking, attacks and ordinary attracted zombies stay normal.
- Set both extra-type region gates to 1 and chances to 40% temporarily. Across
  sufficient spawns, check all three large types and both bosses for rendering,
  movement, combat, loot and reload identity. Random selection does not promise
  every type in a short test. Restore the chosen gates/chances afterward.

## Damage resistance

- Compare the same zombie type, level, weapon and hit location with resistance
  at 0% and 50%. Actual health loss should halve; maximum HP and kill XP should
  not change. Check actual HP loss rather than relying only on floating damage
  text. Avoid critical hits, armor and changing difficulty during the comparison.
- Set regular/large/boss values differently and confirm each category. Ordinary
  attracted zombies must retain their native damage behavior.
- Test an overkill hit: if the reduced damage still exceeds remaining HP, the
  zombie must die normally and release its living slot. Check healing and native
  falling-structure damage as well as direct weapons.
- Leave horde survivors after spawning ends and after dawn. Resistance remains;
  running speed returns to normal. Save/reload survivors: resistance follows
  their category using current settings, with vanilla HP restoration unchanged.
- Let a survivor return to the native pool, then observe later ordinary spawns.
  They must not inherit horde resistance. Check combat with the usual other mods
  enabled, especially any health, damage or zombie-overhaul mod.

## Corpses

- At the default 300, sustained kills should continue to produce living
  replacements even when old corpses are being removed. Observe the profiler's
  settled-body count if needed; temporary ragdolls and hidden saved bodies are
  not the same count.
- Raise the setting above 300 (start with 500) and confirm additional nearby
  settled bodies can remain. Keep the world's corpse lifetime long enough for
  this test. Native first-use prefab behavior can exceed the target slightly.
- Check distance hiding/reappearance, expiry, save/reload and normal looting.
  Permanent body removal can delete loot; no separate preservation is promised.
  Confirm the game's saved corpse setting was not overwritten by the mod.

## Diagnostics and release

- Enable Performance Profiling, restart, and collect several 15-second windows
  during idle, a horde and heavy corpse accumulation. Check CSV headers/rows,
  frame times, living/body counts and selected method timings. CPU/GPU timing
  must say `unavailable` when Unity supplies none. No missing-data bottleneck
  should be presented as a measured diagnosis.
- Turn both diagnostics switches off and restart. Routine per-event/placement
  debug and profiling output should stop; no new CSV rows should be added.
  Previously collected CSV files remain available. Errors stay enabled.
- Check a clean single-copy installation with default config in the usual
  mod setup. Restore desired settings after tests. Review performance before
  recommending population or corpse limits to other players.
- Rebuild the release package only if code/docs changed, then repeat affected
  checks. Record the final DLL SHA-256 from `SHA256SUMS.txt` and test results.
  Publication and account/Workshop agreement setup remain manual owner actions.

## Test record

| Field | Result |
| --- | --- |
| Date, game build, DLL SHA-256 | Pending |
| HHMM discovery and settings | Pending |
| Native cadence, quantity, living target, run speed | Pending |
| Composition, both bosses and three large types | Pending |
| Resistance categories, lethal damage, XP, survivors, pool reuse | Pending |
| Corpse retention, cleanup, loot, reload | Pending |
| Diagnostics on/off and representative performance | Pending |
| Other installed mods / observed conflicts | Pending |
| Approved to publish by owner | Pending |
