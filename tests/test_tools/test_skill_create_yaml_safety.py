"""A description/trigger containing YAML-significant characters must not
silently produce a skill the loader can never see again.

``skill_create``/``skill_edit`` write their frontmatter by hand-formatting
strings into a YAML document. Before this fix, a perfectly ordinary
description such as "Convert times: UTC to PST" (a colon followed by a
space is a YAML mapping separator) produced frontmatter that
``yaml.safe_load`` cannot parse. ``agentos.skills.loader._parse_frontmatter``
treats unparseable frontmatter the same as a missing "name" key: it returns
``({}, text)`` and the skill directory is skipped entirely (see
``SkillLoader._load_skill_from_dir``, ``if not frontmatter or "name" not in
frontmatter: return None``). The tool call itself reports success, so the
caller has no signal that the skill it just "created" is invisible to
``skill_list``, ``skill_view``, and the model's own skill catalog.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml

from agentos.skills.loader import SkillLoader
from agentos.tools.builtin import skill_tools as skill_tools_module
from agentos.tools.registry import get_default_registry


async def _skill_create(
    name: str,
    description: str,
    content: str = "Body text.",
    triggers: list[str] | None = None,
) -> str:
    registered = get_default_registry().get("skill_create")
    assert registered is not None
    kwargs = {"name": name, "description": description, "content": content}
    if triggers is not None:
        kwargs["triggers"] = triggers
    return await registered.handler(**kwargs)


async def _skill_edit(
    name: str,
    description: str | None = None,
    triggers: list[str] | None = None,
) -> str:
    registered = get_default_registry().get("skill_edit")
    assert registered is not None
    kwargs: dict[str, object] = {"name": name}
    if description is not None:
        kwargs["description"] = description
    if triggers is not None:
        kwargs["triggers"] = triggers
    return await registered.handler(**kwargs)


@pytest.fixture()
def skill_loader(tmp_path: Path) -> Iterator[SkillLoader]:
    bundled_root = tmp_path / "bundled"
    bundled_root.mkdir(parents=True)
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True)

    loader = SkillLoader(
        bundled_dir=bundled_root,
        workspace_dir=workspace_root,
        managed_dir=tmp_path / "managed",
        personal_agents_dir=tmp_path / "personal",
        project_agents_dir=tmp_path / "project",
        snapshot_path=tmp_path / "skills.snapshot.json",
    )
    previous_loader = skill_tools_module._loader
    skill_tools_module.create_skill_tools(loader)
    try:
        yield loader
    finally:
        skill_tools_module._loader = previous_loader


@pytest.mark.asyncio
async def test_skill_create_with_colon_in_description_stays_loadable(
    skill_loader: SkillLoader,
) -> None:
    """A colon-space in the description is a completely ordinary sentence,
    not malformed input the caller should have to know to avoid — but it is
    a YAML mapping separator, so it must round-trip through frontmatter."""
    description = "Convert times: UTC to PST"

    result = await _skill_create("time-zone-helper", description=description)
    assert "created" in result.lower()

    skill_file = skill_loader.workspace_dir / "time-zone-helper" / "SKILL.md"
    written = skill_file.read_text(encoding="utf-8")
    fm_text = written.split("---")[1]
    parsed = yaml.safe_load(fm_text)
    assert parsed is not None, "frontmatter must remain valid YAML"
    assert parsed["description"] == description

    found = skill_loader.get_by_name("time-zone-helper")
    assert found is not None, (
        "skill_create reported success but the loader cannot see the skill — it silently vanished"
    )
    assert found.description == description


@pytest.mark.parametrize(
    "description",
    [
        "Convert times: UTC to PST",
        "# not a comment, a real description",
        "- looks like a list item, not one",
        "Has \"double\" and 'single' quotes",
        "Multiple: colons: in: one: line",
    ],
)
@pytest.mark.asyncio
async def test_skill_create_various_yaml_significant_descriptions(
    skill_loader: SkillLoader, description: str
) -> None:
    name = "yaml-edge-case"
    await _skill_create(name, description=description)
    found = skill_loader.get_by_name(name)
    assert found is not None, f"description {description!r} broke the frontmatter"
    assert found.description == description

    skill_dir = skill_loader.workspace_dir / name
    import shutil

    shutil.rmtree(skill_dir)
    skill_loader.invalidate_cache()


@pytest.mark.asyncio
async def test_skill_create_with_colon_in_trigger_stays_loadable(
    skill_loader: SkillLoader,
) -> None:
    result = await _skill_create(
        "trigger-edge-case",
        description="Plain description",
        triggers=["do: the thing", "plain trigger"],
    )
    assert "created" in result.lower()

    found = skill_loader.get_by_name("trigger-edge-case")
    assert found is not None
    assert found.triggers == ["do: the thing", "plain trigger"]


@pytest.mark.asyncio
async def test_skill_edit_with_colon_in_description_stays_loadable(
    skill_loader: SkillLoader,
) -> None:
    await _skill_create("editable-skill", description="Plain description")
    assert skill_loader.get_by_name("editable-skill") is not None

    description = "Report status: green, yellow, or red"
    result = await _skill_edit("editable-skill", description=description)
    assert "updated" in result.lower()

    found = skill_loader.get_by_name("editable-skill")
    assert found is not None, (
        "skill_edit reported success but the loader cannot see the skill — it silently vanished"
    )
    assert found.description == description
