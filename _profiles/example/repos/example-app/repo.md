# Repository example-app

What working in this repository needs, by topic. Skills read the sections they name.
Point to the repository's own documents where they hold a rule, instead of copying it
here. No section names a branch or a ticket key: those are values in `config.json` and
the company's `ticketProjects`. Leave out a section the repository does not need; the
skill then uses its default and says so.

## Worktree

<How a worktree of this repository is made, for any purpose: the procedure (a documented
route, or plain `git worktree add`), the parent folder, the env provisioning step, how to
enter it, how to resolve the remote name, the dependency install command. Name any hook
that must not be used, e.g. because it branches off the main branch.>

## Review worktree

<Only what a review worktree does differently from `Worktree`, e.g. a provisioned file
that is a secret file and must be deleted right after creation.>

## Branch name

<The branch convention, e.g. `<initials>/<KEY>-<Title>`, and where the repository
defines it.>

## Hotfix

<What in a ticket points at a production branch (fix version, label, words such as
"production", a country), so the skill asks before it creates a hotfix worktree.>

## Build and tests

<How to build only what the touched packages' tests need, how to run one unit spec, and
the CLI to search merge requests by ticket key.>

## e2e

| Package | Command | Needs the full stack | Run by CI |
| --- | --- | --- | --- |
| `<path>` | `<command>` | <no / yes> | <yes / no> |

<Builds that must run first, so a stale build output does not fail unrelated specs.> A
suite that needs the full stack runs only by the steps of `Full stack`, never on its own.
The suites CI does not run are named in a merge request's "Not tested" line when they did
not run in this work.

## Full stack

1. <How to check that no other local stack runs, without printing any process's
   environment.>
2. <How to dump the local databases the stack writes, into `$SP/checks/db-before/`.>
3. <Builds, the start command (in the background) and the wait command.>
4. <The command that runs named e2e spec files.>
5. <How to stop the stack's processes by name and restore the databases from step 2.>

## Commits

- Conventions: <the file that sets type, scope, header length and language>.
- Merge: <how merge requests are merged (squash or not) and what the merge commit
  carries, so title and description are written for it>.
- Lint gate: <the command to run on the staged files before each commit>.
- Push: <the push command, with any setting the pre-push hook needs>.

## Merge requests

- Screenshot upload: <the API call; which field of its response goes into the table>.
- Create: <the CLI call with the project's flags, e.g. squash, remove source branch>.
- Update: <the CLI call>.
- Last steps: <what to ask the user after the MR exists, e.g. moving the ticket to review>.

## Review threads

<Rules for review threads that only this repository has, e.g. a bot whose threads are
not answered. The platform calls are the company's.>

## Ignored folders

<A git-ignored folder in the repository for the diagnosis and the plan, e.g.
`docs/superpowers/`.>
