# Runbook: game update to published wiki

## Rules

- The normal update stops at a local release and retention.
- Publish only from reviewed, merged code on main, after exact-commit CI and a fresh successful rehearsal against live state.
- Scrap failed publication runs. Never resume or salvage them. Local update stages and capture rollback have their own recovery rules below.
- Never push decompiled game code, game DLLs or raw catalogs anywhere. The capture repository stays local with no remote.

Start in HumanHostMods and record its path with `$mods = (Get-Location).Path`.
Wiki commands run from its independent `HumanHostWiki/` checkout.
Read its [instructions](../HumanHostWiki/AGENTS.md) and [workflow](../HumanHostWiki/docs/WORKFLOW.md).
Use PowerShell 7 and the dependencies in [capture setup](GAME_CODEBASE.md#setup-and-refresh).
Resolve existing work in each owning repository. Do not bypass dirty-state checks or discard unknown files.

## 1. Detect the update

Wait for Steam to finish installing the update. From HumanHostMods, run:
```powershell
pwsh -NoProfile -File tools/Get-ModEnvStatus.ps1
Get-ChildItem .local/runs/capture-*.json | Sort-Object Name | Select-Object -Last 5 | ForEach-Object { Get-Content -LiteralPath $_.FullName }
```

Compare the installed `Steam build ID` with `game.build` in the latest successful
or reused capture receipt for the normal output path. A different build means
the installed distribution changed. Do not use a failed receipt as the baseline.
Success means the manifest build is known and Steam is no longer changing inputs.
These read-only checks create no timing receipt. If the manifest is missing or
Steam is still writing, repair the installation or wait before capture.

Record both the Steam build ID and developer-assigned game version after capture.
`game.version` comes from captured Unity PlayerSettings. The executable reports
Unity's version; Steam metadata does not reliably provide the game label. A null label stays unknown.
The wiki checks remote branch availability separately. An available build without a matching
installed capture is awaiting capture. An unavailable check cannot establish currency.
See [availability](../HumanHostWiki/docs/AVAILABILITY.md) and [version evidence](../HumanHostWiki/docs/GAME_VERSION.md).

## 2. Capture and decompile

From HumanHostMods, run the full entrypoint:

```powershell
pwsh -NoProfile -File tools/Decompile-GameCode.ps1
```

The wrapper bounds capture at **14400 seconds** and the wiki handoff at
**15000 seconds**. These are built-in bounds, not command flags. Full capture
is the default. Do not use `-SkipWiki`, `-NoGit` or `-Assemblies` for this path.
`-WikiPath` can select another configured wiki checkout; `-GameDir` selects the install.

Success prints `Complete:` with the output path or `Unchanged:` with the reused commit, then runs
`wiki.py update --source <captured-path> --operator-report`. Unchanged inputs still
receive the wiki handoff. The wrapper passes `--capture-timing` when supported.
Capture timing lands in HumanHostMods at `.local/runs/capture-*.json`, including
failed and reused captures when diagnostics can write. Check its outcome,
`output_commit`, `game.version` and `game.build`; wiki success is a separate check.

After capture, audit the recorded version against installed bytes:

```powershell
py -3 tools/check_game_version.py --source HumanHostCodebase --game 'C:/Steam/steamapps/common/Human Host'
```

Use the actual configured game path. Success reports `status: passed` and the version.
This audit creates no timing receipt. Unknown versions fail the audit;
record the gap and investigate the version selector before claiming verification.
If capture fails, keep the old snapshot and use interrupted-capture recovery in
step 8. If only the wiki handoff fails, keep the successful capture and use step 3.
See [capture receipts](GAME_CODEBASE.md#timing-receipt) and
[capture recovery](GAME_CODEBASE.md#comparisons-failure-recovery-and-validation).

## 3. Complete the local wiki release

The wrapper already ran the update. Enter the wiki checkout for every remaining step.
Use the `-WikiPath` checkout if capture selected one. Then read the run's timing:

```powershell
Set-Location HumanHostWiki
py -3 wiki.py timing --last 5
```

Only if the wrapper's wiki handoff failed, rerun the same update against the existing capture:

```powershell
py -3 wiki.py update --operator-report
```

If capture used a nondefault source, preserve its `--source <path>` on the retry.
Success prints the grouped report, `release_id` and `next_step`. It finishes the
local release, release retention and reader retention. It does not publish sites.
`releases/<release-id>.json` pins the child commits; `releases/latest.json` selects it.

The update watchdog has a **14400-second** deadline and exits **124** after
supervised cleanup, with a 60-second cleanup grace. Run timing lands in the wiki's
`.local/runs/wiki-update-<UTC>-<8 hex>.json`. Stage diagnostics also land in
`.local/pipeline/timings/`; immutable run/failure receipts live in
`.local/pipeline/runs/` and `.local/pipeline/failures/`.

On failure, inspect the named failure receipt and repair the failing stage.
Rerun the same command. Journaled stages revalidate artifacts before reuse, and
local release transactions recover their exact prepared commits. Do not edit
stage outputs or manually advance pointers. Timing warnings do not change the
command outcome; abrupt termination can leave no timing receipt.
See [pipeline recovery and timing](../HumanHostWiki/docs/PIPELINE.md) and
[local release transactions](../HumanHostWiki/docs/RELEASE.md).

## 4. Review exceptions and the release

Stay in HumanHostWiki. Run:

```powershell
py -3 wiki.py validate
py -3 wiki.py status
py -3 wiki.py check-lock
Get-Content releases/latest.json
```

Use the reported release ID for all remaining steps:
```powershell
$releaseId = 'REPLACE_WITH_REVIEWED_RELEASE_ID'
Get-Content "releases/$releaseId.json"
```

Success means the registry validates, children are clean and the checkout lock is current.
The manifest must pin the intended capture, child commits and outputs.
Review generated changes in their owning child repositories and inspect that release's reader.
Check version/build labels, coverage, provenance, historical selection and cross-topic links.
Follow [release review](../HumanHostWiki/docs/RELEASE.md#validation-and-preview). These checks create no run timing receipt.

Present grouped content and article exceptions for direction. Keep execution
failures, unavailable providers and retention issues separate. Decide whether
the explicit gaps are acceptable for publication; successful stages alone do not
prove gameplay verification. If corrections are needed, make, review and commit
them in their owning repositories. Identity corrections and extraction rules
belong in the umbrella; curated content belongs in its child repository. When
reviewed child commits change, adopt them with `py -3 wiki.py lock` before the
update, or update rejects the stale checkout lock. Then rerun the update and
select the resulting release. See [curated changes](../HumanHostWiki/docs/CURATED.md).
Review and merge umbrella changes, use main at fetched origin/main, and wait for
CI on that exact merged commit before rehearsal. See
[operator report](../HumanHostWiki/docs/PIPELINE.md#operator-report) and
[CI ownership](../HumanHostWiki/docs/ARCHITECTURE.md#running-tests).

## 5. Rehearse against live state

From the clean, merged HumanHostWiki checkout, run:

```powershell
py -3 tools/rehearse_publication.py --release $releaseId
```

Success prints `REHEARSAL PASSED` and saves `.local/publication/rehearsals/<release-id>.json`.
This hash-checked receipt binds the release, workspace commit, publication contract,
live branch refs and destination settings. It has no separate wiki run timing record.
The runner reads live state, simulates publication in owned OS-temp clones,
checks that real refs, pins, objects and publication state are unchanged, and
removes its temporary workspace before saving success.

On failure, fix the reported problem and rehearse afresh; do not use an older receipt.
A retained backup or failed restore requires explicit recovery. Keep its ownership record.
The next invocation cleans an abandoned temp root only after verifying ownership.
See [rehearsal contract](../HumanHostWiki/docs/PUBLICATION.md#production-gate).

## 6. Pass the publish gate

From reviewed, merged HumanHostWiki main, run:

```powershell
py -3 wiki.py publish --release $releaseId
```

Before provisioning or any remote effect, an incomplete publication journal
blocks the command. Abandon it as in step 8. Then the gate fails closed on the
first failed check, in this order:

1. No tracked changes or non-ignored untracked files in the umbrella.
2. `origin` identifies `github.com/rk-gamemods/HumanHostWiki` through accepted HTTPS or SSH syntax.
3. A bounded main fetch succeeds and HEAD equals fetched origin/main.
4. The newest matching `CI` run/attempt for that exact commit is completed and successful, from a main push of `.github/workflows/ci.yml`. Missing or malformed evidence fails.
5. A merged PR has a nonempty `merged_at` and this exact `merge_commit_sha`. A direct push is insufficient.
6. The hash-checked rehearsal receipt exists, uses the supported schema, and matches the release, workspace commit and publication contract, including the rehearsal runner. Its UTC timestamp is at most 24 hours old and not in the future.
7. Receipt refs have valid unique repository/branch identities and valid SHAs or null. They cover main and gh-pages for every current destination. Every recorded live ref still matches.
8. Destination observations are valid, unique and complete. Live identity, visibility, administrator permission and Pages settings still match, including absent or disabled destinations. Existing repositories must be public, unarchived and not forks; Pages must use gh-pages at `/`, legacy branch publishing, no CNAME and the expected URL.

There is no override flag. Repair the failed condition; refresh rehearsal after
expiry, contract changes or live drift. Preparation rechecks refs. Each push
checks ancestry and enforces the expected tip with a lease. Destination settings
are checked again before remote effects and hub promotion. See the owning
[publication contract](../HumanHostWiki/docs/PUBLICATION.md) and
[gate implementation](../HumanHostWiki/wikibuild/publish_gate.py).

Success reports `status: published` and advances `publications/latest.json` last.
The immutable receipt is `publications/<release-id>.json`.
Timing lands in `.local/runs/wiki-publish-<UTC>-<8 hex>.json`; use `wiki.py timing` from step 3.
On failure or exit 124, follow step 8 before any further publication.

## 7. Verify the 13 sites

From HumanHostWiki, inspect the completed receipt:

```powershell
Get-Content publications/latest.json
$published = Get-Content "publications/$releaseId.json" -Raw | ConvertFrom-Json
$published.repositories.PSObject.Properties | ForEach-Object { $_.Value | Select-Object name, base, main, pages, verified }
```

Success means latest selects the reviewed release and every destination is
verified. Publication already observes the exact pushed Pages commits and checks
public file hashes before selecting the hub. Check the hub plus all 12 topic
sites using the receipt's `base` URLs and the
[repository map](../HumanHostWiki/docs/REPOSITORIES.md). Open each landing page;
check the selected release and version/build, search, historical selection and
cross-topic navigation. Include any allocated storage or successor sites beyond
the 13 logical sites. Browser review creates no timing receipt.
If a site serves the wrong release or bytes, retain evidence and diagnose under
[publication verification](../HumanHostWiki/docs/PUBLICATION.md). Do not declare
success or manually advance the hub. Publishing moves the refs its rehearsal
receipt recorded, so a repeat publish needs a fresh rehearsal against the
post-publication state first.

## 8. Recover failures

- **Stuck Pages build:** inspect the pushed SHA and its newest workflow attempt, not unrelated queued runs. After five continuous minutes queued/waiting/pending with no started job for the same run ID/attempt, the tool makes one successor commit with the same tree and the stuck commit as parent. It pushes with a lease expecting the stuck SHA. Check the journal's transition, live ref and successor build. The original 30-minute deadline still applies. A second stuck attempt fails. Do not cancel/delete runs or manufacture another successor manually.
- **Building with a failed workflow:** after five minutes the adapter checks the matching deployment workflow and reruns a failed attempt at most three times. A fourth failure stops with its link. Missing builds and unknown observations do not trigger successor recovery. See [stuck builds](../HumanHostWiki/docs/PUBLICATION.md#stuck-pages-builds).
- **Timeout:** capture is bounded at 14400 seconds, the wrapper's wiki handoff at 15000, and wiki update/publish at 14400. GitHub API calls have 120 seconds, pushes 600, Pages waits 1800 and Steam metadata 300. Inspect timing, errors, owned child PIDs and lock-owner diagnostics. Rerun a repaired local update; abandon a failed publication. See [watchdog cleanup](../HumanHostWiki/docs/PIPELINE.md#run-timing-schema).
- **Pending publication:** never resume or salvage a failed attempt. From HumanHostWiki run:

  ```powershell
  py -3 wiki.py abandon-publication
  ```

  Success archives the journal and invalidates its rehearsals under `.local/publication/abandoned/` without remote calls. It creates no run timing receipt. It preserves completed selected publication history. If abandonment fails, resolve the local error before proceeding. Rehearse against current live state and publish afresh; rollback belongs only to the failing invocation. See [abandonment](../HumanHostWiki/docs/PUBLICATION.md#durable-state-and-abandonment).
- **Interrupted capture:** first confirm the old process has exited. Rerun the full capture command in step 2. Its journal rolls back recognized incomplete swaps or retains the exact completed commit. Never delete a live journal/backup. If recovery reports ambiguity, stop and inspect the reported output, staging and backup identities. Scrap only the proven incomplete capture, preserve the valid baseline and rerun; do not transplant guessed files or commits. No automated abandonment flag exists. See [capture recovery](GAME_CODEBASE.md#comparisons-failure-recovery-and-validation).

## 9. Leave a finished workspace

From HumanHostWiki, check local operational state:

```powershell
py -3 wiki.py status
git status --short
git -C $mods status --short
Get-ChildItem .local/publication, .local/releases, .local/reader-retention -ErrorAction SilentlyContinue
Get-Content .local/publication/pending.json, .local/releases/pending.json -ErrorAction SilentlyContinue
Get-Content .local/writer.lock.owner.json, .local/publication/rehearsal-temp.json -ErrorAction SilentlyContinue
Get-ChildItem ../HumanHostCodebase.catalog-* -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^(python|py|pwsh|ilspycmd|steamcmd|git|gh)(\.exe)?$' } | Select-Object ProcessId, ParentProcessId, CommandLine
```

No incomplete release/publication transaction, active writer, preview server,
owned child process or rehearsal temp root may remain. A saved publication
journal with `phase: complete` is completion evidence, not pending work. Persistent
OS lock files are normal; do not delete them to bypass a writer. Confirm any
reported process belongs to this run before stopping it. Both Git status checks
must be empty, or every listed change must belong to reviewed work that still
has to land through a pull request.

Check the capture's reported sibling `.catalog-stage`, `.catalog-backup` and `.catalog-journal.json` paths.
Resolve leftover capture temporaries, rehearsal roots and retention links through their owners.
Keep timing receipts, abandoned evidence, small release journals/preparation metadata and immutable reader paths.
These are retained records, not stray temp folders. Retention reports must have no unresolved cleanup issues.
Unknown or protected files require ownership review, not blanket deletion. See
[retention](../HumanHostWiki/docs/RETENTION.md) and
[workflow recovery](../HumanHostWiki/docs/WORKFLOW.md#failure-and-recovery).
These final read-only checks create no timing receipt.
