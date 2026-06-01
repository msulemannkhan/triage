"""Deepgram nova-3 transcription (the Transcriber seam, SDK v7).

Live-verified only when DEEPGRAM_API_KEY is set; the fake transcriber is the
key-less default. Lazy-imported by the factory so the SDK isn't touched otherwise.
"""

from time import perf_counter

from deepgram import AsyncDeepgramClient

from triage.core.logging import get_logger, ms_since

from .base import Transcriber

_log = get_logger("transcription")


class DeepgramTranscriber(Transcriber):
    def __init__(self, api_key: str, model: str = "nova-3") -> None:
        self._client = AsyncDeepgramClient(api_key=api_key)
        self._model = model

    async def transcribe(self, audio: bytes) -> str:
        start = perf_counter()
        response = await self._client.listen.v1.media.transcribe_file(
            request=audio,
            model=self._model,  # type: ignore[arg-type]  # SDK uses a Literal; model is configurable
            smart_format=True,
        )
        transcript: str = (
            response.results.channels[0].alternatives[0].transcript or ""  # type: ignore[union-attr]
        )
        _log.info(
            "transcribe",
            model=self._model,
            audio_bytes=len(audio),
            transcript_chars=len(transcript),
            duration_ms=ms_since(start),
        )
        return transcript
