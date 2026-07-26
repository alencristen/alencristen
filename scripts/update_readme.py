#!/usr/bin/env python3
"""Refresh the stats block in README.md from the GitHub GraphQL API.

Runs in CI (GITHUB_TOKEN provided by Actions) and locally
(GITHUB_TOKEN=$(gh auth token) python3 scripts/update_readme.py).
"""
import datetime
import json
import os
import sys
import urllib.request

LOGIN = "alencristen"
README = os.path.join(os.path.dirname(__file__), "..", "README.md")
START = "<!-- STATS:START -->"
END = "<!-- STATS:END -->"

QUERY = """
query($login: String!, $prSearch: String!, $mergedSearch: String!) {
  user(login: $login) {
    followers { totalCount }
    repositories(privacy: PUBLIC, ownerAffiliations: OWNER, first: 100) {
      totalCount
      nodes { stargazerCount }
    }
    contributionsCollection {
      totalCommitContributions
      totalIssueContributions
      totalPullRequestReviewContributions
      contributionCalendar { totalContributions }
    }
  }
  prs: search(query: $prSearch, type: ISSUE) { issueCount }
  merged: search(query: $mergedSearch, type: ISSUE) { issueCount }
}
"""


def fetch():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("error: set GITHUB_TOKEN")
    body = json.dumps({
        "query": QUERY,
        "variables": {
            "login": LOGIN,
            "prSearch": f"author:{LOGIN} is:pr",
            "mergedSearch": f"author:{LOGIN} is:pr is:merged",
        },
    }).encode()
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=body,
        headers={
            "Authorization": f"bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": LOGIN,
        },
    )
    with urllib.request.urlopen(req) as resp:
        data = json.load(resp)
    if data.get("errors"):
        sys.exit(f"graphql errors: {data['errors']}")
    return data["data"]


def line(label, value, width=58):
    dots = "." * (width - len(label) - len(str(value)) - 4)
    return f"  {label} {dots} {value}"


def bar(ratio, slots=24):
    filled = round(ratio * slots)
    return "#" * filled + "-" * (slots - filled)


def render(d):
    user = d["user"]
    contrib = user["contributionsCollection"]
    prs = d["prs"]["issueCount"]
    merged = d["merged"]["issueCount"]
    stars = sum(n["stargazerCount"] for n in user["repositories"]["nodes"])
    ratio = merged / prs if prs else 0.0
    today = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")
    rows = [
        f"$ gh stats --user {LOGIN}" + f"updated {today} utc".rjust(58 - 18 - len(LOGIN)),
        "",
        line("pull requests", f"{prs} opened / {merged} merged"),
        line("merge bar", f"[{bar(ratio)}] {round(ratio * 100)}%"),
        line("contributions (12mo)", contrib["contributionCalendar"]["totalContributions"]),
        line("commits (12mo)", contrib["totalCommitContributions"]),
        line("issues (12mo)", contrib["totalIssueContributions"]),
        line("pr reviews (12mo)", contrib["totalPullRequestReviewContributions"]),
        line("stars earned", stars),
        line("followers", user["followers"]["totalCount"]),
        line("public repos", user["repositories"]["totalCount"]),
    ]
    return "\n".join(rows)


def main():
    with open(README, encoding="utf-8") as f:
        readme = f.read()
    if START not in readme or END not in readme:
        sys.exit("error: stats markers not found in README.md")
    head, rest = readme.split(START, 1)
    _, tail = rest.split(END, 1)
    block = f"{START}\n```text\n{render(fetch())}\n```\n{END}"
    with open(README, "w", encoding="utf-8") as f:
        f.write(head + block + tail)
    print("README.md stats refreshed")


if __name__ == "__main__":
    main()
