"""The transcription interface. The real implementation lands at M11; the
deterministic fake is used everywhere in tests and key-less local dev."""

from abc import ABC, abstractmethod


class Transcriber(ABC):
    @abstractmethod
    async def transcribe(self, audio: bytes) -> str:
        """Transcribe audio bytes to text, to feed the same pipeline as typed input."""
