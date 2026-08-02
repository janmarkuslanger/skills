---
name: resolve-github-issues
description: Fetch a GitHub repo's open issues (optionally filtered by label or milestone), plan and implement a fix for each in an isolated git worktree, get an independent review per issue, then open one PR per issue after a single consolidated approval. Use this when the user wants to work through a GitHub issue backlog in bulk, e.g. "resolve the open issues in this repo", "create PRs for everything labeled bug", "work through the Q3 milestone", or "clear the issue backlog". Not for a single issue picked by the user — handle that directly instead of invoking this bulk flow.
disable-model-invocation: true
---

# Resolve GitHub issues

Turns a batch of open GitHub issues into reviewed, ready-to-open pull requests — one PR per issue, each implemented and reviewed independently. The expensive, hard-to-reverse step is opening PRs and pushing branches, so that step never happens until the user has seen every plan, every diff summary, and every review verdict at once and approved in one shot.

## Workflow

```
1. Resolve scope  →  2. Fetch open issues  →  [size gate]
  →  3. Workflow: per issue → plan+complexity → implement (isolated worktree) → independent review
  →  4. Consolidated summary  →  [APPROVAL]  →  5. Push + open PRs  →  6. Wrap up
```

## 1. Resolve scope

Default to the repo the user is already in (`gh repo view` to confirm), unless they name another one (`owner/repo`). If they mentioned a label or milestone ("everything labeled bug", "the Q3 milestone"), carry that as a filter. Don't guess a label/milestone the user didn't mention — an unfiltered run is a fine default.

## 2. Fetch open issues

```bash
gh issue list --repo <owner/repo> --state open --json number,title,body,url,labels,milestone \
  [--label <label>] [--milestone <milestone>]
```

## Size gate

Cap a single run at 5 issues — more than that means 5+ concurrent worktrees and subagent chains, expensive and hard to review in one sitting. If more than 5 issues match:

1. List all matched issues (number, title, labels, milestone).
2. Ask the user how to narrow it down to 5:
   - **Pick explicitly** — they name the issues to run this round.
   - **Prioritize automatically** — they name a sort (a priority label, oldest first, nearest milestone due date, ...) and you take the top 5 by that sort.
3. Ask every time the count is exceeded; don't reuse a strategy from a previous run without confirming it still applies — priorities shift.

The rest stay open on GitHub, untouched, for a future run.

## 3. Run the per-issue pipeline

Build `args.issues` as an array of `{number, title, body}` from the fetched issues, then invoke the Workflow tool with the script below. Each issue runs independently through plan → implement → review; nothing here pushes or opens anything.

```js
export const meta = {
  name: 'resolve-github-issues',
  description: 'Plan, implement, and review a fix for each open GitHub issue in its own git worktree',
  phases: [
    { title: 'Plan' },
    { title: 'Implement' },
    { title: 'Review' },
  ],
}

const PLAN_SCHEMA = {
  type: 'object',
  required: ['complexity', 'plan'],
  properties: {
    complexity: { type: 'string', enum: ['low', 'medium', 'high'] },
    plan: { type: 'string' },
    filesTouched: { type: 'array', items: { type: 'string' } },
  },
}

const IMPLEMENT_SCHEMA = {
  type: 'object',
  required: ['branch', 'worktreePath', 'commits', 'testsRun', 'testsPassed', 'summary'],
  properties: {
    branch: { type: 'string' },
    worktreePath: { type: 'string' },
    commits: { type: 'array', items: { type: 'string' } },
    testsRun: { type: 'boolean' },
    testsPassed: { type: 'boolean' },
    summary: { type: 'string' },
  },
}

const REVIEW_SCHEMA = {
  type: 'object',
  required: ['verdict', 'findings'],
  properties: {
    verdict: { type: 'string', enum: ['pass', 'concerns'] },
    findings: { type: 'array', items: { type: 'string' } },
  },
}

function modelFor(complexity) {
  if (complexity === 'low') return { model: 'haiku' }
  if (complexity === 'high') return { effort: 'high' }
  return {}
}

// Every stage returns a record for the issue and never throws past itself: agent()
// yields null on skip/terminal error, so each stage normalises null-or-throw into a
// `failed` marker and later stages pass a failed record straight through. That way no
// issue silently disappears from the final results — the summary can list what fell over.
const results = await pipeline(
  args.issues,
  issue => agent(
    `Read GitHub issue #${issue.number} — "${issue.title}".\n\nBody:\n${issue.body}\n\n` +
    `Investigate the codebase and produce a fix plan. Rate implementation complexity as low ` +
    `(trivial, single file, no design decisions), medium (a few files, no architectural change), ` +
    `or high (touches a shared contract, needs a design call, or spans 3+ modules). ` +
    `List the files you expect to touch.`,
    { phase: 'Plan', schema: PLAN_SCHEMA, label: `plan:#${issue.number}` }
  )
    .then(plan => plan ? { issue, plan } : { issue, failed: { stage: 'plan' } })
    .catch(err => ({ issue, failed: { stage: 'plan', error: String(err) } })),
  prev => {
    if (prev.failed) return prev
    const { issue, plan } = prev
    return agent(
      `Implement this plan for GitHub issue #${issue.number} — "${issue.title}":\n\n${plan.plan}\n\n` +
      `Create a branch named issue/${issue.number}-<slug>. Follow the repo's existing ` +
      `commit style and conventions. Write at least one test for the change — if the project genuinely ` +
      `has no test infrastructure, say so in the summary instead of skipping silently. Run the project's ` +
      `tests and lint before committing. Commit your work but do NOT push and do NOT open a PR.`,
      { phase: 'Implement', schema: IMPLEMENT_SCHEMA, label: `implement:#${issue.number}`, isolation: 'worktree', ...modelFor(plan.complexity) }
    )
      .then(impl => impl ? { issue, plan, impl } : { issue, plan, failed: { stage: 'implement' } })
      .catch(err => ({ issue, plan, failed: { stage: 'implement', error: String(err) } }))
  },
  prev => {
    if (prev.failed) return prev
    const { issue, plan, impl } = prev
    return agent(
      `Independently review the changes on branch ${impl.branch} at ${impl.worktreePath} (run git diff there). ` +
      `Look for correctness bugs, missed edge cases, and anything that contradicts the original issue ` +
      `"${issue.title}". Do not fix anything — only report findings.`,
      { phase: 'Review', schema: REVIEW_SCHEMA, label: `review:#${issue.number}`, effort: 'high' }
    )
      .then(review => review ? { issue, plan, impl, review } : { issue, plan, impl, failed: { stage: 'review' } })
      .catch(err => ({ issue, plan, impl, failed: { stage: 'review', error: String(err) } }))
  }
)

