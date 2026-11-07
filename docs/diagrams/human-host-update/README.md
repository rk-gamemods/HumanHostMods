# Human Host update diagrams

Invoke `$update-human-host` in this workspace for the manual update cycle. The [skill](../../../.agents/skills/update-human-host/SKILL.md) coordinates the work; the [game-update runbook](../../RUNBOOK-game-update.md) owns commands, recovery and publication requirements.

| Diagram | What it explains | Pinned evidence |
| --- | --- | --- |
| [Update workflow](workflow/workflow.html) | Capture, fast source/identity precheck, parallel Expanded Hordes review and gated wiki publication | HumanHostMods `531ee4efb2dea068c3da09881b8af95502f9af18` |
| [Source lineage](lineage/lineage.html) | Local source, explicit extraction, early source review, identity history, release pins and public reader | HumanHostWiki `8e23a499d51389a016d5817af88f2b7378b8aa08` |

Each diagram includes verified repository-relative source locations. The source links remain local because these are private workspace contracts. No game source or raw catalog is embedded. The diagrams describe the process, not the success of a particular game update.

Both artifacts passed Archify showcase finalization, strict artifact checks and automated browser checks with zero errors or warnings. Fresh light/dark captures at 1440×900 and 2048×1320 were visually inspected for labels, routes, legend fit and clipping. The retained three-bend receipt-to-extraction route remains clear. These diagram checks are separate from the native T3 browser review of the generated wiki.

Current evidence is in [workflow/review-3](workflow/review-3/workflow.finalize-summary.json) and [lineage/review-5](lineage/review-5/lineage.finalize-summary.json). Their contact sheets are [workflow](workflow/review-3/workflow.visual-check.html) and [lineage](lineage/review-5/lineage.visual-check.html). [Visual review](visual-review.json) binds the inspected artifacts and distinguishes perceptual review from automated checks. Earlier receipts remain as history, including the rejected first route for the new source-review branch.

To revise a diagram, edit its `candidate.json`, inspect the owning committed contracts and update its repository pin when those contracts change. Follow the installed Archify skill's repository-backed `finalize` command with the correct repository root. Use a fresh evidence directory after changing a delivered candidate, then inspect the resulting captures before renewing the visual-review record.
