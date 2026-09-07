"""Tests for secret redaction helpers."""

from agentos.onboarding.redaction import (
    REDACTED_PLACEHOLDER,
    redact_channel_entry,
    redact_memory_embedding_payload,
    redact_provider_payload,
)


def test_provider_api_key_is_redacted():
    out = redact_provider_payload({"api_key": "sk-secret", "model": "x"})
    assert out["api_key"] == REDACTED_PLACEHOLDER
    assert out["model"] == "x"


def test_empty_api_key_redacts_to_empty_string():
    out = redact_provider_payload({"api_key": "", "model": "x"})
    assert out["api_key"] == ""


def test_memory_embedding_remote_key_is_redacted():
    out = redact_memory_embedding_payload(
        {"provider": "openai", "remote": {"api_key": "mem-secret"}}
    )
    assert out["remote"]["api_key"] == REDACTED_PLACEHOLDER


def test_telegram_secrets_are_redacted():
    out = redact_channel_entry(
        "telegram",
        {"name": "tg", "token": "abcd", "webhook_secret_token": "wxyz"},
    )
    assert out["token"] == REDACTED_PLACEHOLDER
    assert out["webhook_secret_token"] == REDACTED_PLACEHOLDER
    assert out["name"] == "tg"


def test_unknown_channel_type_redacts_everything_but_common_fields():
    """Fail closed for a channel type the onboarding catalog doesn't know:
    the catalog not listing secret fields for it doesn't mean it has none —
    see the msteams case below, a real channel hidden from that catalog."""
    payload = {"name": "x", "type": "not-a-type", "enabled": True, "token": "y"}
    out = redact_channel_entry("not-a-type", payload)
    assert out == {"name": "x", "type": "not-a-type", "enabled": True}
    assert "token" not in out


def test_msteams_app_password_is_redacted_though_hidden_from_catalog():
    """Regression test: msteams is a real, constructible channel entry
    (channels/msteams.py, gateway/config.py) with a secret app_password
    field, but it is intentionally absent from the onboarding setup-spec
    catalog (channel_specs.py) that redact_channel_entry used to rely on
    exclusively. Before this fix, that made its secret leak unredacted
    through list_channel_entries / upsert_channel's public_payload."""
    payload = {
        "name": "teams",
        "type": "msteams",
        "enabled": True,
        "app_id": "app-123",
        "app_password": "super-secret",
    }
    out = redact_channel_entry("msteams", payload)
    assert "app_password" not in out
    assert "app_id" not in out
    assert out == {"name": "teams", "type": "msteams", "enabled": True}


def test_input_dict_is_not_mutated():
    src = {"api_key": "s", "model": "m"}
    out = redact_provider_payload(src)
    assert src["api_key"] == "s"
    assert out["api_key"] == REDACTED_PLACEHOLDER
