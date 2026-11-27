# Claude dotfiles

A personal Claude Code setup: skills, general working rules and a status line.

## Setup

### 1. Install

Start Claude Code in any folder and give it this prompt:

```text
Set up https://github.com/qubit-11/claude-dotfiles following "Manual setup" in its README.
```

When it is done, restart Claude Code: it reads `~/.claude/CLAUDE.md` and the status line
setting only when a session starts. The skills then work with general defaults and say
what they skipped, until step 2 adds the values of a working environment.

<details>
<summary><b>Manual setup</b>: the steps behind the prompt, to set up without Claude</summary>

Needs `git`, `python3` (for `install.sh` and `profile.py`) and `jq` (for the status line);
install what is missing first, on macOS with Homebrew. Then run, from any folder:

```sh
git clone https://github.com/qubit-11/claude-dotfiles.git ~/.claude/skills
~/.claude/skills/install.sh
```

Restart Claude Code afterwards.

- The repository lands in `~/.claude/skills` because Claude Code loads personal skills
  only from there.
- If that folder exists and is not empty (Claude Code creates `synced/` in it for skills
  from the claude.ai account), `git clone` refuses it: initialize the repository in the
  folder and pull `main` into it instead. If it already holds this repository, run
  `git pull` and `install.sh` instead.
- [`install.sh`](install.sh) links the status line, adds the `statusLine` setting and adds
  an import line to `~/.claude/CLAUDE.md` for each rule in `global/`. It asks nothing,
  leaves other settings alone and can be run again after a `git pull`.

</details>

### 2. Add a working environment

A working environment is where the skills are used: a company, an organization or a team.
Its values (tracker URL, ticket keys, secret files, repository commands) stay out of this
repository. To add them, start Claude Code in one of its repositories and give it this
prompt:

```text
Set up the working environment this repository belongs to, following "Add a working environment" in ~/.claude/skills/README.md.
```

Claude sets up the following and asks for what it cannot find in the repository:

- a profile `~/.claude/skills/_profiles/<name>/`, named after the environment, copied from
  `_profiles/example/` and filled in as [_profiles/README.md](_profiles/README.md) describes;
- the tracker URL and ticket key pattern in `~/.claude/statusline.local.env`, in the format
  the header of [statusline/statusline.sh](statusline/statusline.sh) shows;
- the values the rules in `global/` ask for (ticket keys, branch names), beside their
  imports in `~/.claude/CLAUDE.md`;
- the command-line tool of its git host: `glab` for GitLab, `gh` for GitHub.
  Claude installs it; logging in is yours (`! glab auth login` or `! gh auth login` in the
  session). The merge request and review skills read and post through it.

## Contents

### Skills

The [skills](https://code.claude.com/docs/en/skills) cover the craft of software work:
writing a ticket, a merge request description, a review and an explanation in one personal
style, independent of the working environment and the repository.

| Skill | What it does |
| --- | --- |
| [`qubit-ticket`](qubit-ticket/SKILL.md) | cuts a request into vertical, ready tickets and writes each: what is wrong and what must be true afterwards, never the implementation; creates them in Jira or another tracker |
| [`qubit-merge-request`](qubit-merge-request/SKILL.md) | writes a layered merge request description: change, design, where to look, how to try it |
| [`qubit-code-review`](qubit-code-review/SKILL.md) | reviews code changes with several independent AI reviewers, checks every claim, publishes a bilingual report; re-reviews the posted comments once the author answered |
| [`qubit-code-review-response`](qubit-code-review-response/SKILL.md) | answers a review of one's own change: checks every reviewer claim, fixes what the user picks, replies in every thread |
| [`qubit-ticket-diagnose`](qubit-ticket-diagnose/SKILL.md) | diagnoses a ticket before work starts: sets up the worktree, checks every claim against the code, reports the root cause or the gap with evidence, then hands over to a plan |
| [`qubit-explanation-page`](qubit-explanation-page/SKILL.md) | explains a topic or a change as a page with diagrams and details per paragraph |

### Other files

| Path | What it is | How it is wired in |
| --- | --- | --- |
| [`global/worktree-naming.md`](global/worktree-naming.md) | rule for naming git worktree folders: `<TYPE>-<ticket>-<name>` | imported in `~/.claude/CLAUDE.md` |
| [`statusline/statusline.sh`](statusline/statusline.sh) | status line: folder, branch, context, model and effort, 5-hour and 7-day limits, account | linked as `~/.claude/statusline.sh` |
| [`install.sh`](install.sh) | setup script: links the status line, adds the `statusLine` setting, adds the imports | run by the setup |
| [`_profiles/`](_profiles/README.md) | the values of a working environment, one folder per environment, and `profile.py`, which reads them for the skills | the skills call `profile.py`; only `example/` is in git |

## Optional tweaks

Fixes for problems seen on some machines, not set up by `install.sh`. Apply one only if
you see its problem. Settings go in the `env` block of `~/.claude/settings.json`.

| Problem | Fix |
| --- | --- |
| Claude's commands fail with `no matches found` or `= not found`: Claude writes bash, but the commands run in zsh | `"CLAUDE_CODE_SHELL": "<path to bash 4 or newer>"` |
| The mouse wheel scrolls through earlier prompts instead of the conversation | `"CLAUDE_CODE_DISABLE_ALTERNATE_SCREEN": "1"` |
