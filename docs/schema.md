# SQLite schema

Alembic revisions `0001_initial`, `0002_selections`, `0003_review_engine`, `0004_quality_checks`, and `0005_release_readiness` create the tables below. The application applies them on startup. The database file is `data/devpilot.db` unless `DEVPILOT_DATABASE_URL` points at another local SQLite file. The file mode is `0600`.

## projects

A registered local Git working tree. `path` is unique and absolute. The current branch and diffs are read from Git when the page loads. They are not copied into this table.

## review_file_selections

The files a user chose for a later review. The primary key is `project_id` plus `path`. Saving a selection replaces the previous rows for that project. Deleting the project deletes the selection. Phase 1 does not create a review from these rows.

## reviews

One review run. `status` is `pending`, `running`, `completed`, `failed`, or `cancelled`. `error_code` is a short code, not a model response. `model_name`, `context_length`, `temperature`, `max_output_tokens`, `timeout_seconds`, and `keep_alive` record the local configuration used for that run. `summary`, `limitations_json`, `reviewed_json`, and `skipped_json` describe the scope. They do not contain the complete diff, the prompt, or the raw model response. A review that is still `running` when the process starts is marked `failed` with `error_code` `interrupted`.

## review_findings

A finding stored after a future review. The database rejects:

- confidence outside 0 to 1
- `end_line` before `start_line`
- confidence below 0.5 when `uncertain` is false
- a finding whose review does not exist

`validation_status` stays `uncertain` for a model finding. `evidence` is a short quote that was present in the reviewed chunk. `remediation` is the model's suggestion. `verification` is `grounded` when the quote and line range matched the chunk. The API still reports `needs_human_verification: true`, because a grounded quote is not a confirmed defect and it is not a test result.

## quality_commands

The argument list saved for one repository and one tool (`phpcs`, `phpstan`, `phpunit`, `composer`, or `magento`). The primary key is `project_id` plus `tool`. `argv_json` is a JSON list of strings. Deleting the project deletes the command.

## quality_check_runs

One confirmed check, or a skipped check whose tool was missing. `status` remains `pending`, `running`, `completed`, `failed`, or `cancelled`. `result` is `pass`, `fail`, `skipped`, or `timed_out`. `command_display` is the exact argument list in display form. `working_directory` is the registered repository. `started_at`, `finished_at`, and `duration_ms` record the run. `exit_code` is null when the command was skipped or timed out. `stdout` and `stderr` are capped. `output_truncated` records that cap. `note` is a short summary of at most 500 characters. `review_id` is optional and must refer to a review of the same project. A row left `running` when the process starts is marked `failed` and is not executed again.

## release_reports

One stored assessment. `status` stays `draft` when DevPilot generates the row. `readiness` is `blocked`, `needs_review`, or `ready_for_human_approval`. `report_json` and `report_markdown` are the snapshot that the export routes return. `head_sha` is the commit recorded on the review. `repository_head_sha` is the repository HEAD at generation time. `model_name` is the model name stored on that review. Generating a report does not set `status` to `ready`.

## finding_decisions

A person's disposition of one finding: `dismissed`, `confirmed`, or `waived`. `reason` and `reviewer_label` are required before a critical waiver or a critical dismissal is stored. The primary key is `finding_id`. Deleting the finding deletes the decision. This table does not change `review_findings.validation_status`.

## release_checklist_decisions

A person's status for one checklist item on one review. The primary key is `review_id` plus `item_key`. `status` is `pending`, `passed`, `failed`, `waived`, or `not_applicable`. `reason` and `reviewer_label` are required for `passed`, `waived`, and `not_applicable`.

## app_settings

JSON values for the editable model settings: `model_name`, `context_length`, `temperature`, `max_output_tokens`, `timeout_seconds`, `ollama_endpoint`, and `large_model_confirmed`. Keys outside that set are ignored and are not returned by the API. Invalid stored values stop startup instead of falling back to a hosted model.

Registering a repository inserts a `projects` row. Saving a file selection inserts `review_file_selections` rows. Starting a review inserts `reviews` and, when findings pass the evidence check, `review_findings`. Saving a quality command inserts `quality_commands`. Confirming a run inserts `quality_check_runs`. Saving a finding or checklist decision inserts `finding_decisions` or `release_checklist_decisions`. Saving a release report inserts `release_reports` with `status` `draft`.
