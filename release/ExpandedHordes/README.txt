EXPANDED HORDES
More pressure. Tougher survivors. Your Horde Night settings.

Requires Human Host on Windows with BepInEx 5 (Unity Mono).
Prepared against Human Host Steam build 25448142 and BepInEx 5.4.23.5.
No other gameplay mod is required. HHMM can manage the local plugin and edit
its standard BepInEx configuration.

INSTALL
Close the game. For a manual install, place the ExpandedHordes folder in
<Human Host>/BepInEx/plugins/. Keep only one installed copy of the DLL.
For Workshop installation, use the game's Workshop mod installation flow.
The Workshop payload uses the same ExpandedHordes/ folder layout.

Launch once to create BepInEx/config/rkgamemods.humanhost.expandedhordes.cfg,
then close the game and edit it with HHMM or a text editor. The repository's
local installer creates the config before the first launch. Restart after
changing settings. Existing accepted values are retained on upgrade.

WHAT CHANGES
- Total Spawn Budget defaults to 1,000 BEFORE the game's Horde Quantity
  percentage. At 800%, that allows up to 8,000 creations, including replacements.
  The setting accepts 1-50,000 before multiplication. Dawn can stop it sooner.
- Living Horde Target defaults to 75 simultaneous horde zombies; Shared AI
  Allowance defaults to 90. Ordinary nearby zombies can be additional attackers.
  The AI allowance affects ordinary zombies as well, even between hordes.
- Horde running speed defaults to 125%, only while nighttime horde spawning
  remains active. Walking and attacks are unchanged. Survivors return to normal
  running speed when spawning ends or dawn arrives, whichever comes first.
- Damage resistance defaults to 25% for regular zombies, 40% for known large
  non-boss types and 50% for bosses. Each setting accepts 0-95%. These apply only
  to native horde members, including survivors after dawn and save/load. Maximum
  HP and health-based kill XP are unchanged. Ordinary attracted zombies do not
  gain this resistance. Settings apply to restored survivors too.
- Each fresh horde spawn can be replaced by a large zombie (20%) or boss (5%)
  once its separately configurable region gate opens (default region 11).
  These are chances per zombie, not guaranteed numbers or exact final ratios.
  Vanilla can also choose special types among the remaining normal selections.
- A one-time silent lure at horde start encourages nearby loaded zombies to
  approach. It cannot create distant zombies or load more of the map.
- Retained Corpse Limit defaults to 300 and accepts up to 5,000. The higher of
  this value and the game's current limit is used. Corpses do not fill living
  horde slots. Native oldest-body eviction, expiry and distance hiding remain.
  This is a shared retention target, not an exact count or permanent physical
  ragdoll pile. Removing bodies can remove their loot. High limits are untested.

Vanilla still controls whether Horde Night is enabled, its every-N-nights
cadence, start timing and dawn. The mod does not add a new event scheduler.

DIAGNOSTICS
Debug Mode and Performance Profiling are separate switches, both off by default.
Debug Mode adds event, placement and patch-overlap details to BepInEx/LogOutput.log.
Errors are logged even when debugging is off. A detected hook failure disables
that feature for the session; check the log after game updates.

Profiling writes 15-second summaries to the log and performance.csv beside the
DLL, rotating to performance.previous.csv at approximately 5 MiB per file.
It records frame times, FPS, selected inclusive method timings, managed memory,
garbage collections, living horde count and settled corpse count. CPU/GPU times
depend on what the game's Unity player exposes. Missing data says unavailable.
CPU/GPU hints are not proof of the cause of a slowdown. Profiling adds overhead;
turn it off after collecting a comparable sample. It is not a full-engine or
per-mod GPU profiler. Do not infer a safe population limit from the config range.

COMPATIBILITY AND LIMITS
The mod uses the game's spawning, saved identities, cleanup and XP calculations.
It adds no save fields and does not bundle game DLLs or another mod's code.
Future zombie types marked as bosses by the game use boss resistance. Unlisted
non-boss types use regular resistance until their identity is added to the catalog.
Mods replacing the same spawning, movement, health or corpse methods can still
conflict. No blanket compatibility guarantee is possible without testing them.
Forced-death effects or mods bypassing normal health handling may bypass resistance.
Some damage displays may show the original hit amount rather than reduced HP loss.
Vanilla survivor HP restoration and zero-survivor reload behavior remain unchanged.

TO REMOVE
Close the game and disable/remove only the ExpandedHordes plugin folder through
the same manager used to install it. The config may be retained for later use.
Do not keep simultaneous manual and Workshop copies enabled.

Created by rk-gamemods. Not affiliated with Virtual Matrix Studio or Valve.
