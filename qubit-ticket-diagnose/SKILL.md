---
name: qubit-ticket-diagnose
description: "Diagnoses a ticket before work on it starts: sets up its worktree and branch, checks every claim of the ticket against the code, and reports the root cause of a bug or the gap of a feature with evidence and open questions, then hands over to a plan. Use when the user gives a ticket key or link to start work on, or asks whether a ticket is still correct, what causes a reported bug, or what a feature would touch. Not for writing or cutting tickets (`qubit-jira-ticket`), or for carrying out a plan that already exists."
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

## Workflow

1. **Pick the profile.** In the repository, run
   `python3 ~/.claude/skills/_profiles/profile.py doc ticket-diagnose`
   ([_profiles/README.md](../_profiles/README.md)). When it prints a path, read that file:
   its sections `Ticket tracker`, `Worktree`, `Branch name`, `Hotfix`, `Build and tests`
   and `Ignored folders` take precedence over the defaults below. When it prints `none`,
   use the defaults and tell the user which of these sections you had to skip or guess.
   Done when you know, for each section, the profile's rule or the default.

2. **Read the ticket.** Take the key from the argument: a key in any case, or a link
   with the key in its path. Write it in the tracker's case from here on. Read the
   ticket, its comments, its linked tickets and its attachments through the tracker the
   profile names (default: ask the user how to reach it). Decide bug or feature by the
   issue type; ask when the type does not tell. Then split the ticket into numbered
   claims (see [FORMAT.md](FORMAT.md), Claims). Done when you have the claims and the kind.

3. **Pre-check, before you create anything.** Look for work that already exists:
   - `git worktree list` and `git branch -a`, matched case-insensitively against the key;
   - `git log --all --oneline -i --grep=<KEY>`;
   - open and merged merge requests that name the key (the CLI from the profile).
   When anything matches, show the user every match with its path, branch, commit or
   merge request, and ask: reuse it, create a new one under another name, or stop. A
   change that already landed is also a finding for the diagnosis. Done when nothing
   matched or the user has decided.

4. **Create the worktree.** Type `DEV`, based on the main branch, unless the profile's
   `Hotfix` section says the ticket points at the release branch; then ask, and on a yes
   use type `HOTFIX` based on the release branch. Name the worktree directory by the
   global worktree-naming rule (`<TYPE>-<ticket>-<name>`) and the branch by the profile's
   `Branch name`. Create the worktree by the profile's `Worktree` route, start the
   dependency install in the background, and enter the worktree. When a directory or a
   branch already exists, stop and tell the user; never delete, force, rename or retry.
   Done when the session is in the worktree on the new branch.

5. **Investigate.** Check every claim against the code, with no depth limit: follow the
   calls, the data and the configuration as far as the claim needs.
   - **Bug:** find the root cause. It is often not what the ticket names. Read the
     history of the lines involved (`git log -L`, `git blame`) when it explains the cause.
     When two causes remain possible, keep both as candidates and name what decides.
   - **Feature:** check that the current state the ticket describes is true (part of it
     may exist, behind a flag or in another module). Find the gap, the touch points
     (packages, files, interfaces, data model, migrations), the patterns and decisions
     the change must follow, and whether each acceptance criterion can be tested.
   - **Tests:** find the unit and e2e specs that cover the code. Once you know the
     touched packages, build what their tests need, in the background (profile
     `Build and tests`). Run the relevant unit specs as a baseline. For a bug, write a
     test that reproduces it when that is cheap. List the e2e specs with their commands;
     do not run them.
   Done when every claim has a finding and you can state the cause or the gap.

6. **Report.** Write the diagnosis by [FORMAT.md](FORMAT.md) and run its checklist. Show
   it in the chat and save it as `<ignored folder>/tickets/<KEY>-diagnose.md` in the
   worktree; the ignored folder comes from the profile (default: ask, and check the
   folder with `git check-ignore` before you write). Done when both exist and match.

7. **Stop** and wait for the user's answers to the open questions. When a question is
   for the ticket author, draft it in the chat; post it to the tracker only after the
   user's explicit OK. Done when every open question is answered or the user moves on.

8. **Plan.** Invoke `superpowers:writing-plans` with the diagnosis file as its spec and
   `<ignored folder>/plans/` as the place for the plan, so a new session in the worktree
   can carry it out. When the change is a few lines in one file, propose to skip the
   plan; the user decides. Done when the plan is saved, or the user chose to skip it.
   Do not start implementing.

## Never

- Commit, push, or open a merge request.
- Change the ticket: no status, assignee or comment without the user's explicit OK.
- Delete, force, rename or retry when a worktree or branch is in the way.
- Run e2e suites during the diagnosis.
- Hand the ticket to a subagent that implements it.
- Write a cause under `Cause:` that the evidence does not prove.
