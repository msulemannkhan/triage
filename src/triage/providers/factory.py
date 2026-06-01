"""Provider selection. Defaults to the key-less heuristic LLM + fake transcriber,
so the whole app runs with no credentials; the real OpenAI/Deepgram providers are
selected only when explicitly configured *and* a key is present. The chosen LLM is
wrapped in ``ResilientLLMProvider`` so any failure degrades gracefully. Real
providers are imported lazily so their SDKs aren't touched in the key-less path.
"""

from triage.core.config import Settings
from triage.providers.llm.base import LLMProvider
from triage.providers.llm.heuristic import HeuristicLLMProvider
from triage.providers.llm.resilient import ResilientLLMProvider
from triage.providers.transcription.base import Transcriber
from triage.providers.transcription.fake import FakeTranscriber


def make_llm_provider(settings: Settings) -> ResilientLLMProvider:
    inner: LLMProvider
    if settings.llm_provider == "openai" and settings.openai_api_key:
        from triage.providers.llm.openai import OpenAIProvider

        inner = OpenAIProvider(settings.openai_api_key, settings.openai_model)
    else:
        inner = HeuristicLLMProvider()
    return ResilientLLMProvider(inner)


def make_transcriber(settings: Settings) -> Transcriber:
    if settings.transcriber == "deepgram" and settings.deepgram_api_key:
        from triage.providers.transcription.deepgram import DeepgramTranscriber

        return DeepgramTranscriber(settings.deepgram_api_key, settings.deepgram_model)
    return FakeTranscriber()
