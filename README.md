# Claude dotfiles

A personal Claude Code setup: skills, general working rules and a status line. It lives in
git, so a new computer is set up with one prompt.

## Setup

### 1. Set up the skills

Start Claude Code in any folder and give it this prompt:

```text
Set up https://github.com/qubit-11/claude-dotfiles following "Manual setup" in its README.
```

When it is done, restart Claude Code: it reads `~/.claude/CLAUDE.md` and the status line
setting only when a session starts. The skills then work with general defaults and say
what they skipped.

<details>
<summary><b>Manual setup</b>: the steps behind the prompt, to set up without Claude</summary>

Needs `git`, `python3` (for `install.sh` and the profiles) and `jq` (for the status line);
install what is missing first, on macOS with Homebrew. Then, from any folder, and restart
Claude Code afterwards:

```sh
git clone https://github.com/qubit-11/claude-dotfiles.git ~/.claude/skills
~/.claude/skills/install.sh
```

- The repository lands in `~/.claude/skills` because Claude Code loads personal skills
  only from there.
- If that folder exists and is not empty (Claude Code creates `synced/` in it for skills
  synced from the claude.ai account), `git clone` refuses it: initialise the repository
  in the folder and pull `main` into it instead.
- [`install.sh`](install.sh) links the status line, adds the `statusLine` setting and
  imports the rules of `global/` in `~/.claude/CLAUDE.md`. It asks nothing, leaves other
  settings alone and can be run again after a `git pull`.

</details>

### 2. Add a company's environment

A company's values (tracker URL, ticket keys, secret files, repository commands) stay out
of the repository. To add them, start Claude Code in one of the company's repositories and
give it this prompt:

```text
Set up the environment of this repository's company following "Add a company's environment" in ~/.claude/skills/README.md.
```

Claude sets up four things and asks for what it cannot find in the repository:

- a profile `~/.claude/skills/_profiles/<company>/`, copied from `_profiles/example/` and
  filled in as [_profiles/README.md](_profiles/README.md) describes;
- the tracker URL and ticket key pattern in `~/.claude/statusline.local.env`, in the format
  the header of [statusline/statusline.sh](statusline/statusline.sh) shows;
- the values the rules in `global/` ask for (ticket keys, branch names), beside their
  imports in `~/.claude/CLAUDE.md`;
- the command-line tool of the company's git host, installed and logged in: `glab` for
  GitLab, `gh` for GitHub. The merge request and review skills read and post through it.

## Contents

### Skills

The [skills](https://docs.claude.com/en/docs/claude-code/skills) cover the craft of software
work: writing a ticket, a merge request description, a review and an explanation in one
personal style, independent of the company or the repository.

| Skill | What it does |
| --- | --- |
| [`qubit-jira-ticket`](qubit-jira-ticket/SKILL.md) | cuts a request into vertical, ready tickets and writes each: what is wrong and what must be true afterwards, never the implementation |
| [`qubit-merge-request`](qubit-merge-request/SKILL.md) | writes a layered merge request description: change, design, where to look, how to try it |
| [`qubit-code-review`](qubit-code-review/SKILL.md) | reviews code changes with independent Claude and Codex reviewers, checks every claim, publishes a bilingual report; re-reviews the posted comments once the author answered |
| [`qubit-code-review-response`](qubit-code-review-response/SKILL.md) | answers a review of one's own change: checks every reviewer claim, fixes what the user picks, replies in every thread |
| [`qubit-explanation-page`](qubit-explanation-page/SKILL.md) | explains a topic or a change as a page with diagrams and details per paragraph |

### Other files

| Path | What it is | How it is wired in |
| --- | --- | --- |
| [`global/worktree-naming.md`](global/worktree-naming.md) | rule for naming git worktree folders: `<TYPE>-<ticket>-<name>` | imported in `~/.claude/CLAUDE.md` |
| [`statusline/statusline.sh`](statusline/statusline.sh) | status line: folder, branch, context, model, 5-hour and 7-day limits | linked as `~/.claude/statusline.sh` |
| [`install.sh`](install.sh) | links the status line, adds the `statusLine` setting, imports the rules of `global/` | run by the setup |
| [`_profiles/`](_profiles/README.md) | a company's values, and `profile.py`, which the skills ask for them | one folder per company, copied from `example/`, not in git |

## Principles

- **General, not tied to a company.** A rule here must hold in any team. The values and
  procedures of one environment live in a local profile, never in a skill.
- **Absorb good practice.** A better practice seen elsewhere (in a colleague's work, a
  standard, a tool) goes into the skill in its general form, under the name it is known by.
- **Change on evidence.** Each round of changes rests on a real run, a replay or a cited
  standard.
