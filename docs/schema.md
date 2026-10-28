# SQLite schema

Alembic revisions `0001_initial` and `0002_selections` create the tables below. The application applies them on startup. The database file is `data/devpilot.db` unless `DEVPILOT_DATABASE_URL` points at another local SQLite file. The file mode is `0600`.

## projects

A registered local Git working tree. `path` is unique and absolute. The current branch and diffs are read from Git when the page loads. They are not copied into this table.

## review_file_selections

The files a user chose for a later review. The primary key is `project_id` plus `path`. Saving a selection replaces the previous rows for that project. Deleting the project deletes the selection. Phase 1 does not create a review from these rows.

## reviews

One review run. `status` is `pending`, `running`, `completed`, `failed`, or `cancelled`. `error_code` is a short code, not a model response. `model_name` records the local model used for that run.

## review_findings

A finding stored after a future review. The database rejects:

- confidence outside 0 to 1
- `end_line` before `start_line`
- confidence below 0.5 when `uncertain` is false
- a finding whose review does not exist

`validation_status` defaults to `uncertain`. A finding is not treated as confirmed unless a later phase marks it `accepted`.

## quality_check_runs

A future quality-check run tied to a project. `note` is limited to 500 characters.

## release_reports

A future release report. `status` is `draft`, `ready`, or `archived`.

## app_settings

JSON values for the editable model settings: `model_name`, `context_length`, `temperature`, `max_output_tokens`, `timeout_seconds`, `ollama_endpoint`, and `large_model_confirmed`. Keys outside that set are ignored and are not returned by the API. Invalid stored values stop startup instead of falling back to a hosted model.

Registering a repository inserts a `projects` row. Saving a file selection inserts `review_file_selections` rows. Reviews, findings, quality checks, and release reports are still not inserted.
