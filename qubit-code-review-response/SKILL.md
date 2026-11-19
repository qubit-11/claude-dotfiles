---
name: qubit-code-review-response
description: "Works through a code review that came back on one's own merge request or pull request, the way an author answers reviewers: checks every reviewer claim against the code, reports which points are clean to fix and explains the doubtful ones, fixes what the user picks, and answers every thread on GitLab or GitHub. Use when a review came back, when the user asks to check, evaluate or address review comments, or to answer the reviewer. Not for reviewing someone else's change; that is `qubit-code-review`."
argument-hint: "[merge request or pull request number or URL]"
---

# Code review response

## Overview

The response to a code review is the author's answer, as the "response to reviewers"
is in peer review: every point is checked, what holds is revised, and every point gets
a decision. A reviewer's comment is a set of claims to check, not an instruction; a
reviewer can be wrong.

The user decides what gets done. The skill checks and reports, then stops; it fixes
and answers only what the user picked.

## Workflow

1. **Find the subject.**
   - Profile: in the repository, run
     `python3 ~/.claude/skills/_profiles/profile.py doc code-review-response`
     ([_profiles/README.md](../_profiles/README.md)). When it prints a path, read that
     file and follow it on top of this workflow. When it prints `none`, use the
     repository's own conventions and its CLI (`glab` for GitLab, `gh` for GitHub).
   - Merge request: the number or URL handed over, else the open merge request of the
     current branch. With several open, ask which one.
   - Worktree: the checkout that has the merge request's source branch
     (`git worktree list`). Work there. When no checkout has it, ask before creating one.
   - Sync: fetch, then compare the local branch with the merge request's head. Local
     commits not yet pushed are fine; say so. When the remote has commits the local
     branch lacks (e.g. a suggestion applied in the web interface), stop and report.
2. **Collect the threads.** Every unresolved review thread and every general comment of
   a reviewer; system notes (pushes, "changed this line", approvals) do not count. A
   thread whose last non-system note is the author's is answered already and is skipped. On a second round, only threads where the
   reviewer wrote after the last answer count.
