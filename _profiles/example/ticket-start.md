# Profile <name>: ticket start

Applies on top of `qubit-ticket-start` in <repository>. Point to the repository's own
documents where they hold a rule, instead of copying it here. Leave out a section the
repository does not need; the skill then uses its default and says so.

## Ticket tracker

<The tracker and how to read a ticket (e.g. an MCP server, a CLI), where its connection
facts live (site, cloud ID, project key), and that the skill only reads.>

## Worktree

<The route to create a worktree that outlives the session: the command, the parent
folder, the env provisioning step, how to enter it. The main branch and the release
branch. How to resolve the remote name. The dependency install command.>

## Branch name

<The branch convention, e.g. `<initials>/<KEY>-<Title>`, and where the repository
defines it.>

## Hotfix

<What in a ticket points at the release branch (fix version, label, words such as
"production"), so the skill asks before it creates a hotfix worktree.>

## Build and tests

<How to build only what the touched packages' tests need, how to run one unit spec, where
the e2e specs live and their commands and prerequisites, and the CLI to search merge
requests by ticket key.>

## Ignored folders

<A git-ignored folder in the repository for the diagnosis and the plan, e.g.
`docs/superpowers/`.>
