#!/usr/bin/env python3
"""Rewrite the GitHub stats line in profile/README.md.

Repos is the number of public repositories. Commits is the sum of
default-branch commits on those repositories, excluding forks.
"""

import json
import os
import sys
import urllib.request

ORG = os.environ.get("GITHUB_REPOSITORY_OWNER", "pretend-studio")
README = os.path.join(os.path.dirname(__file__), "..", "profile", "README.md")
W = 75
QUERY = """
query($login: String!, $cursor: String) {
  organization(login: $login) {
    repositories(privacy: PUBLIC, first: 100, after: $cursor) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        isFork
        defaultBranchRef {
          target {
            ... on Commit {
              history { totalCount }
            }
          }
        }
      }
    }
  }
}
"""


def field(label, value, width):
    text = f"{value:,}"
    left = label + " "
    right = " " + text
    gap = width - len(left) - len(right)
    if gap < 2:
        raise SystemExit(f"{label} {text} does not fit the stats row")
    return left + ("." * gap) + right


def stats_line(repos, commits):
    width = (W - 7) // 2
    row = "  . " + field("Repos:", repos, width) + " | " + field("Commits:", commits, width)
    if len(row) != W:
        raise SystemExit(f"stats line is {len(row)} characters, expected {W}")
    return row


def github_json(url, token, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "pretend-readme-stats",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def fetch_counts(token):
    repos = 0
    commits = 0
    cursor = None
    while True:
        payload = {"query": QUERY, "variables": {"login": ORG, "cursor": cursor}}
        body = github_json("https://api.github.com/graphql", token, payload)
        if body.get("errors"):
            raise SystemExit(body["errors"])
        page = body["data"]["organization"]["repositories"]
        repos = page["totalCount"]
        for node in page["nodes"]:
            if node["isFork"] or not node["defaultBranchRef"]:
                continue
            commits += node["defaultBranchRef"]["target"]["history"]["totalCount"]
        if not page["pageInfo"]["hasNextPage"]:
            return repos, commits
        cursor = page["pageInfo"]["endCursor"]


def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        raise SystemExit("Set GITHUB_TOKEN or GH_TOKEN")
    repos, commits = fetch_counts(token)
    line = stats_line(repos, commits)
    path = os.path.normpath(README)
    with open(path) as handle:
        original = handle.read()
    updated = []
    found = False
    for row in original.splitlines(keepends=True):
        if row.startswith("  . Repos:"):
            newline = "\n" if row.endswith("\n") else ""
            updated.append(line + newline)
            found = True
        else:
            updated.append(row)
    if not found:
        raise SystemExit("Could not find the Repos stats line in profile/README.md")
    text = "".join(updated)
    if text == original:
        print(f"unchanged: {repos} repos, {commits} commits")
        return
    with open(path, "w") as handle:
        handle.write(text)
    print(f"updated: {repos} repos, {commits} commits")


if __name__ == "__main__":
    main()
