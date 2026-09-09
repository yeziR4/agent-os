"""Regression tests: exec_command/background_process must gate (and then
execute) a sandboxed command against the *resolved* workdir, not the raw
caller-supplied one.

``gate_action``'s ``cwd`` resolves a relative path only when it can fall
back to ``ctx.workspace_dir`` — passing the raw, still-relative ``workdir``
straight through means the resolver's ``is_absolute()`` check fails and it
silently substitutes the workspace root instead, both for policy/level
selection and for the actual sandboxed subprocess's working directory.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from agentos.sandbox.config import SandboxSettings
from agentos.sandbox.integration import configure_runtime, reset_runtime
from agentos.sandbox.types import DenialReason, DenialResult, SecurityLevel, SuggestedNextStep
from agentos.tools.builtin import shell
from agentos.tools.builtin.shell_policy import PolicyResult
from agentos.tools.types import CallerKind, ToolContext, current_tool_context


@pytest.fixture(autouse=True)
def _reset_state():
    reset_runtime()
    elevate_token = shell._elevate_current_call.set(False)
    yield
    shell._elevate_current_call.reset(elevate_token)
    reset_runtime()


def _recording_gate_action() -> Any:
    """A fake ``gate_action`` that records its ``cwd`` kwarg and denies,
    so the caller returns immediately without needing a real backend."""

    calls: list[dict[str, Any]] = []

    async def _fake(**kwargs: Any):
        calls.append(kwargs)
        decision = DenialResult(
            reason=DenialReason.HUMAN_REJECTED,
            suggested_next_step=SuggestedNextStep.ASK_USER,
            level=SecurityLevel.STANDARD,
            action_fingerprint="test-fingerprint",
            message="denied for test",
        )
        return decision, None, None

    _fake.calls = calls  # type: ignore[attr-defined]
    return _fake


def _configure(workspace: Path) -> None:
    configure_runtime(
        SandboxSettings(
            sandbox=True, security_grading=False, backend="noop", allow_legacy_mode=True
        ),
        workspace=workspace,
    )


@pytest.mark.asyncio
async def test_exec_command_gates_against_resolved_relative_workdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "subproject").mkdir()
    token = current_tool_context.set(
        ToolContext(caller_kind=CallerKind.CLI, session_key="t", workspace_dir=str(tmp_path))
    )
    try:
        _configure(tmp_path)
        monkeypatch.setattr(
            shell,
            "check_safe_bin",
            lambda command: PolicyResult(allowed=True, reason="", needs_approval=False),
        )
        fake_gate = _recording_gate_action()
        monkeypatch.setattr(shell, "gate_action", fake_gate)

        await shell.exec_command("ls", workdir="subproject")

        assert len(fake_gate.calls) == 1
        assert fake_gate.calls[0]["cwd"] == (tmp_path / "subproject").resolve()
    finally:
        current_tool_context.reset(token)


@pytest.mark.asyncio
async def test_background_process_gates_against_resolved_relative_workdir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "subproject").mkdir()
    token = current_tool_context.set(
        ToolContext(caller_kind=CallerKind.CLI, session_key="t", workspace_dir=str(tmp_path))
    )
    try:
        _configure(tmp_path)
        monkeypatch.setattr(
            shell,
            "check_safe_bin",
            lambda command: PolicyResult(allowed=True, reason="", needs_approval=False),
        )
        fake_gate = _recording_gate_action()
        monkeypatch.setattr(shell, "gate_action", fake_gate)

        await shell.background_process("sleep 0", workdir="subproject")

        assert len(fake_gate.calls) == 1
        assert fake_gate.calls[0]["cwd"] == (tmp_path / "subproject").resolve()
    finally:
        current_tool_context.reset(token)
