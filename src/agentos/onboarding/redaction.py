"""Secret-aware redaction helpers used by mutations, RPC, and CLI output."""

from __future__ import annotations

from typing import Any

from agentos.onboarding.channel_specs import get_channel_setup_spec

REDACTED_PLACEHOLDER = "***"

_PROVIDER_SECRET_FIELDS = frozenset({"api_key"})

# Metadata fields common to every channel entry model (see
# ``channels.registry._COMMON_ENTRY_FIELDS``), never secret. Used as the
# fail-closed allowlist below for channel types the onboarding catalog
# doesn't know about (e.g. "msteams", which is hidden from the catalog per
# channel_specs.py but is still a real, constructible channel entry with a
# secret ``app_password`` field).
_ALWAYS_SAFE_ENTRY_FIELDS = frozenset({"name", "type", "enabled", "agent_id"})


def redact_provider_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    for key in _PROVIDER_SECRET_FIELDS:
        if key in out and out[key]:
            out[key] = REDACTED_PLACEHOLDER
    return out


def redact_search_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    if out.get("api_key"):
        out["api_key"] = REDACTED_PLACEHOLDER
    return out


def redact_x_search_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    if out.get("api_key"):
        out["api_key"] = REDACTED_PLACEHOLDER
    return out


def redact_image_generation_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    if out.get("api_key"):
        out["api_key"] = REDACTED_PLACEHOLDER
    return out


def redact_audio_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    if out.get("api_key"):
        out["api_key"] = REDACTED_PLACEHOLDER
    return out


def redact_memory_embedding_payload(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    if out.get("api_key"):
        out["api_key"] = REDACTED_PLACEHOLDER
    remote = out.get("remote")
    if isinstance(remote, dict) and remote.get("api_key"):
        remote = dict(remote)
        remote["api_key"] = REDACTED_PLACEHOLDER
        out["remote"] = remote
    return out


def redact_channel_entry(type_name: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        spec = get_channel_setup_spec(type_name)
    except KeyError:
        # Unknown to the onboarding catalog — fail closed rather than echo
        # the raw entry. A channel type can be a real, constructible entry
        # (e.g. a hidden-but-supported adapter, or a legacy type retained in
        # an existing config) without appearing in the catalog this function
        # otherwise relies on for its list of secret field names, so we
        # can't assume "not in the catalog" means "has no secrets."
        return {
            key: value
            for key, value in payload.items()
            if key in _ALWAYS_SAFE_ENTRY_FIELDS
        }
    secret_names = {f.name for f in spec.fields if f.secret}
    out = dict(payload)
    for key in secret_names:
        if key in out and out[key]:
            out[key] = REDACTED_PLACEHOLDER
    return out
