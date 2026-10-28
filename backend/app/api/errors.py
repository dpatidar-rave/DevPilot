"""Error bodies that do not echo request values or stack traces."""

from collections.abc import Sequence
from typing import Protocol

from pydantic import ValidationError


class _ErrorList(Protocol):
    def errors(self) -> Sequence[object]:
        """Validation errors with loc and msg keys."""


def validation_body(exc: ValidationError | _ErrorList) -> dict[str, object]:
    errors: list[dict[str, str]] = []
    for error in exc.errors():
        if not isinstance(error, dict):
            continue
        location = error.get("loc", ())
        parts: list[str] = []
        if isinstance(location, Sequence) and not isinstance(location, str):
            parts = [str(part) for part in location if part not in {"body", "query", "path"}]
        field = ".".join(parts) if parts else "settings"
        if field == "model_name":
            field = "model"
        message = str(error.get("msg", "Invalid value."))
        prefix = "Value error, "
        if message.startswith(prefix):
            message = message[len(prefix) :]
        errors.append({"field": field, "message": message})
    return {"detail": "Settings were rejected.", "errors": errors}
