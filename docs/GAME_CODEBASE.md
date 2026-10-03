# Game source and text catalogs

`tools/Decompile-GameCode.ps1` generates one local reference in
`HumanHostCodebase/`. It includes decompiled managed code, a catalog of asset
objects, serialized gameplay fields, resolved references, and readable views.
It does not export image, mesh, audio, video, or other bulk engine payloads.

## Setup and refresh

Requirements: PowerShell 7, Python 3.13, Git, ilspycmd 11+, and its .NET runtime.
Install the Python dependencies in an isolated directory:

```powershell
py -3 -m pip install --target .cache/catalog-python -r tools/game_catalog/requirements.txt
pwsh -NoProfile -File tools/Decompile-GameCode.ps1
```

Reuse an existing installation with `-PythonPackagesPath`, or set
`CatalogPythonPackages` in the gitignored `GamePaths.local.props`. The command
uses that setting before `.cache/catalog-python`. It does not install packages
or change the game installation. Avoid refreshing while Steam is modifying the
game files. Input changes detected during generation abort publication.

After a successful full capture, the command runs the independent
`HumanHostWiki/wiki.py update --operator-report` entrypoint. An unchanged capture
also follows this handoff. The wiki reads selected facts and evidence in place;
raw code and whole catalogs are not copied into wiki content. Supported wiki work
finishes before the operator receives its grouped unresolved-content report.
Execution failures are reported separately. The configured wiki now creates a
coordinated Git release and publishes supported content to GitHub Pages, verifying
topic sites before advancing the hub. Gameplay coverage and verification remain
incomplete and are labeled in the reader.
See [wiki workflow](../HumanHostWiki/docs/WORKFLOW.md).

Use `-WikiPath` for another configured wiki umbrella. `-SkipWiki` explicitly runs
source-only diagnostics. Partial `-Assemblies` and `-NoGit` exports skip the wiki
because they cannot provide its full committed input contract. A missing wiki
entrypoint after normal capture is reported as an execution failure.

`-All` remains accepted; all non-framework managed assemblies are now the
default. `-Assemblies Player,UI` requires a new `-OutputPath` and marks its
assembly coverage as partial. It cannot overwrite the normal full snapshot.
`-NoGit` publishes the text without creating a commit.
An existing output without a local Git baseline cannot be overwritten; use a
new path for another `-NoGit` export. Outputs inside the workspace must be
gitignored, such as `HumanHostCodebase` or a path under `.local`.

## Timing receipt

Every capture writes an atomic JSON receipt under the workspace root at
`.local/runs/capture-<UTC yyyymmddTHHMMSSZ>-<pid>-<8 hex run id>.json`, including failures,
deadlines and unchanged-input reuse. Schema `humanhost.capture-timing.v1` has
UTC `started_at` and `finished_at` strings ending in `Z`, total `seconds`,
`outcome` (`succeeded`, `failed` or `reused`), a short `error` or null,
`output_path`, `output_commit` (SHA or null), and `game` (a `version` and `build`
object, with unknown version null, or null before identity is available).
`phases` and `assemblies` contain `{name, seconds, outcome}` entries; their
outcomes are `succeeded`, `failed` or `skipped`. Phases are `input hashing/reuse
check`, `catalog decode`, `decompile`, `Git promotion` and `cleanup`. Assembly
times include resource-name listing; concurrent times overlap. Unstarted work
has zero seconds and is skipped; reuse has no assembly entries.

Durations use `time.perf_counter`. The supervising process finalizes timeout
receipts from an atomic `.pending` checkpoint beside the receipt, then removes
the checkpoint. It prints an aligned phase/seconds/outcome table and total to
stderr. Timing stays in gitignored `.local/`; it never enters generated inputs,
snapshot hashes or commits. `timing.py` is excluded from the generator/tool
provenance hashes because it does not affect generated outputs. Timing generates
the random run id and reserves receipt/checkpoint names exclusively; an existing
file is never overwritten. `--timing-receipt <path>` (also `--timing-receipt=<path>`)
selects a parent directory inside `.local/runs/`; timing still generates the
filename. Paths outside that directory are usage errors rejected before writes.
Receipt/checkpoint I/O runs in a background worker with a bounded final flush.
Diagnostic failures emit a warning and preserve capture success, failure or
timeout, even when no receipt can be saved. Timing reports the generated path to
the wrapper only after saving the receipt. The wiki handoff appends `--capture-timing <path>`
after `--operator-report` only when `wiki.py update --help` advertises it.

## What is generated

