"""Ollama adapter behind the inference protocol. Concurrency is fixed at one."""

from __future__ import annotations

import threading

from app.services.model.errors import InferenceBusy, LocalModelUnavailable, ModelMissingError
from app.services.model.inference import InferenceRequest, ModelOptions
from app.services.model.ollama import GenerationSpec, OllamaClient, OllamaUnavailableError
from app.services.model.policy import MAX_CONCURRENT_INFERENCE, assert_local_model_name, setup_instruction


class OllamaInference:
    """Local Ollama implementation of `InferenceClient`."""

    def __init__(self, client: OllamaClient) -> None:
        self._client = client
        self._slots = threading.BoundedSemaphore(MAX_CONCURRENT_INFERENCE)

    def prepare(self, options: ModelOptions) -> None:
        """Check that the selected tag is installed. Does not pull weights."""
        model = assert_local_model_name(options.model)
        if options.endpoint != self._client.base_url:
            raise InferenceBusy("Refusing to call an endpoint other than the configured loopback Ollama.")
        try:
            status = self._client.status()
        except OllamaUnavailableError as exc:
            raise LocalModelUnavailable(str(exc), exc.retry) from exc
        installed = set(status.models)
        if model not in installed:
            raise ModelMissingError(setup_instruction(model))

    def complete(self, request: InferenceRequest, cancel_event: threading.Event) -> str:
        """Run one generation. A second caller is rejected instead of queued."""
        if not self._slots.acquire(blocking=False):
            raise InferenceBusy("Only one local inference request can run at a time.")
        try:
            options = request.options
            return self._client.generate(
                GenerationSpec(
                    model=assert_local_model_name(options.model),
                    prompt=request.prompt,
                    temperature=options.temperature,
                    context_length=options.context_length,
                    max_output_tokens=options.max_output_tokens,
                    timeout_seconds=options.timeout_seconds,
                    keep_alive=options.keep_alive,
                ),
                cancel_event,
            )
        except OllamaUnavailableError as exc:
            raise LocalModelUnavailable(str(exc), exc.retry) from exc
        finally:
            self._slots.release()