3. **Check the claim, design the fix, check the fix.** A reviewer's suggested fix is a
   second opinion to compare with, not the fix to take.
   - **Simple threads** (a name, a comment's wording, line length, formatting): the
     claim is checked directly and the fix is the obvious one; none of the agents
     below.
   - **Every other thread** (behaviour, library semantics, a fix that changes code)
     goes through two stages, all threads at once. No agent gets another agent's
     result or an opinion of the skill.
     - **The problem statement.** Both stage-1 agents get the comment with every
       remedy cut out: the reviewer's observations stay, every sentence or code block
       that says what to do instead goes. When the claim is itself the remedy ("this
       does not need X"), the problem is the observation plus "the reviewer questions
       <the code at file:line>".
     - **Stage 1, in parallel.** The *claim agent* gets the problem statement and the
       code and decides whether the claim is true at the merge request's head, with the
       evidence either way (never "confirm"): the primary source (code, installed
       library, configuration, tests), every number and line reference recomputed, a
       behaviour claim run, a claimed defect reproduced. The *design agent* gets the
       same problem statement and the code, and proposes its own fix.
     - **Compare** the design agent's fix with the reviewer's. The same fix, or no
       suggestion from the reviewer: one candidate. Different only in style: the
       reviewer's, as one candidate ("only in style" means the same behaviour and the
       same changes apart from names and formatting). Different in effect, a missing
       follow-on cleanup included: both are candidates.
     - **Stage 2** starts as soon as the design agent is back; it does not wait for
       the claim agent. One *fix-check agent* per candidate gets the problem, that one
       candidate and the code (never the other candidate), takes the claim as true,
       and looks for what the fix breaks or misses: the other users of the changed
       code, the affected tests, the edge values (`undefined`, `null`, empty, the
       largest and smallest input). It answers in this shape:

       ```
       solves the problem: yes / no / in part (why)
       breaks: <list, or "nothing found">
       size: <files and lines touched>
       fits the existing code: yes / no (why)
       ```

     - When the claim does not hold, the stage-2 results are dropped.
   - **Merge** (the skill itself, by rule, in this order): the candidate that breaks
     nothing over one that breaks something; with both breaking something, neither,
     and a third way if there is one; with neither breaking anything, the smaller
     change, then the one that fits the existing code, then the reviewer's. The skill
     never overrules an agent's finding: when it disagrees with one, the item is Needs
     a look and the block says so.
   - **Clean** means: the claim is true, the fix check found nothing, and the fix is
     the one obvious fix (the design agent's and the reviewer's agree, or the reviewer
     gave none). Anything else (a claim that holds in part, a check that could not be
     finished, two candidates, a fix with side effects, an agent that disagrees with
     the direct reading) is **Needs a look**.
   - Kind per thread: a **defect** (triggerable in this change: wrong behaviour, a
     failing test or build), a **suggestion** (anything else that asks for a change),
     or **Info** (asks for no change here: a confirmation, an announced follow-up). The
     kind sets the reply (step 6); the reviewer's own label (Optional, Nit) does not.
4. **Report, then stop.** The report is ordered by group, not by the threads' order on
   the platform. It is a numbered list, never a table: the terminal may be a third of a
   screen wide. Items are numbered straight through all groups (1, 2, 3, …), so the
   user can answer "do 1–4 and 6"; within a group, defects come first. Each item's
   title links its thread. The groups, in this order:
   - **Clean** (step 3's definition): three lines per item, no sources and no
     description of the checks; the user asks for them when needed. When the reviewer offers several fixes that
     differ only in style, the item stays Clean and names the one planned.

     ```
     1. Test name promises more than it checks
        Fix: rename to the suggested name
        Reply: Addressed in <hash>.
     ```

   - **Needs a look** (everything not Clean, step 3): one block per item.

     ```
     3. <title>
        Reviewer: <what the comment claims>
        Verdict: <claim holds / holds in part / does not hold>
        Code: <what the source shows, with the file and line>
        Fix A (ours): <the fix> — <what its check found>
        Fix B (reviewer): <the fix> — <what its check found>
        Plan: <A or B> (<the merge rule that decided>)
        Reply: <the reply, written out when it is a two-sentence one>
        Also: <optional: a finding outside the thread, e.g. about the change itself>
     ```

     With one candidate, a single `Fix:` line replaces the two.

   - **Info (no reply)** (no change asked here): one line per item; a fact worth
     passing to the reviewer is named in the line, for the user to decide.

   End with the recommended set ("recommended: 1–5") and ask which items to do. Wait
   for the answer.
5. **Fix the picked items.**
   - Only the picked items, with the fix the report planned. A fix the reviewer
     offered, also one of several, counts as done as suggested; any other solution
     becomes a deviation reply (step 6).
   - Prove a fix where a test can: the test fails without the fix (revert it for one
     run, then restore) and passes with it.
   - Run the affected tests and the repository's lint gate.
   - Commit by kind (tests, production code, documentation), following the repository's
     commit conventions. Every reply then names the commit that did its part.
6. **Push and answer.**
   - Push first; the replies name hashes that must exist on the server.
   - One reply per thread, inside the thread. The text comes from this table, never
     from the reviewer's comments or the other notes in the thread (no copied prefix,
     language or length):

     | Outcome | Reply |
     | --- | --- |
     | done as suggested | `Addressed in <hash>.` |
     | a real defect, fixed | `Fixed in <hash>.` |
     | done differently or in part | two sentences: what was done instead (with the hash); why the suggestion as written was not taken, or how its goal is still met |
     | not done | two sentences: what stays; the technical reason |
     | Info | no reply |

   - Post the `Addressed` and `Fixed` replies right away. Show the two-sentence replies
     to the user first and post them after the user's OK.
   - A reply describes and never speaks for the user: no questions, no promises of
     later work, no @mentions, no thanks or apologies. English unless the profile says
     otherwise.
   - Threads stay open; the reviewer resolves them.
7. **Status.** The pipeline of the new head, whether the approvals survived the push,
   the threads still open, and anything picked but not done. Tickets stay unchanged.

## Common mistakes

| Mistake | Instead |
| --- | --- |
| A standard reply that retells the change ("renamed to …", "the spy is now restored …") | `Addressed in <hash>.`; the diff shows the rest |
| Taking the reply's prefix, language or form from the reviewer's comments | the reply table in step 6 |
| Agreeing with a claim because the reviewer sounds sure, or quoting the reviewer's numbers | check it against the source and recompute |
| Fixing every comment straight away | report, stop, fix what the user picked |
| Replying to an Info thread to pass on a fact | name the fact in the report; the user decides |
| Replying before the push | push first, so the hash resolves |
