"""Review orchestration.

This service depends on the InferenceClient protocol. Swapping the local model
does not require a change here. Phase 0 does not start a review and does not
call the client.
"""

from app.services.model_gateway import InferenceClient
from app.services.persistence import SessionFactory


class ReviewService:
    def __init__(self, inference: InferenceClient, sessions: SessionFactory) -> None:
        self._inference = inference
        self._sessions = sessions

    @property
    def inference(self) -> InferenceClient:
        return self._inference

    @property
    def sessions(self) -> SessionFactory:
        return self._sessions
