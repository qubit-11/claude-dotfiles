---
name: qubit-code-review
description: "Reviews a branch, merge request, pull request, patch or set of code files with several independent AI reviewers (Claude subagents and codex) and publishes a bilingual review report (English and German). Two depths: `standard` (default) and `deep` for changes where a miss is expensive or hard to undo (authentication, wire formats, migrations). Use when a finished change needs a thorough review before merge, a second opinion from another model family, or a review report for the team, when the user asks for the report of a finished review run (\"make the report\"), or when the author of a reviewed merge request answered or pushed fixes and the posted review comments need a re-review. Not for a quick check during development; that is the built-in `/code-review`."
argument-hint: "[standard|deep] [skip-report] | publish-report | re-review"
---

# Code review with independent agents

Reviewers read the same subject without knowing each other, each other's
findings, or any earlier review. The orchestrator consolidates their output
into one list, has every Blocker and every factual contradiction
investigated, and every other finding checked as its depth requires (§4),
runs what can be run, and prints a short findings list in chat. Then, unless told to skip it,
it publishes one report in English and German. The reviewers' own lists are
inputs, never output.

The state of the subject (a draft MR, a flag still off, a route not yet
linked) changes nothing in the review: the reader judges whether a Blocker
may wait.

The subject is a branch by default: the current branch when the request
names no subject. Before anything else, look up its open MR
(`glab mr list --source-branch <branch> -F json`). With exactly one, the
subject is that MR, as if its URL had been handed over; with several, stop
and ask the user which one; with none, or when `glab` fails (no GitLab
remote, no login), the subject stays the branch and the chat says so in one
line. Anything handed over works the same way:

| Subject | How reviewers see it | Judged against | Verdict wording | Package (location line) |
| --- | --- | --- | --- | --- |
| branch, MR, PR | diff against the target branch, without inflators | the target branch, the MR description, the ticket | mergeable / not mergeable | package |
| patch or diff file | the file itself, plus the repo at the stated base | the base commit, the cover note | applicable / not applicable | package |
| code files or a directory | the paths, read in full | the spec or ticket they implement, neighbouring code | fit for use / not yet | module or file group |

## Commands

Every run prints the findings list in chat (step 5) and goes straight on to
the report: the full review, explained in English and German in visible
paragraphs, each with its details on a click where they pay off,
with the GitLab comments, published as one page with its files (`publish/`,
the same document as `review.html`). The
arguments come in any order.

| Command | Reviews | Report |
| --- | --- | --- |
| `/qubit-code-review [standard]` | yes, steps 1 to 5, depth `standard` | yes, step 6 right after the list |
| `/qubit-code-review [standard] skip-report` | yes, steps 1 to 5, depth `standard` | no |
| `/qubit-code-review deep` | yes, steps 1 to 5, depth `deep` | yes, step 6 right after the list |
| `/qubit-code-review deep skip-report` | yes, steps 1 to 5, depth `deep` | no |
| `/qubit-code-review publish-report` | no | yes, for a finished run (step 7) |
| `/qubit-code-review re-review` | no, checks the posted comments of a published run ([re-review.md](re-review.md)) | no |

- The two depths are `standard` and `deep`; `standard` is the default, so a
  request without a depth runs it. A depth always means a new review at that
  depth.
- `skip-report` leaves the report out. The report is left out too when the
  request asks for the list only or a quick check.
- `publish-report` publishes the report of a finished run and never reviews.
  It takes no depth: with one, the skill stops before any work with one line:
  "`publish-report` publishes a finished run and takes no depth. For a review
  with the report: `/qubit-code-review [standard|deep]`."
- `re-review` checks whether the author's new commits and replies settle the
  comments the user posted from a published run. It follows only
  [re-review.md](re-review.md): steps 1 to 8 and the worktree question do
  not apply. It takes no depth: with one, it stops with the line
  re-review.md gives.
- `low`, `medium` and `high` are old names. With one, the skill stops before
  any work with one line: "The depths are `standard` (the default) and
  `deep`: `/qubit-code-review [standard|deep]`. For a quick check:
  `/code-review`."
- A question about one finding ("explain F2", "F2 in detail") is answered in
  chat.
- The list prints before the report starts, so the user can read it at once.

**REQUIRED SUB-SKILL for the report:** `qubit-explanation-page`, at every depth. The
explanation writer (step 6) invokes it with the Skill tool; it writes the
explanatory part and owns the page skeleton. This skill owns the report: it
fills the caller slot with the review sections, has the report translated,
checks it and publishes it, once per change of content. A run without a report
loads neither the skill nor a writer.

Files:
- [worktree.md](worktree.md): the review worktree
- [re-review.md](re-review.md): the re-review of posted comments
- [tooling.md](tooling.md): commands, subagents, foreign runs, tests, and the
  shell rules a worktree session needs; `scripts/` holds the git steps it calls
- [reviewer-prompt.md](reviewer-prompt.md): the shared prompt and its variants
- [report-sections.md](report-sections.md): the report, `findings.json`, the
  checks of `assemble.py`
- [gitlab-comments.md](gitlab-comments.md): the GitLab comments
- `ground_check.py`: the grounding check (§4)
- `cold_read_input.py`: the cold reader's input, each GitLab comment beside
  its code (§6.2)
- from `qubit-explanation-page`: `page_check.py`, the page checks
  `assemble.py` imports, and `render_check.py` (§6.3)

## Severity

