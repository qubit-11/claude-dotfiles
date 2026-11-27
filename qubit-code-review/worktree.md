# Review worktree: branch, MR, PR or patch

Step 1 of [SKILL.md](SKILL.md) sends every branch, MR, PR or patch here
before anything else. Code files need no worktree. Where this file
says "stop and ask", ask the user with AskUserQuestion and wait; never pick
an option yourself. The commands that follow the worktree are in
[tooling.md](tooling.md), Preparation.

## Branch, MR or PR

A branch, MR or PR is reviewed in a worktree of its own, never in the main
checkout, without the user having to ask.

- Name it `REVIEW-<ticket>-<name>` (`REVIEW-noticket-<name>` without a
  ticket).
- First settle the subject sha, the commit under review. Fetch the target
  from its remote, and the branch too when `git ls-remote --exit-code
  <remote> <branch>` finds it (exit 0; exit 2 means the branch is not
  pushed). A fetch that fails, or an `ls-remote` with any other exit
  (network, credentials, a renamed branch): stop and ask the user; never
  settle the sha on the refs already there.
  - For an MR, the subject sha is the MR's head (`glab mr view -F json`,
    field `sha`), even when the local branch has commits the MR lacks; name
    those commits to the user, they are not reviewed.
  - For a branch without an MR, it is the remote tip when the branch is
    pushed, and the local tip when the local branch has commits the remote
    lacks or exists only locally.
  - A local branch without a remote is a valid subject; nothing is fetched
    for it.
  - A repository with no remote at all: stop and ask the user: review against
    the local target (the report and `subject.txt` say "local target, not
    fetched"), or stop. This is the one case where the local target branch
    stands in for `<remote>/<target>`.
- When a `REVIEW-` worktree for the subject already exists (it holds the
  same branch, or is detached at an earlier commit of it), stop and ask the
  user before anything else happens in it. The question names the
  worktree; its HEAD against the subject sha, and whether HEAD is an
  ancestor of the sha (`git merge-base --is-ancestor HEAD <sha>`); whether
  it is clean (`git status --porcelain` prints nothing; the excluded run
  folder does not show), else the changed files; and whether it holds
  earlier run folders (`review-runs/`), with the earlier report's link and
  the sha it reviewed. The options, worded neutrally and without a
  recommendation: which one fits depends on why the user reviews again,
  which the skill cannot know.
  1. Stop: the user checks the worktree first.
  2. Update the existing report: a new run in this worktree whose findings
     are consolidated with the earlier run's, and the earlier report is
     republished at its link (SKILL.md §4.1, Update of an earlier report).
     With new commits since the earlier run, every earlier finding is
     checked again at the new sha. Offered only when the worktree is clean,
     its HEAD is an ancestor of the sha, and an earlier run folder holds a
     `report/findings.json` of a published report (`meta.published`; else the
     question says why it is missing); the
     worktree is then brought to the sha as below. With several earlier
     runs, the one whose report is published (`meta.published`) and newest.
     A worktree with changes (an earlier write, a test run, the user's own
     edits or dev stack) is never re-run in; option 1 lets the user clean it
     up.
  3. New independent report: a new detached worktree at the subject sha,
     created as below, a new run and a new report at a new link; nothing
     from the earlier run is read or compared. The old worktree stays
     untouched.

  Nothing is reused without this question. Never delete, reset, stash or
  check out anything in an existing worktree, the user's changes included.
- A new detached worktree (option 3) goes into the directory
  `REVIEW-<ticket>-<name>-<short sha>`, created with `git worktree add
  --detach <dir> <sha>` where the repository's worktree procedure puts
  manually created worktrees, never by a hook or command that branches off
  the default branch (the profile's `Worktree` section names the route, and
  `Review worktree` what a review worktree does differently; `profile.py doc
  code-review`, every path it prints, in order). An existing directory of that name stops the review (ask the
  user). Then the repository's env provisioning runs on it (the profile's
  sections Worktree and Review worktree name it), since tests need its env files, and `EnterWorktree path:` enters it.
- A worktree reaches the subject sha the same way whether it was reused or
  just created: when its HEAD is an ancestor of the sha (`git merge-base
  --is-ancestor HEAD <sha>`), `git merge --ff-only <sha>`, or for a detached
  one `git checkout --detach <sha>`. When a just created worktree's HEAD is
  not an ancestor (a force-push, a rewritten branch, local commits the
  subject lacks), stop and ask the user: a new detached worktree at the sha
  (as option 3), or stop. For an existing worktree this state is part of
  the question above.
- When no review worktree exists for the subject, create it by the
  repository's worktree procedure if it has one (the profile's sections
  Worktree and Review worktree name it), else
  `git worktree add <dir> <existing branch>`; a local branch from an earlier
  review may sit at an older tip, so bring it to the sha as above. Then
  `EnterWorktree path:`, never `EnterWorktree name:` (it may branch off the
  default branch, and a clean one is removed at session end). When
  `EnterWorktree` refuses (a session already in a worktree may only switch to
  one under `.claude/worktrees/`), stop and ask the user; never go on from
  another checkout.
- When git refuses because the branch is checked out elsewhere (the main
  checkout or a `FEAT-`/`FIX-` worktree), stop and ask the user, naming where
  it is checked out:
  - a detached review worktree at the subject sha (`git worktree add
    --detach <dir> <sha>`). Later commits are not followed. When the local
    and remote tips differ, name both and say which one the sha is. Then run
    the repository's env provisioning on it (the profile's sections Worktree
    and Review worktree name it), since tests need its env files, and
    `EnterWorktree path:` on it;
  - or stop.

  Never force the add, and never review in the other checkout. A detached
  review worktree is created only by the user's choice (option 3 above, or
  an answer to one of these questions); the patch worktree below is the
  exception.

## Patch

Every patch gets a detached review worktree at its stated base (default: the
freshly fetched `<remote>/<target>`), named the same way, without asking,
provisioned like a branch worktree, then entered with `EnterWorktree path:`.
The tests resolve the workspace from the working directory; a session left in
the main checkout would test the base there instead of the patch.

- The original patch stays in `$SP/original/` and is never copied to the
  run folder; the reviewers get it as `change.diff` only after git's file
  list shows no secret file ([tooling.md](tooling.md), Preparation).
- Only the orchestrator applies it, for the tests, and takes it out again
  ([tooling.md](tooling.md), Tests and lint).
- A marker `$SP/checks/patch-applied` left at the end, or after a
  compaction, means the patch is still applied: the reverse block runs next.

## Every review worktree

- Secrets live in the secret files only (`SECRET_FILES` in `scripts/secrets.sh`, from the
  profile). If the procedure provisions one of them, delete that copy right after
  creation. Env files the tests need that hold dummies may stay.
- Check that its HEAD is the subject sha (for a patch: the base). On a
  mismatch, stop: never record HEAD as the subject. The sha goes into
  `$SP/inputs/subject.txt` with the branch and the target, later into
  `meta.state`.
- It stays after the review (the footer names it); removing it is the user's
  call.
