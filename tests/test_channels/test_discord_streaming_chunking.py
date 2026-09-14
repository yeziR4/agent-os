"""Issue #2105: DiscordChannel.send_streaming had no 2000-char chunking.

``send()`` already splits an over-limit reply via ``_split_content_for_send``
(added for #1544), and Telegram's ``send_streaming`` already rolls over into
a new message at its own length cap via ``_post_segments``. Discord's
``send_streaming`` had neither: ``StreamThrottle`` re-posted/re-edited the
full accumulated text verbatim, and once that text crossed 2000 characters
Discord would reject the PATCH/POST with a 400, killing the stream mid-reply.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest

from agentos.channels.discord import DiscordChannel, DiscordChannelConfig


class _FakeResponse:
    status_code = 200

    def __init__(self, message_id: str) -> None:
        self._message_id = message_id

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return {"id": self._message_id}


Call = tuple[str, str, dict[str, Any]]


def _discord_channel(**config: Any) -> tuple[DiscordChannel, list[Call]]:
    channel = DiscordChannel(DiscordChannelConfig(token="token", application_id="app", **config))
    calls: list[Call] = []

    class _Client:
        async def post(self, path: str, **kwargs: Any) -> _FakeResponse:
            calls.append(("POST", path, kwargs.get("json", {})))
            return _FakeResponse(str(len(calls)))

        async def patch(self, path: str, **kwargs: Any) -> _FakeResponse:
            calls.append(("PATCH", path, kwargs.get("json", {})))
            return _FakeResponse(str(len(calls)))

    channel._client = _Client()
    return channel, calls


async def _stream(*chunks: str) -> AsyncIterator[str]:
    for chunk in chunks:
        yield chunk


def _contents(calls: list[Call], method: str) -> list[str]:
    return [str(payload["content"]) for name, _path, payload in calls if name == method]


@pytest.mark.asyncio
async def test_discord_send_streaming_rolls_over_at_the_message_limit() -> None:
    channel, calls = _discord_channel()
    long_text = "word " * 1200  # 6000 chars, past Discord's 2000-char cap

    message_id = await channel.send_streaming(
        _stream(long_text),
        channel_id="channel-1",
        update_interval_ms=0,
    )

    posts = [c for c in calls if c[0] == "POST"]
    assert len(posts) == 3
    for _method, path, payload in posts:
        assert path == "/channels/channel-1/messages"
        assert len(payload["content"]) <= 2000
    assert "".join(_contents(calls, "POST")) == long_text
    assert message_id == "3"


@pytest.mark.asyncio
async def test_discord_send_streaming_keeps_editing_after_rollover() -> None:
    channel, calls = _discord_channel()
    long_text = "word " * 500  # splits into a full 2000-char message plus a 500-char one

    await channel.send_streaming(
        _stream(long_text, "tail"),
        channel_id="channel-1",
        update_interval_ms=0,
    )

    methods = [name for name, _path, _payload in calls]
    assert methods == ["POST", "POST", "PATCH"]
    # The edit targets the newest (second) message, not the first.
    _method, path, payload = calls[-1]
    assert path == "/channels/channel-1/messages/2"
    # And it carries that whole message's content plus the new chunk --
    # editing replaces a message's text, so it can't be just the delta.
    assert payload["content"] == long_text[2000:] + "tail"
    assert len(payload["content"]) <= 2000


@pytest.mark.asyncio
async def test_discord_send_streaming_short_reply_is_a_single_post() -> None:
    channel, calls = _discord_channel()

    message_id = await channel.send_streaming(
        _stream("hello", " world"),
        channel_id="channel-1",
        update_interval_ms=60_000,
    )

    # Chunks inside the throttle interval coalesce: one open, one final flush.
    assert [name for name, _path, _payload in calls] == ["POST", "PATCH"]
    assert calls[-1][2]["content"] == "hello world"
    assert message_id == "1"


@pytest.mark.asyncio
async def test_discord_send_streaming_interaction_overflow_goes_to_channel_followups() -> None:
    """The interaction original-response slot holds exactly one message;
    overflow must still reach the user as regular channel messages instead
    of being dropped or crashing the stream (mirrors send()'s handling of
    the same constraint for a non-streamed reply)."""
    channel, calls = _discord_channel()
    long_text = "word " * 500  # 2500 chars: fills @original, 500 chars roll over

    message_id = await channel.send_streaming(
        _stream(long_text, "tail"),
        channel_id="channel-1",
        interaction_id="int-1",
        interaction_token="tok",
        interaction_application_id="app",
        update_interval_ms=0,
    )

    assert [name for name, _path, _payload in calls] == ["PATCH", "POST", "PATCH"]
    assert calls[0][1] == "/webhooks/app/tok/messages/@original"
    assert len(calls[0][2]["content"]) == 2000
    # The rolled-over overflow is a regular channel message, not another
    # interaction-webhook call.
    assert calls[1][1] == "/channels/channel-1/messages"
    # And later edits (including the "tail" chunk) land on that new message,
    # never back on the one-shot @original slot.
    assert calls[2][1] == "/channels/channel-1/messages/2"
    assert calls[2][2]["content"] == long_text[2000:] + "tail"
    assert message_id == "2"
