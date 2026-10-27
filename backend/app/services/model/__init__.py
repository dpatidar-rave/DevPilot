"""Model service. Inference goes through local Ollama only."""

from app.services.model.ollama import OllamaClient, OllamaStatus, OllamaUnavailableError

__all__ = ["OllamaClient", "OllamaStatus", "OllamaUnavailableError"]
