"""Errors for local inference. Messages stay free of source text."""


class ModelPolicyError(Exception):
    """The configured model or endpoint is not allowed."""


class ModelMissingError(Exception):
    """The selected local model is not installed. Nothing was downloaded."""

    def __init__(self, setup_instruction: str) -> None:
        super().__init__(setup_instruction)
        self.setup_instruction = setup_instruction


class InferenceBusy(Exception):
    """Another local inference request is already running."""


class InferenceCancelled(Exception):
    """The user cancelled the local inference request."""


class InferenceTimeout(Exception):
    """The local inference request exceeded the configured timeout."""


class LocalModelUnavailable(Exception):
    """The local model daemon could not be used."""

    def __init__(self, message: str, retry: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.retry = tuple(retry)