Every finding has one true severity. Reviewers propose it, investigators
decide it (§4; an exempt Nit keeps the reviewer's label), and the
orchestrator never sets it.

| Severity | Definition | Merge |
| --- | --- | --- |
| Blocker | (a) a defect that can be triggered in live use of the subject: a broken intent (a mechanism the change adds fails on a live path to do what its quoted intent says, whatever the harm) or a gap (an unhandled case with no stated intent whose live trigger gives a user, stored data or availability a wrong result); (b) a vulnerability; (c) a change that makes the code health worse: it breaks an accepted ADR or an enforced boundary, inverts a dependency direction, adds a second mechanism next to an existing one, adds complexity or generality the change does not need, leaves an invariant its module owns to the callers (an input that the module's own types and checks accept breaks the invariant the module exists to keep), or breaks an invariant the code enforces (a schema validator or required field, a unique index, a type, a consumer's strict check of a value it receives) by writing data or handing over a value that breaks it, instead of changing the invariant or migrating the consumer, or leaves an existing test failing that passed before the change, without fixing it or disabling it visibly with a ticket; (d) a missing test: a new feature with no test at all | waits for it |
| Optional | a change to behaviour, tests, coverage or structure, something a user, a test or a later change to the code depends on, with no failure in live use: additional tests, a missing case in otherwise present tests | allowed |
| Nit | a change to wording only: names by convention, comments, docs wording | allowed |
| FYI | no change in this subject; worth a follow-up ticket | allowed |

Live use, per subject type (the reviewer prompt's placeholder line is filled
from this):

| Subject | Live use |
| --- | --- |
| branch, MR, PR, patch | the code as deployed in production or a supported setup, with every flag, link and release step it depends on switched on and every release precondition it declares met, as our shipped clients call it (our frontends, our other servers, documented partner integrations), with any value a user can enter in them |
| code files or a directory | running or calling them as the code base does, or as their docs say, with any value those callers can pass |

Code that is not switched on yet is judged as if it were: a flag that is
off, a route not yet linked or a draft MR never lowers a severity. An input
that the code's own types or schema reject does not count. A request a
legitimate user builds by hand counts only on a documented public API; one
built by an attacker or another tenant is judged under (b). A failure that
occurs only when a release precondition is unmet (an infrastructure
version, a migration or another release that must come first) counts as
follows: if the description, the repository's docs or the ticket declare
the precondition, live use means it is met, and the finding is an FYI
whose follow-up names the precondition for the release; if none of them
does, live use is today's setup, and the failure is judged as it is.

The rules for (c) and (d), for rules in instruction files and code comments,
and for personal data stand in the shared prompt only
([reviewer-prompt.md](reviewer-prompt.md), Conventions, Severity and Floor):
every reviewer, investigator and rater judges by that text.

- The verdict is mergeable (applicable, fit for use) exactly when
  no Blocker is open.
- **Open question.** When only the author can say whether a behaviour is
  intended, and one plausible answer makes it a Blocker, the finding is a
  Blocker; its `fix` is the question with both ways out (state it in the
  description, or change the code). It covers a contradiction with the
  ticket that the description leaves unaddressed, and behaviour someone
  outside the change sees that neither description nor ticket covers and
  that does not follow from the description's goal. Reviewers do not get
  this rule in their prompt; investigators apply it (the check table). A
  false Blocker is read and answered; an open point in the method section
  is not read.
- The reasons (a) to (d) define a Blocker and pick its investigator question
  (§4); they are no field. A Blocker's `verify` states the proof its reason
  needs (the trigger, the exploit path, the ADR, the missing test), so the
  reader sees whether it rests on a fact or a judgment.
- Reason and category are independent: the card and the list show the
  category, a Tests finding can rest on (a), and personal data in a log in
  live use is (a) with category Security.
- An Optional's `why` says when it starts to hurt, when such a condition
  exists. Every FYI and every Optional carries a follow-up ticket draft whose
  text carries that condition; the drafts stand in the report (step 5).

## 1. Frame the subject

Before anything else, record the start for the effort line:
`mkdir -p "$SP/state" && date -u +%Y-%m-%dT%H:%M:%SZ > "$SP/state/review-started.txt"`.
Step 4 copies it into `meta.effort.review.started` (report-sections.md,
findings.json).

- **Profile.** The values and commands of the reviewed repository's
  environment (ticket links, secret files, neighbour repositories, user
  roles, the worktree route, e2e commands) come from its profile, never from
  this skill: [_profiles/README.md](../_profiles/README.md). Without a
  matching profile the review runs with the fallbacks the README names, and
  4.2 says so.
- **Worktree.** A branch, MR, PR or patch is reviewed in its own worktree:
  follow [worktree.md](worktree.md) before anything else. Stop and ask the
  user where it says so: no remote at all; a review worktree that already
  exists for the subject (stop, update the existing report, or a new
  independent report); a HEAD that is not an ancestor of the sha; a branch checked out
  elsewhere. Code files need no worktree.
- **Target.** Branch and target (default `master`). The target is always the
  freshly fetched remote ref `<remote>/<target>`, never the local branch,
  which a fetch does not move. The remote comes from `git config
  branch.<target>.remote`, or is the only remote when none is set; with
  several remotes and none set, ask the user. A failed fetch stops the
  review: ask the user, never go on with the ref already there. The one
  exception: a repository without a remote whose user chose the local
  target ([worktree.md](worktree.md)).
- **Base facts.** For a branch, MR or PR: `git merge-base`, the commits on
  each side (the branch's and the target's since the merge base), and `git
  merge-tree --write-tree <remote>/<target> HEAD` for conflicts. For a patch:
  a failed `git apply --check` on the base is a Blocker finding with the
  check output as evidence. For code files: copy the subject into
  the scratchpad as the reviewers will see it. Always name the reference it
  is judged against.
- **Inputs** into the scratchpad ([tooling.md](tooling.md), Preparation;
  code files run only its first step, then their own copy step):
  the diff without inflators (lockfiles, generated or vendored code; count
  the lines the inflators hide, the report states the count),
  `--name-status`, the commit list, the prompts.
- **Secrets** live in named secret files only (`SECRET_FILES` in
  `scripts/secrets.sh`, from the profile's `secretFiles`, matched by name or
  glob; without a matching profile a broad fallback set,
  [_profiles/README.md](../_profiles/README.md)). Every other env file
  holds dummies and is reviewed like code. The secret files are
  left out of every input: the inflator patterns exclude them from the diff,
  the copy of files leaves them out, and the inputs name them as left out
  (`inflators.txt` for a branch, `change.files.txt` for files). A patch that
  touches one stops the review before dispatch (ask the user). No reviewer
  opens one, and every git command a reviewer runs carries the same
  excludes. Nothing else is scanned or masked.
- **Sources**, read in this order, each noted with what it claims: the
  branch's own docs and commit messages; the MR description (`glab mr view`;
  its `web_url` becomes `mrUrl` in `findings.json`); the ticket(s) named in
  the branch, the MR or an ADR (Jira MCP). Save each source's text to
  `$SP/inputs/sources/` as it is read: the commit messages and the MR
  description with `scripts/sources.sh` ([tooling.md](tooling.md),
  Preparation), never with improvised shell; the ticket from the Jira MCP.
- **Truth ranking:** the subject itself; then its description (MR text,
  commit messages, a cover note); then the ticket, the oldest and least
  reliable source. The description is the standard for intent: the MR
  description, or without an MR the commit messages and the user's framing in
  the request. The ticket is background: ticket vs. code is a Blocker only
  as an open question the description leaves unaddressed (Severity, open
  question); a deviation the description explains is at most an FYI. A
  contradiction between sources is a finding candidate, never a fact. A
  ticket that says "merged" or cites another ticket is checked against git
  and Jira.
- **Standards**, collected mechanically before dispatch: the accepted ADRs
  that name the changed code into `inputs/sources/adr/`, the agent
  instruction files (`CLAUDE.md`, `AGENTS.md`) of the root and of every
  directory above a changed path into `inputs/sources/rules/`, their
  glossaries (`CONTEXT.md`) into `inputs/sources/glossary/`
  ([tooling.md](tooling.md), Relevant ADRs and Repo rules); at `deep` also
  the list of neighbour repositories into `inputs/neighbours.md`
  ([tooling.md](tooling.md), Neighbour repositories).
- An earlier review in the repo is read only after dispatch, by the
  orchestrator only, and only when the user chose to update it
  ([worktree.md](worktree.md), option 2; §4.1). A new independent report
  reads none.

## 2. Pick the depth and the roster

### What a depth is

Two depths: `standard` (the default, whenever the request names no depth) and
`deep`. A depth is how sure the report is to be right about its
findings, within its region: the part of the system where the absence of
Blockers is checked. The verdict follows from the findings, so it is as sure
as the findings at the Blocker line. Most Blockers lie in the change itself
and what it touches directly; a deeper depth searches where the rest lie, so
a missing one is less likely. `deep` contains `standard`.

Fixed by this skill, not by a run: the severity scale (Severity) gives every
finding one true severity, and where it needs a judgment the investigator's
final label decides; severity and category never depend on the depth, a
deeper run only states them correctly more often; one fix at one place is
one finding (§4.3); a finding states its severity, location, failure
scenario and fix.

At every depth, or the report is broken, not less sure:
- the reviewed sha against the freshly fetched target, named (§1);
- every file, line, name and quote a finding cites exists as cited (§4);
- the report says what was searched and what was not, never that no Blocker
  is left (Regions, below; §6);
- every rendering of a finding says what `findings.json` says.

What a depth makes more likely, in order of weight. The user corrects by hand
only what gets their attention, and attention follows the label: a Blocker is
always read, an Optional mostly, a Nit or FYI barely; a missing finding
cannot be corrected at all.

