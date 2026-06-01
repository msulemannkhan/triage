"""A deterministic transcriber that returns a preset transcript."""

from .base import Transcriber


class FakeTranscriber(Transcriber):
    def __init__(self, transcript: str = "") -> None:
        self._transcript = transcript

    async def transcribe(self, audio: bytes) -> str:
        return self._transcript
