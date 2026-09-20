"""deep-research iterate: an evidence field sent as JSON ``null`` must not

become the literal string ``"None"`` in a recorded ``Source``.

The `evidence_round_N.json` shape SKILL.md documents has `title`, `excerpt`
and `fetched_at` as strings the host may not always have (a bare URL with no
scraped title yet, no excerpt pulled, no known fetch time), and `url` itself
can be missing on a still-being-filled-in item. JSON `null` is the natural
way to spell "no value" for a `str`-typed field, and it is valid JSON the
`--record` file's own schema does not forbid. `record_evidence` builds each
`Source` with `str(item.get(key, ""))`: when the key is *present* with value
`null`, `.get` returns `None` (the default only applies when the key is
absent), and `str(None)` is the four-character string `"None"` — recorded
into the plan, then rendered by `compile.py` into the report's Findings
bullet and References citation, both of which treat a non-empty string as
real content instead of falling back to something else. The run still exits
0 and reports success (`added: 1`); nothing is missing, but what is there is
wrong.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "src" / "agentos" / "skills" / "bundled" / "deep-research" / "scripts"


def _import_scripts():
    sys.path.insert(0, str(SCRIPTS))
    try:
        import compile as compile_script  # type: ignore[import-not-found]
        import iterate  # type: ignore[import-not-found]
        import plan as plan_script  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)
    return plan_script, iterate, compile_script


def _make_plan(plan_script, target_sources: int = 2):
    return plan_script.Plan(
        question="What is the impact of AI on programming?",
        depth="overview",
        created_at="2026-01-01T00:00:00Z",
        subquestions=[
            plan_script.SubQuestion(id="sq-001", question="q", target_sources=target_sources)
        ],
    )


def test_a_null_title_excerpt_and_fetched_at_stay_empty_not_the_string_none() -> None:
    plan_script, iterate, _ = _import_scripts()
    plan = _make_plan(plan_script)
    evidence = [
        {
            "subquestion_id": "sq-001",
            "url": "https://example.com/a",
            "title": None,
            "excerpt": None,
            "fetched_at": None,
            "relevance": 0.7,
        }
    ]

    added = iterate.record_evidence(plan, evidence)

    assert added == 1
    source = plan.subquestions[0].sources[0]
    assert source.url == "https://example.com/a"
    assert source.title == ""
    assert source.excerpt == ""
    assert source.fetched_at == ""


def test_a_null_url_stays_empty_not_the_string_none() -> None:
    plan_script, iterate, _ = _import_scripts()
    plan = _make_plan(plan_script)
    evidence = [{"subquestion_id": "sq-001", "url": None, "title": "Some Title"}]

    iterate.record_evidence(plan, evidence)

    assert plan.subquestions[0].sources[0].url == ""


def test_a_missing_field_still_defaults_to_empty_string_as_before() -> None:
    # Positive control: the fix must not disturb the existing "field absent
    # entirely" path, which was already correct (`.get`'s own default fires).
    plan_script, iterate, _ = _import_scripts()
    plan = _make_plan(plan_script)
    evidence = [{"subquestion_id": "sq-001", "url": "https://example.com/a"}]

    iterate.record_evidence(plan, evidence)

    source = plan.subquestions[0].sources[0]
    assert source.title == ""
    assert source.excerpt == ""
    assert source.fetched_at == ""


def test_compiled_report_never_prints_the_literal_word_none_for_a_null_field(
    tmp_path: Path,
) -> None:
    plan_script, iterate, compile_script = _import_scripts()
    plan = _make_plan(plan_script, target_sources=1)
    evidence = [
        {
            "subquestion_id": "sq-001",
            "url": "https://example.com/a",
            "title": None,
            "excerpt": None,
            "fetched_at": None,
            "relevance": 0.7,
        }
    ]
    iterate.record_evidence(plan, evidence)

    report = compile_script.render(plan)

    assert "None" not in report
    # The findings bullet and the reference both fall back to the URL when
    # there is no title/excerpt, instead of showing the word "None".
    assert "- https://example.com/a [^1]" in report
    assert "[^1]: <https://example.com/a>" in report