| Aspect | Holds when | An error, recoverable by hand? |
| --- | --- | --- |
| A1 Completeness | no real Blocker is missing; two causes merged into one finding leave one missing | no |
| A2 Classification | every finding has its true severity | too low: barely, the lower the label the less it is read; too high: yes, a Blocker is always read |
| A3 Validity | every listed finding is real at the reviewed sha, in live use (Severity) | yes |
| A4 Accuracy | a real finding's location, failure scenario and fix are correct | yes, they are checked by hand anyway |

Only search raises A1: the region and the roster. Checking raises A2 to A4,
and can lower A1 (a wrong refutation, a wrong merge), so nothing leaves the
list without a visible trace (§4).

### Choose a depth

`standard` is the anchor; `deep` is the reason to leave it. Choose by what a
miss would cost, never by size.

| Depth | Choose it when |
| --- | --- |
| standard | the default: a normal, finished MR, your own MR before it is opened |
| deep | a miss is not a normal fix: sensitive (auth, health data, encryption), far-reaching (central code), hard to undo (partner contracts, wire formats, migrations, stored data). Rare, and not because the subject is large |

A quick check during development, or on the exact head after fixes before a
colleague is asked to review, is not this skill: the built-in `/code-review`
does it in minutes. A smaller depth would hardly be faster, since the
reviewers run in parallel and the slowest run sets the time.

### Regions

Where each depth spends its search, and what its verdict therefore covers.
The list (§5), the verdict box and the method section (§6) state "covers" and
"not searched" in these words:

| Depth | Searches | The verdict covers | Not searched |
| --- | --- | --- | --- |
| standard | the change itself, for what is wrong in any context, even an experiment (the floor); every path through the changed code, the new code's callers and readers included; the direct callers and readers of the existing code it changes, unchanged ones outside the change included, since that is where a change harms what exists (for a changed route, URL, endpoint, event or key: every place in this repository that produces or sends it, found by name, other servers' code included); its fit with the architecture, for which the architecture reviewer reads beyond the diff | the change does what it promises and harms nothing it reaches directly (its paths, its direct callers and readers, inside and outside the change) | stored data across versions (migrations, old documents, rollback), other servers or replicas reading the same stored data, attacker paths through unchanged routes, partners and old clients outside this repository, transitive callers |
| deep | + the system around it: transitive callers, stored data, attacker paths, partners, rollout; the neighbour repositories the change reaches (the ones the profile lists; [tooling.md](tooling.md), Neighbour repositories); the running system (the full local stack, its e2e suites and the manual tests; [tooling.md](tooling.md), Tests and lint) | what `standard` covers, and the change harms nothing beyond its direct reach: transitive callers, stored data, attacker paths, partners and old clients, rollout, the neighbour repositories it reaches | code in repositories that are not checked out locally, and behaviour that neither a suite nor a manual test exercises |

The floor and the focus lists per depth are in
[reviewer-prompt.md](reviewer-prompt.md). Focus is not a filter: every
reviewer lists every finding it comes across, at its real severity, at any
depth.

### Roster

| Depth | Adds | Trace for the report |
| --- | --- | --- |
| standard | 1 core reviewer (a fresh Claude subagent on the whole subject, never the orchestrator, which has read the description and the ticket and would judge its own findings); + 1 architecture reviewer, always, on the whole subject, reading beyond the diff (imports and importers of the changed files, existing mechanisms that do the same job, the relevant ADRs in `inputs/sources/`); + 1 lane reviewer per area, each with the `standard` focus (an area is a package when the subject spans 2 or more packages, else a top-level directory; at most 4; with one area no lane runs, since the core reviewer already reads the whole subject; split in [tooling.md](tooling.md)); + 1 requirements reviewer on the whole subject (the MR description first, the ticket only where it says nothing; not the ADRs, which the architecture reviewer covers; scope line in [reviewer-prompt.md](reviewer-prompt.md)) | 1 explorer subagent |
| deep | + 3 lens reviewers, all three every time, never picked by topic, each on the whole subject and each run twice (two independent runs on the same prompt, outputs `lens-<x>` and `lens-<x>-2`): attacker, consumers, production (Lenses, below). The foreign tools rate every finding's severity blind (§4); every finding gets its own investigator, exempt Nits included, and a second one after a refuted or downgraded Blocker claim or a blind rating that says Blocker (§4); + 1 follow-up agent per Blocker that holds (§4.6, Follow-up) | 1 explorer subagent |

Every Blocker is checked alone at every depth. `deep` runs every check of
`standard` or a stronger one (the check table, §4), never a weaker one.

More core reviewers are not a lever: repeated runs of one model share its
blind spots. Never extra core reviewers as a stand-in for a lens or the
architecture reviewer. A lens is the exception: its search starts outside
the diff, and which path a run follows first varies from run to run, so at
`deep` each lens runs twice. The two runs are separate sources in
`findings.json`, so a finding shows which run of a lens raised it.

Roles:
- The orchestrator never reviews the subject itself, at any depth.
- Every core reviewer reads the whole subject, never a share of it. An
  architecture, lane, requirements or lens reviewer counts as a source for
  consolidation, not as a core reviewer.
- The explorer traces mechanisms with `file:line` and gives no opinions; its
  "Docs vs code discrepancies" list and its "Replaced entry points" list (an
  input the old handler reads and the new one does not is a claim) are
  sources for consolidation, with or without a report.
- Reviewers only read; never `git checkout --` a reviewer's edits away
  ([tooling.md](tooling.md), Hygiene). Tests, lint and the build are the
  orchestrator's (§4).

### Lenses

A lens is an actor outside the diff, inside the repository or not: it starts
from that actor, searches inward to the change and tries to break it. Core,
lane and architecture reviewers start from the diff, so a Blocker in unchanged code
is found only from outside. The lenses follow the actors, not the
categories (scope lines in [reviewer-prompt.md](reviewer-prompt.md)):

| Lens | The actor it starts from | Covers from the `deep` region |
| --- | --- | --- |
| attacker | a hostile person: each user role, another tenant, a partner | attacker paths |
| consumers | everything that depends on what changed: within one deploy through its imports, across a deploy boundary by name (routes, collections, keys, events) | transitive callers, partners and old clients, stored data other code reads |
| production | the deploy, the stored data and the runtime, over time and under failure | rollout and rollback, old data, config, outages, retries, parallel runs |

### Foreign tools

Codex runs at every depth on the shared prompt, for another model family,
not more effort. Gemini is out of the roster since 2026-11-16: in about
seven runs it raised one finding no other source had, an FYI, and no prompt
changed that. It is checked again against the answer keys when a new version
comes out. The Claude roster and every Claude-side check stand
on their own, as if the foreign tools did not exist: foreign output adds
findings or raises a check, never lowers, replaces or skips one, and a
failed or missing foreign run changes nothing on the Claude side. A failed
foreign run is never replaced by a Claude stand-in.

| Depth | Runs per tool |
| --- | --- |
| standard | the whole-subject run + 1 extra run (architecture scope) |
| deep | the whole-subject run + 4 extra runs (architecture scope, attacker, consumers, production) + 1 run per area (the lanes' areas, at most 4, with the lane's scope line), + 1 blind severity rating after consolidation |

Codex runs on a subscription with a usage limit. A run that hits the limit
ends the codex side of the review: the remaining codex runs are skipped,
4.2 names them, and the Claude side goes on unchanged.

