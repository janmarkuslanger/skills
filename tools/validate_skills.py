#!/usr/bin/env python3
"""Validate marketplace.json, plugin.json, and SKILL.md files.

Checks:
- .claude-plugin/marketplace.json exists and is valid JSON with required fields.
- Every plugin listed in marketplace.json resolves to a directory containing
  .claude-plugin/plugin.json.
- Every plugin.json has required fields (name, version, description).
- Every SKILL.md inside a plugin has valid YAML frontmatter with required
  fields (name, description).
- Skill names are kebab-case; descriptions do not exceed 1024 characters.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_FILE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
KEBAB_CASE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
MAX_DESCRIPTION_LEN = 1024
REQUIRED_MARKETPLACE_FIELDS = ("name", "owner", "plugins")
REQUIRED_PLUGIN_FIELDS = ("name", "version", "description")
REQUIRED_SKILL_FIELDS = ("name", "description")
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)

    def fail(self, message: str) -> None:
        self.errors.append(message)

    def ok(self) -> bool:
        return not self.errors


def load_json(path: Path, report: Report) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        report.fail(f"{path}: file not found")
    except json.JSONDecodeError as exc:
        report.fail(f"{path}: invalid JSON ({exc})")
    return None


def parse_frontmatter(path: Path, report: Report) -> dict | None:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        report.fail(f"{path}: missing YAML frontmatter (must start with ---)")
        return None
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        report.fail(f"{path}: invalid YAML frontmatter ({exc})")
        return None
    if not isinstance(data, dict):
        report.fail(f"{path}: frontmatter must be a YAML mapping")
        return None
    return data


def check_required(path: Path, data: dict, fields: tuple[str, ...], report: Report) -> None:
    for name in fields:
        if name not in data or data[name] in (None, ""):
            report.fail(f"{path}: missing required field '{name}'")


def check_kebab_case(path: Path, value: str, field_name: str, report: Report) -> None:
    if not isinstance(value, str) or not KEBAB_CASE.match(value):
        report.fail(f"{path}: '{field_name}' must be kebab-case, got '{value}'")


def check_description(path: Path, value: str, report: Report) -> None:
    if isinstance(value, str) and len(value) > MAX_DESCRIPTION_LEN:
        report.fail(
            f"{path}: description exceeds {MAX_DESCRIPTION_LEN} chars ({len(value)})"
        )


def validate_skill_file(skill_md: Path, report: Report) -> None:
    data = parse_frontmatter(skill_md, report)
    if data is None:
        return
    check_required(skill_md, data, REQUIRED_SKILL_FIELDS, report)
    if "name" in data:
        check_kebab_case(skill_md, data["name"], "name", report)
    if "description" in data:
        check_description(skill_md, data["description"], report)


def validate_plugin_dir(plugin_dir: Path, report: Report) -> None:
    plugin_json = plugin_dir / ".claude-plugin" / "plugin.json"
    if not plugin_json.exists():
        report.fail(f"{plugin_dir}: missing .claude-plugin/plugin.json")
        return
    data = load_json(plugin_json, report)
    if data is None:
        return
    check_required(plugin_json, data, REQUIRED_PLUGIN_FIELDS, report)
    if "name" in data:
        check_kebab_case(plugin_json, data["name"], "name", report)
    if "description" in data:
        check_description(plugin_json, data["description"], report)

    skills_dir = plugin_dir / "skills"
    if skills_dir.is_dir():
        for skill_md in skills_dir.rglob("SKILL.md"):
            validate_skill_file(skill_md, report)


def validate_marketplace(report: Report) -> dict | None:
    data = load_json(MARKETPLACE_FILE, report)
    if data is None:
        return None
    check_required(MARKETPLACE_FILE, data, REQUIRED_MARKETPLACE_FIELDS, report)
    plugins = data.get("plugins", [])
    if not isinstance(plugins, list):
        report.fail(f"{MARKETPLACE_FILE}: 'plugins' must be an array")
        return data

    for entry in plugins:
        if not isinstance(entry, dict):
            report.fail(f"{MARKETPLACE_FILE}: plugin entry must be an object")
            continue
        source = entry.get("source")
        name = entry.get("name", "<unnamed>")
        if not source:
            report.fail(f"{MARKETPLACE_FILE}: plugin '{name}' missing 'source'")
            continue
        plugin_dir = (REPO_ROOT / source).resolve()
        try:
            plugin_dir.relative_to(REPO_ROOT)
        except ValueError:
            report.fail(
                f"{MARKETPLACE_FILE}: plugin '{name}' source '{source}' escapes repo root"
            )
            continue
        if not plugin_dir.is_dir():
            report.fail(
                f"{MARKETPLACE_FILE}: plugin '{name}' source '{source}' is not a directory"
            )
            continue
        validate_plugin_dir(plugin_dir, report)
    return data


def main() -> int:
    report = Report()
    validate_marketplace(report)

    if report.ok():
        print("OK: marketplace, plugins, and skills validated.")
        return 0

    print("Validation failed:", file=sys.stderr)
    for error in report.errors:
        print(f"  - {error}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
