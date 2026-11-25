# Claude skills

Personal [Claude Code skills](https://docs.claude.com/en/docs/claude-code/skills) for the craft
of software work: writing a ticket, a merge request description, a review and an explanation
in one personal style, independent of the company or the repository.

| Skill | What it does |
| --- | --- |
| `qubit-jira-ticket` | cuts a request into vertical, ready tickets and writes each: what is wrong and what must be true afterwards, never the implementation |
| `qubit-merge-request` | writes a layered MR description: change, design, where to look, how to try it |
| `qubit-code-review` | reviews code changes with independent Claude and codex reviewers, checks every claim, publishes a bilingual report; re-reviews the posted comments once the author answered |
| `qubit-code-review-response` | answers a review of one's own change: checks every reviewer claim, fixes what the user picks, replies in every thread |
| `qubit-explanation-page` | explains a topic or a change as a page with diagrams and details per paragraph |

General working rules that are not skills live in [global/](global/), for example
[worktree naming](global/worktree-naming.md). The personal `~/.claude/CLAUDE.md` imports
them with `@~/.claude/skills/global/<file>.md` and keeps the environment's values beside
the import.

The [status line](statusline/statusline.sh) shows folder, branch, context, model and the
5-hour and 7-day limits. Link it as `~/.claude/statusline.sh`, the path the `statusLine`
setting runs. Ticket links to the tracker come from a local, untracked
`~/.claude/statusline.local.env`; the script's header shows its format.

## Principles

- **General, not tied to a company.** A rule here must hold in any team. The values and
  procedures of one environment (URLs, ticket keys, secret files, repository commands) live in
  a local profile, never in a skill: see [_profiles/README.md](_profiles/README.md).
- **Absorb good practice.** A better practice seen elsewhere (in a colleague's work, a
  standard, a tool) goes into the skill in its general form, under the name it is known by.
- **Change on evidence.** Each round of changes rests on a real run, a replay or a cited
  standard.

## Setup

Clone into `~/.claude/skills`, copy `_profiles/example/` to `_profiles/<name>/` and fill it
in. Without a profile the skills run with general defaults and say what they skipped.