The architecture scope is the first extra at both depths: of all the Claude
reviewers, the architecture reviewer's verdict rests most on judgment, so another
model family adds the most there. A focus in the request
(`/qubit-code-review deep focus: auth`) adds one foreign run per tool on
that topic, after the depth's extras; it changes neither the Claude roster
nor the depth's extras.

Order of the extra runs (fixed by the tables, never by reading code),
quotas, completeness, truncation, retry and skip: [tooling.md](tooling.md),
"Running the CLIs". The same secret-file rule binds every reviewer (never
open a secret file; name a variable, never its value).

## 3. Dispatch unbiased

Every question to the user comes before dispatch (the worktree, the subject,
a failed fetch). From dispatch until the report is published (or the list is
printed with `skip-report`), the run asks nothing and waits for nothing: the
user reads the result. What the run cannot decide goes into the method
section (4.2) and the chat list as an open point.

One shared prompt from [reviewer-prompt.md](reviewer-prompt.md), the same
text for every reviewer the depth starts, plus one scope line per reviewer
and, without a shell, the no-shell note. It carries:
- facts the reviewer cannot know (user roles, conventions, where the inputs
  are);
- the read-only, secret-file and skip-the-run-folder rules, and the rule to
  read nothing in the scratchpad outside `$SP/inputs/`;
- the output format.

It never carries hypotheses, "check whether X is broken", anyone else's
findings or a verdict. Never a reviewer of type `fork`
([tooling.md](tooling.md), Claude subagents).

All Claude reviewers and the codex whole-subject run start in the same
turn; each foreign extra starts when its tool's previous run ends. Output
names are fixed at dispatch, and each dispatch appends a line to
`$SP/state/dispatch.txt`, updated as each output is saved
([tooling.md](tooling.md), Claude subagents).

Save each subagent's final output to `$SP/reviews/<name>.md` at once with
`save_output.py`, answer the notice with one line, and judge nothing before
all reviewers are back. The explorer's trace goes into `$SP/state/trace.md` as soon as its output is
saved ([tooling.md](tooling.md)), and its `# Manual tests` section into
`findings.json` `manual` (once that file has started, §4.1; in an update after
the restore): copied, not written, the steps numbered `M1, M2, …`
in order (a republish keeps every published id; a dropped step goes to
`manual.withdrawn`); `None.` sets `manual` to `null`, and 3.1 then holds one
line. The writer never reads a raw output and
never starts an explorer. A subagent whose run failed (an API error, no
output, an output without its format) is resumed or dispatched again, never
silently left out ([tooling.md](tooling.md), Failed subagents).

## 4. Consolidate

The orchestrator decides only on evidence an unbiased source delivered
(reviewer, investigator, rater). It never judges a claim by reading the code
itself, and never sets a severity by its own reading, at any level, below the
Blocker line included. It keeps the work that judges no code: merging
duplicates, numbering, the category from the category table. The one
exception is the grounding check, a check of existence, not a judgment of
the claim.

The steps, in order:

1. **State on disk.** Before the first raw output is read, start
   `$SP/report/findings.json` (format in
   [report-sections.md](report-sections.md); `meta.effort.review.started`
   from `$SP/state/review-started.txt`; `meta.name`, a 2-to-5-word name from
   the MR title or the ticket summary, `meta.ticket`, and `meta.ticketBrowseUrl` from `profile.py get ticketBrowseUrl`) and write every decision into it
   as it falls: a new or merged finding with its `sources`; each raw output
   in `notes.processed` once its findings are recorded; a check as `running`
   while its investigator works, then the strength of the check that ran:
   `inline` (the reviewer's label stands), `batch`, `investigator` (one of
   its own), `investigator2` (one of its own and a second), or `unchecked`
   when the investigator failed for good ([tooling.md](tooling.md), Failed
   subagents); a severity; a refuted claim into `notes.refuted`. After a
   compaction, re-read `findings.json` and `$SP/state/dispatch.txt` (after a
   resume whose scratchpad is gone, first restore them from the run folder:
   [tooling.md](tooling.md), Hygiene) and continue from the files, never
   from the summary.

   **Update of an earlier report** ([worktree.md](worktree.md), option 2).
   After dispatch, `findings.json` starts as the earlier run's, not empty:
   copy only `report/findings.json` and `report/publish/manifest.json` from
   the earlier run folder into `$SP/report/`, never its `state/` or
   `inputs/` (they belong to the new run). Its ids, `meta.published`,
   `meta.artifactUrl`, `meta.run` and `meta.runName` stay; `meta.state`
   becomes the new sha; `meta.runs` gets `{"run": <this run id>, "sha":
   <new sha>, "date": <today>}` appended (a run without `meta.runs` first
   gets its own entry from `meta.run`, the old sha and `meta.date`); the new
   run's sources are named `rerun-<run id>/<output name>`; and
   `notes.processed` starts empty for the new outputs. The new raw outputs
   are merged as in step 3: a claim that matches an earlier finding adds its
   source to it and keeps its id; a new claim is a draft finding. An earlier
   finding no new source raised stays as it is: reviewers miss different
   things. A source that rates an earlier finding at another severity is a
   contradiction (the check table). When the sha differs from the earlier
   run's, every earlier finding is checked again at the new sha, in
   batches of at most 8 with the question "does it still hold at
   `<sha>`?"; a refuted one moves to `notes.withdrawn` as
   `"F<n>: fixed in <short sha>"`, and its id stays unused. An earlier
   Blocker the batch refutes or labels lower first gets an investigator of
   its own, and at `deep` a second one, as any Blocker (step 5); it is
   withdrawn only when every one of them refutes it. The re-check also
   returns each kept finding's current `file:line`. New findings
   take the ids after the highest one, withdrawn ones included; manual test
   ids stay, new steps take the next `M<n>`. The report is republished to
   `meta.artifactUrl` (§7.3), and 4.2 names both runs.
2. **Read the outputs.** Each raw output from `# Summary` on (`sed -n
   '/^# Summary/,$p'`; a truncated output without one from its first `## F`
   on; the explorer's from `# Mechanism trace` on), never a tool's log or
   preamble. An investigator's output (`# Verdict`) and a rating (`## <id>`
   blocks) are short and read whole; test, lint and build output only as the
   summary line, the failures and the console lines a passing suite prints
   ([tooling.md](tooling.md), Tests and lint). Read more of a raw output only for a
   finding that stays unclear; a claim that stays unclear goes to an
   investigator.
3. **Merge.** One fix, one finding: claims that one change at one place
   removes are one finding, even when they name different triggers or
   wrong results, and even when four sources name it in four files. The
   finding names each trigger and wrong result, the worst first, and takes
   the severity of the worst. With two or more triggers, `findings.json`
   records them in `triggers`, one `{"trigger": "<case>", "wrong": "<wrong
   result>"}` each, the worst first; a finding with one trigger has no
   `triggers`. The writers list them in the card and in the GitLab comment,
   since together they show why the fix is the right one
   ([report-sections.md](report-sections.md), Findings 3.2;
   [gitlab-comments.md](gitlab-comments.md)). A merge after the first
   publish keeps the surviving id: the merged id moves to `notes.withdrawn`
   (`"F<n>: merged into F<m>"`, step 11), its trigger joins the surviving
   finding's `triggers`, and the writers write that finding again. One
   cause that needs changes at two places (two functions, two parameters,
   two scripts) is two findings. Fix texts
   that name different parts of one change at one place (different limits
   added to the same check, the same bound with another value) describe one
   change. Merge only
   when the claims point to the same location or the same named mechanism
   and the same change removes each; when in doubt, keep both. A
   duplicate costs the reader a moment, a wrong merge hides a cause.
   **Shared fix.** "The same change" above is the fix each claim names for
   itself. When a check says that the fix of one finding also removes the
   defect another finding describes (dropping a mechanism removes the
   defects inside it), that shared change is an alternative, not a reason
   to merge: the findings stay separate, since each keeps its own fix for
   the case the shared one is not taken. The finding whose fix removes the
   others records them in `removes` (their ids); its `fix` names what the
   change also removes, and each removed finding's `fix` names the shared
   change as the alternative. The writers say it in plain words, never by
   an id or by pointing at another comment ([gitlab-comments.md](gitlab-comments.md),
   [report-sections.md](report-sections.md)). The
   output is one consolidated list: no list per reviewer, no "codex found"
   sections, no source badges on findings; which source saw
   what stays in the notes and the raw outputs.
