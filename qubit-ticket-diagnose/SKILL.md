---
name: qubit-ticket-diagnose
description: "Diagnoses a ticket before work on it starts: sets up its worktree and branch, checks every claim of the ticket against the code, and reports the root cause of a bug or the gap of a feature with evidence and open questions, then hands over to a plan. Use when the user gives a ticket key or link to start work on, or asks whether a ticket is still correct, what causes a reported bug, or what a feature would touch. Not for writing or cutting tickets (`qubit-ticket`), or for carrying out a plan that already exists."
---

# Ticket diagnosis

## Overview

Work on a ticket starts the same way every time: read the ticket, set up a worktree,
compare the ticket with the code, find what is open. This skill does all of it from one
call, `/qubit-ticket-diagnose <KEY or link>`, and ends with a diagnosis and then a plan.

A ticket usually describes a symptom or a wish. The diagnosis adds what only the code
can say: why the bug happens, or what a feature is really missing and where it lands.
It is the start of the implementation, so it is exact: every claim is checked, and
every finding has evidence you read yourself.

The user's session drives the ticket from start to plan. Explore agents may search,
but they only read, and their findings are evidence only after you have read the cited
lines yourself.

## Profile and defaults

In the repository, run `python3 ~/.claude/skills/_profiles/profile.py doc ticket-diagnose`
([_profiles/README.md](../_profiles/README.md)). When it prints a path, read that file.
Each of its sections replaces the default of the same name below. For every section the
profile lacks (all of them when it prints `none`), use the default and tell the user
which defaults you used.

| Section | Default |
|---|---|
| `Ticket tracker` | Ask the user how to read the ticket. |
| `Worktree` | Remote: the one the main branch tracks, else `origin`. Main branch: `git symbolic-ref refs/remotes/<remote>/HEAD`. Folder: ask the user once. Install: the package manager whose lockfile is in the root. |
| `Branch name` | `<KEY>-<short-title>` |
| `Hotfix` | Ask when the ticket names production, a release, a released version or a hotfix; ask for the release branch. |
| `Build and tests` | From the touched package's manifest and README. Merge request CLI: `glab` for a GitLab remote, `gh` for GitHub. |
| `Ignored folders` | Ask; confirm the folder with `git check-ignore` before writing to it. |

## Workflow

1. **Read the ticket.** Take the key from the argument: a key in any case, or a link
   with the key anywhere in it (path or query). Use the tracker's case for the ticket
   and the branch, lower case for the worktree directory. Read the ticket, its comments,
   its linked tickets and its attachments. Decide bug or feature by the issue type; ask
   when the type does not tell. Split the ticket into numbered claims
   ([FORMAT.md](FORMAT.md), Claims). Done when you have the claims and the kind.

2. **Pre-check, before you create anything.** Fetch the remote first. Then look for
   work that exists, matching the key case-insensitively and not followed by a digit
   (`PROJ-12` must not match `PROJ-123`):
   - `git worktree list` and `git branch -a`;
   - `git log --all --oneline -i -E --grep='<KEY>([^0-9]|$)'`;
   - open and merged merge requests that name the key (CLI from `Build and tests`).
   Show the user every match with its path, branch, commit or merge request, and ask:
   - **a worktree or branch exists:** reuse it, create a new one under another name, or
     stop;
   - **the change already landed:** is a worktree still needed, or is the diagnosis
     enough?
   Done when nothing matched or the user has decided.

3. **Set up the worktree.**
   - **Reuse:** enter the existing worktree; for an existing branch without a worktree,
     `git worktree add <dir> <branch>`, then provision and enter it as below.
   - **New:** type `DEV` based on `<remote>/<main branch>`; when `Hotfix` applies, ask,
     and on a yes use type `HOTFIX` based on the release branch. Name the directory by
     the [worktree-naming rule](../global/worktree-naming.md) (`<TYPE>-<ticket>-<name>`)
     and the branch by `Branch name`. Create it by the `Worktree` route.
   - **None** (the user chose the diagnosis only): stay in the main checkout and skip
     the install, the build and the test runs of step 4.
   Then enter the worktree, and only then start the install in the background, from
   inside it. When a directory or a branch is in the way, stop and tell the user; never
   delete, force, rename or retry. Done when the session is in the worktree.

4. **Investigate.** Check every claim against the code, with no depth limit: follow the
   calls, the data and the configuration as far as the claim needs.
   - **Bug:** find the root cause. It is often not what the ticket names. Read the
     history of the lines involved (`git log -L`, `git blame`) when it explains the cause.
     When two causes remain possible, keep both as candidates and name what decides.
   - **Feature:** check that the current state the ticket describes is true (part of it
     may exist, behind a flag or in another module). Find the gap, the touch points
     (packages, files, interfaces, data model, migrations), the patterns and decisions
     the change must follow, and whether each acceptance criterion can be tested.
   - **Tests:** find the unit and e2e specs that cover the code. Wait for the install to
     finish, then build what the touched packages' tests need, in the background
     (`Build and tests`). Run the relevant unit specs as a baseline. For a bug, write a
     test that reproduces it when that is cheap. List the e2e specs with their commands;
     do not run them.
   Done when every claim has a finding and you can state the cause or the gap.

5. **Report.** Write the diagnosis by [FORMAT.md](FORMAT.md) and run its checklist. Show
   it in the chat and save it as `<ignored folder>/tickets/<KEY>-diagnose.md` in the
   worktree, or in the main checkout when there is none. Done when both exist and match.

6. **Stop** and wait for the user's answers to the open questions. When a question is
   for the ticket author, draft it in the chat; post it as a ticket comment only after
   the user's explicit OK. Done when every open question is answered or the user moves on.

7. **Plan.** Invoke `superpowers:writing-plans` with the diagnosis file as its spec and
   `<ignored folder>/plans/` as the place for the plan, so a new session in the worktree
   can carry it out. When the change is a few lines in one file, propose to skip the
   plan; the user decides. Stop once the plan is saved: skip the execution handoff of
   writing-plans, and do not start implementing. Done when the plan is saved, or the
   user chose to skip it.

## Never

- Commit, push, or open a merge request.
- Write to the ticket, except the drafted question of step 6 after the user's explicit
  OK. No status, assignee, field or link changes, even when a repository rule asks for
  them.
- Delete, force, rename or retry when a worktree or branch is in the way.
- Run e2e suites during the diagnosis.
- Hand the ticket to a subagent that implements it.
- Write a cause under `Cause:` that the evidence does not prove.
