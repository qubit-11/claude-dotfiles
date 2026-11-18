---
name: qubit-merge-request
description: "Writes a layered merge request or pull request description (the change, its design, where to look, how to try it) and opens or updates the merge request on GitLab or GitHub; the branch is rebased onto its target. Use when the user wants a merge request or pull request opened, updated or its description rewritten, or when a reviewer says a description does not explain the goal, the design or why the change exists."
---

# Merge request

## Overview

An MR description is read top-down and most readers stop early. So it is short and
layered: where the change lives, what was wrong, what behaves differently, how it is
built, then where to look and how to try it. A reader who stops after the Change knows
whether the change should exist; one who stops after the Design knows how it works,
before opening a file.

## Workflow

1. **Pick the profile.** In the repository, run
   `python3 ~/.claude/skills/_profiles/profile.py doc merge-request`
   ([_profiles/README.md](../_profiles/README.md)). When it prints a path, read that file
   and follow it on top of the format. When it prints `none`, use the format alone, with
   the repository's own conventions and its CLI (`glab` for GitLab, `gh` for GitHub).
2. **Rebase onto the target branch.** The target is the existing MR's target branch;
   for a new MR, the branch the work was cut from (usually the default branch, a
   backport e.g. `stable`). Ask the user when that is not certain. Fetch the target and
   run `git merge-base --is-ancestor <remote>/<target> HEAD`. When it fails, run
   `git rebase <remote>/<target>`, never a merge. Show the user every conflict, and
   resolve it only with their OK. Then rerun the tests of the files the conflicts touched.
3. **Gather.** The commits and the diff from the merge base, the ticket or issue with its
   title, the ADRs the change follows, and any review results of the branch (as
   input only; FORMAT.md says where a result may appear).
4. **Draft** the title and the description by [FORMAT.md](FORMAT.md), then run its
   checklist on the draft.
5. **Show** the title and the description to the user and wait for an OK or their changes.
   In the same message, ask what was checked when a line reads `Not tested: <ask>`.
   For a Screenshots section, find the user's screenshots instead of asking for paths:
   the folder is `defaults read com.apple.screencapture location` on macOS (else
   `~/Desktop`), and only images created since the branch's first commit count. View
   them, propose which image is the Before or After of which row, and let the user
   confirm. A Before image from the ticket counts too, unless it shows personal or
   customer data. With no After image, the section goes.
6. **Create or update** the MR only after that OK. Right before the push, run the
   ancestor check of step 2 again. When the target has moved, go back to step 2. A rebased
   branch that is already on the remote needs `git push --force-with-lease`; ask the user
   before you run it. Push the branch. Upload the confirmed screenshots to the project and
   put the returned Markdown into the table (the profile has the command). Then create
   the MR with the target of step 2, or update the existing MR of the branch. Write the description to a file and pass the
   file's text; never retype it into the command.
7. **Finish** with the profile's last steps, and give the user the MR link.