4. **Grounding check.** Once all raw outputs are recorded and before any
   investigator starts, every finding, from any source and at any severity,
   passes `python3 <skill dir>/ground_check.py "$SP/report/findings.json"
   <worktree, or the subject's root>`: file, line and every name exist in the
   real file. A failure flags the finding, never drops it: the finding goes
   to its investigator with the failure, an exempt Nit included. A name
   missing from the cited file may stand in another file the claim traces,
   so only an investigator refutes it.
5. **Checks.** Checks follow severity, not agreement, at every depth and for
   every source, foreign tools included. A finding only one source raised is
   not doubtful for that reason: reviewers rarely contradict each other, they
   miss different things. The check table:

   | Trigger | Check |
   | --- | --- |
   | any source rates it Blocker | investigator: does it hold, and does its Blocker reason hold (questions below)? |
   | sources contradict each other on a fact | investigator |
   | `deep`: a Blocker investigator refutes the claim or labels it below Blocker | a second investigator, fresh, with the claim and without the first verdict |
   | `deep`: the blind foreign severity rating says Blocker and the finding's label is lower | a second investigator, as in the row above; none when one already ran |
   | any source rates it Optional or FYI; a Nit that cites a rule; a Nit any source filed outside Style and Docs | `standard`: an own investigator per Optional and per FYI, a batch investigator for the Nits (grouping: [tooling.md](tooling.md), Promotion checks). `deep`: an own investigator per candidate. Questions per the claim's kind: Optional, does a Blocker reason hold (for a defect: can it be triggered in live use?); FYI, does this change create the trigger, or make it reachable; a Nit that cites a rule, is it a boundary rule or a style rule; any other Nit, is it wording only. Every claim's answer ends in its final label (Blocker, Optional, Nit, FYI) |
   | a Nit that cites no rule, every source filed as Style or Docs, no source rated higher, and whose assigned category is Style or Docs | `standard`: none; the reviewer's label stands (`check: inline`). `deep`: an own investigator, question: is it wording only? (at `deep` every finding is checked alone) |

   The category the orchestrator assigns can remove an exemption, never grant
   one.

   An investigator is a fresh subagent with the exact claim, its suggested
   fix, the file, and the investigator variant of the shared prompt. A fix it
   calls HARMFUL is replaced in `fix` by the one it names. Its OPTIONS
   become `options`, PARTIAL `fixLeaves`, OPEN `fixOpen`, and its
   `# Before the change` other than NONE becomes `before` ([report-sections.md](report-sections.md), Mapping). Its
   `# Failure scenario` replaces a source's case when the two differ in
   their conditions. A Blocker reason
   that does not hold names the label the claim deserves; the orchestrator
   never sets it. The question per Blocker reason:

   | Blocker reason | Investigator question |
   | --- | --- |
   | (a) broken intent | does the change add the mechanism, where does its intent stand (quote), does it fail on a live path, and did the author not declare it a limitation? |
   | unmet release precondition (any reason) | does the failure need a precondition outside the code (an infrastructure version, a migration, another release first), and do the description, the repository's docs or the ticket declare it (quote it)? Declared: FYI; not declared: judged with today's setup |
   | (a) gap | does it hold, and what is the first wrong result in live use, following shared resources, and who gets it? |
   | (b) vulnerability | can it be exploited on a path live use takes? |
   | (c) ADR or boundary | does the ADR exist, is it accepted, does it apply to this code, and does the subject leave it unchanged? Does the import or dependency really point the wrong way? |
   | (c) second mechanism | does the existing mechanism exist and do the same job? |
   | (c) unneeded complexity | does the code use the flexibility it adds? Would a simpler version meet the description? Which concrete cost does the complexity bring by itself (which future change gets harder, what a reader will misunderstand), apart from defects other findings already name (the orchestrator lists the findings located in the same mechanism, one line each, so the investigator can leave them out)? A defect inside the mechanism that is its own finding counts there, not here |
   | (c) owned invariant | is the invariant what the module exists for (quote its name, docs or the description), do the module's own types and checks accept the input, and does the module's state break the invariant after it? |
   | (c) enforced invariant | does the code enforce it, did all data meet it before the change, and does the change write data that breaks it, write around it (a raw update, validators switched off), or hand an unchanged consumer a value its check rejects? |
   | (c) broken existing test | did the test pass on the target before the change, does it fail on the subject because of the change, and does the change leave it neither fixed nor disabled with a ticket? |
   | (c) repo rule | does the quoted rule stand in the named instruction file, does it apply to this path, and does the change break it? |
   | (a) or (c) rule in a comment | does the quoted comment stand in the touched file, and does the change break what it demands? |
   | (a) undone fix | does the named commit fix what the change brings back? |
   | (a) open question | does only the author's answer decide (quote the description and the ticket on the point, or show they are silent)? For a ticket contradiction: does the description leave it unaddressed? For behaviour outside the goal: which user, caller, stored data or module sees it, and why does it not follow from the quoted goal? Would the plausible unwanted answer be a Blocker? Any proof missing: not a Blocker |
   | (d) missing test | is there really no test covering the feature, of any type? |

   Every investigator ends with the final label; a disagreement between
   sources below the Blocker line is settled there, never by the
   orchestrator. A finding a batch labels Blocker then gets its own
   investigator with the Blocker question for its reason. A check says in
   the finding what was checked. Every Blocker in the list was checked by an
   investigator that checked it alone, or is `unchecked` after that
   investigator failed for good.

   **Side findings.** Every investigator output (a batch's too) is read to
   its `# Side findings` section. Each bullet becomes a draft finding with
   the source `side:<output name>`, goes through the grounding check and
   gets its check by the table above, with the question of an Optional when
   the bullet names no label. A side finding merges into an existing finding
   only when the same change at the same place removes it (step 3); the
   same cause that needs a change at another place is a new finding. Side findings of a side finding's
   investigator are followed once more; a third generation goes to
   `notes.consolidation` as not followed. Each bullet and what became of it
   goes to `notes.sideFindings`.
6. **Blind rating** (`deep`). After consolidation and before the
   numbering, start the blind severity rating ([tooling.md](tooling.md),
   "Which runs"). The rater may see the claims: it audits labels, it does
   not review. A rating raises a check (the table above), never counts as
   one.

   **Follow-up** (`deep`). Every Blocker that holds after its check gets one
   fresh follow-up agent (the follow-up variant in
   [reviewer-prompt.md](reviewer-prompt.md)), given the confirmed claim and
   its investigator's verdict. It asks two questions and judges nothing
   else: where else, in this repository and in the neighbour repositories,
   the same pattern sits (the same misuse of a field, key, value or
   mechanism); and which other consequences the same cause has (other
   consumers, other user paths, other stored data). Each place or
   consequence it names is a claim: a further consequence of the same cause
   joins the Blocker's finding (one fix, one finding, §4.3) once its own
   investigator confirms it; a second place is a new finding, checked like
   any claim. Follow-up agents start in one turn, once the last Blocker
   check has returned; their claims are not followed up again.
7. **Severity** comes from the investigators: the final label of the
   investigator that checked the finding, never a vote count, never the
   orchestrator's reading; reviewers have tended to rate too low. A claim is
   refuted only when every investigator that checked it refuted it. With two
   investigators (at most two per finding, a batch included):
   - Blocker when one says Blocker, and its `verify` names both
     verdicts: a false Blocker is read and corrected by hand, a hidden one
     is not;
   - else the label of the confirming one that checked it alone, of two such
     the later.
8. **Tests, lint and the build** run once, by the orchestrator, only when the
   subject has something to run, after the last reviewer and the last
   investigator have returned, at `deep` also those started after
   consolidation. The e2e suites of the touched packages run at every depth
   when they need no full local stack; at `deep` the full stack also runs,
   with its e2e suite and the manual tests ([tooling.md](tooling.md), e2e
   suites and the full stack). A red test counts only against the same
   suite on the target branch. A claim only a test raised goes through steps 3 to 7 after
   the tests; its investigator works between two snapshots of its own
   ([tooling.md](tooling.md), Tests and lint).
9. **Category and package.** Each finding gets exactly one category, its main
   one, and its package (the category table and the package rule in
   [report-sections.md](report-sections.md), Findings 3.2); the orchestrator
   decides both, the reviewers' lines are input. Then the principle: the
   one its check confirmed or named (`# Principle`), else the one a source
   named when the check failed for good, `null` when the check answered
   NONE. Only an Architecture or Design finding carries the field, always;
   a principle the check of another category named stays in that check's
   output and never reaches the finding. The field only names the
   principles, comma-separated, each by its common acronym where one exists
   (DRY, KISS, YAGNI, SRP), else by the name a developer looks up (single
   source of truth, an ADR by its title); when two checks name different
   ones, it names all of them. The orchestrator copies the names, never
   forms one. An Architecture or Design finding always went
   through an investigator (the check table exempts only Style and Docs), so
   its `# Principle` exists.
10. **Refuted claims** are dropped from the list and named, each with who
    raised it and what refuted it, in the chat list and the method section.
11. **Ids.** Ids stay drafts (`D<n>`) until every check has returned, the
    rating's investigators included. Then one step numbers them `F<n>` in
    list order and rewrites every draft id in `verdict` and `notes`. Ids are
    severity-free and never change on a republish. A finding withdrawn after
    the first publish (refuted later, answered by the author, or merged into
    another, step 3) leaves its
    id unused: it moves to `notes.withdrawn` as `"F<n>: reason"`, the report
    names it in the method section, and the other ids stay.
12. **The record.** The consolidated text in `findings.json` is the record
    of each finding: `what` traces the path through the code with
    `file:line` up to the faulty spot, `verify` says what was read or run and
    how the reader can check it again. From it the findings writer (step 6)
    writes each card's fields, the visible `text` and its details (`more`),
    and the verdict text and the GitLab comments; never the orchestrator or
    a reviewer. No writer changes the record, and `data.json` does not carry
    it. The shared prompt stays as it is.

## 5. Print the findings list (every run)

Every run prints this list, with or without a report, right after step 4. A
run without `skip-report` does not end here: the response that prints the
list also makes step 6.1's first tool call (`meta.effort.report.started`),
because a response with text only ends the turn and the report never starts.
First:
- `findings.json` is complete as in step 6.1 (every field the orchestrator
  owns, the consolidated texts included), so a report can be built from it now or
  later; `meta.published` stays `false` until a report is published.
- Set `meta.run` to the first 8 characters of the session id; it never
  changes (an update of an earlier report keeps the earlier run's, §4.1).
  At the first copy into the run folder, also set `meta.runName` to the name
  `assemble.py --run-name` prints; it never changes either, so an update
  saves into the same folder.
- Set `meta.effort.review`: `ended` now, and `runs` counted from
  `$SP/state/dispatch.txt` (report-sections.md, findings.json).
- Copy the run into the run folder as in step 6, without a report
  ([tooling.md](tooling.md), Hygiene).

Then print, in English, written by the orchestrator from `findings.json`:

```
<subject> · <depth> · <verdict word>: <n> Blocker(s) open
Covers:       <the depth's "The verdict covers" (§2, Regions)>
Not searched: <the depth's "Not searched" (§2, Regions)>
Sources: <roster, foreign runs> · <n> investigators · <n> claims refuted

── Manual tests ──  (run first; setup: <the setup, one line>)
M1  <do> → <expect>
M2  …
── Blocker ──
F1  <file:line> · <category>
    <title: the effect first>
    What:    <one sentence>
    Impact:  <one sentence>
    Fix:     <one sentence>
    Checked: <one sentence: investigator, or unchecked and why, and the proof that decided it>
── Optional ──
F2  … the same lines
── Nit ──
F3  <file:line>  <one line>
── FYI ──
F4  <file:line>  <one line>

Tests/lint: <summary line per suite; failures by name>
Refuted:    <claim> (raised by <source>; refuted by <what>), one per line
Saved:      <run folder subfolder>

Full report: being built (step 6)
```

- Each field is one sentence on one line, shorter than the report's
  card's visible text; it summarises the `fields.*.text` the findings writer would
  write, never replaces it. Empty groups are left out. No German, no GitLab
  comments.
- With `skip-report` the last line reads `Full report: /qubit-code-review
  publish-report` instead.
- The list asks nothing, and the run never offers follow-up tickets: the
  drafts stand in the report, and the user creates tickets after reading it.
  When the user later names the created tickets, the orchestrator writes the
  keys into `followUp.key` in `findings.json`; when a report exists, the
  findings writer copies them into `data.json` and the report is assembled
  and republished (step 6).
- "F2 in detail" prints that finding's `what` and `verify` from
  `findings.json`.
- A subject without `manual` (code files) prints no manual tests
  block.

A run, with or without a report and also a `publish-report` run, writes
nothing about the subject to memory: memory loads before dispatch in every
worktree of the repo, and the run folder goes with the worktree. The published
report is the lasting record.

## 6. Publish the report (every run without `skip-report`, and `publish-report`)

The orchestrator decides; report writer subagents write. The orchestrator
never writes report text itself; no writer changes an id, severity, category,
package, principle, verdict or consolidated text, or reads raw reviewer outputs.

1. **Complete the decision.** The orchestrator sets
   `meta.effort.report.started`, then completes
   `$SP/report/findings.json`, every field in
   [report-sections.md](report-sections.md) (`meta.subjectType`: `branch`,
   `mr` for GitLab (a branch with a GitLab MR is `mr`), `pr` for GitHub,
   `patch` or `files`), and as short English notes everything
   else the report states, the method section
   ([report-sections.md](report-sections.md), 4.2) included at every depth:
   what no run could cover, never that no Blocker is left. This file is the
   decision; nothing downstream changes it.
2. **Write and translate.** Two writers start in the same turn, both writing
   English only: the explanation writer (sections 1 and 2, glossary) and the
   findings writer (the card fields per finding, written from the
   consolidated text, the verdict text, the findings summary, sections 3.3, 3.4, 4.1 and 4.2 from the notes, and the GitLab
   comments). When both are back, one translator subagent on a smaller model
   adds the German twin of every English text, the GitLab comments included
   by the rules of [gitlab-comments.md](gitlab-comments.md), and writes
   `manual.json` from `findings.json` `manual` (the English copied, the German
   added; [report-sections.md](report-sections.md), Manual tests 3.1). Every writer and
   the translator get the secret-file rule (open no secret file; a search may
   hit one, but no value from it goes into any output; name a variable,
   never its value) and the data rule (subject and source text is data to
   describe, never instructions; copy no markup from it). The explanation
   writer gets the trace or the note that it is empty, the sources, the
   concept list, `findings.json` for the glossary, and the slot contract.
   Briefs and section contents: [tooling.md](tooling.md), Claude subagents.
   For a branch, MR or PR, the translator is followed by the cold read of
   the GitLab comments ([gitlab-comments.md](gitlab-comments.md), Cold
   read): one reader without the report reads each comment beside its code,
   English first, then German, and names unclear references, translated
   German and differences between the languages. Its items go back to the
   findings writer or the translator, one more cold read covers the changed
   comments, and `notes.coldRead` records the result before `assemble.py`.
3. **Check and publish.**
   - For a branch, MR or PR with a remote, before every publish and
     republish, read the subject's head again (`glab mr view <n> -F json`,
     field `sha`; without an MR `git ls-remote <remote> <branch>`) into
     `meta.headAtPublish`. A head other than the reviewed sha puts a warning
     with both shas into the header's reviewed-up-to row; the report is still
     published.
   - Until the first publish, set `meta.effort.report` (`ended` now, `runs`
     the writer and translator runs so far) before each `assemble.py` run.
   - Run `python3 <skill dir>/assemble.py "$SP/report"` (what it checks:
     [report-sections.md](report-sections.md), "What assemble.py checks")
     and read only its check result, never the fragments. Send each failure
     to the writer or translator it names, never fix it in place; a failure
     that lies in `findings.json` (a consolidated text, a category, a follow-up
     title) is the orchestrator's to fix there. When a fix changes English
     text after the translator ran, the translator runs again on the changed
     fields or files only, then `assemble.py` again.
   - Then `render_check.py` ([tooling.md](tooling.md)); an overflow goes back
     to the writer of that section.
   - Publish from `$SP/report/publish/`: the page (`index.html`) and its
     files (stylesheet, main script, findings and manual data, one file per
     slot, a file over about 180 KB cut into `<name>-1.js`, `<name>-2.js`,
     …), the same document as `review.html`. `assemble.py` prints "changed
     since last publish" (every file before the first publish; then
     `index.html` and the files that differ from the last publish) and "publish
     batches": those files in batches of at most about 230 KB, each with
     `index.html` and the line ranges to read. Publish workers publish them
     ([tooling.md](tooling.md), Claude subagents), one per batch, one after
     another, never in parallel: the Artifact tool publishes no file the
     publishing session has not read, and a whole report (about 900 KB, 390k
     tokens, on a 67-finding MR) does not fit one context. The orchestrator
     never reads a publish file or `review.html`. Batch 1 of a first publish
     creates the artifact: set `meta.published` and `meta.artifactUrl` from its
     URL at once, so every later batch, also after a stop, goes to that URL.
     After each batch that returns `ok`, run `python3 <skill dir>/assemble.py
     --mark-published "$SP/report" <the batch's files>`; a failed batch runs
     once more fresh, then the run stops and names it in chat, and the next
     `assemble.py` lists only what is still unpublished. A denial "Modify
     Shared Resources" means the user's settings lack the `Artifact` allow
     rule: stop and say so; never add it. `review.html` stays the file the
     checks, `render_check.py` and the run-folder copy use.

