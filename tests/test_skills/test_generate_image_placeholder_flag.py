"""Regression tests for nano-banana-pro's ``--placeholder-on-fail`` flag (#2477).

The script's own usage docs advertise a bare flag; the SKILL.md harness always
passes it with an explicit ``yes``/``no`` value. Both call styles must parse.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
IMAGE_SCRIPT = REPO_ROOT / "src/agentos/skills/bundled/nano-banana-pro/scripts/generate_image.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "_agentos_test_generate_image_placeholder", IMAGE_SCRIPT
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module.__name__] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def image_script(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    module = _load_script()
    # Every attempt "fails" without making a real network call, so the test
    # only exercises argument parsing and the placeholder-on-fail branch.
    monkeypatch.setattr(
        module, "_try_one_attempt", lambda **_: (_ for _ in ()).throw(RuntimeError("no model"))
    )
    monkeypatch.setattr(module, "resolve_api_key", lambda _provided: "fake-key")
    return module


def _run(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch, out_path: Path, extra: list[str]
) -> int:
    monkeypatch.setattr(
        sys,
        "argv",
        ["generate_image.py", "--prompt", "a cat", "--filename", str(out_path), *extra],
    )
    return module.main()


def test_bare_flag_is_accepted_as_documented(
    image_script: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``--placeholder-on-fail`` with no value used to raise argparse error 2 (#2477)."""
    out = tmp_path / "out.png"
    assert _run(image_script, monkeypatch, out, ["--placeholder-on-fail"]) == 0
    assert out.is_file()


def test_explicit_yes_from_the_skill_harness_still_works(
    image_script: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """SKILL.md always passes an explicit value; that contract must not break."""
    out = tmp_path / "out.png"
    assert _run(image_script, monkeypatch, out, ["--placeholder-on-fail", "yes"]) == 0
    assert out.is_file()


def test_explicit_no_from_the_skill_harness_still_declines(
    image_script: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = tmp_path / "out.png"
    assert _run(image_script, monkeypatch, out, ["--placeholder-on-fail", "no"]) == 1
    assert not out.is_file()


def test_omitted_flag_defaults_to_no_placeholder(
    image_script: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = tmp_path / "out.png"
    assert _run(image_script, monkeypatch, out, []) == 1
    assert not out.is_file()


def test_invalid_explicit_value_is_still_rejected(
    image_script: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    out = tmp_path / "out.png"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "generate_image.py",
            "--prompt",
            "a cat",
            "--filename",
            str(out),
            "--placeholder-on-fail",
            "maybe",
        ],
    )
    with pytest.raises(SystemExit) as exc_info:
        image_script.main()
    assert exc_info.value.code == 2


def test_bare_flag_followed_by_another_option_does_not_consume_it(
    image_script: ModuleType, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``--placeholder-on-fail --api-key KEY`` must not swallow ``--api-key`` as its value."""
    out = tmp_path / "out.png"
    assert (
        _run(image_script, monkeypatch, out, ["--placeholder-on-fail", "--api-key", "explicit-key"])
        == 0
    )
    assert out.is_file()
