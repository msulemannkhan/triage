"""M11/M12: provider selection. Key-less defaults to heuristic/fake; the real
providers are chosen only when configured with a key (construction only — no
network). The LLM is always wrapped for graceful degradation."""

from triage.core.config import Settings
from triage.providers.factory import make_llm_provider, make_transcriber
from triage.providers.llm.heuristic import HeuristicLLMProvider
from triage.providers.llm.resilient import ResilientLLMProvider
from triage.providers.transcription.fake import FakeTranscriber


def test_keyless_defaults_to_heuristic_wrapped_and_fake():
    settings = Settings(llm_provider="heuristic", transcriber="fake")
    provider = make_llm_provider(settings)
    assert isinstance(provider, ResilientLLMProvider)
    assert isinstance(provider._inner, HeuristicLLMProvider)
    assert isinstance(make_transcriber(settings), FakeTranscriber)


def test_openai_not_selected_without_a_key():
    provider = make_llm_provider(Settings(llm_provider="openai", openai_api_key=""))
    assert isinstance(provider._inner, HeuristicLLMProvider)


def test_openai_selected_when_configured_with_a_key():
    from triage.providers.llm.openai import OpenAIProvider

    provider = make_llm_provider(Settings(llm_provider="openai", openai_api_key="sk-test"))
    assert isinstance(provider._inner, OpenAIProvider)


def test_deepgram_selected_when_configured_with_a_key():
    from triage.providers.transcription.deepgram import DeepgramTranscriber

    settings = Settings(transcriber="deepgram", deepgram_api_key="dg-test")
    assert isinstance(make_transcriber(settings), DeepgramTranscriber)
