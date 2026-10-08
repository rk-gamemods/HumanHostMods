# Human Host update diagrams

Invoke `$update-human-host` in this workspace for the manual update cycle. The [skill](../../../.agents/skills/update-human-host/SKILL.md) coordinates the work; the [game-update runbook](../../RUNBOOK-game-update.md) owns commands, recovery and publication requirements.

| Diagram | What it explains | Pinned evidence |
| --- | --- | --- |
| [Update workflow](workflow/workflow.html) | Capture, parallel Expanded Hordes review, source repairs and gated wiki publication | HumanHostMods `0f2a8bbb4f0c31ea988f4f2e649917c6ef5713ca` |
| [Source lineage](lineage/lineage.html) | Local source, explicit extraction, identity history, reviewed corrections, release pins and public reader | HumanHostWiki `15bf651e8b7b9641013a869d9c2517ab0d0e6b40` |

Each diagram includes verified repository-relative source locations. The source links remain local because these are private workspace contracts. No game source or raw catalog is embedded. The diagrams describe the process, not the success of a particular game update.

Both artifacts passed Archify showcase finalization, strict artifact checks and automated browser checks with zero errors or warnings. Browser checks covered light mode at 1440×900, 1600×1000, 1920×1080 and 2048×1320, plus dark mode at both endpoints. The final light/dark captures at both endpoints were visually inspected for labels, routes, legend fit and clipping. Native T3 browser checks also exercised node focus, pinned source passports and passport closure.

Current evidence is in [workflow/review-2](workflow/review-2/workflow.finalize-summary.json) and [lineage/review-3](lineage/review-3/lineage.finalize-summary.json). Their contact sheets are [workflow](workflow/review-2/workflow.visual-check.html) and [lineage](lineage/review-3/lineage.visual-check.html). [Visual review](visual-review.json) binds the inspected artifacts and distinguishes perceptual review from automated checks.

To revise a diagram, edit its `candidate.json`, inspect the owning committed contracts and update its repository pin when those contracts change. Follow the installed Archify skill's repository-backed `finalize` command with the correct repository root. Use a fresh evidence directory after changing a delivered candidate, then inspect the resulting captures before renewing the visual-review record.