return results.filter(Boolean)
```

Complexity → model is a cost lever, not a quality one: `low` drops to a cheaper model, `high` bumps reasoning effort, `medium` inherits the session default. The review stage always runs at `high` effort regardless of implementation complexity — it's the safety net, so it doesn't get cheaper just because the fix looked simple.

## 4. Consolidated summary

One table, all issues at once — this is the only place the user needs to look before deciding:

```
| Issue | Complexity | Tests | Review | Branch |
|-------|-----------|-------|--------|--------|
| #142 | low | pass | pass | issue/142-fix-null-check |
| #156 | high | pass | concerns: assumes UTC, prod runs in CET | issue/156-schedule-fix |
```

Under the table, one line per issue with `concerns` — quote the finding, don't just flag it. Recommend holding back anything with `concerns` or failing tests; recommend proceeding on the rest. The user decides, not the workflow.

Any result carrying a `failed` marker (a stage that returned null or threw — a skipped agent, a terminal API error, no worktree produced) never reached a reviewable diff. List these separately below the table — issue number and which stage failed — so a dropped issue is visible, not silently missing. They are not push candidates.

## 5. Approval, then push and open PRs

Ask once, for the whole batch: which issues to push (all / all-except-flagged / an explicit subset).

Before pushing each approved issue, confirm its worktree still exists and holds the committed branch — the workflow's isolated worktrees are the only place the commits live, and a cleaned-up or reused path would mean pushing the wrong thing or nothing:

```bash
git -C <worktreePath> rev-parse --abbrev-ref HEAD   # must print <branch>
```

If the path is gone or on a different branch, stop for that issue and report it — do not improvise a branch or fabricate a push. Then, for each approved issue whose worktree checks out:

```bash
git -C <worktreePath> push -u origin <branch>
gh pr create --repo <owner/repo> --title "#<number>: <title>" --body "<plan summary + review verdict>

Closes #<number>"
```

`Closes #<number>` in the body auto-links the PR to the issue and closes it on merge — no separate comment needed.

Issues the user held back keep their branch and worktree locally, untouched — mention the worktree path so they can inspect or resume by hand. Don't delete worktrees or branches without being asked; that's their call.

## 6. Wrap up

Short summary: PRs opened (with links), issues held back and why, any test or lint failures surfaced during implementation. If review found `concerns` on something that got pushed anyway, restate that plainly — it's the one thing most likely to bite later.

## Guardrails

- **Never push or open a PR before the consolidated approval in step 5.** Steps 3–4 only read, plan, and write to isolated worktrees.
- **No fabrication.** If `gh` auth fails, say so and stop — don't guess at issue content or PR state.
- **Don't merge PRs, don't force-push, don't touch a shared/default branch.** This skill only creates topic branches and PRs.
- **Respect the size gate.** Don't silently run more than 5 issues at once; ask first.
