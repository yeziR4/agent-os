"""Offline regression tests for the gmgn-wallet-analysis script's ``--fixture`` loader.

A fixture whose ``_gaps`` field is a string rather than a list used to pass
``json.load`` and then hit ``gaps += d.get("_gaps", [])``: Python's ``list +=
str`` iterates the string character by character instead of raising, so the
report's DATA GAPS section silently rendered one bullet per character of the
string instead of erroring on the malformed fixture.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = (
    ROOT
    / "src"
    / "agentos"
    / "skills"
    / "bundled"
    / "gmgn-wallet-analysis"
    / "scripts"
    / "analyze.py"
)


def _run(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
    )


def test_fixture_with_string_gaps_errors_instead_of_exploding_into_chars(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "bad.json"
    fixture.write_text(
        json.dumps(
            {
                "_wallet": "TESTWALLET1234567890",
                "_chain": "sol",
                "_gaps": "holdings rate limited, retry later",
            }
        )
    )

    result = _run("--fixture", str(fixture), "en")

    assert result.returncode == 2
    assert "_gaps" in result.stderr
    assert "must be a list" in result.stderr
    assert "⚪ h" not in result.stdout
    assert "Traceback" not in result.stderr


def test_fixture_with_list_gaps_still_renders_them(tmp_path: Path) -> None:
    fixture = tmp_path / "good.json"
    fixture.write_text(
        json.dumps(
            {
                "_wallet": "TESTWALLET1234567890",
                "_chain": "sol",
                "_gaps": ["holdings rate limited, retry later"],
            }
        )
    )

    result = _run("--fixture", str(fixture), "en")

    assert result.returncode == 0
    assert "holdings rate limited, retry later" in result.stdout
    assert "Traceback" not in result.stderr
