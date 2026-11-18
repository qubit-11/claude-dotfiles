# Review sections of the report

The report is built from [review-report-template.html](review-report-template.html)
in this folder. It embeds the `qubit-explanation-page` skeleton (tokens, both themes, the
top bar with the expand-all button and the language switch, the paragraph
disclosures, root-attribute visibility, print rules) and adds the review
components. The embedded parts are a copy: a change to the skeleton's top
bar, scripts, disclosure or visibility CSS is made in the template too.
`SkeletonSyncTest` holds the two in step: the top bar's buttons and their
labels, the language visibility, the `details.pt` and button CSS, the
counter, table-of-contents, reduced-motion and print CSS,
`overflow-anchor`, the scroll spy, the expand-all script and the switch
script; the template's tokens hold every skeleton token with the same value
and add the review's own colours. Allowed
to differ: `keyOf`, `notePlace` and `restorePlace`, and the template's own
`LABELS` selector, with which the template also keeps the reader's place on
finding cards and their fields. The cards render after the expand-all
script binds its disclosures, so the template calls `syncToggle()` itself
when a card disclosure opens or closes and after every render, and a filter
that renders the cards again while every disclosure is open opens theirs
too.
`assemble.py` fills it: `{{name}}` placeholders and the stats from
`findings.json`, each `<!-- slot:name -->` block from `$SP/report/name.html`,
the data slot from `data.json` (parsed, checked, and written into the report as
that checked array), the category chips and the table of contents from the
content. The placeholder content inside a slot shows the writer the expected
shape; where it and this file differ, this file wins.

To change a report published by an older version of the skill, edit that report's own HTML: its
data pairs are `[de, en]`, the current template's are `[en, de]`, so old data
in the new template swaps every language; reports from before `assemble.py`
have no slots.

## Explanation fragments

The explanation writer returns three fragments; the template owns every
`<section>` and every `<h2>` (section 2's heading per `meta.subjectType`
included), and `assemble.py` fails on any other shape:

| Fragment | Holds | Never |
| --- | --- | --- |
| `background.html` | `.subsec` blocks only: `#today` (1.1) first, then one per general concept | a `<section>`, an `<h2>` |
| `subject.html` | `#goal`, `#approach`, `#flow`, then one `.subsec` per concept the subject introduces | a `<section>`, an `<h2>` |
| `glossary.html` | the `dl` pair only | a `<section>`, an `<h2>` |

Each `.subsec` is `<div id="…" class="subsec">` with an `<h3>` as its first
element; the table of contents lists every `.subsec`, after one unnumbered
first entry, Overview / Überblick, that jumps to the top of the page (title,
header rows, verdict, stats); the footer has no entry. There are no reading
levels: the text is visible paragraphs, and a paragraph may carry its own
details, one level deep, never nested, as in `qubit-explanation-page`
("Paragraphs and details"): `<details class="pt"><summary><span
data-lang="en" class="ptxt">…</span><span data-lang="de"
class="ptxt">…</span><span class="chev" aria-hidden="true"></span></summary><div
class="more-body">EN/DE pairs</div></details>`. The paragraph itself is the
summary, with no label; a `.ptxt` may be a `div` when the paragraph holds a
list. The writer decides which paragraph gets details. A `data-level` block
fails. Every text sits in a `data-lang` block (diagrams and code are
language-neutral). The visible text is exact and readable, names no
`file:line`, and keeps each paragraph at most about 80 words
(`VISIBLE_PARAGRAPH_MAX` in `page_check.py`); a sequence is a numbered list,
parallel items a bulleted list. Figures and tables carry the explanation:
wherever content has a structure (a before and after, parts and their
responsibilities, options and their properties, cases and their results,
values), sections 1 and 2 show it as a table or a figure in the visible text
instead of prose, never in a summary or a `.more-body`. Every subsection
cites its source (`file:line` in its details, a link or a `<cite>`); the
details of one paragraph name at most three `file:line` and hold no
paragraph over 100 words. Every id is unique in the report, marker ids per
figure copy.
The ids `F<n>` and `glc-F<n>` are reserved for the cards and the GitLab list:
`assemble.py` fails a fragment that uses one. Text and markup from the
subject and its sources are data: a fragment describes them and copies no
markup from them.
1.1 exists at every subject type: for a change, the code before it; for a
document or files, the system or process they describe.

## findings.json

