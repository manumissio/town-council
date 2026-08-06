# Issue Tracker: GitHub

Issues and specifications live in this repository's GitHub Issues. Use the `gh` CLI from the repository checkout.

## Operations

- Create: `gh issue create --title "..." --body "..."`
- Read: `gh issue view <number> --comments`
- List: `gh issue list --state open`
- Comment: `gh issue comment <number> --body "..."`
- Label: `gh issue edit <number> --add-label "..."`
- Close: `gh issue close <number> --comment "..."`

Infer the repository from `git remote -v`.

## Pull Requests as a Triage Surface

PRs as a request surface: no.

A bare `#<number>` may identify an issue or pull request because GitHub shares their number space. Check with `gh pr view <number>` and fall back to `gh issue view <number>`.

## Skill Conventions

When a skill says "publish to the issue tracker," create a GitHub issue.

When a skill says "fetch the relevant ticket," read the GitHub issue and its comments.
