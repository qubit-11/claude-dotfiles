---
name: qubit-code-review-response
description: "Works through a code review that came back on one's own merge request or pull request, the way an author answers reviewers: checks every reviewer claim against the code, reports which points are clean to fix and explains the doubtful ones, fixes what the user picks, and answers every thread on GitLab or GitHub, over as many review rounds as it takes. Use when a review came back or the reviewer answered again, when the user asks to check, evaluate or address review comments, or to answer the reviewer. Not for reviewing someone else's change, or re-reviewing it after its author answered; that is `qubit-code-review` (`re-review`)."
argument-hint: "[merge request or pull request number or URL]"
---

# Code review response

## Overview

The response to a code review is the author's answer, as the "response to reviewers"
is in peer review: every point is checked, what holds is revised, and every point gets
a decision. A reviewer's comment is a set of claims to check, not an instruction; a
reviewer can be wrong.

A response fix is the smallest change that settles the comment. It refactors nothing
and cleans up nothing outside the comment; whatever else turns up is reported, and a
follow-up change takes it.

The user decides what gets done. The skill checks and reports, then stops; it fixes
and answers only what the user picked. Every round is kept in a run file (see Run
file), so a later round, or the same round after a context compaction, picks up from it.

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
   - Round: read the run files of this merge request (see Run file). The newest one
     that is not finished is this round, picked up where it stopped; otherwise this is
     the next round.
2. **Collect the threads.** Every unresolved review thread and every general comment of
   a reviewer; system notes (pushes, "changed this line", approvals) do not count. A
   thread whose last non-system note is the author's is answered and is skipped.
   - **Later rounds**: a thread counts when the reviewer wrote after the last answer
     (a pushback, a question, a new point), and so does every new thread. For such a
     thread, the earlier rounds' entries in the run files (claim verdict, plan, reply)
     are the context; the newest reviewer note is the comment to check.
