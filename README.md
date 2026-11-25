# Claude dotfiles

My personal Claude Code setup, versioned in git so a new machine is set up by cloning:
skills, general working rules and a status line.

## Contents

### Skills

The [skills](https://docs.claude.com/en/docs/claude-code/skills) cover the craft of software
work: writing a ticket, a merge request description, a review and an explanation in one
personal style, independent of the company or the repository.

| Skill | What it does |
| --- | --- |
| [`qubit-jira-ticket`](qubit-jira-ticket/SKILL.md) | cuts a request into vertical, ready tickets and writes each: what is wrong and what must be true afterwards, never the implementation |
| [`qubit-merge-request`](qubit-merge-request/SKILL.md) | writes a layered MR description: change, design, where to look, how to try it |
| [`qubit-code-review`](qubit-code-review/SKILL.md) | reviews code changes with independent Claude and codex reviewers, checks every claim, publishes a bilingual report; re-reviews the posted comments once the author answered |
| [`qubit-code-review-response`](qubit-code-review-response/SKILL.md) | answers a review of one's own change: checks every reviewer claim, fixes what the user picks, replies in every thread |
| [`qubit-explanation-page`](qubit-explanation-page/SKILL.md) | explains a topic or a change as a page with diagrams and details per paragraph |

### Other files

| Path | What it is | How it is wired in |
| --- | --- | --- |
| [`global/worktree-naming.md`](global/worktree-naming.md) | rule for naming git worktree folders: `<TYPE>-<ticket>-<name>` | imported by `~/.claude/CLAUDE.md` with `@~/.claude/skills/global/worktree-naming.md`; the environment's values (ticket keys, branch names) stay beside the import |
| [`statusline/statusline.sh`](statusline/statusline.sh) | status line: folder, branch, context, model, 5-hour and 7-day limits | symlinked as `~/.claude/statusline.sh`, the path the `statusLine` setting runs; ticket links come from the untracked `~/.claude/statusline.local.env` (format in the script's header) |
| [`_profiles/`](_profiles/README.md) | the values of one environment (URLs, ticket keys, secret files, repository commands) and `profile.py`, which the skills ask for them | `_profiles/example/` is the template; a filled-in copy in `_profiles/<name>/` stays local and untracked |

## Principles

- **General, not tied to a company.** A rule here must hold in any team. The values and
  procedures of one environment live in a local profile, never in a skill.
- **Absorb good practice.** A better practice seen elsewhere (in a colleague's work, a
  standard, a tool) goes into the skill in its general form, under the name it is known by.
- **Change on evidence.** Each round of changes rests on a real run, a replay or a cited
  standard.

## Setup

```sh
git clone https://github.com/qubit-11/claude-dotfiles.git ~/.claude/skills
ln -s ~/.claude/skills/statusline/statusline.sh ~/.claude/statusline.sh
cp -R ~/.claude/skills/_profiles/example ~/.claude/skills/_profiles/<name>   # then fill it in
```

The folder name differs from the repository name on purpose: Claude Code loads personal
skills only from `~/.claude/skills`. Without a profile the skills run with general defaults
and say what they skipped.
