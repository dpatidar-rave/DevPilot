# Quality checks

Phase 3 runs project commands that you configure and confirm. A result is the command's exit status. It is not an AI suggestion, and a review does not start one.

DevPilot does not assume a PHP version, a Magento version, or a directory layout. It looks for known configuration files and tool paths in the registered repository. A suggestion appears only when the interpreter and the project file are both present. You can replace that suggestion with another allowlisted argument list for that repository.

## What you confirm

Open `http://127.0.0.1:5173/quality`. Choose a repository. Each check shows the files that were found, one argument per line, and the saved command. **Save command** does not run it. **Run saved command** stays disabled until you check **I confirm this run** for that execution. Editing the arguments requires another save, and the confirmation is cleared after each run.

The page shows the exact command, working directory, start time, duration, exit status, standard output, and error output. The status is pass, fail, skipped, or timed out. A skipped row means the interpreter or the project tool was not available, so no process was started.

You can attach a result to a review from the same repository. The review page lists those rows separately from AI suggestions.

Approved project scripts can still have side effects. PHPUnit and the Magento CLI can write files or bootstrap the application. DevPilot does not install Composer packages, change project configuration, or run deployment commands.

## Allowlist

The saved value is an argument list, not a shell string. The process is started with `shell=False`. A command from model output is not accepted. These shapes are allowed:

| Check | Command |
| --- | --- |
| PHP_CodeSniffer | `php` and `vendor/bin/phpcs`, plus paths inside the repository |
| PHPStan | `php` and `vendor/bin/phpstan`, with `analyse`, `list`, or `--version` |
| PHPUnit | `php` and `vendor/bin/phpunit` |
| Composer validation | `composer validate` with `--no-check-publish` and `--no-check-all`, or `composer check-platform-reqs` |
| Magento project check | `php` and `bin/magento`, with `--version` or `module:status` |

`php` and `composer` are resolved from `PATH` outside the repository. A `vendor/bin` tool may be the normal Composer symlink when its target stays inside the repository. A symlink that leaves the repository is rejected. The working directory is the registered root. A path argument cannot be absolute or contain `..`.

`composer install`, `update`, `require`, `config`, and `run-script` are rejected. `phpcbf` is rejected. Magento `setup:upgrade`, `setup:di:compile`, `setup:static-content:deploy`, cache flush, indexer reindex, and module enable or disable are rejected. PHP interpreter switches such as `-r` and `-d` are rejected.

Each run has a time limit: 60 seconds for Composer, 120 seconds for Magento, and 180 seconds for PHP_CodeSniffer, PHPStan, and PHPUnit. Output is kept up to 64 KiB per stream. A longer stream is marked truncated. A timeout stops the process.

Registration and an AI review do not start these commands. Detection only stats known filenames. It does not read `.env` or `app/etc/env.php`, and it does not install packages.

## Tests

```bash
backend/.venv/bin/pytest backend/tests/test_quality_checks.py
```

The tests use a temporary Git repository. They cover the allowlist, path arguments, a timeout, oversized output, a nonzero exit, and a command that would leave the repository.
