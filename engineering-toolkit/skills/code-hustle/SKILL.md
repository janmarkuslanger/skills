---
name: code-hustle
description: Autonomous, unattended pass over GitHub repositories that turns open issues labelled `claude` into pull requests and addresses review comments on open pull requests, then reports what it did. Built for scheduled/unattended runs where no human is present to approve steps — it acts within fixed per-run limits instead of asking. Use this from a scheduled task or routine after the caller has determined the set of target repositories (e.g. all repos a given owner can push to, or a named owner list). Not for interactive, human-in-the-loop work on a single issue or PR — use `resolve-github-issues` or `address-pr-comments` for that.
---

# Code hustle

Runs two loops over a caller-provided set of GitHub repositories, **unattended**:
issues labelled `claude` become pull requests, and review comments on open pull
requests get addressed. It is the autonomous counterpart to the interactive
`resolve-github-issues` and `address-pr-comments` skills: there is no human to
approve anything mid-run, so instead of approval gates it works within strict
per-run limits and reports honestly at the end.

## Scope comes from the caller

This skill does **not** discover repositories itself. The caller (a scheduled
task or routine) determines the target set — all repos a given owner can push
to, a named owner list, an explicit repo list — and hands it over. Work only
those repositories.

For every target repository, before touching it:

- Confirm push access: `gh api repos/<owner>/<repo> --jq '.permissions.push'`
  must be `true`. Skip and note it otherwise.
- Skip archived repos (`.archived == true`) and forks you don't own.
- If there is no local checkout, clone it to a scratch directory; otherwise use
  the existing one and bring it up to date with its remote before branching.

Confirm GitHub access first (`gh auth status` or a GitHub MCP connector). If you
have none, stop and say so in one sentence.

## Ground rules

- Each repository sets its own rules. Before touching code, read whatever the
  repository provides: `CLAUDE.md`, `AGENTS.md`, `CONTRIBUTING.md`, ADRs. Follow
  them over your own habits.
- Never state a table name, column, config key, function signature or CLI flag
  from memory — open the file first.
- Never invent verification results. If you could not run a check, say exactly
  that.
- Discover each repository's verification commands rather than assuming them:
  `Taskfile.yml`, `Makefile`, `package.json` scripts, `pyproject.toml`, CI
  workflow files. Run lint and the affected tests.
- **Per-run limits, across all repositories combined:** at most 3 issues and 5
  pull requests, and no more than 2 items per repository. The rest waits for the
  next run.
- Branch names mirror the issue: `<issue-number>-<slugified-issue-title>`, e.g.
  issue #42 "Fix silver run scope filter" becomes `42-fix-silver-run-scope-filter`.
  Lowercase, non-alphanumerics collapsed to single hyphens, truncated at 60
  characters.
- **Unattended means no approval gates and no questions.** Act within these
  rules and the limits above; do not wait for a human. But never merge a PR,
  never force-push, and never push to a shared or default branch — this skill
  only creates topic branches, opens PRs, and pushes to existing PR branches.

## Part 1 — Issues into pull requests

For each open issue labelled `claude` in the target repositories (up to the
limits):

1. Skip the issue if its branch already has an open pull request.
2. Create the branch from that repository's default branch using the naming
   scheme above.
3. Read the relevant code, implement the smallest correct change, and add or
   extend the matching tests.
4. Verify with the repository's own lint and test commands. Document honestly
   whatever you could not run.
5. Open a pull request against the default branch. Title is the issue title. The
   body states what changed and why, which verification ran with which result,
   what remains unverified, and `Closes #<number>`.
6. Swap the issue's `claude` label for `claude-done`. If `claude-done` doesn't
   exist in that repository, create it.
7. If no change was produced, open no pull request. Comment on the issue
   explaining why and leave the label untouched.

## Part 2 — Review comments on open pull requests

For each open pull request in the target repositories (up to the limits):

1. Collect both conversation comments and inline review comments.
2. A comment counts as **unaddressed** if no reply to it carries the marker
   `<!-- claude-bot:addressed -->`. Ignore your own comments and pure bot noise
   (CI/deploy status, automated summaries). Comments that are only praise or
   small talk get a reply but no code change.
3. For each pull request with unaddressed comments, check out its head branch
   and read the diff against the default branch.
4. Work through the comments, deciding deliberately which of three cases applies:
   - **Change request** — implement it, one commit per comment.
   - **Question** — answer it, change no code.
   - **Reasoned disagreement** — do not implement it, explain why. You are
     allowed to push back; do it factually, citing concrete code or a documented
     decision.
5. Verify as in Part 1, then push to the pull request branch.
6. Reply to **every** comment, including the ones you did not implement. Reply in
   the comment's own thread where the tooling allows it, otherwise as a pull
   request comment quoting the location as `file:line`. Each reply states:
   - the outcome: implemented / answered / deliberately not implemented
   - the detail: which file, which change, which commit — or the reasoning
   - the marker `<!-- claude-bot:addressed -->` at the end

## Final report

Summarise in prose, grouped by repository: which issues became which pull
requests, which pull requests received comment fixes, what you deliberately did
not implement, which repositories were skipped and why, and what failed. If a
run found nothing to do, "nothing to do" is the complete answer.
