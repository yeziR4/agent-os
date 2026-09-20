"""html-to-pdf skill — load + eligibility + render smoke (skipped without weasyprint)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from agentos.skills.eligibility import EligibilityContext, check_eligibility
from agentos.skills.loader import SkillLoader

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / "src" / "agentos" / "skills" / "bundled"
SCRIPTS = BUNDLED / "html-to-pdf" / "scripts"


def _spec() -> object:
    return SkillLoader(bundled_dir=BUNDLED).get_by_name("html-to-pdf")


def test_skill_loads() -> None:
    spec = _spec()
    assert spec is not None
    assert spec.name == "html-to-pdf"


def test_skill_instructs_artifact_delivery() -> None:
    spec = _spec()
    assert spec is not None
    assert "publish_artifact" in spec.content
    assert "file-authoring tools" in spec.content
    assert "If none of those file-authoring tools are available" in spec.content
    assert "Do not attempt to generate, save, or modify the final file" in spec.content
    assert "Ignore the Quick start and Workflow sections below" in spec.content
    assert "Do not paste the full HTML/CSS source" in spec.content


def test_eligibility_with_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "agentos.skills.eligibility.shutil.which",
        lambda name: "/usr/bin/python3" if name in {"python", "python3"} else None,
    )
    spec = _spec()
    assert spec is not None
    assert check_eligibility(spec, EligibilityContext.auto())


def _render_module():
    sys.path.insert(0, str(SCRIPTS))
    try:
        import render  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    return render


def _plain_html(tmp_path: Path) -> Path:
    html_path = tmp_path / "doc.html"
    html_path.write_text(
        "<!doctype html><html><body><h1>Hello</h1><p>World.</p></body></html>",
        encoding="utf-8",
    )
    return html_path


def test_render_html_to_pdf(tmp_path: Path) -> None:
    pytest.importorskip(
        "weasyprint",
        reason="weasyprint is opt-in via use-agent-os[document-extras]; skip when absent",
    )
    render = _render_module()

    html_path = tmp_path / "doc.html"
    html_path.write_text(
        """<!doctype html><html><head><title>x</title>
        <style>@page { size: Letter; margin: 0.5in; } body { font-family: serif; }</style>
        </head><body><h1>Hello</h1><p>World.</p></body></html>""",
        encoding="utf-8",
    )
    out_path = tmp_path / "out.pdf"
    render.render(str(html_path), out_path, "Letter")
    assert out_path.is_file()
    # Sanity: a non-trivial PDF is at least a few hundred bytes and starts with %PDF.
    blob = out_path.read_bytes()
    assert blob.startswith(b"%PDF")
    assert len(blob) > 500


def test_known_page_size_alias_is_honored(tmp_path: Path) -> None:
    """Regression: ``--page-size Letter`` must actually produce a Letter page.

    Pins the correct case so the malformed-input fix below cannot be
    satisfied by breaking every ``--page-size`` value instead of just the
    invalid ones.
    """
    pytest.importorskip(
        "weasyprint",
        reason="weasyprint is opt-in via use-agent-os[document-extras]; skip when absent",
    )
    from pypdf import PdfReader

    render = _render_module()
    out_path = tmp_path / "out.pdf"
    render.render(str(_plain_html(tmp_path)), out_path, "Letter")

    box = PdfReader(str(out_path)).pages[0].mediabox
    assert (round(float(box.width)), round(float(box.height))) == (612, 792)


def test_unrecognized_but_valid_css_page_size_still_passes_through(tmp_path: Path) -> None:
    """``A5`` is not in the script's shorthand map but is valid CSS and must
    still reach WeasyPrint unchanged (documented: "or any valid CSS size
    value")."""
    pytest.importorskip(
        "weasyprint",
        reason="weasyprint is opt-in via use-agent-os[document-extras]; skip when absent",
    )
    from pypdf import PdfReader

    render = _render_module()
    out_path = tmp_path / "out.pdf"
    render.render(str(_plain_html(tmp_path)), out_path, "A5")

    box = PdfReader(str(out_path)).pages[0].mediabox
    assert (round(float(box.width)), round(float(box.height))) == (420, 595)


def test_invalid_page_size_is_rejected_instead_of_silently_ignored(tmp_path: Path) -> None:
    """A typo'd ``--page-size`` must fail loudly, not silently render at
    WeasyPrint's default page size while reporting success.

    Before the fix, WeasyPrint's CSS parser dropped the unrecognized `size`
    value per CSS error-recovery rules and rendering fell back to its A4
    default with no exception and nothing on stderr: the script wrote a
    "successful" PDF at the wrong page size.
    """
    pytest.importorskip(
        "weasyprint",
        reason="weasyprint is opt-in via use-agent-os[document-extras]; skip when absent",
    )
    render = _render_module()
    out_path = tmp_path / "out.pdf"

    with pytest.raises(SystemExit) as exc_info:
        render.render(str(_plain_html(tmp_path)), out_path, "Letterr")

    assert exc_info.value.code == 2
    assert not out_path.exists()
