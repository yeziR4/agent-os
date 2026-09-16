from __future__ import annotations

from types import SimpleNamespace

import pytest

from agentos.gateway.subagent_announce import _read_child_result


class _NewestFirstAwareSessionManager:
    """Mirrors SessionManager.read_transcript's newest_first parameter."""

    def __init__(self, messages: list[SimpleNamespace]) -> None:
        self._messages = messages

    async def read_transcript(
        self, session_key: str, limit: int | None = None, *, newest_first: bool = False
    ) -> list[SimpleNamespace]:
        window = self._messages[-limit:] if newest_first else self._messages[:limit]
        return list(window)


class _LegacySessionManager:
    """Predates the newest_first flag -- only accepts limit, like older duck-typed callers."""

    def __init__(self, messages: list[SimpleNamespace]) -> None:
        self._messages = messages

    async def read_transcript(self, session_key: str, limit: int = 50) -> list[SimpleNamespace]:
        return list(self._messages[:limit])


def _long_transcript() -> list[SimpleNamespace]:
    rows = [
        SimpleNamespace(role="user" if i % 2 == 0 else "assistant", content=f"msg-{i:03d}")
        for i in range(80)
    ]
    rows.append(SimpleNamespace(role="assistant", content="the real final answer"))
    return rows


@pytest.mark.asyncio
async def test_read_child_result_finds_latest_answer_past_the_50_row_window() -> None:
    session_manager = _NewestFirstAwareSessionManager(_long_transcript())

    result = await _read_child_result("agent:main:webchat:child", session_manager=session_manager)

    assert result["text"] == "the real final answer"


@pytest.mark.asyncio
async def test_read_child_result_falls_back_for_a_session_manager_without_newest_first() -> None:
    session_manager = _LegacySessionManager(_long_transcript())

    result = await _read_child_result("agent:main:webchat:child", session_manager=session_manager)

    # No newest_first support on this duck-typed manager -- best it can do is
    # the stale first-50 window, same as before the fix.
    assert result["text"] == "msg-049"
