# Diagnosis format

The diagnosis is read by the user who will build the ticket. They know the ticket
already; its title usually says what it is about. What they do not know is what the
code says: why the bug happens, or what a feature is really missing and where it
lands. So the head states that first, and everything below it is the evidence.

The diagnosis is written in the language of the conversation with the user. It goes
into the chat and, unchanged, into the diagnosis file (SKILL.md, step 6).

## Head

The head is a fenced `text` block. Its shape depends on the ticket kind.

**Bug:**

```text
PROJ-123 · Bug · <the ticket's title, verbatim>

Ticket:           <one sentence on the content; leave the line out when the title says it>
Cause:            <one or two sentences: why the bug happens, with file:line>
Verdict:          <does the ticket hold, and is the fix clear?>
Judgement:        simple | questions needed
Checked against:  <branch> @ <short sha>
```

When the cause is not certain, `Cause candidates:` takes the place of `Cause:`, as a
list. Each candidate names its evidence and the check that would confirm or refute it:

```text
Cause candidates:
  1. <cause>, file:line. Decided by: <a test, a log, a question>
  2. …
```

**Feature:**

```text
PROJ-123 · Feature · <the ticket's title, verbatim>

Ticket:           <one sentence on the content; leave the line out when the title says it>
Gap:              <one sentence: what is really missing compared with the current state>
Touch points:
  - <package>: <file or area>, <what changes there>
  - …
  - Migration needed: yes | no
Verdict:          <does the ticket hold, and is it clear what to build?>
Judgement:        simple | questions needed
Checked against:  <branch> @ <short sha>
```

`Judgement` is `questions needed` as soon as one open question below is numbered;
otherwise `simple`.

## Claims

A table with one row per claim of the ticket, in the order of step 2 of SKILL.md:

```md
| # | Claim in the ticket | Finding | Evidence |
|---|---|---|---|
| 1 | <the claim, shortened> | ✅ holds | `path/file.ts:42` |
| 2 | <the claim> | ❌ does not hold: <what is true instead> | `path/file.ts:88`, commit `abc1234` |
| 3 | <the claim> | ❓ cannot be checked: <why> | <what would check it> |
```

- Evidence is a `file:line`, a commit, a merge request or a test result that you read
  yourself in this session.
- For a bug, the claims are the steps to reproduce, the observed and the expected
  behaviour, and any cause the ticket names.
- For a feature, the claims are the current state the ticket describes and each
  acceptance criterion. A criterion is ✅ when it can be written as a test and the
  code has a place for it; ❓ when it is vague or depends on a decision.

## Below the table

In this order, each under a bold lead-in:

1. **Open questions.** Numbered. Each one says who can answer it (the user, the ticket
   author, product) and what changes with the answer. Leave the part out when there is
   none.
2. **Tests.** The unit specs that cover the code, with the baseline result of the run
   (`green`, `red: <failing test>`); a reproducing test, if one was written; the e2e specs
   that cover the flow, each with its command, marked `not run`.
3. **Approach.** At most three lines: where the change goes and what it does. Not a
   plan; the plan comes after the open questions are settled.

## Checklist

Before the diagnosis is shown, every line is true:

- The head starts with the cause (bug) or the gap and touch points (feature), not with
  a restatement of the ticket.
- `Cause:` holds only a cause that the evidence proves; anything less is under
  `Cause candidates:`.
- Every ✅ and ❌ row has evidence you read yourself.
- `Checked against` names a branch and a sha.
- `Judgement` matches the open questions.
