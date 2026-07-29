#!/usr/bin/env python3
"""Fetch unresolved review threads on a GitHub PR, and reply to them.

Uses the `gh` CLI for auth and transport, so it works anywhere `gh auth status`
is happy. Stdlib only.

    python3 pr_threads.py list 482
    python3 pr_threads.py list 482 --repo janmarkuslanger/joviva-commerce
    python3 pr_threads.py list 482 --all          # include resolved threads
    python3 pr_threads.py reply PRRT_kwDOA... "Fixed in a3f9c21."
"""

import argparse
import json
import subprocess
import sys

LIST_QUERY = """
query($owner: String!, $repo: String!, $pr: Int!, $cursor: String) {
  repository(owner: $owner, name: $repo) {
    pullRequest(number: $pr) {
      title
      headRefName
      baseRefName
      reviewThreads(first: 50, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          id
          isResolved
          isOutdated
          path
          line
          originalLine
          comments(first: 50) {
            nodes {
              author { login }
              body
              createdAt
              url
            }
          }
        }
      }
    }
  }
}
"""

REPLY_MUTATION = """
mutation($threadId: ID!, $body: String!) {
  addPullRequestReviewThreadReply(
    input: { pullRequestReviewThreadId: $threadId, body: $body }
  ) {
    comment { url }
  }
}
"""


def gh(args, **kwargs):
    """Run a gh command, exiting with a readable message on failure."""
    try:
        proc = subprocess.run(
            ["gh"] + args, capture_output=True, text=True, check=False, **kwargs
        )
    except FileNotFoundError:
        sys.exit("gh CLI not found. Install it, or run this where gh is available.")
    if proc.returncode != 0:
        sys.exit(f"gh failed: {(proc.stderr or proc.stdout).strip()}")
    return proc.stdout


def graphql(query, **variables):
    args = ["api", "graphql", "-f", f"query={query}"]
    for key, value in variables.items():
        # -F coerces ints/bools; -f keeps strings as strings.
        flag = "-F" if isinstance(value, (int, bool)) else "-f"
        args += [flag, f"{key}={value}"]
    payload = json.loads(gh(args))
    if payload.get("errors"):
        sys.exit("GraphQL error: " + json.dumps(payload["errors"], indent=2))
    return payload["data"]


def resolve_repo(repo_flag):
    if repo_flag:
        if "/" not in repo_flag:
            sys.exit("--repo must look like owner/name")
        owner, _, name = repo_flag.partition("/")
        return owner, name
    info = json.loads(gh(["repo", "view", "--json", "owner,name"]))
    return info["owner"]["login"], info["name"]


def cmd_list(args):
    owner, name = resolve_repo(args.repo)
    threads, cursor, meta = [], None, {}

    while True:
        data = graphql(LIST_QUERY, owner=owner, repo=name, pr=args.pr, cursor=cursor or "")
        pull_request = data["repository"]["pullRequest"]
        if pull_request is None:
            sys.exit(f"PR #{args.pr} not found in {owner}/{name}")
        meta = {
            "repo": f"{owner}/{name}",
            "pr": args.pr,
            "title": pull_request["title"],
            "head_branch": pull_request["headRefName"],
            "base_branch": pull_request["baseRefName"],
        }
        block = pull_request["reviewThreads"]
        threads.extend(block["nodes"])
        if not block["pageInfo"]["hasNextPage"]:
            break
        cursor = block["pageInfo"]["endCursor"]

    if not args.all:
        threads = [t for t in threads if not t["isResolved"]]

    out = []
    for thread in threads:
        comments = [
            {
                "author": (c["author"] or {}).get("login", "ghost"),
                "body": c["body"],
                "created_at": c["createdAt"],
                "url": c["url"],
            }
            for c in thread["comments"]["nodes"]
        ]
        out.append(
            {
                "thread_id": thread["id"],
                "path": thread["path"],
                "line": thread["line"] or thread["originalLine"],
                "is_resolved": thread["isResolved"],
                "is_outdated": thread["isOutdated"],
                "comments": comments,
            }
        )

    print(json.dumps({**meta, "thread_count": len(out), "threads": out}, indent=2))


def cmd_reply(args):
    body = args.body.strip()
    if not body:
        sys.exit("Reply body is empty.")
    data = graphql(REPLY_MUTATION, threadId=args.thread_id, body=body)
    print(data["addPullRequestReviewThreadReply"]["comment"]["url"])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="list review threads as JSON")
    p_list.add_argument("pr", type=int)
    p_list.add_argument("--repo", help="owner/name (default: inferred from cwd)")
    p_list.add_argument("--all", action="store_true", help="include resolved threads")
    p_list.set_defaults(func=cmd_list)

    p_reply = sub.add_parser("reply", help="post a reply to one review thread")
    p_reply.add_argument("thread_id")
    p_reply.add_argument("body")
    p_reply.set_defaults(func=cmd_reply)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
