---
name: qubit-jira-ticket
description: "Drafts Jira tickets (story, bug, epic, initiative) that state the problem and the required outcome without prescribing the implementation, and creates them in Jira after approval. Use when the user wants a ticket created or drafted, when an investigation or a found bug should become a ticket, or when an existing ticket is wrong, too long, out of date with the code, or prescribes the implementation."
---

# Ticket

## Overview

A ticket is written before the work. It is the starting point for whoever implements it,
often an AI agent that reads it in full, and the record of what was wanted. People read
the title and the first sentences. So the ticket says what is wrong and what must be true
afterwards, what is already decided, and what is open. It never plans the
implementation: the implementer explores the code when the work starts, and a guessed
code detail goes stale and anchors whoever reads it.

The planner (the user, or the session that calls this skill) decides what becomes a
ticket, its type and its place in Jira. This skill writes the ticket, checks it, and
reports what it finds; it decides nothing on its own.

## Workflow

1. **Gather** from the session: the problem, what was investigated and found, what the
   user decided, the intended type and place. Read the profile's `jira-ticket.md`
   (`python3 ~/.claude/skills/_profiles/profile.py doc jira-ticket`,
   [_profiles/README.md](../_profiles/README.md)): where the Jira facts live (cloud ID,
   project, types, fields, link types), the team's rules, and the product names. It
   takes precedence over this skill where they differ. Without a profile, ask the user
   for the project and the cloud ID before drafting.
2. **Verify**, quickly, even when the session already did:
   - Bug: reproduce it, or re-check its evidence (the code path, the log, the console).
     If it does not reproduce, stop and report that; no ticket.
   - Story: confirm that the stated current state is true.
   - A cause found in the session: re-check it and note how it was checked.
   Stop as soon as each claim is confirmed or refuted; this is no investigation.
3. **Check the structure** in Jira (JQL on the problem's key terms and on the module's
   open epics):
   - duplicates: a ticket that already covers the problem;
   - a home: an open epic or initiative the ticket belongs under;
   - neighbours: tickets to link with the relates link type or `Blocks`;
   - collisions: the planner's intended type or parent against what exists;
   - size and readiness against the intended type (the conditions in
     [FORMAT.md](FORMAT.md), Size).
4. **Draft** the ticket by [FORMAT.md](FORMAT.md), then run its checklist on the draft.
5. **Show one report and the draft, then ask once.** The report is a short list: the
   verification result, the proposed type with one reason, every structure finding
   with its suggestion, and the source of each Akzeptanzkriterium (the Ziel, which
   Entscheidung, which unchanged behaviour, or "vom Planer festgelegt"). Then one AskUserQuestion with at most four questions: approve
   the draft or give changes; the parent (the found epic, another, none); story points
   for a story or bug (offer 1, 2, 3, 5; never propose a number); the assignee (default:
   the user, from `atlassianUserInfo`).
6. **Create** after the approval: `createJiraIssue` with `contentFormat: "markdown"`, or
   `"adf"` from `md2adf.py` when the text holds a mention (FORMAT.md, Jira facts); an
   edit of an existing ticket follows the same rule,
   one `additional_fields` object (component by its live name, story points), `parent`
   when approved, the assignee. Then the approved links with `createIssueLink`. Give the
   user the key and the link. When the user asked for Markdown only, give the text
   instead, by FORMAT.md's paste rules.

## Revising an existing ticket

Existing tickets are changed only when the user asks for that change. Then the workflow
runs on that ticket:

1. **Read** the ticket with its comments and links, and the profile as in step 1.
2. **Verify** its claims as in step 2: the stated current state, a cause, a code detail
   it names.
3. **Check** the text against [FORMAT.md](FORMAT.md)'s checklist and its Size
   conditions. Each finding names the passage and why: wrong (refuted in step 2), too
   long, out of date with the code, or prescribing the implementation.
4. **Draft** the rewrite by [FORMAT.md](FORMAT.md). It keeps what still holds, the
   recorded decisions and the links; a dropped code detail gets no replacement.
5. **Show the findings and the draft, then ask once:** approve or give changes. A
   different type, parent, story points or assignee is a finding with a suggestion, never
   part of the rewrite.
6. **Update** after the approval with `editJiraIssue`, in the content format of step 6.
   Comments, status and every field the user did not approve stay as they are.