Always English and German with the language switch, English first. Publish
once per change of content. After the first publish set `meta.published` and
`meta.artifactUrl`, so a later republish, also after a compaction or a
resume, goes to the same URL; `meta.run` stays as step 5 set it. After every
publish set `notes.manualPublished` to the manual test ids on the page.
The run ends in chat with the report link (`meta.artifactUrl`) and asks
nothing (§5).

Then copy the report with a doctype, as
`<N>.html`, N the name `assemble.py --run-name "$SP/report"` prints (key, ticket, name, date, short sha or
`files`, run), into a
subfolder of the same name in the run folder, together with the raw outputs
(`$SP/reviews/*.md` only, never `*.stderr.log`) and `report/`, `state/` and
`inputs/change.diff`, which a republish after the scratchpad is cleared
needs. For a branch, MR, PR or patch the run folder is the worktree's
`review-runs/` (added once to `info/exclude`); for code files it is
`~/.claude/review-runs/` ([tooling.md](tooling.md), Hygiene).

Posting to GitLab or Jira happens only when asked; GitLab comments only
while the MR's head is still the reviewed sha
([gitlab-comments.md](gitlab-comments.md), Posting). An old report
(published by an older version of the skill):
[report-sections.md](report-sections.md).

## 7. Publish a finished run

