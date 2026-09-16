from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from agentos.tools.builtin import sessions as sessions_tools


class _LongTranscriptSessionManager:
    """Mimics SessionManager.read_transcript over a transcript longer than limit."""

    def __init__(self, messages: list[dict]) -> None:
        self._messages = messages

    async def get_session(self, session_key: str) -> object:
        return SimpleNamespace(session_key=session_key)

    async def read_transcript(
        self, session_key: str, limit: int | None = None, *, newest_first: bool = False
    ) -> list[dict]:
        if limit is None:
            window = self._messages
        elif newest_first:
            window = self._messages[-limit:]
        else:
            window = self._messages[:limit]
        return list(window)


@pytest.mark.asyncio
async def test_sessions_history_returns_the_most_recent_messages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    messages = [{"role": "user", "content": f"msg-{i:03d}"} for i in range(80)]
    messages.append({"role": "assistant", "content": "the real final answer"})
    monkeypatch.setattr(sessions_tools, "_session_manager", _LongTranscriptSessionManager(messages))

    result = await sessions_tools.sessions_history(session_key="agent:main:main", limit=20)

    payload = json.loads(result)
    assert payload["messages"][-1]["content"] == "the real final answer"
