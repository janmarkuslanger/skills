---
name: address-pr-comments
description: Work through unresolved review comments on a GitHub pull request — triage them by severity, agree a fix plan with the user, implement one commit per comment, push, and reply to each reviewer. Use this whenever the user references a PR by number and wants its feedback handled, e.g. "address the PR 482", "work through the review comments on 217", "the reviewers left notes on my PR, can you sort them out", or when they ask what still needs doing before a PR can merge. Also use it when they just paste a GitHub PR URL and ask you to deal with the feedback.
---

# Address PR comments

Turn a pile of review feedback into commits and replies, without ever surprising the user by pushing or posting something they haven't seen.

The whole point of this skill is the approval gates. Review feedback is a conversation with the user's colleagues — a wrong fix or a clumsy reply costs them credibility, and unlike a local edit it can't be undone quietly. So the work splits into two halves: figure out what to do and get sign-off, then execute. Never blur them.

## Workflow

```
1. Fetch unresolved threads  →  2. Triage table  →  3. Fix plan  →  [APPROVAL]
   →  4. Implement (one commit per comment)  →  5. Push  →  6. Draft replies  →  [APPROVAL]  →  7. Post
```

## 1. Fetch the unresolved threads

Only unresolved review threads are in scope. Resolved ones have been dealt with already, and general PR-level comments aren't review feedback on code — pulling them in creates noise and makes the triage list untrustworthy.

```bash
python3 scripts/pr_threads.py list <PR_NUMBER>
```

Run it from inside the repo so `gh` can infer the remote; pass `--repo owner/name` if you're elsewhere. It returns JSON: one entry per unresolved thread with `thread_id`, `path`, `line`, `is_outdated`, and the comments in order (author, body, url).

Then get onto the right branch:

```bash
git status --porcelain          # bail out to the user if the tree is dirty
gh pr checkout <PR_NUMBER>      # skip if already on the head branch
```

If the working tree has uncommitted changes, stop and ask. Checking out over someone's work in progress is the kind of thing that loses an afternoon.

Read the code around each comment before triaging. A reviewer's one-liner ("this'll blow up on empty input") only makes sense next to the actual function, and severity is impossible to judge from the comment text alone.

## 2. Triage table

Present every thread in one table, in severity order (BLOCKER first):

```
| # | Author | What it's about | Severity |
|---|--------|-----------------|----------|
| 1 | @mlehmann | Cart total is computed before tax, so discounts apply to the gross amount | BLOCKER |
| 2 | @skoch | No error handling if the SQS receive call times out | HIGH |
| 3 | @mlehmann | Prefers `orderId` over `order_id` for consistency with the rest of the module | LOW |
```

One sentence per comment. Describe the *substance*, not the wording — "asks about the retry count" is useless, "questions whether 3 retries is enough for the Rhiem SOAP endpoint" is what the user needs to decide with.

Severity is about consequence, not tone. A politely-phrased comment can be a blocker and a blunt one can be a nit:

- **BLOCKER** — shouldn't merge like this: incorrect behaviour, security or data-loss risk, breaks a published contract, will fail in production
- **HIGH** — a real problem worth fixing in this PR: missing error handling, a design choice that'll cause pain later, an untested path
- **LOW** — naming, style, phrasing, personal preference, optional refactors

If a thread is outdated (the code moved under it), flag that in the table — it may already be fixed, and the right response is a reply rather than a commit.

## 3. Fix plan

Under the table, one short block per comment:

```
**1 — @mlehmann, tax before discount** (BLOCKER)
Move the discount application after `calculateTax()` in `cart-totals.ts` and add a case to
the totals test for a discounted, taxed cart. He's right: currently a 10% discount comes off
the gross, so we under-charge tax on every discounted order — that's an invoicing problem,
not just a rounding one.
```

Two things per block: what you'd change, and why it's worth doing. The "why" is what the user is actually approving — they know the codebase and can tell instantly whether the reasoning is sound, which they can't do from a diff summary.

Not every comment deserves a fix, and pretending otherwise is worse than useless. Three other verdicts are legitimate:

- **Push back** — the reviewer is mistaken or the tradeoff was deliberate. Say so, with the reasoning. The action is a reply, not a commit.
- **Answer only** — the comment is a question. Draft the answer instead of a change.
- **Out of scope** — a fair point, but it belongs in its own issue. Say what the follow-up would be.

Label these clearly so the user sees at a glance which comments will produce commits.

Then stop. Ask for approval, and make it easy to give partial approval — "all good except 3, skip that one" or "on 2 do X instead" should be enough to proceed. Don't touch a file until you have an answer.

## 4. Implement — one commit per comment

One commit per comment, so each is reviewable on its own and any single fix can be reverted without unpicking the others.

Match the repo's existing commit style — read `git log --oneline -20` first. Most repos here use Conventional Commits:

```
fix(cart): apply discount after tax calculation

Addresses review comment from @mlehmann.
```

Work through the approved items in severity order. Run whatever the repo uses for tests and lint before committing each one — pushing a fix that fails CI turns one review round into two. If a fix turns out to be bigger than the plan suggested, stop and say so rather than quietly expanding scope.

## 5. Push

```bash
git push
```

Then note the commit SHAs — the replies reference them.

## 6. Draft replies, one per comment

Show every draft reply at once, numbered to match the triage table, and wait for approval on each. Presenting them together saves a round trip per comment; the user can approve some, edit others.

Replies are short. One or two sentences. A reviewer scanning ten threads wants to know *what changed* and *where* — anything longer reads as defensive:

```
1 → "Good catch — discount now applies after tax, plus a test for the discounted+taxed case. a3f9c21"
2 → "Added a retry with backoff around the receive call. 7b2e440"
3 → "Renamed to orderId throughout. 91c4d0e"
```

For a push-back, be direct and give the reason, not a hedge:

```
4 → "Left this as-is — the lock TTL has to outlive the SOAP timeout (30s), otherwise a slow
     Rhiem response can release the lock mid-flight. Happy to revisit if you'd rather cap it lower."
```

Don't thank the reviewer in every reply, don't restate their comment back at them, and don't apologise. Include the short SHA where a commit fixed it.

Once approved:

```bash
python3 scripts/pr_threads.py reply <THREAD_ID> "<body>"
```

Leave threads unresolved. Marking your own feedback as resolved takes the decision away from the reviewer, and most teams treat it as theirs to close.

## 7. Wrap up

Short summary: commits pushed, replies posted, anything deferred to a follow-up issue, and whether CI is green. If something was skipped or pushed back on, say so explicitly — that's what determines whether the PR can merge.

## Notes

- **No `gh` auth** — if `gh auth status` fails, tell the user rather than trying to work around it with a raw token.
- **A comment you don't understand** — ask. Guessing at a reviewer's intent and committing the guess is the worst outcome here.
- **Very large reviews (20+ threads)** — triage everything, but suggest tackling BLOCKER and HIGH first and coming back for the nits, so the PR can move.
- **Merge conflicts on checkout** — surface them; don't attempt a resolution as part of this flow.