| Output | Information |
| --- | --- |
| `<assembly>/*.cs` | C# from game and package assemblies, with shipped PDB variable names where available |
| `Catalog/inputs.jsonl` | Input paths, sizes, SHA-256 hashes and categories |
| `Catalog/steam-build.json` | Steam build, branch and installed depot manifest identities, without playtime or account state |
| `Catalog/game-version.json` | Captured application version from `PlayerSettings.bundleVersion`, or an explicit unknown reason; includes input hash and object/field evidence |
| `Catalog/assemblies.jsonl` | Every managed DLL, decompilation status and exclusion reason |
| `Catalog/embedded-resources.jsonl` | Names of resources embedded in selected assemblies; resource bodies are not extracted |
| `Catalog/serialized-files.jsonl` | Original bundle/member paths, Unity versions, external dependencies and object counts |
| `Catalog/bundle-members.jsonl` | Serialized files and resource streams inside bundles |
| `Catalog/objects/` | Object IDs, names, types, serialized sizes, gameplay fields and reference results |
| `Catalog/addressables.jsonl` | Decoded addresses, GUIDs, providers, resource types, dependencies and object targets |
| `Catalog/containers.jsonl` | Named asset paths mapped to objects |
| `Catalog/references.jsonl` | Reference edges, source field paths, targets and resolution status |
| `Catalog/loose-text.jsonl` | Readable installed configuration and text files |
| `Catalog/compressed-text.jsonl` | Compressed text companions, including the game's Lua loader data |
| `Catalog/views/LOOT.md` | Loot tags, eligible item names, loot sets and serialized source objects |
| `Catalog/views/*.jsonl` | Searchable loot, item, spawn, recipe, localization and object indexes |
| `Catalog/coverage.json` | Object/type counts, omitted payload categories and decoding/reference gaps |
| `Catalog/generator.json` | Parser/decompiler versions and generator hashes, normalizing CRLF to LF |

Script records have verified byte offsets, sizes and SHA-256 hashes in the object
index. Records of at least 1 MiB also carry a `members` map: each top-level name
maps to its encoded JSON value size; `fields` maps every field name to its value
size. Names and sizes describe the complete record, including fields that a wiki
adapter does not select. Values stay in the original object shard. The producer
writes the same sorted, space-separated UTF-8 JSON bytes as before, with LF endings.
Readers can hash skipped values in bounded chunks and decode selected fields.
They must verify the record hash, member names/boundaries and total byte coverage
before accepting a projected record. Older indexes remain valid without this map.

The inventory excludes the game's `Save` and `ModBrowser` runtime directories,
`*.log`, `log-*.txt`, and `output_log.txt`, including Chromium's plugin log.
Steam account state, playtime and download progress are excluded; build and depot
identities are recorded separately so those transient fields do not create diffs.
Native executable/module files and framework DLLs are inventoried. Their native
implementations are not reconstructed as C#. The assembly manifest explicitly
identifies framework exclusions.