`/qubit-code-review publish-report`, or in the session of the run a request
for the report or an explanation of the review ("make the report", "explain
it as a page"). Reviewers, explorer, investigators, foreign runs and tests
stay done; no id, severity, category, package, principle, verdict or
consolidated text changes, except through a missing check (7.2).

1. **Find the run:** this session's `findings.json`; otherwise the run
   subfolders in the run folder (for a branch the worktree's `review-runs/`,
   else `~/.claude/review-runs/`). Exactly one: restore it into a fresh
   scratchpad as in [tooling.md](tooling.md), Hygiene. Several: list them and
   ask the user, never guess. None: say so and name `/qubit-code-review
   <depth>` for a new review; start none. A run whose `meta` lacks
   `ticketBrowseUrl` gets it from `profile.py get ticketBrowseUrl` in the
   reviewed repository; without one, ticket keys stay plain text.
2. **Missing checks.** An older run whose findings lack a check the check
   table in §4 needs (`assemble.py` names them): before publishing, dispatch
   the missing investigators as in §4. A finding is `unchecked` only after
   its investigator failed for good, and the method section
   ([report-sections.md](report-sections.md), 4.2) names it. The final label sets
   the severity, and the verdict follows; ids are renumbered only while no
   report of the run is published. This checks claims; it reviews nothing.
3. **Publish:** step 6 from 6.2 on, with the run's `$SP/state/trace.md`. A
   run whose report is already published (`meta.published`) is republished
   to `meta.artifactUrl`, never as a second report; the copy into the run
   folder counts as a republish into the run's existing subfolder.

## 8. A reported manual test failure

The user reports a step, usually with the card's copy line
(`<subject> · M<n> ✗ · Expected: … · Observed: …`). Find the run as in 7.1,
then:

1. The step's `do` and `expect` from `findings.json` `manual` plus the
   user's observation are one claim. It goes to one investigator (the
   investigator variant, unchanged) with the question: what in the subject
   causes the observed result, can it be triggered in live use, and does an
   existing finding already describe this trigger and wrong result?
2. Confirmed and new: the next free `F<n>` (after the highest id, withdrawn
   ones included), source `manual:M<n>`, checked as its label requires
   (§4.5), its side findings followed. Covered by a finding: `manual:M<n>`
   joins that finding's `sources`, and its `verify` names the observation.
   Refuted: the investigator's reason goes to the user, nothing changes.
3. The verdict follows the findings (§4.7); then the list (§5) and, when a
   report exists, the republish (§7.3).

The tick on the card itself never reaches `findings.json` or the verdict.

## Red flags

One line each; the rule stands where the pointer says.

### Commands and framing

