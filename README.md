# skills

Personal collection of Claude Code skills, published as a plugin marketplace.

## Install

```
/plugin marketplace add janmarkuslanger/skills
```

Then browse and install individual plugins via `/plugin`.

## Repository layout

```
.
├── .claude-plugin/
│   └── marketplace.json      # marketplace manifest, lists all plugins
├── engineering/              # engineering-category plugins
│   └── <plugin-name>/
│       ├── .claude-plugin/plugin.json
│       └── skills/<skill-name>/SKILL.md
├── web/                      # web-category plugins
│   └── <plugin-name>/
│       └── ...
├── tools/
│   └── validate_skills.py    # validator for marketplace + plugins + skills
└── .github/workflows/
    └── validate.yml          # CI: runs the validator on every push/PR
```

## Adding a plugin

1. Create a directory under the target category, e.g. `engineering/my-plugin/`.
2. Add `engineering/my-plugin/.claude-plugin/plugin.json`:

   ```json
   {
     "name": "my-plugin",
     "version": "0.1.0",
     "description": "One-line summary of what this plugin does."
   }
   ```

3. Add one or more skills under `engineering/my-plugin/skills/<skill-name>/SKILL.md`:

   ```markdown
   ---
   name: my-skill
   description: One-line summary of when Claude should invoke this skill.
   ---

   # My Skill

   Skill instructions go here.
   ```

4. Register the plugin in `.claude-plugin/marketplace.json` by appending to the
   `plugins` array:

   ```json
   {
     "name": "my-plugin",
     "source": "engineering/my-plugin",
     "category": "engineering"
   }
   ```

5. Run the validator locally:

   ```
   python3 tools/validate_skills.py
   ```

## Validation rules

- Marketplace manifest must have `name`, `owner`, and `plugins` fields.
- Every plugin listed in the manifest must resolve to a directory with a valid
  `plugin.json` (fields: `name`, `version`, `description`).
- Every `SKILL.md` must start with YAML frontmatter containing `name` and
  `description`.
- `name` fields must be kebab-case.
- `description` fields must not exceed 1024 characters.