`tools/game_catalog/game_version.py` selects the unique captured `PlayerSettings`
object's `bundleVersion`. Unity documents this as the value of
[Application.version](https://docs.unity3d.com/2022.3/Documentation/ScriptReference/Application-version.html).
Missing, ambiguous or invalid settings record an unknown version. Input evidence
must resolve to the normal hash inventory. No executable-version fallback is used:
the installed `Human Host.exe` product version identifies the Unity engine.
The wiki consumes this small record from new source commits; it does not backfill
version claims into older immutable snapshot receipts.

After a capture, independently audit that field against the catalog and installed
input bytes with:

```powershell
py -3 tools/check_game_version.py --source HumanHostCodebase --game 'C:/Steam/steamapps/common/Human Host'
```

This checks a recorded version; unknown versions remain an explicit gap and do
not satisfy that audit. The check never modifies installed files.

## Reading loot data

Start with `Catalog/views/LOOT.md`. It joins these serialized relationships:

1. `Loot_Mgr._All_Loot_Icons` supplies tags and item AssetReference GUIDs.
2. Addressables entries and AssetBundle containers resolve GUIDs to objects.
3. GameObject components locate `Icon_Info` and its `Tooltip_Text` reference.
4. Tooltip entries provide English names and the other shipped translations.
5. `Loot_Rate_Sets._LootSpawnRates` supplies tag/rate/stack fields.
6. References to those sets identify containers and other serialized sources.

The exported `_spawnRateRange` is a serialized field, not an unconditional drop
probability. Consult `Loot_Mgr` and caller code for selection rules, difficulty,
distance and runtime assignment. Dynamic game state and mod-added entries are
not present in an installed-data snapshot.

Every row retains an object ID that leads back to the object record and its
original serialized file. Null, unresolved, ambiguous, and engine-builtin
references are distinguished. A GUID with multiple targets retains all of them;
the exporter does not silently select one.

## Payload and schema rules

UnityFS data is read through a seekable member stream. Uncompressed blocks use
range reads; compressed blocks use a small cache. The installed game's decoder
handles its encrypted bundle in a separate process through binary stdout.
Decoded bundles are never saved. This still needs memory for decoding and the
reference index.

Graphical/media objects retain catalog entries, while their bodies are omitted
with an explicit reason. Binary serialized fields retain a size/hash descriptor.
This includes baked gore meshes stored in script objects and baked animation
matrices; putting mesh data in a ScriptableObject does not make it gameplay text.
Bundle preload bookkeeping is summarized; named container paths are exported
separately. Gameplay lists, rates, IDs, strings and references are retained.
The omission type list is versioned in `catalog.py` and emitted in coverage.

Embedded Unity type trees define field layouts when available. The pinned
exporter reuses matching embedded layouts across files, then reconstructs stripped
layouts from installed managed DLLs. Its adapter corrects generated primitive
array nodes and handles inline managed-reference data without Unity object headers.
All serialized files are indexed before resolving scripts and asset references.
Any object decoding failure prevents publication. Reference gaps remain visible
in coverage and the reference index.
Editor-only objects whose declaring DLLs were not shipped remain cataloged with
an explicit `decode_gap` and a raw-data hash; their absent field schemas cannot
be reconstructed from the installed player. These gaps are listed in coverage.

## Comparisons, failure recovery and validation

Records and files use deterministic ordering. Generation timestamps and absolute
machine paths are excluded from the snapshot. Bundle content hashes are removed
from logical file names, while original names remain in provenance records.
Object identities combine the logical file, serialized-member ordinal and Unity
path ID. These path IDs can change across builds; GUIDs and container paths help
trace such changes and are not falsely described as immutable identities.

Generation uses an OS-held lock and a sibling staging directory containing text
only. The old snapshot remains available during generation. A journal and backup
directory make publication recoverable. A failed or interrupted publication is
rolled back on the next invocation; a completed commit is retained. Do not
manually delete a journal or backup while a refresh is active.

Git plumbing and decompiler version probes have a 2-minute deadline; each assembly
decompilation, resource listing and bundle decoder has 20 minutes. The whole
capture has 4 hours and the subsequent wiki update has 4 hours 10 minutes, allowing
the wiki's 4-hour watchdog to report its own timeout. Failed or expired
processes lose their owned Windows job or POSIX process group (descendant cleanup
is best effort on POSIX); pipe cleanup has bounded joins even if forwarding blocks.
An assembly failure also cancels pending and running siblings. Before promotion,
the journal records the prepared tree, commit and index identities. Recovery
retains that exact completed result and rolls back recognized intermediate swap
states; unrecognized states preserve both directories and require inspection.
A second interruption during recovery can halt as ambiguous while preserving both
directories; the operator must scrap the incomplete capture and rerun.
Deadlines add no timing fields to generator inputs or hashes.

The command refuses dirty snapshots, ignored local files, Git remotes, and
unrecognized output directories. Resolve such files before refreshing. Generated
data stays out of the workspace repository and all remotes; only the separate
local snapshot repository records it.

```powershell
py -3 tools/game_catalog/test_catalog.py --python-packages .cache/catalog-python
git -C HumanHostCodebase log -3 --oneline
git -C HumanHostCodebase diff HEAD~1 --stat
git -C HumanHostCodebase diff HEAD~1 -- Catalog/views/loot-tags.jsonl
```

An unchanged-input repeat must leave the snapshot's Git HEAD and working tree
unchanged. Refresh hashes the installed inputs and compares the Steam identity,
parser/decompiler versions and generator hashes before export. An exact match
reuses the clean full snapshot, skipping catalog decoding and assembly decompilation.
The stability checks still run; partial assembly captures are not reusable full
snapshots. Changes to parser versions or generator source intentionally change
`Catalog/generator.json`. The local unit tests exercise binary omission,
Addressables decoding, lazy bundle reads, reference ambiguity, writer locking,
rollback, dirty-state preservation and repeat publication.

Implementation references: [UnityPy](https://github.com/K0lb3/UnityPy), the
installed `Unity.Addressables.dll` members `ContentCatalogData.CreateLocator`
and `SerializationUtilities.ReadObjectFromByteArray`, and the installed
`UIResource.dll` members `EnLootIndicatorBundleResource.BeginLoad` and
`LootIndiC.DeLootIndiBytes`. Installed DLL hashes are recorded in the inventory.
