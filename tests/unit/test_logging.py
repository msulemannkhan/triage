"""M12: PII redaction in the structured-logging processor."""

from triage.core.logging import _redact_pii, configure_logging


def test_redacts_email_phone_and_card():
    event = {
        "event": "turn",
        "blob": "reach me at a.user@example.com or 555-123-4567; card 4111111111111111",
    }
    out = _redact_pii(None, "info", event)
    assert "a.user@example.com" not in out["blob"]
    assert "555-123-4567" not in out["blob"]
    assert "4111111111111111" not in out["blob"]
    assert "[redacted-email]" in out["blob"]
    assert "[redacted-phone]" in out["blob"]
    assert "[redacted-card]" in out["blob"]


def test_non_string_values_are_left_alone():
    event = {"event": "turn", "count": 3, "ok": True}
    out = _redact_pii(None, "info", event)
    assert out["count"] == 3 and out["ok"] is True


def test_redacts_pii_nested_in_dicts_and_lists():
    event = {
        "event": "turn",
        "payload": {"contact": "a.user@example.com", "tags": ["ok", "call 555-123-4567"]},
    }
    out = _redact_pii(None, "info", event)
    assert out["payload"]["contact"] == "[redacted-email]"
    assert "[redacted-phone]" in out["payload"]["tags"][1]


def test_configure_logging_is_idempotent():
    configure_logging()
    configure_logging()  # no error on re-configure
