# Description format

The description serves two readers. The reviewer reads it now, to decide whether the
change should exist and where to look. A developer reads it later, through the merge
request link of the merge commit, to learn why the code is the way it is. Each section
below states which of them it serves; text that serves neither stays out.

The ticket holds the requirement: what is wanted and why it matters. The description
holds the change: how this MR meets the ticket and why this way. Link the ticket; never
copy its acceptance criteria or its background.

The description is the state handed over, never the way there: no self-review section,
no review rounds, no work in progress, no author's notes. A review result that describes
the state goes where that state belongs: a decision into Decisions, an untested part into
Not tested.

The description is written in English. The title follows the repository's commit style.
A profile may add sections, constrain the title or change the form of a slot. The sections
stand in this order, each under its own `##` heading.

## Size

Two shapes, chosen by an observable condition:

- **Large**: the diff touches more than one package or top-level directory, or adds a
  module, service, component, route, schema or other mechanism. All sections apply.
- **Small**: everything else. No Design section.

Word budget: Context with Problem at most 100 words, Design at most 300. Count without
headings, the ticket line, links, diagrams, tables and code blocks. Change has at most
seven bullets; the other sections have their own limits below. A draft over budget is cut
in this order: sentences that repeat the ticket, file paths, then Design items down to one
sentence each.

## Title

For the git log reader. One line, in the repository's commit style, that says what the
change does without the description.

## Context

For every reader: where in the system the change lives. Exactly these slots:

```md
**Ticket:** [<KEY>](<url>) "<the ticket's title, verbatim>"

<The module, screen or flow the change sits in, and who uses it.> <How it works there today.>
```

The second paragraph is one or two sentences of technical location, not the ticket's
business background.

## Problem

For the reviewer: whether the change should exist. One or two sentences on what is wrong
or missing in the state that Context describes. How it works today is the Context; the
state after the merge is the Change. No file names.

## Change

For every reader: what behaves differently after the merge, for whom, and what stays the
same, as a user, a caller or an operator sees it. How it is built is the Design. One or
two sentences; when more than two behaviours change, one bullet per behaviour.

## Design (large only)

For the reviewer: whether the design holds. For the later developer: whether a part may
be changed. Three parts, as bold lead-ins:

- **Parts.** A numbered list in the order the data or the control flows, at most seven
  items. Each item: the part's role in one or two sentences, and its identifier once in
  backticks. When there is a flow, a routing table or a state change, add one fenced
  `text` diagram, indented to the list item. When an ADR describes the design, link it.
- **Decisions.** One line each: the answer to an open question of the ticket ("Offen"),
  an alternative that was rejected and why, or a known weakness the design accepts.
  Leave the part out when there is none.
- **Out of scope.** What the MR deliberately leaves to other work, each item with its
  ticket. Leave the part out when there is none.

## Screenshots (UI changes only)

For the reviewer: the change at a glance. Present when the diff changes what a user sees
(a template, a style, a UI text). A table with one row per screen or state:

```md
| Screen or state | Before | After |
| --------------- | ------ | ----- |
| <e.g. menu open, desktop> | <image or –> | <image> |
```

A row needs its After image; the Before image is optional (`–` without one). The images
come from screenshots the user took while working (step 5); until then the cells hold
`<image>`. When there is no After image, the section is left out.

## How to set up and validate

For the reviewer who wants to try the change: a recipe, not a report of the author's own
runs. Numbered steps, from the setup (instance, flag, URL) to what the reviewer should
see, at most six. When a behaviour or a suite the change reaches was checked neither by
hand nor by a run in this work, a last line names it:

```md
1. <setup step>
2. <action> → <what you should see>

Not tested: <behaviour or suite that nobody checked>.
```

While it is not known what was checked, the line reads `Not tested: <ask>`, and step 5
asks the user.

Leave the section out when the change has no behaviour to try (documentation, build
configuration, a refactor that changes no behaviour).

## Notes for the reviewer

For the reviewer: where to spend attention. One to three bullets, each naming a place
(a Design part number, or a file when there is no Design) and what feedback is wanted
there: a risk to check, a decision to challenge, an assumption to confirm.

## Effects on others

For testers, operations and other teams. Bullets on behaviour that changes outside the
feature's own users: other callers of a changed shared function, other environments,
other teams' workflows. Leave the section out when there is none.

## Checklist (run it on the draft)

- Context with Problem, and Design, are each within budget: write the draft to a file and
  count each part (`wc -w`, after removing headings, the ticket line, links, diagrams,
  tables and code blocks); never estimate.
- Context starts with the ticket line, with the ticket's title copied from the ticket.
- Context says how it works today, Problem only what is wrong with that, Change only the
  behaviour after; no sentence of one restates another.
- Design is present exactly for a large MR; its Parts follow the flow and each has a
  role, not only a file.
- Screenshots is in the draft exactly when the diff changes what a user sees, and in the
  MR only with an After image in every row.
- How to set up and validate has steps a reviewer can follow, each action with what they
  should see; no line reports a suite that ran green.
- Every Notes for the reviewer bullet names a place and the feedback wanted.
- No section or sentence tells how the change was reviewed or worked on; only the state.
- Problem and Change are in the MR's own words, about what this diff does: no sentence is
  copied or translated from the ticket, and no acceptance-criteria table is reproduced.
