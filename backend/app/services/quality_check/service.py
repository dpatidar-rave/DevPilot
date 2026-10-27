"""Catalog of Magento quality checks. Phase 0 does not execute them."""

from __future__ import annotations

from dataclasses import dataclass

from app.security.command_gate import CommandRejected


@dataclass(frozen=True)
class QualityCheck:
    """A check DevPilot knows about. `executed` is false until a later approved run."""

    check_id: str
    description: str
    execution: str
    requires_explicit_approval: bool
    executed: bool


_CHECKS = (
    QualityCheck(
        check_id="phpstan",
        description="PHPStan at the Magento project's configured level.",
        execution="disabled",
        requires_explicit_approval=True,
        executed=False,
    ),
    QualityCheck(
        check_id="phpcs",
        description="PHPCS using the Magento project's coding standard.",
        execution="disabled",
        requires_explicit_approval=True,
        executed=False,
    ),
)


class QualityCheckService:
    """List quality checks and refuse to run them until a runner is deliberately enabled."""

    def list_checks(self) -> list[QualityCheck]:
        """Return the catalog. Listing a check does not run it."""
        return list(_CHECKS)

    def run_check(self, check_id: str, *, approved: bool) -> None:
        """Refuse execution. Approval is required, and no runner is enabled."""
        known = {item.check_id for item in _CHECKS}
        if check_id not in known:
            raise CommandRejected(f"Unknown quality check {check_id!r}. Nothing was executed.")
        if approved is not True:
            raise CommandRejected(
                "Quality checks run only after an explicit user-approved action. "
                "Nothing was executed."
            )
        raise CommandRejected(
            f"The {check_id} check is not enabled. DevPilot did not execute it."
        )
