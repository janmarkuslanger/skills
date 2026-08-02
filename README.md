# skills

Personal collection of Claude Code skills, published as a plugin marketplace.

## Install

Add the marketplace once:

```
/plugin marketplace add janmarkuslanger/skills
```

Then either install a specific plugin:

```
/plugin install engineering-toolkit@skills
```

…or browse everything interactively with `/plugin`.

## Skills by category

### Engineering

**`engineering-toolkit`** — practical, day-to-day engineering tooling.

- **address-pr-comments** — Work through unresolved GitHub PR review comments: triage them by severity, agree a fix plan with the user, implement one commit per comment, push, and reply to each reviewer.
- **resolve-github-issues** — Fetch a repo's open GitHub issues (optionally by label/milestone), plan and implement a fix for each in an isolated worktree, get an independent review per issue, then open one PR per issue after a single consolidated approval.

## Repository layout

Plugins live at the repo root — one directory per plugin. Category is metadata
in `marketplace.json`, not a directory level.

```
.
├── .claude-plugin/
│   └── marketplace.json                    # marketplace manifest, lists all plugins
├── engineering-toolkit/                    # a plugin
│   ├── .claude-plugin/plugin.json
│   └── skills/<skill-name>/SKILL.md
├── tools/
│   └── validate_skills.py                  # validator for marketplace + plugins + skills
└── .github/workflows/
    └── validate.yml                        # CI: runs the validator on every push/PR
```

## Adding a plugin

1. Create a plugin directory at the repo root, e.g. `web-toolkit/`.
2. Add `web-toolkit/.claude-plugin/plugin.json`:

   ```json
   {
     "name": "web-toolkit",
     "version": "0.1.0",
     "description": "One-line summary of what this plugin does."
   }
   ```

3. Add one or more skills under `web-toolkit/skills/<skill-name>/SKILL.md`:

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
     "name": "web-toolkit",
     "source": "web-toolkit",
     "category": "web"
   }
   ```

5. Add an entry to the "Skills by category" section of this README under the
   matching category (create the category heading if it's new).

6. Run the validator locally:

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
