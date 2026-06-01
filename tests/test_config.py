"""M0 smoke: the package imports and settings load with sane defaults."""

from triage.core.config import get_settings


def test_settings_load_with_defaults():
    settings = get_settings()
    assert settings.clarification_cap == 2
    assert settings.clarification_cap_sensitive == 1
    assert settings.openai_model == "gpt-5.4-mini"
    assert settings.deepgram_model == "nova-3"


def test_settings_are_cached():
    assert get_settings() is get_settings()