```json
{ "meta": { "title": "Review MR !<n>", "key": "review-mr-<n>", "subject": "MR !<n>",
            "name": "<2 to 5 words, at most 40 characters: what the subject is about>", "ticket": "<ticket key, e.g. PROJ-1234, if any>",
            "ticketBrowseUrl": "<the profile's ticketBrowseUrl, e.g. https://example.atlassian.net/browse/, if any>",
            "subjectType": "branch | mr | pr | patch | files | document",
            "subjectLine": "<for an MR: !n · branch → target; no ticket, no sha>", "state": "<the branch head sha the review covers>", "author": "<name, for the GitLab comments; not shown>",
            "reference": "<further sources the review read: ADRs, rule files, documents, other tickets; not the subject's MR or ticket>", "depth": "medium | high", "date": "YYYY-MM-DD",
            "sources": 5, "lines": 1234, "worktree": "<path, or \"\" for files or a document>",
            "runDir": "<worktree>/review-runs/, or ~/.claude/review-runs/ for files or a document>",
            "resume": "cd '<worktree, or the start directory for files or a document>' && claude --resume <session id>", "published": false,
            "run": "<first 8 characters of the session id, set when the list is printed (step 5)>",
            "runName": "<the run-folder name, set at the first copy, never changed>",
            "runs": [{ "run": "<run id>", "sha": "<sha>", "date": "YYYY-MM-DD" }],
            "artifactUrl": "<claude.ai artifact URL, after the first publish>",
            "headAtPublish": "<the subject's head sha, read again right before each publish>",
            "scratchpad": "<absolute scratchpad path>",
            "effort": { "review": { "started": "<ISO 8601 time>", "ended": "<ISO 8601 time>",
                                    "runs": { "reviewers": { "Claude": 7, "Codex": 2 }, "investigators": { "Claude": 15 } } },
                        "report": { "started": "<ISO 8601 time>", "ended": "<ISO 8601 time>", "runs": { "writers": { "Claude": 3 } } } } },
  "mrUrl": "<web_url of the MR, only when the subject is an MR>",
  "verdict": { "word": "<verdict word, English>", "openBlockers": ["F1"] },
  "concepts": ["<concept a finding depends on>"],
  "notes": { "works": "…", "samePass": "…", "questions": ["…"], "good": ["…"],
             "checks": [["<check>", "green | red | skipped", "<detail>"]], "method": [["<source>", "<what it did>", "m:ss", 3, 1]],
             "consolidation": "…", "refuted": ["…"], "withdrawn": ["F<n>: <reason, after publish only>"],
             "sideFindings": [["<investigator output name>", "<the bullet>", "<draft id, 'merged into D<n>' or 'not followed'>"]],
             "processed": ["<raw output whose findings are recorded>"],
             "ranking": "<foreign scope ranking and the scopes that got runs>",
             "manualPublished": ["<manual test ids on the page at the last publish>"],
             "coldRead": { "comments": 16, "rounds": 1, "items": { "ref": 2, "calque": 3, "mismatch": 0 }, "fixed": 4,
                           "left": ["F<n> <ref | calque | mismatch>: <reason>"] } /* with GitLab comments; gitlab-comments.md, Cold read */ },
  "manual": null | { "setup": "<one shared setup: stack, URL, accounts>",
              "steps": [ { "id": "M1", "do": "…", "expect": "…", "flow": "<trace flow it comes from>" } ],
              "withdrawn": ["M<n>: <reason, after publish only>"] },
  "findings": [ { "id": "F1", "sev": "blocker | optional | nit | fyi", "category": "<category key>",
                  "package": "<package>" | ["<EN>", "<DE>"], "file": "<path>:<line>",
                  "what": "…", "why": "…", "fix": "…", "verify": "…",
                  "principle": "<names, comma-separated: DRY, KISS>" | null /* architecture and design only: required there, null when the check named none; never on another category; acronym where one exists */,
                  "triggers": [ { "trigger": "<case>", "wrong": "<wrong result>" } ] /* two or more, worst first; else left out */,
                  "removes": ["F<n>"] /* other findings this finding's fix also removes (SKILL.md §4, step 3, Shared fix); else left out */,
                  "before": "<the cases in which the target already gave the wrong result>" /* from the checks' # Before the change; else left out */,
                  "options": ["<option>: <the cases it fixes or leaves, its cost>"] /* two or more, when the checks answered OPTIONS; else left out */,
                  "fixLeaves": "<the cases the fix leaves>" /* when the checks answered PARTIAL; else left out */,
                  "fixOpen": "<what is open about the fix>" /* when the checks answered OPEN; else left out */,
                  "followUp": { "title": "<FYI and Optional: ticket title>", "key": null },
                  "sources": ["<reviewer run>"], "check": "pending | running | inline | batch | investigator | investigator2 | unchecked" } ] }
```

`assemble.py` requires the `meta` keys `title`, `key`, `subject`,
`subjectLine`, `state`, `author`, `reference`, `depth`, `date`, `sources`,
`lines`, `worktree`, `runDir` and `resume`; `subjectType` (default
`branch`) and `scratchpad` are written from the start; `run` is set when the
list is printed (SKILL.md step 5); `published` and `artifactUrl` are set at
the first publish, never before. `name` (at most 40 characters) and `ticket`
(a ticket key such as `PROJ-1234`) are written with the other header values
when the file starts; both are optional, and the title and the run-folder
name use them. The Ticket row links `ticket` to Jira at `ticketBrowseUrl` (from the profile,
[_profiles/README.md](../_profiles/README.md)); without it, ticket keys stay
plain text everywhere. Every key of its project is a Jira link in all report text:
`reference`, the fragments (`assemble.py` `link_text`, outside tags, links,
`code` and `pre`) and the cards (the template's `jira()`, follow-up keys
included); the GitLab comment texts stay plain, since they are copied into
GitLab. A key inside a branch name or path stays text. The ids of known
findings in the fragments link to their cards, as in the cards.
`effort` records how much ran and how long, for the first line of 4.2, which
`assemble.py` builds from it (no writer touches it). Each phase has `started`
and `ended`, ISO 8601 times with a time zone (`date -u
+%Y-%m-%dT%H:%M:%SZ`), and `runs`, a run count per model under each role,
models by their product names (`Claude`, `Codex`, never the CLI name), reruns
included. Roles, which the line shows in this order: `reviewers` (core,
architecture, requirements, lanes, lenses, explorer, every whole-subject and
extra run of another tool), `raters` (the blind severity rating, `high`),
`investigators` (every investigator and batch run), and in the report phase
`writers` (the writers and the translator). Times: `review.started` from `$SP/state/review-started.txt` (step 1), `review.ended` right
before the list is printed (step 5), `report.started` when step 6 starts,
`report.ended` before every `assemble.py` run until the first publish, then
never again; `publish-report` keeps the review phase of the run. A run
without `effort` (older than this line) gets no line and a note; an `effort`
without both phases fails.
`headAtPublish` is optional and only for a branch, MR or PR with a remote
(SKILL.md, step 6.3): a commit sha of 7 to 40 hex characters, compared with
the first sha in `state` by prefix. A head that differs puts a warning with
both shas into the reviewed-up-to row; a value that is no sha, or a `state` without
one, fails.
`worktree` is an empty string for files or a document, which have none, and the footer then leaves the worktree sentence
out. `reference` and `subjectLine` are header values: names,
paths and ticket keys, no prose, so they read the same in both languages.

