---
name: update-human-host
description: Manually coordinate an installed Human Host game update through capture, source reconciliation, wiki validation and publication, with parallel Expanded Hordes compatibility review.
---

# UpdateHumanHost

Use `$update-human-host` from HumanHostMods to request this cycle. A host may expose skills in its slash-command picker; `/UpdateHumanHost` is not a portable command. The display name is UpdateHumanHost.

The [game-update runbook](../../../docs/RUNBOOK-game-update.md) owns the procedure and commands. Read it, the workspace instructions and the wiki's instructions before starting. This skill coordinates supervised work; it adds no scheduler or automatic LLM stage to the pipeline. Honor any narrower scope in the invocation, including local-only work or a review boundary.

## Run the cycle

1. Resolve outstanding state in each repository that will participate. Record the prior successful capture commit, installed build and published release. Capture the operation's intent and final outcome through the applicable Open Brain workflow.
2. Follow the runbook's input freeze and reader preflight before generation. Follow runbook detection and the full `pwsh -NoProfile -File tools/Decompile-GameCode.ps1` entrypoint. Its successful capture already invokes the local wiki update, including when inputs are unchanged. Do not repeat that update merely to advance to review. Use the runbook's recovery path if capture or the wiki handoff fails, and audit the captured game version against the configured installation.
3. As soon as a successful capture and its exact before/after diff exist, delegate the Expanded Hordes review below. Continue wiki work independently; the shared decompiled snapshot is read-only evidence for both branches.
4. Review every reported content, identity, extraction and article exception, including records detached from their prior sources. Compare the pinned source and prior capture, determine whether each case is an actual removal, identifier change, unsupported field or defective mapping, and repair its owning rule or reviewed correction. Preserve legitimate historical absence and explicit uncertainty. Do not suppress warnings, invent references or turn unknown gameplay behavior into a verified claim to obtain an empty report. Revalidate affected articles and links as well as regenerated facts. Own corrections in the umbrella or topic repository prescribed by the runbook, then regenerate through the supported pipeline.
   The normal update stops at its fast source/identity precheck when input review is required (exit 3). Repair the owning rules, then use `py -3 wiki.py precheck --operator-report` until `inputs-ready`, before starting reader/release work. This uses the normal stage caches and adds no duplicate extraction pass. Keep article and reader validation in the full update.
5. Complete the runbook's release review, required tests and independent source/reader/release checks. Exercise an unchanged repeat; when generation changes, prove failure before promotion preserves the previous snapshot or selected release. Inspect the selected release in the browser, including version/build, history, search, provenance and cross-topic navigation. Resolve reproducible failures before publication and report any evidence limit accurately.
6. When publication is in scope, complete review and merge of wiki changes, exact-commit CI, a fresh live-state rehearsal and the separate publish command. Follow every production gate. Abandon failed publication attempts through the supported command before a new rehearsal. Verify the publication receipt and visually inspect all current destination sites, then complete retention and clean-state checks.

## Parallel Expanded Hordes review

Use the standalone public repository identified by the workspace glossary and read its nearest instructions. Give the reviewer both capture commits and the complete changed-path list. Review all changed game code, direct patch targets and relevant callers/configuration for actual or possible mod impact; do not infer compatibility from a successful compilation alone.

Decide whether the current mod has a defect or an unmet requirement within the user's scope before editing it. Name the failing behavior, supporting evidence and useful change required. If the review finds no required change, leave the mod repository and version unchanged. Record the inspected boundaries, checks and limitations in the parent update report and Open Brain. Do not manufacture a documentation-only mod PR, compatibility commit or release preparation just to record a successful review. A mod documentation update requires a specific user request or a concrete documentation defect necessary to complete the task.

Trace existing work through the integration commits and published payload before calling it unfinished. Historical features, old branches and differing version labels alone do not establish a new defect or a release requirement. Complete actual unfinished work within the user's authorization; remove only verified abandoned, task-owned leftovers. Preserve completed, accepted implementation. Do not present older completed changes as additional fixes discovered by this game update.

Build and test the one intended current mod revision against the captured game. Use older revisions as read-only comparison evidence. An additional revision build needs a specific diagnostic reason, such as isolating a reproduced regression; a version-label discrepancy alone is insufficient.

When a useful change is required, apply only that evidenced change. Follow the mod repository's build, tests and runtime-validation requirements, keeping game source and private workspace material out of public commits. Prepare and push a regular ready-for-review PR targeting `develop`, identifying the defect or unmet requirement it resolves. Keep it pending the user's review and merge only after that review authorizes integration. Do not advance `main`, make a release or publish to Steam Workshop without the user's authorization for that release work. If no change is needed, finish the mod review with the finding and its evidence.

## Keep the cycle small and measured

Use existing capture receipts and `wiki.py timing` to identify expensive phases before proposing an optimization. Preserve content-addressed reuse, immutable outputs, writer exclusion and publication gates. Change only a demonstrated defect or a measured bottleneck; keep unrelated prose and configuration intact. Reuse the existing runbook and deterministic commands instead of adding a competing all-in-one script.

For source or documentation discovery, refresh the appropriate Munch index against current files with an explicit set of relevant tracked owner paths. Exclude generated receipts, readers, raw catalogs, nested repositories and `bin`/`obj` outputs from code-index traversal. Keep documentation embeddings disabled unless requested. This avoids walking large generated trees before a small source review.

Reuse one verified preview process per immutable release. Restart it when the selected release or preview-server code changes; do not replace startup byte verification with a housekeeping receipt.

Finish with the capture version/build and commits, selected release and publication result, exception dispositions, tests and visual evidence, mod-review/PR status, timing findings, clean-state status and verified memory ID. Link the [process diagrams](../../../docs/diagrams/human-host-update/README.md); update their repository evidence when the documented flow changes.
