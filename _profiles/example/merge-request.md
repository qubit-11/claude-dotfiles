# Profile <name>: merge request

Applies on top of the format of `qubit-merge-request` (its FORMAT.md) in <repository>.
Leave out a section the repository does not need.

## Title and description after the merge

<How MRs are merged (squash or not), what the merge commit carries, which file sets the
commit conventions (type, scope, header length, language), and in which language the
title and the description are written.>

## Ticket line

<How the description names the ticket, e.g. `**Ticket:** PROJ-NNNN "<ticket title>"`,
and whether the tracker integration turns a bare key into a link.>

## Suites CI does not run

<Which packages or e2e suites CI skips, so the "Not tested" line names them when they did
not run in this work.>

## Create and update

- Push: <the push command, with any setting the pre-push hook needs>.
- Screenshot upload: <the API call; which field of its response goes into the table>.
- Create: <the CLI call with the project's flags, e.g. squash, remove source branch>.
- Update: <the CLI call>.

## Last steps

<What to ask the user after the MR exists, e.g. moving the ticket to review.>
