---
name: qubit-ticket
description: "Cuts a request into vertical, ready tickets or issues (initiative, epic, story, bug, chore) that state the problem and the required outcome without prescribing the implementation, and creates them after approval: in Jira directly, in another tracker (GitLab, GitHub, Linear) through the session's tools, or as Markdown to paste. Use when the user wants a ticket created or drafted, when an investigation, a found bug or a feature should become one or more tickets, when an epic or initiative should be broken down, when a ticket is too big, a bucket of unrelated fixes, horizontal (one layer only) or not ready to estimate, or when an existing ticket is wrong, too long, out of date with the code, or prescribes the implementation. Not for checking whether a report or a claim holds before a ticket is wanted (`qubit-claim-check`), or starting work on a ticket (`qubit-ticket-start`)."
---

# Ticket

## Overview

A ticket is written before the work. It is the starting point for whoever implements it,
often an AI agent that reads it in full, and the record of what was wanted. People read
the title and the first sentences. So the ticket says what is wrong and what must be true
afterwards, what is already decided, and what is open. It never plans the
implementation: the implementer explores the code when the work starts, and a guessed
code detail goes stale and anchors whoever reads it.

The planner (the user, or the session that calls this skill) owns the problem and every
business decision. This skill owns the cut: it checks that each ticket is ready to be
built without a refinement about its shape, proposes a vertical cut when it is not, and
writes the tickets ([SLICING.md](SLICING.md)). The planner approves the cut, the answers
and the drafts; the skill changes nothing in the tracker without that approval.

## Workflow

1. **Gather** from the session: the problem, what was investigated and found, what the
   user decided, the intended type and place. Read the profile's `ticket.md`
   (`python3 ~/.claude/skills/_profiles/profile.py doc ticket`,
   [_profiles/README.md](../_profiles/README.md); read every path it prints, in order; a
   later section replaces an earlier one of the same name): the tracker and where its
   facts live (site, types, fields, link types), the team's rules, and the product names.
   It takes precedence over this skill where they differ. The project is one of
   `profile.py get ticketProjects`: the one whose name and description in the tracker
   fit what the ticket is about, read from the tracker; ask when two fit. The repository
   the session is in is no hint: tickets and repositories are many-to-many. Then read the tracker's
   document, [trackers/](trackers/)`<tracker>.md`: how to search, read, create, link and
   edit tickets there, and its content rules. Without a profile, ask the user for the
   tracker and the project before drafting. Without a document for the tracker, use the
   tools the session has for it (an MCP server, `glab`, `gh`), ask the user when that is
   unclear, and write mentions and links in the tracker's own syntax.
2. **Verify**, quickly, even when the session already did:
   - Bug: reproduce it, or re-check its evidence (the code path, the log, the console).
     If it does not reproduce, stop and report that; no ticket.
   - Story: confirm that the stated current state is true.
   - A cause found in the session: re-check it and note how it was checked.
   - Size signals for step 4: how many variants (platforms, markets, user roles),
     servers or packages the outcome touches, and the short code look of
     [SLICING.md](SLICING.md), Code. They stay in the report.
   Stop as soon as each claim is confirmed or refuted; this is no investigation.
3. **Check the structure** in the tracker (a search on the problem's key terms and on
   the module's open epics):
   - duplicates: a ticket that already covers the problem;
   - a home: an open epic or initiative the ticket belongs under;
   - neighbours: tickets to link with the relates link type or a blocks link;
   - collisions: the planner's intended type or parent against what exists.
4. **Cut** the request by [SLICING.md](SLICING.md), one level down: the kind of each
   ticket, the readiness rows, a proposed cut when a row is not met or a ticket is a
   bucket, and every open question sorted into Produkt and Umsetzung. Then **check** it:
   a checker subagent in a fresh context gets the request, the facts of steps 1 to 3,
   the proposed cut (each ticket with kind, title, Ziel in one sentence, and the ticket
   it waits for) and the path of SLICING.md. It looks only for the errors in SLICING.md,
   Wrong cuts, and returns each one with the ticket and one sentence of evidence, or
   „keine Schnittfehler“; it does not cut anew. Fix each clear error in the cut; every
   finding, fixed or not, goes into the report.
5. **Ask about the cut first**, when the cut has more than one ticket or a Produkt
   question is open: one AskUserQuestion with at most four questions, no drafts yet.
   Before it, a short report in this order: the readiness table (SLICING.md), the
   proposed cut as a table (slice, kind, title, pattern, who gains what, the slice it
   waits for), the checker's findings and what was fixed, the vertical alternative to a
   one-layer request in one sentence. Verification
   and structure findings wait for step 7. The questions: approve the cut (the proposed cut, the request
   as it was, or another cut); then each Produkt question with the recommended answer
   first. A Produkt question that finds no place among the four or stays unanswered goes into the ticket
   as an Offen bullet labelled **Produkt:**, and the report names it as what the
   refinement must decide.
6. **Draft** each approved ticket by [FORMAT.md](FORMAT.md), then run its checklist on
   each draft. With five or more tickets, one subagent per ticket drafts in parallel; each
   gets FORMAT.md, the profile's `ticket.md`, the tracker's document, the facts, its slice, the planner's
   answers and the titles of the other slices. Then one pass over all drafts: no
   behaviour in two tickets, each Out of Scope names the neighbour that covers it, and the
   links match the cut.
7. **Show one report and the drafts, then ask once.** The report is a short list: the
   verification result, the proposed type with one reason, every structure finding with
   its suggestion, the readiness table and the checker's findings when step 5 did not
   show them, and the source of
   each Akzeptanzkriterium (the Ziel, which Entscheidung, which unchanged behaviour, or
   "vom Planer festgelegt"). Report items never enter a ticket. Then one AskUserQuestion
   with at most four questions: approve the drafts or give changes; the parent (the
   found epic, another, none); story points for a single story, bug or chore (offer 1, 2, 3, 5;
   never propose a number; with several tickets they stay empty and the report says the
   team sets them); the assignee (default: the user, as the tracker document finds them).
8. **Create** after the approval, as the tracker's document says: the content format,
   the fields (component, story points), the parent when approved, the assignee; the
   issue type is the profile's type for the kind. A parent is created before its
   children, so they can name it. Then the approved links, including the blocks links
   between the slices of a cut. Give the user the keys and the links.
   When the user asked for Markdown only, give the text instead, by the paste rules of
   the tracker's document.

## Revising an existing ticket

Existing tickets are changed only when the user asks for that change. Then the workflow
runs on that ticket:

1. **Read** the ticket with its comments and links, and the profile and the tracker's
   document as in step 1.
2. **Verify** its claims as in step 2: the stated current state, a cause, a code detail
   it names.
3. **Check** the text against [FORMAT.md](FORMAT.md)'s checklist and the readiness rows
   of [SLICING.md](SLICING.md). Each finding names the passage and why: wrong (refuted
   in step 2), too long, out of date with the code, prescribing the implementation, or a
   readiness row not met.
4. **Draft** the rewrite by [FORMAT.md](FORMAT.md). It keeps what still holds, the
   recorded decisions and the links; a dropped code detail gets no replacement.
5. **Show the findings and the draft, then ask once:** approve or give changes. A
   different type, parent, story points or assignee, or a cut into several tickets, is a
   finding with a suggestion, never part of the rewrite.
6. **Update** after the approval, as the tracker's document says, in the content format
   of step 8.
   Comments, status and every field the user did not approve stay as they are.