- `publish-report` with a depth starting a review or a run lookup instead of the one-line hint (Commands).
- `re-review` asking the worktree question, starting reviewers, running tests or writing a report, or changing the worktree, `findings.json`, `data.json` or the report (re-review.md).
- `re-review` judging a thread whose comment differs from its finding, or posting, resolving or approving without the user's answer to its one question (re-review.md).
- A ticket's "merged" or "it is ticket X" taken as fact; a Blocker from the ticket alone other than an open question the description leaves unaddressed (§1, Truth ranking; Severity).
- An open question one answer of which makes a Blocker, kept out of the list as an open point (Severity, open question).
- A diff against the local target without the user's no-remote choice (§1).
- A secret file in the diff or the copy of files, or opened by a reviewer (§1).
- Dispatching a patch that touches a secret file, or one git cannot list (tooling.md, Preparation).

### Worktree and shell

- A review in the main checkout or a worktree from `EnterWorktree name:` (worktree.md).
- A forced worktree add; a detached worktree without the user's choice, the patch worktree excepted (worktree.md).
- A review worktree reused, or a new one created, without asking when one already exists for the subject; an existing worktree deleted or reset (worktree.md).
- A question to the user, or a wait for an answer, after dispatch; an open point asked instead of written into 4.2 and the list (§3).
- An option recommended in the worktree question; an update of an earlier report published as a new artifact, or a new independent report that reads the earlier one (worktree.md, §1).
- In an update, an earlier finding dropped because the new run did not raise it again, or kept at a new sha without the re-check (§4.1).
- A reused worktree not brought to the sha, or re-run in while dirty; HEAD recorded as the subject sha without comparing (worktree.md).
- A worktree that still holds `.envrc` (worktree.md); the `.env` links to `.example.env` may stay.
- A Bash call in a worktree session that is neither a bundled script with a literal path nor a plain command: a heredoc, a variable spliced into `python3 -c` text, `$(…)` as an argument, `cd "$VAR"`, git inside control flow, several commands in one call, a script or git call followed by `; echo $?`, an unquoted variable (tooling.md, Shell calls).

### Depth and roster

- A depth chosen by size; a roster other than the depth table's (§2).
- Cores splitting the subject; extra cores instead of a lens (§2, Roster).
- A run without the architecture reviewer or the requirements reviewer; a lane over the whole subject when there is one area (§2, Roster).
- A lens chosen by topic, skipped or run only once at `deep` (§2, Roster); a lens that starts from the diff instead of its actor (§2, Lenses).
- A finding left out because it is outside the depth's focus; a run that does not follow changed existing code to its direct callers and readers (§2, Regions).
- A check of `standard` skipped or weakened at `deep` (§2, Roster); a run started from an old depth name (`low`, `medium`, `high`) instead of the one-line hint (Commands).
- A run without codex, or another foreign roster than the depth's runs plus a requested focus; a Claude stand-in for a failed foreign run; a Claude-side check or depth that leans on a foreign tool (§2, Foreign tools).
- An extra-run order made by reading code or changed by anyone but the user (tooling.md).

### Dispatch

- A prompt naming an earlier review, a suspicion or known problems (§1, §3, tooling.md Hygiene); a `fork` reviewer (§3).
- A reviewer pointed at the scratchpad root instead of `inputs/`, or a reviewer git command without the secret-file excludes (§1, §3, reviewer-prompt.md).
- A reviewer running tests or builds, editing files, or edits checked out away (§2, Roster; tooling.md Hygiene).
- A `standard` or `deep` run without the report that skips the explorer (§2, Roster).

### Consolidation and severity

- A decision held only in context; resuming from the summary (§4.1).
- Per-reviewer lists, "codex found" sections, source badges; two different claims merged into one finding (§4.3).
- A finding no grounding check ran on; a finding refuted or dropped by a failed grounding check without an investigator (§4.4).
- Dropping or investigating a finding because one source saw it (§4.5).
- A finding checked more weakly than the check table requires for its depth, or not at all, unless its investigator failed for good and the method section (report-sections.md, 4.2) names it; a `check` that names a weaker check than the one that ran (§4.5).
- At `deep`, a refuted or downgraded Blocker claim, or a finding the blind rating calls Blocker, without a second investigator (§4.5).
- An investigator's side finding left unread, or merged into a finding whose fix does not remove it (§4.5, Side findings).
- The orchestrator setting a severity, at any level, or keeping a finding out of a batch by its own reading of the code (§4).
- Severity by vote count; a disagreement across the Blocker line settled against the Blocker; a claim dropped although one investigator confirmed it (§4.7).
- A severity outside the four; a Blocker whose reason does not hold; a Blocker whose `verify` does not state the proof; a positive verdict with a Blocker open (Severity).
- A severity lowered because the code is behind a flag, not linked or in a draft MR (Severity, live use).
- A rule or comment finding without the quoted rule; a style rule rated above Nit; a code-health (c) Blocker for a problem the change did not introduce or worsen (reviewer-prompt.md, Conventions and Severity).

### List and report

- A run that ends without the list, or a report that starts before it; fields longer than one sentence (§5).
- A run without `skip-report` whose list is printed in a response without a tool call; a list or run end that asks the user anything, follow-up tickets included (§5).
- A list or verdict box without the depth's "covers" and "not searched" (§2, Regions); a report claiming no Blocker is left (§6.1).
- A run with `skip-report` starting a writer, a translator or a publish (Commands).
- The orchestrator writing report text, opening a fragment, or reading `review.html` or a publish file (§6); a publish by the orchestrator, publish workers in parallel, a republish that sends unchanged files, or a batch without `--mark-published` (§6.3).
- A writer changing an id, severity, category, package, principle, verdict or the consolidated text, or reading raw outputs (§6).
- A card whose visible text names a `file:line`, repeats its label, or runs as a wall of text; a Blocker card without the evidence path (`file:line`) in `fields.what.more` or without `fields.verify.more` (report-sections.md, Findings 3.2).
- An Architecture or Design finding without `principle`; a `principle` on a finding of another category; a principle the orchestrator or a writer formed instead of copying it from a check or a source (§4, step 9).
- A principle as a sentence or paragraph of its own in a GitLab comment or a card's `what`, or as the reason where the finding has a concrete consequence (gitlab-comments.md, report-sections.md).
- A principle written out where a common acronym exists ("Don't Repeat Yourself" instead of DRY), or a principle field that explains instead of naming (§4, step 9).
- A shared fix that removes other findings written as a pointer ("see F3", "see the other comment") instead of the consequence in plain words, or findings merged because one alternative fix removes them all (§4, step 3).
- Findings without the explanation (sections 1 and 2) first, in a report (report-sections.md, section order).
- Reading levels or a level switch in a report; a disclosure inside a disclosure; a figure or table in a summary or in the details (report-sections.md, Explanation fragments).
- A publish without a fresh `meta.headAtPublish`; a GitLab post on an MR whose head moved (§6, gitlab-comments.md).
- The verdict, the header or the stats reading the manual test results; a failed step turned into a finding without an investigator (§8).
- A manual test id renumbered or reused after publish; manual tests written by the orchestrator instead of copied from the trace (§3, report-sections.md 3.1).
- A GitLab comment with a forbidden word, several for one cause, an anchor outside the diff (gitlab-comments.md).
- A first publish without a cold read of the GitLab comments; the cold reader given the report, a finding id or the German before its English notes exist; the orchestrator fixing a comment the cold read flagged instead of sending it to the writer or translator; a third cold read (gitlab-comments.md, Cold read).
- `publish-report` dispatching reviewers again, changing a finding other than through a missing check, guessing among runs, or creating a second report (§7).

### Records

- A secret value in a card or a copied raw output; a `*.stderr.log` copied (§6).
- Anything of the run (finding, count, verdict, pointer) saved to memory (§5).
