"""Review boundary. Model text is data and is never executed."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UntrustedText:
    """Model or repository text that DevPilot will not run."""

    content: str
    executable: bool = False


class ReviewService:
    """Accept model output as untrusted text.

    This service has no command runner. There is no path from model text to a process.
    """

    def accept_model_output(self, output: str) -> UntrustedText:
        """Record model output as data. `executable` is always false."""
        return UntrustedText(content=output, executable=False)
