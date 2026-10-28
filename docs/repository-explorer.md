# Repository explorer

Phase 1 registers a local Git working tree and shows its status and diffs. It does not start a review, call Ollama, or modify the repository.

## What you can do

1. Open `http://127.0.0.1:5173/repositories`.
2. Paste an absolute path, or move through local folders and choose **Register this folder**.
3. DevPilot checks that the path is the root of a Git working tree whose `.git` entry is a real directory inside that folder.
4. The name, path, and registration time are stored in the local SQLite database.
5. Open the repository to see the current branch, detached-HEAD state, latest commit, local branches, and whether the tree is dirty.
6. Choose a base branch. The page separates:
   - staged changes
   - unstaged changes
   - commits that are on `HEAD` and not in the base branch
   - untracked files
7. Open a file to read its diff. Added lines are marked `+` and deleted lines are marked `−`, with syntax highlighting for common Magento file types.
8. Check the files that should be included in a later review and choose **Save review selection**. This build does not start the review.

A dirty working tree shows a warning. DevPilot still does not commit, discard, reset, or switch branches.

## Magento detection

A project is reported as Magento only when both `composer.json` and `app/etc/di.xml` are present and `composer.json` requires a `magento/` package. The edition is Adobe Commerce or Magento Open Source only when the product package name says so.

The Magento version is shown only when `composer.lock` or an exact `composer.json` constraint contains a concrete version such as `2.4.7-p3`. A range such as `^2.4` is not shown as the version. PHP is shown only when `composer.lock` records an exact platform version such as `8.2.27`.

## What is not read

The diff viewer does not load:

- `vendor/`, `generated/`, `var/`, `node_modules/`, `pub/static/`, `pub/media/`, and Magento integration temp directories
- `.env`, `.env.*`, `auth.json`, `app/etc/env.php`, private keys, and other credential-shaped filenames

Those paths can still appear in the list, marked as not loaded. Git hooks, external diff commands, and repository aliases are not executed. Commands are argument lists, and every Git command is pinned to the registered work tree.

## Manual test

Use a temporary repository. Do not point this test at a client project.

```bash
tmpdir=$(mktemp -d)
git init -b main "$tmpdir"
printf '<?php\n' > "$tmpdir/base.php"
git -C "$tmpdir" add base.php
git -C "$tmpdir" -c user.name='DevPilot Test' -c user.email='devpilot@localhost' commit -m base
printf '<?php\nchanged\n' > "$tmpdir/base.php"
printf '<?php\nnew\n' > "$tmpdir/untracked.php"
```

Start DevPilot with `scripts/start.sh` if it is not already running. Register `$tmpdir` in the UI.

Expect the branch `main`, an uncommitted-changes warning, `base.php` under unstaged changes, and `untracked.php` under untracked files. Open `base.php` and confirm the deleted and added lines. Select `base.php`, save the selection, and reload the page. The selection should still be checked. The temporary folder's `HEAD` and file contents should be unchanged.

Remove the temporary folder when you are finished: `rm -rf "$tmpdir"`.

## Automated tests

From the repository root:

```bash
backend/.venv/bin/pytest backend/tests/test_repository_explorer.py
cd frontend && npm test
```

The backend tests create temporary Git repositories. They cover a missing path, a non-Git directory, a `.git` file, detached HEAD, staged changes, unstaged changes, untracked files, and unusual filenames.
