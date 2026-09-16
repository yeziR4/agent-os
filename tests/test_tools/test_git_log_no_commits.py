"""``git_log`` must not crash on a repository before its first commit.

``git log`` exits 128 with "does not have any commits yet" when ``HEAD`` is
unborn, and the tool had no guard for it (#2502) -- unlike ``git_diff``,
which already falls back via ``_diff_revision`` (#614).
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from agentos.sandbox.config import SandboxSettings
from agentos.sandbox.integration import configure_runtime, reset_runtime
from agentos.tools.builtin import git
from agentos.tools.types import ToolContext, current_tool_context


def _git(repo: Path, *args: str) -> None:
    """Run git with the ambient user/system config neutralised.

    A maintainer's global ``commit.gpgsign`` or commit template would otherwise
    decide whether this test can make a commit, and the env is copied rather
    than replaced because git on Windows needs the ambient ``SYSTEMROOT``.
    """
    missing = str(repo.parent / "no-such-gitconfig")
    subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_CONFIG_GLOBAL": missing,
            "GIT_CONFIG_SYSTEM": missing,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        },
    )


@pytest.fixture
def empty_repo(tmp_path: Path) -> Iterator[Path]:
    """A repository with no commit yet -- ``HEAD`` does not resolve."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    configure_runtime(
        SandboxSettings(sandbox=False, security_grading=False, allow_legacy_mode=True),
        workspace=repo,
    )
    token = current_tool_context.set(ToolContext(workspace_dir=str(repo)))
    try:
        yield repo
    finally:
        current_tool_context.reset(token)
        reset_runtime()


async def test_git_log_reports_no_commits_instead_of_raising(empty_repo: Path) -> None:
    """A fresh, commit-less repository must not crash ``git_log``."""
    out = await git.git_log(workdir=str(empty_repo))

    assert out == "(no commits yet)"


async def test_git_log_still_lists_commits_once_one_exists(empty_repo: Path) -> None:
    """The fallback must not shadow the normal, populated-history path."""
    (empty_repo / "first.txt").write_text("hello\n", encoding="utf-8", newline="\n")
    _git(empty_repo, "add", "-A")
    _git(empty_repo, "commit", "-qm", "init")

    out = await git.git_log(workdir=str(empty_repo))

    assert "init" in out
