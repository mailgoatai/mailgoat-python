from __future__ import annotations

from pathlib import Path

from mailgoat.templates import Template, create_template, list_templates, load_template, parse_vars, render_template, validate_template


def test_frontmatter_and_render_if_each(tmp_path: Path) -> None:
    path = tmp_path / "templates"
    path.mkdir(parents=True)
    tpl_file = path / "welcome.hbs"
    tpl_file.write_text(
        """---
subject: Hi {{name}}
from: noreply@example.com
---
Hello {{name}}\n
{{#if isPro}}Pro{{else}}Free{{/if}}\n
{{#each items}}- {{this}}\n{{/each}}
""",
        encoding="utf-8",
    )

    template = load_template("welcome", str(path))
    body, warnings = render_template(template, {"name": "Ada", "isPro": True, "items": ["A", "B"]})

    assert template.metadata["from"] == "noreply@example.com"
    assert "Hello Ada" in body
    assert "Pro" in body
    assert "- A" in body
    assert warnings == []


def test_parse_vars_and_validate(tmp_path: Path) -> None:
    vars_file = tmp_path / "vars.json"
    vars_file.write_text('{"name":"Lin","count":2}', encoding="utf-8")
    result = parse_vars(["active=true", "level=3"], str(vars_file))
    assert result["name"] == "Lin"
    assert result["active"] is True
    assert result["level"] == 3

    template = Template(name="x", path=tmp_path / "x.hbs", metadata={}, body="Hi {{name}} {{missing}}")
    errors = validate_template(template, {"name": "Lin"})
    assert any("unresolved variables" in item for item in errors)


def test_builtin_and_create_template(tmp_path: Path) -> None:
    names = list_templates(str(tmp_path / "templates"))
    assert "welcome" in names

    target = create_template("custom", "Subject", "from@example.com", "Body", str(tmp_path / "templates"))
    assert target.exists()
    custom = load_template("custom", str(tmp_path / "templates"))
    assert custom.metadata["subject"] == "Subject"
