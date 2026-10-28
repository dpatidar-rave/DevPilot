# How to read a release readiness report

DevPilot builds this report from five sources that stay separate:

- AI review findings. These are suggestions. A completed review is evidence that the run finished, not evidence that the change is safe.
- Deterministic quality-check results. A row is a pass, fail, skip, or timeout of a command you confirmed.
- Human decisions on findings. Dismissed, confirmed, or waived, with a reason and a reviewer label when the rules require them.
- The deployment checklist. Ten items, each pending, passed, failed, waived, or not applicable.
- Unresolved risk. Dirty work trees, review limitations, and checks that were skipped.

The reviewer label is an attestation you type. DevPilot has no login and does not verify that name.

Saving a report stores a snapshot. The lifecycle status of that row stays `draft`. DevPilot does not set it to ready. Exporting Markdown or JSON returns that snapshot, so two downloads of the same report match.

## The three readiness values

**Blocked.** Do not ship on this assessment. At least one item below is open. Fix it, or record a valid waiver, and generate the report again.

**Needs review.** Nothing is currently a blocker, and the report is still not clean enough for the ready state. A waiver, a not-applicable item, a warning, or missing evidence puts the report here. Read those sections before you decide.

**Ready for human approval.** Every checklist item is passed, and the report has no blockers, warnings, waivers, or missing evidence. This is the best result the tool can produce. It is the point where a technical lead approves or rejects the release. The report text says that DevPilot has not approved it. A model that returned no findings cannot produce this state by itself, because the deployment checklist and the automated-test result still have to be present.

## What blocks a release

- A critical finding with no decision, a critical finding marked confirmed, or a critical waiver or dismissal that has no reason or reviewer.
- A high-severity finding with no decision, or a high-severity finding marked confirmed. Dismissing it is a disposition. Waiving it requires a reason and a reviewer, and that waiver does not count as a pass.
- A required checklist item that is pending or failed. Pending is missing evidence. It is not a pass.
- A review that is not completed. A failed or cancelled review fails the code-review item.
- PHPUnit failed or timed out. A human "passed" on automated tests is ignored unless PHPUnit itself exited 0.
- No PHPUnit result, or a skipped PHPUnit run. The automated-tests item stays pending.
- PHP_CodeSniffer, PHPStan, Composer validation, or the Magento check failed or timed out. Composer can be waived only with a reason and a reviewer. The other failed checks block until a later run passes.
- The review has no Git commit identifier.

## What a waiver means

A waiver is an explicit acceptance of a risk. The report lists the subject, the reason, and the reviewer. It appears under Waivers, not under Passed checks. A valid waiver removes that item from the blockers and leaves the report at Needs review, so a second person can see what was accepted.

A waiver without a reason or a reviewer is rejected and the item stays a blocker. There is no silent waiver.

Not applicable is the same kind of decision for a checklist item that does not apply to this change. It also needs a reason and a reviewer. It is a warning, not a pass. A failed Composer or PHPUnit result cannot be marked not applicable to hide it.

A dismissed critical finding is not a waiver. It is a warning, with the reason and reviewer, and the report stays at Needs review.

## What the checklist is asking

| Item | What to look for |
| --- | --- |
| Code review completion | The review run completed. A pass recorded by hand does not replace a failed or unfinished run. |
| Critical and high-severity findings | Each finding has its own disposition. One checklist waiver cannot close the group. |
| Automated tests | A PHPUnit result of pass for this review. A missing or skipped run is not a pass. |
| Database schema and data patches | `db_schema.xml`, data patches, and whitelist changes in the reviewed files. Confirm the upgrade path, or record why there is no schema change. |
| Dependency and composer.lock changes | `composer.json` and `composer.lock`. A failed Composer validation fails this item. A passing validation still needs a person to accept the dependency change. |
| Configuration changes | `config.php`, `system.xml`, `config.xml`, crontab, and communication XML. `env.php` and `.env` are not read. |
| Cache and indexer implications | Whether the change needs a cache flush or an indexer run after deploy. The report does not run those commands. |
| API and backward compatibility | Service contracts and web API changes that callers already depend on. |
| Rollback plan | How this change would be reversed if production misbehaves. |
| Deployment and post-deployment verification | The checks that happen during and after the deploy. The report does not deploy. |

Passed checklist items other than the ones derived from the review and from PHPUnit require a reason and a reviewer. A pass with a blank reason is stored as still pending.

## The rest of the page

**Warnings** are open medium findings, a dismissed critical finding, a dirty work tree, or a checklist item marked not applicable. They keep the report at Needs review.

**Missing evidence** is a required item with no passing result, a skipped quality tool, or a limitation recorded by the review. A skipped PHPStan run is not listed as passed. A tool that was never run is also not listed as passed. PHPUnit is the one missing tool that blocks, because automated tests are required.

**Model and review configuration** repeats the model name, context length, temperature, max output, and timeout stored on the review, plus the review id and status. Use it to see which local settings produced the findings.

**Git** shows the base ref, the commit recorded on the review, and the repository HEAD at the moment the report was generated. If those differ, or if the work tree is dirty, the commit id is not the whole tree that would ship.

Regenerate the report after you change a decision or rerun a check. An older snapshot does not update itself.
