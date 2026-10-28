"""Read-only git inspection boundary.

Phase 0 validates command lists and does not run them. Nothing in the API calls
this service automatically.
"""

from app.services.command_policy import validate_git_argv


class RepositoryService:
    def __init__(self) -> None:
        self.executions = 0

    def prepare(self, argv: list[str]) -> list[str]:
        """Validate a git command. The execution counter stays at zero."""
        return validate_git_argv(argv)
