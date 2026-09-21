"""srt-from-script ``build_srt.py`` — a VOICEOVER value that wraps onto a
second physical line is rejected, not silently truncated.

ai-video-script's OUTPUT FORMAT documents VOICEOVER as a single line ("No
multi-line values"), and srt-from-script's own SKILL.md promises drift away
from the expected format is fatal ("zero cues, exit 1") — the same contract
already enforced for a missing DURATION_S field. But ``_VO_RE`` matched only
the first physical line of the value with no notion of what followed, so a
VOICEOVER that wrapped (something LLM output does routinely for a long
quoted line) was silently chopped at the line break: the reader got a
truncated sentence, and the script still exited 0 with a well-formed-looking
SRT.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "src" / "agentos" / "skills" / "bundled" / "srt-from-script" / "scripts"


def _build_srt_module():
    sys.path.insert(0, str(SCRIPTS))
    try:
        import build_srt  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    return build_srt


def test_parse_script_rejects_a_voiceover_that_wraps_onto_a_second_line() -> None:
    build_srt = _build_srt_module()
    script = (
        "=== SHOT_1 ===\n"
        "DURATION_S: 5\n"
        'VOICEOVER: "Hello there,\n'
        'this continues on the next line and should be part of the subtitle too."\n'
    )
    with pytest.raises(ValueError, match="SHOT_1 has a multi-line VOICEOVER"):
        build_srt.parse_script(script)


def test_parse_script_accepts_voiceover_immediately_followed_by_another_field() -> None:
    """A well-formed script where VOICEOVER is followed by ON_SCREEN_TEXT (or
    any other ``FIELD: value`` line) on the very next line must still parse —
    only a non-field continuation line is format drift."""
    build_srt = _build_srt_module()
    script = (
        "=== SHOT_1 ===\n"
        "DURATION_S: 5\n"
        "CAMERA: wide, static\n"
        "VOICEOVER: A normal single-line voiceover.\n"
        "ON_SCREEN_TEXT: Some text\n\n"
        "=== SHOT_2 ===\n"
        "DURATION_S: 4\n"
        "VOICEOVER: Second shot line.\n"
    )
    shots = build_srt.parse_script(script)
    assert shots == [
        (1, 5.0, "A normal single-line voiceover."),
        (2, 4.0, "Second shot line."),
    ]


def test_parse_script_accepts_voiceover_as_the_last_line_in_its_block() -> None:
    build_srt = _build_srt_module()
    script = "=== SHOT_1 ===\nDURATION_S: 3\nVOICEOVER: last field in block\n"

    shots = build_srt.parse_script(script)

    assert shots == [(1, 3.0, "last field in block")]


def test_main_exits_1_with_a_clear_message_on_a_multiline_voiceover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    build_srt = _build_srt_module()
    script_path = tmp_path / "script.txt"
    script_path.write_text(
        "=== SHOT_1 ===\nDURATION_S: 5\nVOICEOVER: first line\nsecond line, no field prefix\n",
        encoding="utf-8",
    )
    out_path = tmp_path / "out.srt"
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_srt.py", "--script", str(script_path), "--output", str(out_path)],
    )

    exit_code = build_srt.main()

    assert exit_code == 1
    assert not out_path.exists()
    captured = capsys.readouterr()
    assert "multi-line VOICEOVER" in captured.err