3. **Check the claim, design the fix, check the fix.** A reviewer's suggested fix is a
   second opinion to compare with, not the fix to take.
   - **Simple threads** (a name, a comment's wording, line length, formatting): the
     claim and the fix are checked directly; none of the agents below. When the
     reviewer offers several fixes, the ranks below pick one.
   - **Every other thread** (behaviour, library semantics, a fix that changes code)
     goes through two stages, all threads at once. No agent gets another agent's
     result or an opinion of the skill.
     - **The problem statement.** Both stage-1 agents get the comment with every
       remedy cut out: the reviewer's observations stay, every sentence or code block
       that says what to do instead goes. When the claim is itself the remedy ("this
       does not need X"), the problem is the observation plus "the reviewer questions
       <the code at file:line>". In a later round, the thread's earlier notes come
       with it, their remedies cut out the same way; the claim agent also gets the
       author's earlier reply whole, since a pushback answers its reasons.
     - **Stage 1, in parallel.** The *claim agent* gets the problem statement and the
       code and decides whether the claim is true at the merge request's head, with the
       evidence either way (never "confirm"): the primary source (code, installed
       library, configuration, tests), every number and line reference recomputed, a
       behaviour claim run, a claimed defect reproduced (when a run is not possible, a
       reading of the source counts only if it leaves no doubt). The *design agent*
       gets the same problem statement, the files and lines it names, and the code, and
       returns its fix as a diff: the smallest change that settles the comment, with no
       refactoring and no cleanup outside the comment's scope; what else it notices it
       lists apart. It gets nothing more: no pointer to a solution, an analogous test
       or a library behaviour the remedy relies on.
     - **Candidates.** The design agent's diff, and the reviewer's suggestion turned
       into a diff when there is one. When the two are the same diff, they are one
       candidate.
     - **Stage 2** starts as soon as the design agent is back; it does not wait for
       the claim agent. One *fix-check agent* per candidate gets the problem, that one
       candidate and the code (never the other candidate), takes the claim as true,
       and looks for what the fix breaks or makes worse: the other users of the
       changed code, the affected tests and their strength, the repository's lint
       rules, the edge values (`undefined`, `null`, empty, the largest and smallest
       input). Only what the fix causes counts; a gap in the existing code that stays
       the same with any fix (e.g. no test covers the component) goes under `apart`.
       It answers in this shape:

       ```
       solves the problem: yes / in part / no (why)
       breaks or weakens: <list, or "nothing found">
       apart: <gaps in the existing code, or "none">
       ```

     - When the claim does not hold, the stage-2 results are dropped.
   - **Pick by rank.** The skill compares the candidates rank by rank; the first rank
     where they differ decides. Ranks 3 to 5 are counted from the diffs.

     | Rank | Criterion | Measure |
     | --- | --- | --- |
     | 1 | settles the comment | "solves" yes over in part over no |
     | 2 | breaks or weakens nothing | fewer findings in "breaks or weakens" |
     | 3 | stays in scope | fewer changed files outside the comment's scope: the file the comment sits on and the files it names, each with its companion files (same base name: template, styles, test) |
     | 4 | small | fewer changed lines (added plus removed) |
     | 5 | smaller still | fewer changed characters |

     When the winner still has findings with a plain fix (a lint rule, a name, the
     same fix as another thread), those fixes are added to it; when its findings have
     no plain fix, the item says so and names a third way if there is one. The skill
     never overrules an agent's finding: when it disagrees with one, the item is Needs
     a look and the block says so.
   - **Clean** means: the claim is true, the fix check (for a simple thread, the
     direct check) found nothing, and there is one candidate (the design agent's and
     the reviewer's are the same diff, or the reviewer gave none). Anything else (a
     claim that holds in part, a check that could not be finished, two candidates, a
     fix with findings, an agent that disagrees with the direct reading) is **Needs a
     look**.
   - Kind per thread, from the check, in the kinds of
     [Conventional Comments](https://conventionalcomments.org) that
     `qubit-code-review` uses: an **issue** (something is wrong or missing in this
     change: wrong behaviour, a failing test or build, a missing test or case), a
     **suggestion** (the code works; another way would be better), a **nitpick**
     (wording only), a **question** (the reviewer asks what only the author can
     answer), a **chore** (a step outside the repository: an infrastructure update, a
     migration in production, a release order) or a **note** (asks for nothing: a
     confirmation, information). The kind sets the reply (step 6). The reviewer's
     prefix (`**issue (blocking):**`, or another convention's `Nit:`) is a hint, never
     the result: a claimed issue that does not hold is answered as one that does not
     hold. A thread the reviewer marked `blocking` is recorded as such, since it holds
     the merge until it is settled.
   - A **question** or a **chore** is never Clean: the answer and the step outside the
     repository are the user's. The item names the facts the check found (for a
     question, what the code and the description say; for a chore, whether the
     description already declares the step).
4. **Report, then stop.** Write the round's run file first. The report is ordered by
   group, not by the threads' order on the platform. It is a numbered list, never a
   table: the terminal may be a third of a screen wide. Items are numbered straight
   through all groups (1, 2, 3, …), so the user can answer "do 1–4 and 6"; within a
   group, threads marked `blocking` come first, then issues. Each item's title links its thread. In a later round,
   the report says which round it is. The groups, in this order:
   - **Clean** (step 3's definition): three lines per item, no sources and no
     description of the checks; the user asks for them when needed. A fourth line,
     `Also:`, only when a finding outside the comment's scope turned up.

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
        Plan: <A or B> (rank <n>: <what differed>)
        Reply: <the reply, written out when it is a two-sentence one>
        Also: <optional: a finding outside the comment's scope>
     ```

     With one candidate, a single `Fix:` line replaces the two, and `Plan:` names the
     fixes added to it.

   - **Notes (no reply)** (kind `note`, nothing asked here): one line per item; a fact
     worth passing to the reviewer is named in the line, for the user to decide.

   End with the recommended set ("recommended: 1–5") and ask which items to do. Wait
   for the answer, then record the picks in the run file.
5. **Fix the picked items.**
   - Only the picked items, with the fix the report planned.
   - Prove a fix where a test can: the test fails without the fix (revert it for one
     run, then restore) and passes with it.
   - Run the affected tests and the repository's lint gate.
   - Commit by kind (tests, production code, documentation), following the repository's
     commit conventions. Every reply then names the commit that did its part. Record
     each item's commit in the run file.
6. **Push and answer.**
   - Push first; the replies name hashes that must exist on the server.
   - One reply per thread, inside the thread. The text comes from this table, never
     from the reviewer's comments or the other notes in the thread (no copied prefix,
     language or length):

     | Outcome | Reply |
     | --- | --- |
     | the reviewer's fix, also with different names or formatting, or with only the cleanup it makes necessary (an import or attribute it leaves unused) | `Addressed in <hash>.` |
     | an issue that holds, fixed (not with the reviewer's fix as written) | `Fixed in <hash>.` |
     | a question, answered | two sentences: the answer; where it now stands (the description, or the commit with its hash) |
     | a chore, done by the user | `Done: <the step, in a few words>.` |
     | the comment is settled, but the commit alone does not show which approach was taken: we took one of several options the reviewer offered (keeping the code counts as one); the reviewer named no remedy and the comment does not make the fix obvious; or the commit, however trivial, changes files beyond the commented file and its companions (as in rank 3) | the `Addressed` or `Fixed` reply plus half a sentence that names the approach, not the steps: `Addressed in <hash>: moved to the sibling entry point <path>.` |
     | another fix, or the comment settled in part | two sentences: what was done instead (with the hash); why the suggestion as written was not taken, or how its goal is still met |
     | not done | two sentences: what stays; the technical reason |
     | a note | no reply |

   - Post the `Addressed` and `Fixed` replies right away. Show the two-sentence replies
     to the user first and post them after the user's OK.
   - A reply describes and never speaks for the user: no questions, no promises of
     later work, no @mentions, no thanks or apologies. English unless the profile says
     otherwise.
   - Threads stay open; the reviewer resolves them.
   - Record each reply (its text and its note id) in the run file.
7. **Status.** The pipeline of the new head, whether the approvals survived the push,
   the threads still open, and anything picked but not done. Tickets stay unchanged.
   Mark the round finished in the run file.

## Run file

One JSON file per round, in the worktree:
`.code-review-responses/<merge request number>/round-<n>.json`. Before the first write,
add `.code-review-responses/` to the repository's `.git/info/exclude` (the path from
`git rev-parse --git-path info/exclude`; shared by every worktree), so it is never
committed. Write it at the end of step 4 and update it at each later step; after a
context compaction, read it before anything else.

```json
{
  "mergeRequest": "<url>",
  "round": 1,
  "head": "<sha the claims were checked at>",
  "finished": false,
  "items": [
    {
      "number": 1,
      "thread": "<thread id>",
      "url": "<link to the note>",
      "title": "<short title>",
      "group": "clean | needs-a-look | note",
      "kind": "issue | suggestion | nitpick | question | chore | note",
      "blocking": true,
      "claim": { "verdict": "holds | in part | does not hold", "evidence": "<file:line, run>" },
      "candidates": [
        { "name": "A", "from": "design | reviewer", "diff": "<diff>",
          "solves": "yes | in part | no", "breaksOrWeakens": ["<finding>"],
          "outOfScopeFiles": 0, "lines": 0, "characters": 0 }
      ],
      "plan": { "candidate": "A", "rank": 2, "why": "<what differed>", "added": ["<plain fix>"] },
      "also": ["<finding outside the scope>"],
      "picked": true,
      "commit": "<hash>",
      "reply": { "text": "<reply>", "noteId": "<id>" }
    }
  ]
}
```

## Common mistakes

| Mistake | Instead |
| --- | --- |
| A standard reply that retells the change ("renamed to …", "the spy is now restored …") | `Addressed in <hash>.`; the diff shows the rest |
| A bare `Addressed in <hash>.` when the commit alone does not show which approach was taken | half a sentence naming the approach (reply table in step 6) |
| Taking the reply's prefix, language or form from the reviewer's comments | the reply table in step 6 |
| Agreeing with a claim because the reviewer sounds sure, or quoting the reviewer's numbers | check it against the source and recompute |
| Refactoring or tidying up beside the fix | the smallest change that settles the comment; the rest goes into `Also:` |
| Fixing every comment straight away | report, stop, fix what the user picked |
| Replying to a note to pass on a fact | name the fact in the report; the user decides |
| Taking the reviewer's label as the kind, or answering a `question` or a `chore` without the user | the check sets the kind; questions and chores go to Needs a look |
| Replying before the push | push first, so the hash resolves |
| Starting a later round from scratch | read the run files of the earlier rounds first |
