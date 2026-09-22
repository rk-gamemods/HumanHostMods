# Expanded Hordes 0.2.0 validation record

Prepared and installed locally on 2026-09-22. Runtime testing and publication
remain pending. No game launch, computer UI, save write or Workshop upload was
performed by the agent.

## Verified

- Installed environment: Steam build 25448142, BepInEx 5.4.23.5, Unity 2022.3 Mono.
  Human Host was closed during installation. Terrain, AI and Creature DLL hashes
  matched the inspected source/asset research snapshot.
- Solution build: **0 warnings, 0 errors**.
- **245 policy and installed-assembly assertions passed**: quantity scaling,
  before-multiplier maximum, living compensation, run-speed boundaries, region
  and composition policy, damage reduction including overkill/healing/dead cases,
  category precedence, higher external corpse limits, bounded frame aggregation,
  missing-data profiler hints and native patch method/field/IL contracts.
- Native corpse slider asset: range 5-300, serialized value 50. The requested
  mod default of 300 is the native menu maximum, not a claim about its default.
- BepInEx read back **16 settings**, with the friendly Expanded Hordes 0.2.0
  header. All **10 pre-upgrade values** were preserved. New settings use regular/
  large/boss resistance 25/40/50%, corpse target 300, debug off and profiling off.
- Repeating the installer preserved config bytes. Repeating packaging preserved
  every release-file hash, including the ZIP and generated preview.
- Installed DLL, build DLL and package DLL match SHA-256:
  `8a815d262d3ca3b77dde1044511d1bbb48f2685ac339cce74de6c9fc74e267f1`.
- Workshop payload/ZIP contain exactly `ExpandedHordes/ExpandedHordes.dll` and
  `ExpandedHordes/README.txt`. ZIP entries read back identically; package hashes
  passed. No game assemblies, third-party binaries, user config, save or logs are
  bundled. The original 1,024-square preview was visually inspected.
- Optional upload manifest uses app 2393970, unpublished ID 0, private visibility
  2 and this machine's verified content/preview paths. Packaging does not upload.

The environment tool also found no errors in the **previous** BepInEx log, dated
2026-09-21. That old log is not evidence that this new DLL loaded or ran correctly.

## Remaining release gates

The [play-test checklist](../release/ExpandedHordes/PLAYTEST.md) covers HHMM
discovery, actual Harmony detours, native cadence/budgets, speed, damage/kill XP,
category selection, survivors/pool reuse, corpse visuals/cleanup and diagnostic
on/off behavior. It also includes testing with the user's usual other mods.
No runtime FPS, CPU/GPU availability, safe population ceiling, saved-survivor
combat result or blanket mod compatibility has been measured or certified.

The [publication guide](../release/ExpandedHordes/PUBLISHING.md), description,
preview and install payload are ready under `dist/ExpandedHordes-0.2.0/`.
Owner playtesting, account/Workshop agreements and the actual upload remain.
