# SQLite schema

Alembic revisions `0001_initial`, `0002_selections`, and `0003_review_engine` create the tables below. The application applies them on startup. The database file is `data/devpilot.db` unless `DEVPILOT_DATABASE_URL` points at another local SQLite file. The file mode is `0600`.

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

## quality_check_runs

A future quality-check run tied to a project. `note` is limited to 500 characters.

## release_reports

A future release report. `status` is `draft`, `ready`, or `archived`.

## app_settings

JSON values for the editable model settings: `model_name`, `context_length`, `temperature`, `max_output_tokens`, `timeout_seconds`, `ollama_endpoint`, and `large_model_confirmed`. Keys outside that set are ignored and are not returned by the API. Invalid stored values stop startup instead of falling back to a hosted model.

Registering a repository inserts a `projects` row. Saving a file selection inserts `review_file_selections` rows. Reviews, findings, quality checks, and release reports are still not inserted.
