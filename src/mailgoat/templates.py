from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import yaml


BUILTIN_TEMPLATES: dict[str, str] = {
    "welcome": """---
subject: Welcome to {{appName}}!
from: noreply@example.com
---
Hi {{name}},

Welcome to {{appName}}! Your account is ready.

{{#if isPro}}
You're on the Pro plan. Enjoy premium features!
{{else}}
Upgrade to Pro for advanced features.
{{/if}}

Best regards,
The {{appName}} Team
""",
    "notification": """---
subject: Notification: {{title}}
from: noreply@example.com
---
Hello {{name}},

{{message}}

Time: {{timestamp}}
""",
    "report": """---
subject: Report for {{period}}
from: reports@example.com
---
Report summary for {{period}}:

{{#each rows}}
- {{name}}: {{value}}
{{/each}}
""",
    "error": """---
subject: Error Alert: {{service}}
from: alerts@example.com
---
Service: {{service}}
Severity: {{severity}}
Details: {{details}}
{{#if action}}Action: {{action}}{{/if}}
""",
}


class TemplateError(Exception):
    """Raised when template handling fails."""


@dataclass
class Template:
    name: str
    path: Path
    metadata: dict[str, Any]
    body: str


class _HTMLValidator(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.stack: list[str] = []
        self.errors: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag not in {"br", "hr", "img", "meta", "link", "input"}:
            self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if not self.stack:
            self.errors.append(f"closing tag without opener: {tag}")
            return
        open_tag = self.stack.pop()
        if open_tag != tag:
            self.errors.append(f"mismatched tag: expected </{open_tag}> got </{tag}>")


def ensure_builtin_templates(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, content in BUILTIN_TEMPLATES.items():
        target = directory / f"{name}.hbs"
        if not target.exists():
            target.write_text(content, encoding="utf-8")


def template_dir(path: str | None = None) -> Path:
    if path:
        return Path(path).expanduser()
    return Path("~/.mailgoat/templates").expanduser()


def list_templates(path: str | None = None) -> list[str]:
    directory = template_dir(path)
    ensure_builtin_templates(directory)
    return sorted(item.stem for item in directory.glob("*.hbs"))


def load_template(name: str, path: str | None = None) -> Template:
    directory = template_dir(path)
    ensure_builtin_templates(directory)
    file_path = directory / f"{name}.hbs"
    if not file_path.exists():
        raise TemplateError(f"template not found: {name}")

    raw = file_path.read_text(encoding="utf-8")
    metadata, body = split_frontmatter(raw)
    return Template(name=name, path=file_path, metadata=metadata, body=body)


def split_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    if not raw.startswith("---\n"):
        return {}, raw

    marker = "\n---\n"
    index = raw.find(marker, 4)
    if index == -1:
        raise TemplateError("template frontmatter is not closed")

    header = raw[4:index]
    body = raw[index + len(marker) :]
    metadata = yaml.safe_load(header) or {}
    if not isinstance(metadata, dict):
        raise TemplateError("template frontmatter must be a YAML object")
    return metadata, body


def parse_vars(var_items: list[str], vars_file: str | None = None) -> dict[str, Any]:
    vars_map: dict[str, Any] = {}
    if vars_file:
        payload = json.loads(Path(vars_file).read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise TemplateError("vars file must contain a JSON object")
        vars_map.update(payload)

    for item in var_items:
        if "=" not in item:
            raise TemplateError(f"invalid --var format: {item} (expected key=value)")
        key, value = item.split("=", 1)
        vars_map[key] = _coerce_value(value)
    return vars_map


def render_template(template: Template, variables: dict[str, Any]) -> tuple[str, list[str]]:
    rendered = _render_section(template.body, variables)
    warnings = []
    unresolved = sorted(set(re.findall(r"{{\s*([\w\.]+)\s*}}", rendered)))
    if unresolved:
        warnings.append("unresolved variables: " + ", ".join(unresolved))
    return rendered, warnings


def render_text(text: str, variables: dict[str, Any]) -> str:
    return _render_section(text, variables)


def validate_template(template: Template, variables: dict[str, Any] | None = None) -> list[str]:
    errors: list[str] = []
    variables = variables or {}

    body, warnings = render_template(template, variables)
    errors.extend(warnings)

    if template.path.suffix in {".html", ".htm"} or "<html" in body.lower() or "</" in body:
        parser = _HTMLValidator()
        parser.feed(body)
        if parser.stack:
            errors.append("unclosed tags: " + ", ".join(parser.stack))
        errors.extend(parser.errors)

    return errors


def create_template(name: str, subject: str, from_address: str, body: str, path: str | None = None) -> Path:
    directory = template_dir(path)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{name}.hbs"
    content = (
        "---\n"
        f"subject: {subject}\n"
        f"from: {from_address}\n"
        "---\n"
        f"{body}\n"
    )
    target.write_text(content, encoding="utf-8")
    return target


def _render_section(text: str, context: dict[str, Any]) -> str:
    text = _render_each(text, context)
    text = _render_if(text, context)
    return _render_vars(text, context)


def _render_each(text: str, context: dict[str, Any]) -> str:
    pattern = re.compile(r"{{#each\s+([\w\.]+)}}(.*?){{/each}}", re.DOTALL)
    while True:
        match = pattern.search(text)
        if not match:
            break
        key = match.group(1)
        block = match.group(2)
        value = _resolve(context, key)
        rendered = ""
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                child = dict(context)
                child["this"] = item
                if isinstance(item, dict):
                    child.update(item)
                parts.append(_render_section(block, child))
            rendered = "".join(parts)
        text = text[: match.start()] + rendered + text[match.end() :]
    return text


def _render_if(text: str, context: dict[str, Any]) -> str:
    pattern = re.compile(r"{{#if\s+([\w\.]+)}}(.*?)(?:{{else}}(.*?))?{{/if}}", re.DOTALL)
    while True:
        match = pattern.search(text)
        if not match:
            break
        key = match.group(1)
        true_block = match.group(2) or ""
        false_block = match.group(3) or ""
        condition = bool(_resolve(context, key))
        chosen = true_block if condition else false_block
        rendered = _render_section(chosen, context)
        text = text[: match.start()] + rendered + text[match.end() :]
    return text


def _render_vars(text: str, context: dict[str, Any]) -> str:
    pattern = re.compile(r"{{\s*([\w\.]+)\s*}}")

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        value = _resolve(context, key)
        if value is None:
            return match.group(0)
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)

    return pattern.sub(replace, text)


def _resolve(context: dict[str, Any], key: str) -> Any:
    current: Any = context
    for part in key.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        return None
    return current


def _coerce_value(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if lowered in {"null", "none"}:
        return None
    try:
        if "." in value:
            return float(value)
        return int(value)
    except ValueError:
        return value