The orchestrator starts the file in step 4 and writes each decision as it
falls, so a compaction loses nothing. `sources` and `check` are its working
state: `sources` feeds the method table's counts and never reaches a card;
`assemble.py` fails while a finding's `check` is still `pending` or
`running`. A final `check` names the strongest check that ran: `inline` (the
reviewer's label stands), `batch`, `investigator` (one of its own),
`investigator2` (one of its own and a second); `unchecked` records an
investigator that failed for good, and 4.2 names that claim. `notes.processed` names each raw output whose findings are
recorded, so a compaction never leads to reading an output twice or not at
all. Until every check has returned, ids are drafts (`D<n>`); one step then
numbers them `F<n>` and rewrites every draft id in `verdict` and `notes`.
`meta.published` turns true after the first publish (below), and the
artifact URL goes into `meta.artifactUrl`, so a republish after a compaction
or a resume reaches the same report.

`category` is one key of the category table under Findings (3.2); `package`
is the text that opens the card's location line.
`meta.subjectType` is the subject type, `branch` when missing. `assemble.py`
fills from it the report's fixed wording that differs per type: section 2's
default heading, the severity legend's "changes in this MR" and "holds the
merge", and the verdict words of the table in SKILL.md. When the field is set,
a verdict word of another subject type fails.
`gitlab` may be left out: the subject type decides, comments exist exactly
for a branch, MR or PR. A `gitlab` value that disagrees with
`meta.subjectType` fails. `meta.run` names the run folder
([tooling.md](tooling.md), Hygiene) and never changes. `mrUrl` starts with `https://` and is set
only for a GitLab MR (`meta.subjectType` `mr`; any other type fails, since a
GitHub PR has another anchor scheme and a PR's comments stay plain text): `assemble.py` then links every comment's `path` and `startLine` to
`<mrUrl>/diffs#<sha1 of the path>_<old>_<new>` (GitLab's line code, worked out
from `$SP/inputs/change.diff`; a range links to its first line); a line outside the diff hunks links to the file,
a general MR comment to the MR. Without `mrUrl` the comments stay plain text. The subject's own `!<number>` (with or without `MR `) in `meta.subjectLine` links to `mrUrl` too (a note says so when there is none); the reviewed-up-to row links the head sha to its commit in the same project. Every review report has the same five numbered sections, so a
number means the same thing in every review:

| # | Section | Subsections, in this order |
| --- | --- | --- |
| – | Header | – |
| 1 | Background / Hintergrund (from `qubit-explanation-page`): what exists without the MR | 1.1 How it works today (for a document or files: the system or process they describe), then one per general concept a finding depends on |
| 2 | The MR / Der MR (from `qubit-explanation-page`; heading per `meta.subjectType`: The branch, The MR, The PR, The patch, The code for `files`, The document) | 2.1 Goal, 2.2 Approach (how the author built the change: modules, their responsibilities and dependencies, the main decision), 2.3 Flow, then one per concept the subject introduces |
| 3 | Assessment / Bewertung | 3.1 Manual tests, 3.2 Findings, 3.3 Open questions for the author, 3.4 What works well, 3.5 GitLab comments by file |
| 4 | Evidence / Nachweis | 4.1 Tests and checks, 4.2 Method and sources |
| 5 | Glossary / Glossar | – |
| – | Footer | – |

No section or fixed subsection is skipped: an empty one holds one line
("No open questions." / "Keine offenen Fragen."). Sections 3 and 4 are
language-switched (every text as an EN/DE pair) and fully visible: a card's
fields show their text, and a field's details open on a click. A card's
GitLab comments and the GitLab comments subsection (3.5) are always visible:
the comments are what gets posted, not an explanation. The card holds its own
comments; 3.5 lists all of them by file, for posting in file order.

## Header

Title: `<meta.name> · <meta.subject> · <meta.ticket>` in the browser tab, the bar and the artifact's name (the name first, since a tab cuts the end off), above the heading a small label with the review type (Merge request review, Branch review, Pull request review, Patch review, Code review for `files`, Document review), the name as the heading (without a name `Review of <subject>`); without a name the tab shows `meta.title` and `assemble.py` prints a note. `meta.name` comes from the MR title, else the ticket summary, shortened by the orchestrator like `subjectLine`. No intro text under the heading: the arrow at the end of a paragraph with details and the "Expand all details" button explain themselves. Then the header rows, each fact once, labels per subject type
(`assemble.py` `HEADER_LABELS`): the subject (Merge request: `!123 ·
<branch> → <target>`, the number linked; Branch, Pull request, Patch, Files,
Document), Ticket (only with `meta.ticket`, linked to Jira), Reviewed up to
(the branch head sha from `meta.state`, short and linked to its commit,
"(branch head)": the review covers the branch's whole change up to it;
Applied to for a patch, Version for files or a document, `meta.state` as it
is) and Reviewed (the date and the depth): only what a reader needs first.
Further sources (`meta.reference`) stand in 4.2 Method and sources, not in
the header. No author
row: the MR on GitLab has it. No internal words such as "consolidated" or
"orchestrator" in the header. `assemble.py` prints a note when
`subjectLine` names the ticket or the head sha, or `reference` the subject's
MR or ticket. The subject row ends with the size of the change ("1,428
lines changed", without lockfiles and generated code, from `meta.lines`).
Then the verdict and a stats row that counts the findings only: findings,
Blocker, Optional, Nit, FYI; the number of review runs (`meta.sources`)
stands in 4.2, not at the top. The subject type comes from `meta.subjectType` (`branch`,
`mr` for a GitLab MR, `pr` for a GitHub PR, `patch`, `files`, `document`;
`branch` when missing) and sets the
verdict words and the type's wording in the report.

The verdict: a label "Verdict" / "Urteil", the banner, and an abstract
under it. `assemble.py` writes the banner from `verdict.word`: ✓ or ✕ and
the word in sentence case ("Not mergeable" / "Nicht mergebar"; "not yet" and
"needs revision" read "Not yet fit for use" / "Noch nicht einsatzbereit" and
"Needs revision" / "Überarbeitung nötig"), green or red tint from the open
Blockers.

The abstract (`verdict.html`) is read first, before the background, the MR
and the findings, so it stands on its own: visible text, 2 to 4 short
sentences, at most 70 words per language (`VERDICT_WORDS_MAX`), no details,
no list. It says:

1. What the subject is for, in words a user understands (what a customer, a
   practice or the system gets).
2. The gist of why it is or is not fit, at the level of "it works as
   intended", "it does not do what it promises", "it breaks the booking",
   "it violates the architecture": the main reason, never a list of the
   findings.

No finding id, no code name (`<code>`), no count, and nothing the banner and
the stats row show (no verdict word, no Blocker count). The abstract adds no
fact the findings lack. `assemble.py` fails each of these for reviews from
`VERDICT_SHORT_SINCE` (2026-11-06) on; older runs build unchanged and keep
their Blockers in the verdict text. A lead `<strong>` with a verdict word
(reports before the banner) is dropped, and one that differs from
`verdict.word` fails. What the verdict covers and what the depth does not
search stands in 4.2.

## Manual tests (3.1)

The first subsection of the assessment: the steps a person runs to reproduce
what the subject promises, before reading the findings. A failing step means
the main path is broken and the findings can wait. Smoke steps only: the main
flows of the trace, normally 3 to 5, after one shared setup (how to start
the stack, the URL, the accounts it needs); no error paths, no edge cases.
For files or a document, and when the trace found nothing to run (`manual`
is `null`, e.g. a docs-only change), the subsection holds one line instead:
"No manual tests for this subject." / "Keine manuellen Tests für diesen
Gegenstand."

The steps come from the explorer's `# Manual tests` section, copied by the orchestrator into `findings.json` `manual`
(English) and translated by the translator into `manual.json`:

```json
{ "setup": ["<EN>", "<DE>"], "steps": [ { "id": "M1", "do": ["<EN>", "<DE>"], "expect": ["<EN>", "<DE>"] } ] }
```

Ids are `M<n>`, assigned in order, and never change or come back once
published: a dropped step goes to `manual.withdrawn` as `"M<n>: reason"`,
and `notes.manualPublished` holds the ids of the last publish. A card shows
its id, what to do, what to expect, and two checkboxes, "✓ as expected" and
"✗ different" (ticking one clears the other; neither is "not run"). On ✗ a
note field opens with a copy line for the review session:
`<meta.subject> · M<n> ✗ · Expected: <expect> · Observed: <note>`. Results
and notes are saved in the viewer's browser only (localStorage under
`meta.key`, like the done marks). They never change the verdict, the header
or the stats: the verdict follows the findings, and a failed step reaches it
only as a finding (SKILL.md, A reported manual test failure). All of it is
template code.

## Findings (3.2)

It opens with the findings summary (`summary.html`, written by the findings
writer): an overview of all findings in seconds, shorter than reading the
cards. A list by severity, always all four in this order: Blocker,
Optional, Nit, FYI; each line says in a few words what those findings are
about in this review, or "none". Every line is an overview, the Blocker line
included: the folded cards below are the complete list, Blockers first. An
id stands in a line only when the line singles out one finding the reader
should not miss, above all an `architecture` or `design` one ("the bar's
logic spread over three places (F9)"); no id lists, no ranges. "Related"
and "Hint" name their findings by id, since the reference is their point.
Then, only when there is one, a line "Related:" /
"Zusammenhänge:" with the dependencies a reader cannot see from one card:
one finding solved by the fix of another, two with the same fix, two
addressing the same thing; ids only, no reasons ("F2 is solved by the fix
of F1"). Then, only when the review has one, a line "Hint:" / "Hinweis:",
one or two short sentences with ids: what a reader would not see from the
order and the severities, such as an Optional or FYI that matters more
than its severity says, a finding where the sources disagreed or the
severity was a close call, or a decision only the author can make. Never
filler: without such a point the line is left out. No reasons, fix
locations or alternatives; the cards carry them.
At most `SUMMARY_WORDS_MAX` (120) words per language, no details;
`assemble.py` checks that, no id range and at most `SUMMARY_LINE_IDS_MAX`
(3) ids in one severity line (a guard against id lists, not a target), and
no unknown id, and requires the file from
`VERDICT_SHORT_SINCE` on.
`assemble.py` adds the line "Not fully checked: …" for findings whose
`check` is `unchecked`, from findings.json.

Under it a closed reference, "What severities and categories mean": each
severity by what it means for the merge, then the skill's definition in
short (SKILL.md severity table), and each category with what it covers
(`assemble.py` `CATEGORY_TEXT`, from the category table below).

The cards form one list. Three filter rows of plain chips: Severity, Category,
Status. Each row works the same way: pick one value, `All` / `Alle` first.
Every chip label is sentence case in both languages. Every chip shows its
count: the number of cards it would show together with the other two rows'
current choice; a chip whose count is 0 stays in place, dimmed, so the rows
never jump while filtering. The severity pill is the only pill on a card,
coloured by group: Blocker red and filled (holds the merge); Optional and Nit
one blue (changes in this MR, not blocking), Optional with a soft fill, Nit as
an outline; FYI violet with a dashed border (no change here, follow-up). The
category follows the pill as muted text, on every card. The
package opens the location line under the title as plain text, before the
paths.

Internal page: no WCAG contrast ratios; colours are judged by whether they are distinguishable from each other and from neighbouring elements, whether their strength follows the order they encode, and what they mean.

Each card carries a checkbox without visible text in its title line (named
"Done / Erledigt" for screen readers and as a tooltip), for the reader's own
to-do list. Every card starts folded to its title line, so the cards form
the complete list of findings; a click on a title line opens the card, and
"Expand all details" opens every card and disclosure. A tick folds the card
(an untick leaves it as it is) and marks the whole card, open or folded (thin green left
edge, green tick, title in muted grey, severity pill in muted grey with its
word kept; nothing is struck through, since only part of the line could be,
and a strike reads as "withdrawn" or "refuted" in a review), so the done state
never depends on whether a card is open. Each card sends one signal: an open
card is coloured by its severity, a done card is grey with a green mark (a red
pill beside a green edge would say danger and done at once). The ticks live in
the reader's browser only, so the grey card is the reader's own to-do mark
(handled, for example posted on GitLab) and no other reader takes it for fixed. The handled cards
of one severity are found with the Status and Severity filters together. The Status row (`All`, `Open`, `Done` / `Alle`, `Offen`,
`Erledigt`) filters by those ticks. The ticks and the status choice are saved
in the viewer's browser only (localStorage under `meta.key`, so they survive a
republish; a report stored under the earlier "hide done" switch starts on
`Open`). They change neither the verdict nor what other viewers see; one line
under the rows says so. The GitLab list follows all three rows. All of it is
template code: writers and the translator add nothing for it.

The category is the review aspect a finding falls under: what the reviewer
checked, not what kind of finding it is (that is the severity). Every finding
has exactly one; when two fit, the more specific one wins, and Functionality
only when no other fits. "The ADR accepts it" is a status (FYI), not a
category. The chips list only categories that have a finding, in this order:
intent first, then structure, then the non-functional qualities by how many
changes they apply to, then the companion artifacts, then Style.

| Category | Label | Covers |
| --- | --- | --- |
| `functionality` | Functionality / Funktion | the change does what it intends, completely and without faults; concurrency, error handling |
| `architecture` | Architecture / Architektur | fit with the system: boundaries, dependency direction, cross-cutting mechanisms, ADRs, a second mechanism; the fix reaches code the change did not write |
| `design` | Design / Design | the inside of the change: unneeded complexity, over-engineering, dead code, misleading names, invented names; the fix stays inside the change |
| `security` | Security / Sicherheit | access control, sessions, secrets, personal data, input validation, the attacker lens |
| `operations` | Ops / Betrieb | deploy and deploy order, config, env, migrations, rollback, dependencies, old clients after a rollout, logging |
| `performance` | Performance / Performance | unbounded queries, missing indexes, N+1, whole collections loaded, work repeated per request |
| `usability` | UX / UX | visible to the user and not a fault: the design guidance, clear texts and errors, accessibility |
| `tests` | Tests / Tests | presence, meaningfulness, robustness, fidelity of fakes |
| `documentation` | Docs / Doku | comments, JSDoc, README, ADR text |
| `style` | Style / Stil | the written style rules of the instruction files, and naming by convention |

The table decides; the fix-reach test (does the fix stay inside the change or
reach code it did not write) only decides what the table does not name. A second
mechanism stays Architecture. Orphans: a permanent break of an interface or
wire format across a deploy boundary (our other servers included) is
Architecture, a break only during rollout is Ops; dependency placement (peer or dependency) is Architecture, version or
presence of a dependency is Ops; a build failure is Functionality, a lint
failure takes the category of the broken rule. A misleading or invented name is
Design, a name that only breaks a convention is Style.

The keys and labels live in `assemble.py` (`CATEGORIES`); `assemble.py` fails on
any other key. The package is the repository's own name for it (its glossary
or CLAUDE.md), else the short package name (`api-server`, `web-app`, `forms`,
`shared-utils`), a string or an `[en, de]` pair. For files or a document it is
the file name (a file group's folder) or the chapter heading. A file outside
any package shows its top-level directory (`ci`, `tools`), or `repo` for a file
at the repository root (`Jenkinsfile`, `pnpm-lock.yaml`); a package never
deployed to production (`tools/http-client`, `test-utils`, a `*-dev` app) shows its
short name like any other. The cards are rendered
from `data.json`, a JSON array (double-quoted keys and strings, no comments),
one object per finding; the shape, written here with comments:

```js
{ id: 'F1', sev: 'blocker|optional|nit|fyi', category: '<category key>', package: '<package>' | ['<EN>', '<DE>'], file: '<path>:<line>',
  t: ['<EN title>', '<DE title>'],
  fields: { what: { text: ['<EN>', '<DE>'], more: ['<EN>', '<DE>'] | null },
            why: { text: [...], more: [...] | null }, fix: { text: [...], more: [...] | null },
            verify: { text: [...], more: [...] | null } /* what the investigator or the grounding check read or ran */ },
  gitlab: [{ path: '<path>', startLine: 11, endLine: 13 /* a range, line comment only */,
             anchor: 'line|file|mr', side: 'old' /* removed lines only */,
             text: ['<English comment, no prefix>', '<German comment, no prefix>'] }],
  followUp: { title: '<ticket title>', key: null | 'PROJ-1234' } /* FYI and Optional */ }
```

`gitlab` is filled only when the subject is a branch, MR or PR, and for every
finding of it, Nits included. One entry per
place a comment goes, usually one; written by the findings writer under the rules
in [gitlab-comments.md](gitlab-comments.md). The renderer adds the bold
severity prefix, puts the block at the end of the card and builds the GitLab
comments section from the same entries, so the two cannot drift. `text` is an
`[en, de]` pair like every other text: the report shows the language of the
switch, and Copy copies the one on screen, which is what gets posted.

`followUp` belongs to every FYI and every Optional finding: the draft title
of the follow-up ticket, and its key once the ticket exists. The title is the
literal ticket title, in the language the ticket will have, so it is one
string, shown the same in both languages after a translated label. The orchestrator
writes both into `findings.json`; the findings writer copies the object
unchanged. An Optional's
ticket is created only when the author does not fix it here, so its comment
stays copyable without a key. For an FYI, until then the card shows "Ticket
missing" (DE "Ticket fehlt") and the FYI comment's copy button stays disabled;
with a key, the renderer appends `Follow-up ticket: <key>` (DE
`Folgeticket: <key>`) to the comment.

Mapping from a reviewer's output: Description becomes `what`, Failure scenario
becomes `why`, Suggested fix becomes `fix`; `verify` states what the
investigator (or the grounding check) read or ran, never a
reviewer's claim. `principle` names the principles the checks confirmed or
named in their `# Principle` sections (SKILL.md §4), all of them when they
differ; `null` when they answered NONE. A check's `# Before the change`
other than NONE becomes `before`, and its `what` and `fields.what.text` say
it in one sentence. A check's OPTIONS become `options`, one entry per
option, and `fix` and `fields.fix.text` name every option. A check's
PARTIAL becomes `fixLeaves`, its OPEN `fixOpen`; `fix` and
`fields.fix.text` say what is left or open.

A finding with a `principle` (only Architecture and Design carry one) gives
it inside its `what`, in the consolidated text and in `fields.what.text`: the
sentence that describes the problem also says why the code should be
different. The reason is the concrete consequence (what goes wrong, gets
harder or has to be kept in step); the principle joins that sentence at
most as a short classification, and stands as the reason only when the
finding has no concrete consequence. Never a closing sentence or paragraph
of its own, never a label per clause. The reader of the card learns the
same reason the GitLab comment gives. A principle is only named, by its
acronym where one exists (DRY, KISS, YAGNI, SRP), else as a developer can
look it up (single source of truth, dependency inversion, an ADR by its
title), never a name the review forms; several may stand together.

A finding with `removes` says in its `fix` (the consolidated text and
`fields.fix.text`) what its change also removes, in plain words; each
finding it removes names that change as
the alternative in its own `fix`, so a reader of either card sees the
link. Cards name the other finding's id (the page turns every `F<n>` in a
card's text into a link to that card); GitLab comments never do
([gitlab-comments.md](gitlab-comments.md)). A Blocker's `verify` states the proof its
reason needs (SKILL.md, Severity): the trigger in live use, the exploit path, the
ADR or rule it breaks, or that no test exists.

A card is a foldable `details.card` with the done mark, folded at the start. Its title line
holds the id, the severity pill, the category and the title `t`: the
effect first, at most one technical term, no paths, no numbers. Under it
stands the location line (package · file), then the four fields under the
labels What, Impact, Fix, Checked (DE Was, Auswirkung, Lösung, Geprüft),
then the follow-up line (FYI and Optional), then the GitLab comments. All of
it is visible without a switch. Each field is `{"text": [en, de], "more":
[en, de] | null}`:

| Part | Shown | Written as |
| --- | --- | --- |
| `text` | always, as the field | two to four sentences, exact and readable, technical, with the real names of the components; says what the code means, not only what it does; complete enough to judge the finding; no `file:line`; never starts with its label ("Fix: …"); each paragraph or list item at most about 80 words (`VISIBLE_PARAGRAPH_MAX`). A reference to a rule or a document says what it says ("rule 2 lets only the main server migrate a replica"), never just its number. `why` carries one concrete example of the failure where the effect stays abstract otherwise |
| `more` | on a click on the field (a paragraph disclosure, `details.pt`), or `null` | the evidence and the depth of that field: each fact with its consequence ("…, so the dialog stays busy"); `file:line` allowed, as many as the evidence path needs; short paragraphs (at most about 100 words), a bold lead where it holds several points |

A field with nothing more to say has `more: null`. A Blocker always has
`fields.what.more` with the path through the code, at least one `file:line`
up to the faulty spot, and `fields.verify.more`: what the review read or ran
and how the reader can check it again (a file to read, a test, a request, a
command). The way out carries the label "Fix" (DE "Lösung"); the GitLab
comment keeps its own `Suggestion:` (DE `Vorschlag:`), since it is posted to
the author as a proposal, or `Question:` (DE `Frage:`) for a finding with
`options` or `fixOpen` (gitlab-comments.md, What it says).

A finding with `triggers` (SKILL.md §4, Merge) shows every trigger in
`fields.what.text`, so no reader misses a reason the fix has to cover. Its
title `t` names the shared cause, not the effect of one trigger. Its `what`,
in the consolidated text and in `fields.what.text`, opens with the cause in
one paragraph; after a blank line follows a list, one line per trigger in
`triggers` order, each starting with "- " and naming the case and its wrong
result. The renderer makes a list only of a paragraph whose every line
starts with "- ", so the list stands alone, with blank lines around it.
`why` names the worst wrong result. `assemble.py` checks that
`fields.what.text` lists at least as many items as `triggers` holds, per
language.

`what`, `why`, `fix` and `verify` in `findings.json` stay the consolidated
finding as settled in step 4: the record, which no writer changes and which
`data.json` does not carry. The findings writer writes each card's `text`
and `more` from it and adds no facts. In every text field, identifiers,
paths, routes and keys stand in backticks and render as code; a blank line
starts a paragraph, a block of lines starting with "- " becomes a list, a
block of lines starting with "1. " a numbered list, and a paragraph that
opens with `**…**` gets that as its bold lead. The person who uses what the subject
changes is "a user" or "the user" (DE "ein User", "der User") in every text
of the report, the explanation sections included, never a collective word
such as "staff"; another role keeps its own name (a customer). A value chosen
only to illustrate (a date, a name, a number the code does not contain) is
marked as an example ("e.g. 01.01.2027", DE "z. B. 01.01.2027"); a value from a
reproduction is named as that ("the reproduction's date 2026-01-01"). A key
combination names every platform the code binds ("Ctrl+Z / Cmd+Z").

Order: Blocker, Optional, Nit, FYI; within a group by weight. Ids are `F<n>`
in that order, severity-free, and never change on a republish. After the
first publish the orchestrator sets `meta.published: true`; a finding
re-graded after that keeps its id and its place in `findings.json`, and
`assemble.py` then skips the order check; the report still shows the cards
by severity, within a group in list order. No value from a secret file in any field; a closing
`script` tag in a string is safe, since `assemble.py` escapes every `<` in the
data it writes into the report.

## Open questions for the author, what works well (3.3, 3.4)

Bullets, as EN/DE pairs. Praise names the concrete mechanism, not "good tests".

## GitLab comments (3.5)

Subsection 3.5, the last of the assessment, always visible. Every
`gitlab` entry of the visible findings, grouped by
file in path order (the MR's file list), by line within a file, general MR
comments last. Each entry links back to its finding and has a copy button that
copies the prefixed text; where the viewer blocks the clipboard, the button
selects the text for Cmd/Ctrl+C. It follows the three filter rows, so
"Blocker" with "Open" shows exactly the comments still to be posted before a merge.
For a subject without GitLab comments the subsection holds one line instead: "No GitLab
comments for this subject type." / "Keine GitLab-Kommentare für diese Art von
Gegenstand."

## Tests and checks (4.1)

A table: check, result pill (green, red, skipped), one line of detail. One row
per suite, lint run, build, merge test, promotion checks, and the final
`git status`. Say what was not run and why.

## Method and sources (4.2)

First, the two lines `assemble.py` builds from `meta.effort`, one per phase,
for example "Review, 30 min: 9 reviewers (7 Claude, 2 Codex) and
15 investigators (Claude)." and "Report, 18 min: 3 writers (Claude)." Then
the line Further sources / Weitere Quellen from `meta.reference` (ADRs, rule
files, documents, other tickets the review read; left out when empty). Then a
table: source with tool version, what it did, run time, how many findings it
raised, how many of those only it raised (`–` for investigators and tests;
the explorer counts the findings its discrepancy list raised). The column headers, exactly: Source / Quelle, What
it did / Was sie tat, Run time / Laufzeit, Findings raised / Findings
gemeldet, Found by no other source / Von keiner anderen Quelle gefunden. The writer's first paragraph, after the effort lines: the depth (`medium`,
`high`), what its verdict covers and what it does not search (SKILL.md §2, Regions), and the extra runs by Codex: the scopes in their
fixed order and which got a Codex run, and any run skipped at its usage limit. Report text names Codex
by its product name; "foreign" is the skill's own word and never appears in the
report, in German never "Fremdlauf". One row per reviewer run (one per scope
for Codex), explorer, investigators, the orchestrator's
own test and lint run, earlier review. Note
tool failures honestly (a reviewer that ran empty, a rerun, a foreign run
truncated or skipped after its quota or auth failed). One paragraph on
consolidation: same root cause equals one finding, checks by severity as the
check table in SKILL.md §4 sets them for the run's depth (every Blocker
checked by its own investigator, or `unchecked` after it failed for good;
severity from the investigators' final labels, a Blocker standing when two
disagree across the Blocker line; a claim refuted only when every
investigator refuted it),
refuted claims named here, every id withdrawn after publish (`notes.withdrawn`, "fixed in <sha>" after an update at a new sha), for an updated report each run in `meta.runs` with its date and sha and which findings each raised, severity from the investigators' final labels; how many side findings the investigators named and how many became findings (`notes.sideFindings`); for GitLab comments, the cold read (`notes.coldRead`): how many comments a reader without the report read, in how many rounds, how many unclear references, translated German sentences and differences between the languages it named, how many were fixed, and each one left with its reason. This is the only place a
source is named; the findings below carry no attribution.

The consolidation paragraph also names what no run covered: failed runs,
`unchecked` claims, at `high` the claims only the tests raised (they come
after the blind foreign rating and get none), and foreign runs without
repository access. Section 4 never says that no Blocker is left.

## Footer

Where the worktree is, where the copy of the report and the raw reviewer outputs
lie, the date of consolidation, and the command that resumes the orchestrator's
Claude session, with a copy button: `cd '<worktree>' && claude --resume
<session id>`. The resumed session works in the directory it is started from,
so the command moves into the review worktree, where the branch and the run
folder lie; `claude --resume` finds a session from any worktree of the same
repository, also one started in the main checkout. For files or a document,
which have no worktree, it moves into the start directory.
[tooling.md](tooling.md) shows how to read the values. The command is the same
text in both languages.

## What assemble.py checks

`python3 <skill dir>/assemble.py "$SP/report"` builds `review.html` from the
template, the fragments and `data.json`, and checks it. `data.json` is
parsed, never executed, and the report carries exactly the checked array.
`test_assemble.py` holds a failing case for each check listed here:

- against `findings.json`: same ids F1..Fn (gaps only for ids in
  `notes.withdrawn` after publish, and a withdrawn id never reused), severity order, categories, packages, locations,
  follow-ups; no finding with a `reason` field (a Blocker's `verify` states
  the proof);
- the card shape: `t` and `fields` with exactly `what`, `why`, `fix` and
  `verify`, each `{"text": [en, de], "more": [en, de] | null}`; no
  consolidated `what`, `why`, `fix` or `verify` in `data.json`; a card with
  `plain` or `tech`, or without `fields`, fails once with a message that a
  report from an older skill version is changed in its own HTML;
- the card text: no `file:line` in a `text`; no `text` that starts with its
  label (What, Impact, Fix, Checked; Was, Auswirkung, Lösung, Geprüft); each
  paragraph or list item of a `text` at most `VISIBLE_PARAGRAPH_MAX` words and
  of a `more` at most `DETAIL_PARAGRAPH_MAX` (both from `page_check.py`); a
  Blocker with a `file:line` in `fields.what.more` in each language and a
  `fields.verify.more`; a `principle` named in the English
  `fields.what.text`; a finding with `removes` names each removed id in its
  `fields.fix.text`, each removed finding names it back in its own, in each
  language, and every id in `removes` is another finding;
- the verdict: `verdict.word` fits the open Blockers, a lead `<strong>`
  verdict word agrees with it, each language names every open Blocker in id
  order and no id that is not a finding;
- every finding in `findings.json` with an id, a severity, a category and a package (else
  it stops before the other checks); `check` one of `inline`, `batch`, `investigator`,
  `investigator2`, `unchecked`; `mrUrl` an `https://` URL, set only for an `mr`; `gitlab`, when
  given, matching the subject type; `meta.headAtPublish`, when given, a sha
  next to a sha in `meta.state`; `meta.effort`, when given, both phases with
  ISO times (time zone included, `ended` not before `started`) and run counts
  per model under known roles; no "foreign" or "Fremd…" in the method section;
- the check a finding needs at `meta.depth` by the check table in SKILL.md
  §4, or a stronger one, or `unchecked` (`required_check` in `assemble.py`;
  the exemption's conditions beyond the category it cannot see, so they
  stay the orchestrator's);
- for a branch, MR or PR subject, every finding has 1 or 2 GitLab comments,
  Nits included;
- every text inside a language block, every block a complete EN/DE twin
  whose German text is no copy of the English one (the same text with three
  or more words that are not code, a name or `file:line`, one of them in
  lower case; the same for every pair in
  `data.json`, `text` and `more` included, and every GitLab comment), the
  fixed subsections present and first, in order (`#today` in section 1;
  `#goal`, `#approach`, `#flow` in section 2), no `data-level` block in a
  fragment, the paragraph disclosures of every fragment (`check_paragraphs`
  from `page_check.py`: one level, never nested, a summary with an EN and a
  DE `.ptxt` and exactly one `.more-body`, no figure or table in either), in
  every subsection no `file:line` and no paragraph over 80 words in the
  visible text and per disclosure at most three `file:line` and no paragraph
  over 100 words, a `file:line` (a path with a file extension or a known
  extensionless name such as `Dockerfile`; a host:port is none), link or
  `<cite>` in every subsection of sections 1 and 2 in each language view; a
  twin of void elements (`<img>`) needs no text;
- the fragment shape: no `<section>`, no `<h2>`, no id twice in the report, no fragment id `F<n>` or
  `glc-F<n>` (reserved for the cards and the GitLab list); every `.subsec`
  has an id and an `<h3>` first and is in the table of contents;
- the GitLab rules: `line` and `file` anchors inside the diff, a range
  (`endLine`) in one hunk and on a `line` comment only, the place fields
  each anchor needs (`path` and `startLine` optional for `mr` only), no old
  `at` field, limits,
  wording (a missing or empty `change.diff` is a printed note, and the
  anchors are then not checked); `Sie` or `Ihr…` after `.`, `!`, `?` or `:`
  counts as sentence-initial;
- a finding with `triggers`: at least two, each with a `trigger` and a
  `wrong` text; `fields.what.text` lists at least one item per trigger in
  each language; each GitLab comment has one "- " line per
  trigger, three at most, in each language, and its trigger lines count
  towards the word limit;
- with GitLab comments, `notes.coldRead` in its shape: `comments` the number
  of comments in `data.json`, `rounds` 1 or 2, `fixed` plus the entries of
  `left` the sum of `items`, each entry of `left` "F<n> <type>: <reason>"
  for a finding of the report; a report published before the cold read
  existed passes without it, with a printed note;
- with `notes.coldRead`, each language of `method.html` names it: the
  `comments` number, the `fixed` number when it is not 0, and every finding
  id that starts an entry of `left`;
- each language of `method.html` names every finding id that starts an
  entry of `notes.withdrawn`;
- no `TODO-DE` left in `data.json`, a fragment or `manual.json`: the
  placeholder a writer puts in the German side of a text it changed after
  the translator ran ([tooling.md](tooling.md), Translator);
- no active content in a fragment: no script, handler or SMIL animation, no
  attribute given twice on one tag, no outside URL in an attribute that loads
  a resource (`src`, `href` on any tag but `<a>`, and the like), and in CSS
  (a `<style>` or a `style`, `fill`, `stroke`, `filter`, `mask`, `clip-path`,
  `marker-*` or `cursor` attribute, CSS escapes decoded) no `@import`, no
  `expression(` and no `url(`, `image(`, `image-set(`, `-webkit-image-set(`,
  `cross-fade(` or `src(` that points anywhere but into the report (`#id`);
- the manual tests: `manual` present for a branch, MR, PR or patch (`null`
  when nothing runs; left out for files or a document; missing in a report
  published before manual tests existed is a printed note); step ids `M<n>`, unique, never an id from
  `manual.withdrawn`, and after publish every id in `notes.manualPublished`
  still a step or withdrawn; `manual.json` with the same ids in the same
  order, every text a translated `[en, de]` pair whose English is the
  `findings.json` text;
- `meta.ticket` a ticket key and `meta.name` at most 40 characters, when
  given (a missing name is a printed note);
- the inline scripts parse; `findings.json`, `data.json` and `manual.json`
  are readable JSON (a broken one is named with line and column);
- the data payload is written one finding per line; no line of `review.html`
  over about 45 KB, the most one Read part holds;
- the publish folder `publish/`: `index.html` with `report.css`, `report.js`,
  `findings.js`, `manual.js` and `slots/<slot>.js` (a file over about 180 KB
  cut into `<name>-1.js`, `<name>-2.js`, …; files the page no longer loads
  removed), the same document as `review.html` (`test_assemble.py` rebuilds
  one from the other); "changed since last publish" against
  `publish/manifest.json`, which `assemble.py --mark-published` writes after
  each batch for that batch's files; "publish batches" for those files, each
  batch with `index.html`, at most about 230 KB, with line ranges; no line of
  a publish file over about 45 KB, and `index.html` at most about 50 KB.

Language blocks and ids are counted on the parsed report, so markup quoted in
a code sample or an attribute value counts as text.

The page checks that `assemble.py` runs on the fragments and the report (parser, twins, paragraph disclosures,
citations, active content, duplicate ids) come from `page_check.py` in the
`qubit-explanation-page` folder, which also checks a standalone explanation page.
